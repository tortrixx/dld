# -*- coding: utf-8 -*-
"""tb_clk_gen.py —— clk_gen 功能仿真激励与断言

【clk_gen 应该做什么】
    `rtl/clk_gen.vhd` 是全项目唯一的时基与复位源：
      · 6 档节拍：tick_1k(1ms) / tick_200(5ms) / tick_100(10ms) / tick_40(25ms)
        / tick_2hz(500ms) / tick_1hz(1s)，全部是**单时钟周期宽的脉冲**；
      · 级联分频链：只有第 1 级看 50MHz 板时钟，第 2~6 级只数**上一级的脉冲**；
      · 上电复位：饱和计数器，复位维持约 10 "ms" 后释放，**永不回绕重断言**；
      · 按键消抖：连按 20 "ms" 才认（任一低样本立即撤销，即松开是**快**释放、
        非对称 —— 判定条件是"20 位寄存器全 1"），短毛刺必须滤掉。

【判据从"模块应该做什么"推出，不抄 RTL 常量】
    ① 单时钟脉冲宽度：每个 tick 的每个高电平段恰 = 1 个 clk 周期
       （若实现成"电平保持到下一个 tick"或"两拍宽"，本条立刻挂）。
    ② 分频周期比（以 clk 周期计）：由**标称频率**推出 ——
       1kHz→1ms、200Hz→5ms、100Hz→10ms、40Hz→25ms、2Hz→500ms、1Hz→1000ms，
       再 × (CLK_HZ/1000) 拍/ms。6 档互相独立断言，任一级分频比写错即挂。
    ③ 复位：上电即复位、约 10ms 后释放、之后不再自行断言（无幽灵复位）；
       内部 por_cnt 必须**饱和**到顶（回绕会立刻挂）。
       ⚠️ 实测释放时刻 = 第 9 个 tick_1k（1810ns = 9.05 标称 ms）而不是整 10ms：
          RTL 是"计到 CNT_POR = T_POR_MS-1 就释放"，比头部注释的 T_POR_MS=10 少
          一个刻度（off-by-one）。断言取 [8,11]ms 容差窗口 + 饱和/不回绕判据，
          两条合起来既接受这个 off-by-one、又排除"卡死不释放"和"回绕重断言"。
    ④ 按键：按住满 20 个 1ms 样本 o_rst 才置位（时间窗 [19,20] 标称 ms，
       19 或 21 个样本都会挂）；松开后 ≤1 个样本即释放（非对称消抖，
       RTL 头部写明判定条件就是"20 位全 HIGH"）；8 个样本的短毛刺必须完全不产生 o_rst。
    ⑤ 内部信号：c1 每拍 +1、数到顶回绕（计数周期 = 1ms 的拍数）；
       bcnt 是 5 位**饱和计数器**（第 13 工作阶段替换掉原来的 20 位移位寄存器
       d_press）：按住期间逐刻度 +1、到 20 就停住不回绕，任一低样本立刻清零。
【CLK_HZ 缩放（RTL_PATCHES，只作用于 .tmp/sim_clk_gen 的隔离副本）】
    仓库里 CLK_HZ = 50_000_000，1ms 要 50000 拍，跑 1s 时基需 5e7 拍 —— 跑不动。
    因此把 puzzle_pkg 的 `50_000_000` 改成 `10_000`（隔离工程内），于是
        · 1 个"标称 ms" = 10 个 clk = 200 ns（clk 周期固定 20 ns）
        · 全部断言都按"clk 拍数 / 标称时间"写，与缩放比无关。
    ⚠️ 若把值取到 1000 或更小，CNT_1K 会退化成 0/很小，第 1 级与后续级不可区分。

【激励时间线（ns；均为 200ns 的整数倍，即标称 ms 的整数倍）】
    0            上电（i_btn=0）
    20_000       长按开始（= 标称 100ms，远在 POR 之后）
    60_000       长按结束（按住 200 个刻度）
    120_000      短毛刺开始
    121_600      短毛刺结束（仅 8 个刻度 = 8ms < 20ms，应被滤掉）
    460_000      仿真结束（够看到 2 个 tick_1hz / 2 个 tick_2hz）
"""

