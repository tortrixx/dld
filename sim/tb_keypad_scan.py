# -*- coding: utf-8 -*-
"""tb_keypad_scan.py —— keypad_scan 功能仿真（扫描 + 消抖 + 单次按下脉冲）

【这一轮要回答什么】
    `keypad_scan` 是整个项目里**唯一**的输入通道，也是历史上出缺陷最多的地方：
    ERR-003（轮次结果被提前清零，永远读到"无键"）、ERR-004（键码编码与比较表
    不一致）。这两条都不是"看波形能看出来"的，必须**按行为断言**。

    本轮做四件事：
      ① 无键时 o_key = K_NONE(0)，且不产生任何 o_press 脉冲；
      ② **按住**一个键：o_key 在消抖轮数内变为 4*行+列，o_press **恰好一次**、
         宽度 = 1 个时钟周期（"按住只动作一次"，ERR-003 的防线）；
      ③ **松开**：o_key 归 0，并且 o_release 恰好一次（与 o_press 成对）；
      ④ **短按**（只按 3 轮 < 消抖 4 轮）：**不得**产生 o_press（消抖有效）；
      ⑤ 换一个 (行,列) 的键仍能得到正确的 4*行+列（证明不是"只对某一列有效"）；
      ⑥ 列驱动的两相扫描自洽：出现"四列全拉低"相，且有效相恰好一位为低。

【激励怎么来的：把 4x4 矩阵的**物理**行为算出来，而不是"猜波形"】
    扫描器在一轮里的采样时刻是**确定的**（`state`/`settle` 计数器决定）：
        SETTLE 相：col_all='1'，四列全低  → 在 SETTLE 末尾锁存 row_all
        RELEASE 相：第 p 相只有第 p 列为低 → 在该相末尾采样，判定"按键在第 p 列"
    所以按下的键 (r,c) 对行线 r 的影响是**可精确算出来**的：
        · SETTLE 期间行 r 为低（所有列都低）；
        · 只有第 c 相期间行 r 为低（该相第 c 列被拉低），其余相为高。
    本文件按这个物理模型生成 i_row 波形 —— 因此如果模块的相序/时序错了，
    断言必然失败；而不是"我给了它想要的波形它当然过"。

【时间刻度】
    TICK = 8000 ns（= 400 个 20 ns 时钟）。一轮扫描 = 2 个 tick = 16 us。
    第 k 轮：SETTLE 的触发 tick 在 (2k+2)T；SETTLE 锁存 row_all 在 +1280 ns；
    第 c 相采样在 +1300+1280*(c+1) ns。消抖**每轮采一个样**（不是每个 tick），
    DEBOUNCE_MAX+1 个相同样才接受 —— 现在 DEBOUNCE_MAX=3 → **4 轮**。
    ⚠️ ERR-031：一轮 = **2 个 tick**（SC_ALL_HIGH 与 SC_ALL_LOW 各等一个 tick），
       所以板上 4 轮 = **40 ms**；旧文档写"16 轮 = 80 ms"把 2 倍算漏了（真实 160 ms）。
"""

T = 8000.0                 # tick 周期 (ns)
CLK = 20.0                 # 50 MHz
GRID_PERIOD = 10.0
DURATION = 112 * 2 * T     # 112 轮 = 1.792 ms

# (起始轮, 结束轮, 行, 列) —— 每一段都按住若干轮，中间留出松开的轮次
KEY_PLAN = [
    (0,  25, 1, 2),        # KEY1 -> 4*1+2 = 6
    (46, 65, 3, 0),        # KEY2 -> 4*3+0 = 12
    (90, 92, 2, 3),        # KEY3 -> 短按 3 轮（应被消抖丢弃，不产生 o_press）
]
KEY1, KEY2, KEY3 = 6, 12, 11

HIGH = 0xF                 # i_row 空闲时四行全高（低有效）

OBSERVE = ["i_clk", "i_row", "o_col", "o_raw", "o_key", "o_press", "o_release",
           "phase", "settle", "cnt", "col_low", "row_all", "stable", "key_r"]


# ---------------------------------------------------------------- 激励
def _round_windows(k, r, c):
    """第 k 轮里"行 r 应被按下的键拉低"的绝对时间窗口 [(起, 止), ...]。"""
    t0 = (2 * k + 2) * T                    # SETTLE 触发 tick
    return [
        (t0 + 20.0, t0 + 1300.0),                                       # SETTLE
        (t0 + 1300.0 + 1280.0 * c, t0 + 1300.0 + 1280.0 * (c + 1)),     # 第 c 相
    ]


def _timeline(spans, duration):
    """把 [(起, 止, 值)] 事件表变成 [(时长, 值)]，覆盖整个仿真时长。"""
    ev = []
    for (a, b, v) in spans:
        ev.append((a, v))
        ev.append((b, HIGH))
    ev.sort(key=lambda x: x[0])
    segs, t, cur = [], 0.0, HIGH
    for (tt, v) in ev:
        if tt > t:
            segs.append((tt - t, cur))
            t = tt
        cur = v
    if t < duration:
        segs.append((duration - t, cur))
    return segs