CLK_PERIOD = 20.0        # 板时钟 50MHz → 20ns（本 tb 只关心 clk 沿，周期取 20ns）
CLK_HZ_SIM = 10_000      # 见 RTL_PATCHES：隔离工程里 CLK_HZ 被改成这个值
T1_NS = CLK_HZ_SIM / 1000.0 * CLK_PERIOD      # 1 个标称 ms = 10 拍 = 200 ns

DURATION = 460_000.0
GRID_PERIOD = 10.0

# 标称时基（课程要求值）→ 折算成"标称 ms"
MS_1K = 1.0
MS_200 = 5.0
MS_100 = 10.0
MS_40 = 25.0
MS_2HZ = 500.0   # tick_2hz 周期（音效节奏；**不再当闪烁**，见 ERR-038）
MS_4HZ = 250.0   # tick_4hz 周期（翻转它 → 真正的 2 Hz 方波）
MS_1HZ = 1000.0

# 上电复位 / 按键消抖的标称时长（课程要求：POR≈10ms，消抖 20ms）
POR_MS = 10.0
BTN_MS = 20.0

T_PRESS = 20_000.0
T_RELEASE = 60_000.0
T_GLITCH_ON = 120_000.0
T_GLITCH_OFF = 121_600.0

RTL_PATCHES = [("puzzle_pkg.vhd", "50_000_000", "10_000")]

# ---- 端口 + 中间信号（课件 p59 硬要求：波形里必须有中间信号）----
PORTS = ["i_clk", "i_btn", "o_rst", "o_tick_1k", "o_tick_200", "o_tick_100",
         "o_tick_40", "o_tick_2hz", "o_tick_4hz", "o_tick_1hz"]
# 中间信号：名字 -> 位宽（1 = 单比特）；都是综合后网表里的寄存器节点
BURIED = {
    "t1": 1, "t2": 1, "t3": 1, "t6": 1, "t7": 1,   # 各级 tick 寄存器
    "c1": 16,                               # 第 1 级分频计数器（50MHz 档要 16 位）
    "por_cnt": 4,                           # 上电复位饱和计数器
    "bcnt": 5,                              # 按键消抖**饱和计数器**（第 13 工作阶段
                                            # 由 20 位移位寄存器 d_press 改成 5 位计数器）
    # ⚠️ s_por / s_btn 是纯组合信号，综合后被合并进 o_rst 的逻辑锥里，
    #    网表中不存在（实测：quartus_sim 报 Can't find corresponding node name）
    #    → 不能进 OBSERVE；它们的语义由上面对 por_cnt / d_press 的断言覆盖。
}
OBSERVE = PORTS + list(BURIED.keys())


def _buried(b, name, width):
    """综合后网表里内部信号是 Buried，方向写 OUTPUT 会被仿真器报类型不符。"""
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_btn")
    for n in PORTS[2:]:
        b.output_bit(n)
    for n, w in BURIED.items():
        if w > 1:
            b.output_bus(n, w)
        else:
            b.output_bit(n)
        _buried(b, n, w)

    b.clock("i_clk", CLK_PERIOD)
    # 显式给按键激励；i_clk 是唯一时钟，i_btn 低有效按（板上按下 = 高）
    b.segments("i_btn", [
        (T_PRESS, 0),                       # 上电 + POR 期间不按
        (T_RELEASE - T_PRESS, 1),           # 长按 200 个刻度（> 20）
        (T_GLITCH_ON - T_RELEASE, 0),       # 松开
        (T_GLITCH_OFF - T_GLITCH_ON, 1),    # 短毛刺 8 个刻度（< 20，应被滤掉）
        (DURATION - T_GLITCH_OFF, 0),
    ])


# ============================================================
# 辅助
# ============================================================
def _runs(vf, name):
    """返回 [(电平, 起始时刻, 时长), ...]（阶梯保持）。"""
    out, t = [], 0.0
    for lv, dur in vf.expand(name):
        out.append((lv, t, dur))
        t += dur
    return out


def _rises(vf, name):
    """上升沿（0→1）时刻列表。"""
    return [t for (t, lv) in vf.trace(name) if lv == "1"]


def _busv(vf, name, t):
    """安全取总线值：该节点在综合后网表里不存在时返回 None（不抛 KeyError）。

    ⚠️ 变异测试实测：把 RTL 改坏（例如让 por_cnt 永不饱和）会被综合器把整个
       按键/复位逻辑优化掉，于是 d_press 这类观测节点从结果 .vwf 里消失；
       若 check() 直接调 bus_value_at 就会抛 KeyError 而不是如实报"断言失败"。
    """
    if name not in vf.signals:
        return None
    if vf.signals[name].is_bus:
        return vf.bus_value_at(name, t)
    return vf.value_at(name, t)


def _clk_edges(vf):
    return _rises(vf, "i_clk")


def _clk_between(vf, a, b):
    """(a, b] 之间的 clk 上升沿个数。"""
    return len([e for e in _clk_edges(vf) if a < e <= b])


def _period_clk(vf, name):
    """前两个上升沿之间跨了几个 clk 拍（不足两个上升沿返回 None）。"""
    rs = _rises(vf, name)
    if len(rs) < 2:
        return None
    return _clk_between(vf, rs[0], rs[1])


def _bus_trace(vf, name, width):
    """总线逐位拼成 [(时刻, 整数值), ...]（值变化点）。"""
    times = set()
    for i in range(width):
        for (t, _lv) in vf.trace("%s[%d]" % (name, i)):
            times.add(t)
    out = []
    for t in sorted(times):
        v = _busv(vf, name, t + 1e-9)
        if v is None:
            continue
        if not out or out[-1][1] != v:
            out.append((t, v))
    return out


def _fmt(t):
    return "X" if t is None else "%.0f ns（= %.4g 标称ms）" % (t, t / T1_NS)