def _buried(b, name, width):
    """把内部信号（含其比特子节点）标成 BURIED —— 综合后网表里内部信号就是 Buried，
    不需要（也不能）给它们预置激励，仿真器会把结果写回来。"""
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_tick")
    b.input_bus("i_row", 4)
    b.output_bus("o_col", 4)
    b.output_bus("o_raw", 4)
    b.output_bus("o_key", 4)
    b.output_bit("o_press")
    b.output_bit("o_release")
    # 中间信号（课程硬要求：波形文件必须含中间信号）
    for n, w in (("phase", 2), ("col_low", 4), ("row_all", 4),
                 ("stable", 4), ("key_r", 4)):
        b.output_bus(n, w)
        _buried(b, n, w)
    # settle/cnt 是宽计数器（消抖采样位置的真值来源）：分开声明
    for n, w in (("settle", 8), ("cnt", 8)):
        b.output_bus(n, w)
        _buried(b, n, w)

    b.clock("i_clk", CLK)
    # ⚠️ 综合后网表寄存器初值是 X —— 必须显式复位
    b.segments("i_rst", [(100.0, 1), (DURATION - 100.0, 0)])
    # tick 从 T 开始，每 T 一拍（一个时钟宽）
    n_tick = int(DURATION // T)
    b.segments("i_tick", [(CLK, 0)] + [(T - CLK, 0), (CLK, 1)] * n_tick)

    spans = []
    for (k0, k1, r, c) in KEY_PLAN:
        for k in range(k0, k1 + 1):
            for (a, bb) in _round_windows(k, r, c):
                spans.append((a, bb, HIGH & ~(1 << r)))
    b.bus_segments("i_row", _timeline(spans, DURATION))


# ---------------------------------------------------------------- 断言
def _pulses(vf, name):
    """列出 name 上所有高电平脉冲的 (开始, 结束)。X 视为非 1。"""
    out, start, prev = [], None, None
    for (t, v) in vf.trace(name):
        hi = (v == "1")
        if hi and prev is not True:
            start = t
        elif (not hi) and prev is True and start is not None:
            out.append((start, t))
        prev = hi
    if prev is True and start is not None:
        out.append((start, DURATION))
    return out


def _key_at(vf, t):
    return vf.bus_value_at("o_key", t)


def check(vf):
    res = []
    press = _pulses(vf, "o_press")
    release = _pulses(vf, "o_release")

    # 关键采样时刻（按上面推导的轮次表；留 100 ns 余量避开时钟边沿）
    t_after_k1 = (2 * 17 + 1) * T + 100.0      # 第 1 个键已接受
    # ⚠️ ERR-031：消抖从 16 轮缩到 4 轮后，KEY1 的**松开**也在第 29 轮就被接受
    #    （旧值 41 轮），所以"仍按住"的检查点必须提前到第 20 轮（按住段是 0~25 轮）。
    t_hold_k1 = (2 * 20 + 1) * T + 100.0       # 仍按住 KEY1 期间
    t_rel_k1 = (2 * 50 + 1) * T + 100.0        # KEY1 已松开
    t_after_k2 = (2 * 63 + 1) * T + 100.0      # 第 2 个键已接受
    t_rel_k2 = (2 * 88 + 1) * T + 100.0        # KEY2 已松开
    t_short = (2 * 108 + 1) * T + 100.0        # 短按之后

    # ① 无键期间
    res.append((
        "① 复位后无键：o_key = 0（K_NONE）且 o_press 无脉冲",
        _key_at(vf, 3 * T + 100.0) == 0 and len(press) == 2,
        "t=%s 时 o_key=%s；全程 o_press 脉冲数=%d（期望 2：KEY1 与 KEY2 各一次）"
        % (3 * T + 100.0, _key_at(vf, 3 * T + 100.0), len(press)),
    ))

    # ② 按住 KEY1 -> 正确键码 + 恰好一次 1 时钟宽的 press
    w_ok = len(press) == 2 and all(abs((b - a) - CLK) < 1e-6 for (a, b) in press)
    res.append((
        "② 按下 (行1,列2) 后 o_key = 4*1+2 = 6（键码 = 4*行+列，ERR-004 的防线）",
        _key_at(vf, t_after_k1) == KEY1,
        "实测 o_key = %s，期望 %d" % (_key_at(vf, t_after_k1), KEY1),
    ))
    res.append((
        "③ o_press 脉冲**恰好 2 次**且**每次宽度 = 1 个时钟周期**(20 ns)",
        w_ok,
        "脉冲时刻/宽度：%s" % ", ".join("%.0fns..%.0fns(%.0fns)" % (a, b, b - a)
                                        for (a, b) in press),
    ))

    # ④ 按住期间不再产生第二次 press（"按住只动作一次"）
    holds = [(a, b) for (a, b) in press if t_after_k1 < a < (2 * 46 + 1) * T]
    res.append((
        "④ 按键保持不放时不再产生新的 o_press（按住只动作一次）",
        len(holds) == 0 and _key_at(vf, t_hold_k1) == KEY1,
        "按住期间(%.0f ns 起)新增脉冲数=%d，o_key=%s"
        % (t_after_k1, len(holds), _key_at(vf, t_hold_k1)),
    ))

    # ⑤ 松开 -> o_key 归零 + o_release 恰好一次
    rel_ok = (len(release) == 2
              and all(abs((b - a) - CLK) < 1e-6 for (a, b) in release))
    res.append((
        "⑤ 松开后 o_key 归 0，并且 o_release 恰好 2 次、每次 1 个时钟宽",
        rel_ok and _key_at(vf, t_rel_k1) == 0,
        "release 脉冲：%s；松开后 o_key=%s" % (
            ", ".join("%.0fns" % a for (a, _b) in release), _key_at(vf, t_rel_k1)),
    ))

    # ⑥ 第二个键（不同行且**第 0 列**）仍编码正确
    res.append((
        "⑥ 换 (行3,列0) 的键仍得到 o_key = 12（第 0 列也能定列，不是只对某列有效）",
        _key_at(vf, t_after_k2) == KEY2 and _key_at(vf, t_rel_k2) == 0,
        "实测 o_key = %s（期望 %d）" % (_key_at(vf, t_after_k2), KEY2),
    ))

    # ⑦ 短按 3 轮（< 消抖 4 轮）必须被丢弃
    res.append((
        "⑦ 短按 3 轮（< 消抖 4 轮）不产生 o_press，o_key 保持 0（消抖有效）",
        _key_at(vf, t_short) == 0 and len(press) == 2,
        "短按后 o_key=%s；全程 press 脉冲总数仍为 %d"
        % (_key_at(vf, t_short), len(press)),
    ))

    # ⑨ ★ 消抖时长本身（ERR-031：一轮 = 2 个 tick = 10 ms 板上，所以 4 轮 = 40 ms）
    #    实测（读 .vwf 的 cnt 跳变，消抖采样拍 = 奇数个 T）：KEY1 的 cnt 序列
    #        1T→1, 3T→2, 5T→3, **7T→0（= 第 4 个相同样，改 stable）**；释放侧
    #        55T→1, 57T→2, 59T→3, **61T→0**。
    #    o_press/o_release 比"改 stable"再晚**一个采样拍**（RTL 里脉冲判定读的是
    #    同拍旧值 stable），所以实测脉冲落在 9T / 63T；KEY2 同构：103T / 143T。
    #    换算板上（× 625）：按下 → o_press ≈ 45 ms（原来是 33T = 165 ms）。
    #    这条断言把"消抖到底几毫秒"钉死：改 DEBOUNCE_MAX 而忘了改这里，立即挂。
    exp_p = [9 * T, 103 * T]          # KEY1 / KEY2 的 o_press 上升沿
    exp_r = [63 * T, 143 * T]         # KEY1 / KEY2 的 o_release 上升沿
    lat_ok = (len(press) == 2 and len(release) == 2
              and all(abs(press[i][0] - exp_p[i]) <= 30.0 for i in range(2))
              and all(abs(release[i][0] - exp_r[i]) <= 30.0 for i in range(2)))
    res.append((
        "⑨ ★ 消抖时长 = **4 个连续相同样 = 40 ms 板上**（DEBOUNCE_MAX=3；ERR-031："
        "一轮扫描 = 2 个 tick_200 = 10 ms，旧文档的「16 轮 = 80 ms」把 2 倍算漏了，"
        "真实曾是 **160 ms**）。实测 o_press 在 9T、o_release 在 63T（改 stable 后"
        "再晚一个采样拍出脉冲；换算板上按下→o_press ≈ **45 ms**，原来 33T = 165 ms）",
        lat_ok,
        "实测 press=%s（期望 %s）、release=%s（期望 %s）；T = 8 us 仿真 = 5 ms 板上"
        % (["%.0f" % a for (a, _b) in press], ["%.0f" % x for x in exp_p],
           ["%.0f" % a for (a, _b) in release], ["%.0f" % x for x in exp_r]),
    ))

    # ⑧ 列驱动两相扫描自洽
    saw_all_low = False
    bad_phase = []
    t = 3 * T
    while t < DURATION:
        v = vf.bus_value_at("o_col", t)
        if v == 0x0:
            saw_all_low = True
        elif v is not None and format(v, "04b").count("0") != 1:
            bad_phase.append((t, v))
        t += 100.0
    res.append((
        "⑧ 列驱动自洽：出现'四列全拉低'相，且其余所有相恰好一位为低",
        saw_all_low and not bad_phase,
        "见到全低相=%s；非法相 %d 个%s" % (
            saw_all_low, len(bad_phase),
            ("，例如 t=%.0f v=%s" % bad_phase[0]) if bad_phase else ""),
    ))

    return res