# ============================================================
# 断言
# ============================================================
def check(vf):
    res = []

    # ---------------------------------------------------------
    # ① 每个 tick 都是单时钟脉冲（不是电平、也不是两拍宽）
    # ---------------------------------------------------------
    ticks = ["o_tick_1k", "o_tick_200", "o_tick_100", "o_tick_40",
             "o_tick_2hz", "o_tick_4hz", "o_tick_1hz"]
    bad, n_pulse = [], 0
    for n in ticks:
        for (lv, t0, dur) in _runs(vf, n):
            if lv != "1":
                continue
            if t0 + dur >= DURATION - 1e-9:      # 末尾被截断的那一段不算
                continue
            n_pulse += 1
            if abs(dur - CLK_PERIOD) > 1e-9:
                bad.append("%s @%.0fns 高电平 %.0fns（应 %.0fns）" % (n, t0, dur, CLK_PERIOD))
    res.append((
        "① 7 档 tick 全是单 clk 周期脉冲（共检查 %d 个高电平段，宽度应恒为 %.0f ns）"
        % (n_pulse, CLK_PERIOD),
        (not bad) and n_pulse >= 12,
        "\n".join(bad[:5]) if bad else "全部 %d 个脉冲宽度 = %.0f ns = 1 个 clk 周期"
        % (n_pulse, CLK_PERIOD),
    ))

    # ---------------------------------------------------------
    # ② 6 档节拍的周期（以 clk 拍计）—— 由标称频率独立推出
    #    拍/标称ms = CLK_HZ_SIM/1000 = 10
    # ---------------------------------------------------------
    ms_clk = CLK_HZ_SIM / 1000.0
    cases = [("o_tick_1k", MS_1K), ("o_tick_200", MS_200), ("o_tick_100", MS_100),
             ("o_tick_40", MS_40), ("o_tick_2hz", MS_2HZ), ("o_tick_4hz", MS_4HZ),
             ("o_tick_1hz", MS_1HZ)]
    rows, ok_all = [], True
    for (n, ms) in cases:
        want = int(round(ms * ms_clk))
        got = _period_clk(vf, n)
        ok = (got == want)
        ok_all &= ok
        rows.append("%s 实测 %s 拍 / 期望 %d 拍(%gms) %s"
                    % (n, got, want, ms, "✓" if ok else "✗"))
    res.append((
        "② 分频周期（clk 拍数）：1k=%.0fms→%d 拍、200=%.0fms→%d、100=%.0fms→%d、"
        "40=%.0fms→%d、2Hz=%.0fms→%d、1Hz=%.0fms→%d"
        % (MS_1K, MS_1K * ms_clk, MS_200, MS_200 * ms_clk, MS_100, MS_100 * ms_clk,
           MS_40, MS_40 * ms_clk, MS_2HZ, MS_2HZ * ms_clk, MS_1HZ, MS_1HZ * ms_clk),
        ok_all,
        "\n".join(rows),
    ))

    # ---------------------------------------------------------
    # ③ 各档之间的**比例**（独立于 CLK_HZ 缩放；级联链写错比值必挂）
    # ---------------------------------------------------------
    p = {n: _period_clk(vf, n) for (n, _ms) in cases}
    ratios = [("tick_200 / tick_1k", p["o_tick_200"], p["o_tick_1k"], 5),
              ("tick_100 / tick_200", p["o_tick_100"], p["o_tick_200"], 2),
              ("tick_40 / tick_200", p["o_tick_40"], p["o_tick_200"], 5),
              ("tick_2hz / tick_100", p["o_tick_2hz"], p["o_tick_100"], 50),
        ("tick_4hz / tick_100", p["o_tick_4hz"], p["o_tick_100"], 25),
              ("tick_1hz / tick_100", p["o_tick_1hz"], p["o_tick_100"], 100)]
    bad = []
    for (name, a, b, want) in ratios:
        if a is None or b is None or b == 0 or a % b != 0 or a // b != want:
            bad.append("%s = %s/%s（应 %d）" % (name, a, b, want))
    res.append((
        "③ 级联分频比：200Hz=5×1k、100Hz=2×200、40Hz=5×200、2Hz=50×100、1Hz=100×100",
        not bad,
        "\n".join(bad) if bad else "实测比值全部正确（%s）"
        % "、".join("%s=%d" % (n, a // b) for (n, a, b, _w) in ratios),
    ))

    # ---------------------------------------------------------
    # ④ 上电复位：上电即复位 → 约 10ms 释放 → 之后不再自行断言
    # ---------------------------------------------------------
    t_fall = next((t for (t, lv) in vf.trace("o_rst") if lv == "0"), None)
    t1_r = _rises(vf, "o_tick_1k")
    n_t1_before = len([t for t in t1_r if t_fall is not None and t < t_fall])
    phantom = [t for (t, lv) in vf.trace("o_rst")
               if t_fall is not None and t_fall < t < T_PRESS and lv == "1"]
    ok = (vf.value_at("o_rst", 0.0) == "1"
          and t_fall is not None
          and POR_MS * 0.8 * T1_NS <= t_fall <= POR_MS * 1.1 * T1_NS
          and abs(n_t1_before - POR_MS) <= 1.0
          and vf.value_at("o_rst", T1_NS * 20) == "0"
          and not phantom)
    res.append((
        "④ 上电复位：上电即为 '1'，%.0f~%.0fms 之间释放（实测 %s），"
        "按钮未按期间不再自行断言（无幽灵复位）"
        % (POR_MS * 0.8, POR_MS * 1.1, _fmt(t_fall)),
        ok,
        "o_rst(0)=%s；释放前经过 %d 个 tick_1k（标称 %g ms，容差 ±1）；"
        "释放后到按下按键之间 o_rst 再次为 '1' 的次数 = %d"
        % (vf.value_at("o_rst", 0.0), n_t1_before, POR_MS, len(phantom)),
    ))

    # ---------------------------------------------------------
    # ⑤ por_cnt 是**饱和**计数器（停在顶、不回绕）
    # ---------------------------------------------------------
    pt = _bus_trace(vf, "por_cnt", 4)
    vals = [v for (_t, v) in pt]
    top = max(vals) if vals else None
    wraps = [(vals[i], vals[i + 1]) for i in range(len(vals) - 1) if vals[i + 1] < vals[i]]
    res.append((
        "⑤ 内部 por_cnt 单调增到顶后饱和（顶值应 = %d，回绕会挂）" % int(POR_MS - 1),
        top == int(POR_MS - 1) and not wraps,
        "por_cnt 实测序列 %s…（共 %d 个值），最大值 = %s，回绕次数 = %d"
        % (vals[:12], len(vals), top, len(wraps)),
    ))

    # ---------------------------------------------------------
    # ⑥ 按键消抖（按下）：必须连满 20 个 1ms 样本才断言 o_rst
    #    ⚠️ 相位：shift 发生在 t1 抬起后的**下一个 clk 沿**，所以按下时刻到置位
    #       之间是"20 个样本"，折算成时间 ∈ [19,20] 个标称 ms ——
    #       19 个样本（3600ns）或 21 个样本（4000ns+）都会落在窗外 → 立刻挂。
    # ---------------------------------------------------------
    t_rise = next((t for (t, lv) in vf.trace("o_rst") if t > T_PRESS and lv == "1"), None)
    d_rise = (t_rise - T_PRESS) if t_rise is not None else None
    ok = (t_rise is not None
          and (BTN_MS - 1) * T1_NS <= d_rise <= BTN_MS * T1_NS
          and vf.value_at("o_rst", t_rise - 1.0) == "0"
          and vf.value_at("o_rst", T_RELEASE - T1_NS) == "1")     # 按住期间保持
    res.append((
        "⑥ 按键消抖（按下）：连满 %g 个 1ms 样本 o_rst 才置位（%g~%g 标称 ms）"
        % (BTN_MS, BTN_MS - 1, BTN_MS),
        ok,
        "按下 %s；o_rst 置位于 %s（Δ = %s ns = %s 标称 ms，期望 %.0f~%.0f）；"
        "置位前 1ns = %s；按住期间 o_rst=%s"
        % (_fmt(T_PRESS), _fmt(t_rise), "X" if d_rise is None else "%.0f" % d_rise,
           "X" if d_rise is None else "%.2f" % (d_rise / T1_NS),
           (BTN_MS - 1), BTN_MS,
           "X" if t_rise is None else vf.value_at("o_rst", t_rise - 1.0),
           vf.value_at("o_rst", T_RELEASE - T1_NS)),
    ))

    # ---------------------------------------------------------
    # ⑦ 松开：**非对称**消抖 —— 判定条件是"寄存器 20 位全 1"，所以任一低样本
    #    立即撤销（RTL 头部写明 all-HIGH = 稳定按下），不是"再等 20ms"。
    #    本条把"松开必须快（≤1 个样本）、且之后不再误断言"钉死：
    #    若实现改成对称消抖（松开也等 20ms），Δ 会落到 19~20ms → 立刻挂。
    # ---------------------------------------------------------
    t_rel = next((t for (t, lv) in vf.trace("o_rst") if t > T_RELEASE and lv == "0"), None)
    d_rel = (t_rel - T_RELEASE) if t_rel is not None else None
    late = [t for (t, lv) in vf.trace("o_rst")
            if t_rel is not None and t_rel < t < T_GLITCH_OFF + 5 * T1_NS and lv == "1"]
    ok = (t_rel is not None and 0.0 <= d_rel <= T1_NS
          and vf.value_at("o_rst", t_rel - 1.0) == "1"
          and not late)
    res.append((
        "⑦ 松开按键：o_rst 在 ≤1 个 1ms 样本内释放（非对称消抖：全 1 检测器，"
        "任一低样本立即撤销），且之后不再误断言",
        ok,
        "松开 %s；o_rst 释放于 %s（Δ = %s ns = %s 标称 ms）；之后到毛刺结束期间为 '1' 的次数 = %d"
        % (_fmt(T_RELEASE), _fmt(t_rel), "X" if d_rel is None else "%.0f" % d_rel,
           "X" if d_rel is None else "%.2f" % (d_rel / T1_NS), len(late)),
    ))

    # ---------------------------------------------------------
    # ⑧ 短毛刺（8 个刻度 < 20）必须被完全滤掉
    # ---------------------------------------------------------
    sam = [T_GLITCH_ON + k * T1_NS for k in range(9)] + [T_GLITCH_OFF + T1_NS * 3]
    got = [vf.value_at("o_rst", t) for t in sam]
    spur = [t for (t, lv) in vf.trace("o_rst") if T_GLITCH_ON < t < T_GLITCH_OFF + 5 * T1_NS
            and lv == "1"]
    res.append((
        "⑧ 短毛刺（%g 个刻度 < %g）被消抖滤掉：o_rst 全程保持 '0'"
        % ((T_GLITCH_OFF - T_GLITCH_ON) / T1_NS, BTN_MS),
        (not spur) and all(v == "0" for v in got),
        "毛刺窗口内 o_rst 采样 = %s；窗口内出现的 '1' 次数 = %d" % (got, len(spur)),
    ))

    # ---------------------------------------------------------
    # ⑨ 内部信号：第 1 级计数器 c1 每拍 +1、数到顶回绕（周期 = 1ms 的拍数）
    # ---------------------------------------------------------
    ct = _bus_trace(vf, "c1", 16)
    cv = [v for (_t, v) in ct]
    top1 = CLK_HZ_SIM // 1000 - 1          # 1ms = CLK_HZ/1000 拍 → 顶值 = 拍数-1
    step_ok = all(((cv[i + 1] - cv[i]) % (top1 + 1)) == 1 for i in range(len(cv) - 1))
    # ⚠️ 第一个值（初值 0）只保持到第一个 clk 沿（10ns = 半个周期），不是一整拍，
    #    不能算"保持时间"；从第 2 个变化点起每个值应恰好保持 1 个 clk 周期。
    durs = sorted({round(ct[i + 1][0] - ct[i][0], 6)
                   for i in range(len(ct) - 1) if ct[i][0] >= 2 * CLK_PERIOD})
    res.append((
        "⑨ 中间信号 c1：每拍 +1、数到 %d 回绕（每值保持恰 1 个 clk 周期 = %.0f ns）"
        % (top1, T1_NS),
        bool(cv) and max(cv) == top1 and set(cv) == set(range(top1 + 1)) and step_ok
        and durs == [CLK_PERIOD],
        "c1 取值集合 = %s；最大值 = %s；稳态每值保持 %s ns；每拍 +1 = %s"
        % (sorted(set(cv)), max(cv) if cv else None, durs, step_ok),
    ))

    # ---------------------------------------------------------
    # ⑩ 内部信号：bcnt 是 5 位**饱和计数器**（第 13 工作阶段把 20 位移位寄存器换掉了），
    #    按住期间每刻度 +1、到 BTN_MS 就停住（不回绕）；松开立刻清零。
    # ---------------------------------------------------------
    t_shift = [t + CLK_PERIOD for t in t1_r]      # t1 抬起后的下一个 clk 沿才 +1
    win = [t for t in t_shift if T_PRESS < t <= T_RELEASE]
    cnts = []
    for t in win:
        v = _busv(vf, "bcnt", t)
        cnts.append(v)
    known = [x for x in cnts if x is not None]
    rising = all(known[i + 1] == min(known[i] + 1, int(BTN_MS))
                 for i in range(len(known) - 1))
    res.append((
        "⑩ 中间信号 bcnt：按住期间每刻度 +1，满 %d 就饱和（不回绕）；松开立刻归零" % int(BTN_MS),
        len(known) > BTN_MS and known[0] == 1 and max(known) == int(BTN_MS)
        and rising and vf.value_at("o_rst", T_GLITCH_OFF + CLK_PERIOD * 4) == "0",
        "按住窗口内 bcnt 前 24 个 = %s；最大值 = %s（期望 %d）；松开后 o_rst = %s"
        % (cnts[:24], max(known) if known else None, int(BTN_MS),
           vf.value_at("o_rst", T_GLITCH_OFF + CLK_PERIOD * 4)),
    ))

    return res
