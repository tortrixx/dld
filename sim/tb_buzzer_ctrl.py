# -*- coding: utf-8 -*-
"""tb_buzzer_ctrl.py —— buzzer_ctrl 功能仿真激励与断言

【本模块是什么】
    `buzzer_ctrl` 把 8 个"音效码"变成蜂鸣器上的方波（`o_buzz`，PIN_60）：
      · 音调 = 一个分频比（查表 half：音调 00→2 kHz，01→1 kHz，10→500 Hz，11→250 Hz）；
      · 节奏 = `phase` 计数器（每来一个 `i_t2`（2 Hz 节拍，500 ms）走一步），
        不同音效码用 phase 的不同位做"通/断"，于是有了短促/连响/长鸣；
      · `i_en='0'` 强制静音（SW7）。
    注意：**方波振荡器一直在跑**，静音是最后一级 `o_buzz <= wave when (en and on_now)`
    门掉的 —— 断言 ⑦ 专门验这一条（静音时 `wave` 仍在翻转而 `o_buzz` 不动）。

【判据的独立来源（不许自证）】
    · 期望频率来自**音效码 → 音调 → 频率**的文档表（本模块头部注释的
      2 kHz / 1 kHz / 500 Hz / 250 Hz 表 + docs/02 对 A1「不同场景不同声音」的要求），
      **不是**从 RTL 的分频常量反推。tb 从**实测**波形量出半周期拍数，再用
      `f = CLK_HZ / (2 * 半周期拍数)` 反算频率与文档值比。
    · `CLK_HZ` 从 `rtl/puzzle_pkg.vhd`（唯一真值源）读，不写死。
    · 计时结构（"数到 half 再翻转"）由**实测**验证：相邻两次翻转之间必须恰为
      `half + 1` 拍 —— 不是 half、不是 half+2（off-by-one 类缺陷的典型位置）。

【⚠️ 隔离工程专用的 RTL 补丁（sim.py 会自动记进轮次记录）】
    真实分频常量是 12500/25000/50000/100000 拍，一个半周期就是 0.25~2 ms，
    整条时间线要 7 ms 以上、几十万个时钟 —— 没必要。
    `RTL_PATCHES` 把 4 个常量**同时除以 500**（25/50/100/200），比例 1:2:4:8 与真实值
    完全一致，整条时间线缩到 99 µs。断言用 `PATCH_DIV` 把实测拍数**换算回真实频率**，
    所以判据仍然是文档里的 2 kHz / 1 kHz / 500 Hz / 250 Hz，而不是补丁后的数字。
    ⚠️ 补丁**只作用于 `.tmp/sim_buzzer_ctrl/` 里的 RTL 副本**，仓库 `rtl/` 一个字节没动。

【中间信号】（课件 p59 / docs/03 §3.1：波形里必须有中间信号）
    综合后网表里**真实存在**的内部寄存器（名字经探针跑确认，不是猜的）：
        `cnt[16:0]`   —— 半周期计数器（音调分频的主角；每次翻转前恰好数到 half）
        `wave`        —— 方波内部寄存器（一直在翻转，与 o_buzz 差一个静音门）
        `phase[2:0]`  —— 节奏计数器（每个 i_t2 走一步；音效码一变就清零）
        `prev[2:0]`   —— 上一次的音效码（用来检测"换码 → 重置节奏"）
    （`half`/`tone_sel`/`on_now` 这三个组合中间量被综合吃掉了，网表里没有对应节点，
      所以波形里用的是上面这四个真实寄存器。）

【时间线】（单位 ns，CLK 周期 20；i_t2 脉冲 = 高 20 ns、恰好覆盖一个上升沿）
     0 ~  1000  复位；i_sel=000（静音档）                     → 恒 0
  1000 ~  4000  i_sel=011 → 音调 00（文档 2 kHz）
  4000 ~  8000  i_sel=001 → 音调 01（文档 1 kHz）
  8000 ~ 12000  i_sel=101 → 音调 01（与上同一音调 → 半周期必须相同）
 12000 ~ 29000  i_sel=100 → 音调 11（文档 250 Hz）
 29000 ~ 46000  i_sel=111 → 音调 11（同一音调 → 半周期相同）
 46000 ~ 50000  i_sel=010（phase(0)=0）→ 静音
 50000 ~ 53000  i_sel=110（phase(2)=0）→ 静音
 53000 ~ 57000  i_sel=011 但 i_en=0     → 强制静音（振荡器仍在跑）
 57000 ~ 87000  i_sel=010 + 4 个 i_t2 脉冲（60110/68110/75110/82110）
                → phase = 0,1,2,3,4，声音"停—响—停—响—停"
 87000 ~ 96000  切到 i_sel=100（换码 → phase 清零、立刻响）
 96000 ~ 99000  i_sel=000（静音档）
"""

import pathlib
import re

CLK = 20.0
DURATION = 99000.0
GRID_PERIOD = 10.0

# ============================================================
# 隔离工程专用的 RTL 补丁：4 个分频常量同时 /500（比例 1:2:4:8 不变）
# ============================================================
PATCH_DIV = 500
PATCHED_HALF = {"00": 25, "01": 50, "10": 100, "11": 200}

RTL_PATCHES = [
    ("buzzer_ctrl.vhd", 'to_unsigned(12500, 17) when "00"',
     'to_unsigned(25, 17) when "00"'),
    ("buzzer_ctrl.vhd", 'to_unsigned(25000, 17) when "01"',
     'to_unsigned(50, 17) when "01"'),
    ("buzzer_ctrl.vhd", 'to_unsigned(50000, 17) when "10"',
     'to_unsigned(100, 17) when "10"'),
    ("buzzer_ctrl.vhd", 'to_unsigned(100000, 17) when others',
     'to_unsigned(200, 17) when others'),
]


def _clk_hz():
    p = pathlib.Path(__file__).resolve().parent.parent / "rtl" / "puzzle_pkg.vhd"
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"constant\s+CLK_HZ\s*:\s*integer\s*:=\s*([0-9_]+)", txt)
    if not m:
        raise RuntimeError("puzzle_pkg 里没找到 CLK_HZ")
    return int(m.group(1).replace("_", ""))


CLK_HZ = _clk_hz()

# ============================================================
# 文档表：音效码 → (phase=0 时的音调, 文档频率 Hz)
#   音调表（模块头部注释 + docs/02 A1）：00→2 kHz, 01→1 kHz, 10→500 Hz, 11→250 Hz
# ============================================================
DOC = {
    "000": (None, None),
    "001": ("01", 1000),
    "010": ("10", 500),
    "011": ("00", 2000),
    "100": ("11", 250),
    "101": ("01", 1000),
    "110": ("00", 2000),
    "111": ("11", 250),
}

# ============================================================
# 时间线：(起, 止, i_sel, i_en)
# ============================================================
SCHED = [
    (0.0,     1000.0,  0, 1),
    (1000.0,  4000.0,  3, 1),
    (4000.0,  8000.0,  1, 1),
    (8000.0,  12000.0, 5, 1),
    (12000.0, 29000.0, 4, 1),
    (29000.0, 46000.0, 7, 1),
    (46000.0, 50000.0, 2, 1),
    (50000.0, 53000.0, 6, 1),
    (53000.0, 57000.0, 3, 0),
    (57000.0, 87000.0, 2, 1),
    (87000.0, 96000.0, 4, 1),
    (96000.0, 99000.0, 0, 1),
]
NAMES = ["RST_sil000", "W011", "W001", "W101", "W100", "W111",
         "W010off", "W110off", "Wen0", "Wrhythm", "Wnewcode", "Wsil000"]
W = {n: SCHED[i] for i, n in enumerate(NAMES)}

# i_t2 脉冲：高 20 ns，恰好覆盖一个时钟上升沿（上升沿在 10 + 20k）
T2_EDGES = [60110.0, 68110.0, 75110.0, 82110.0]
RHY_PHASE_WINS = {                       # i_sel=010 时各相位对应的发声窗口
    "phase0": (57000.0, 60110.0),
    "phase1": (60110.0, 68110.0),
    "phase2": (68110.0, 75110.0),
    "phase3": (75110.0, 82110.0),
    "phase4": (82110.0, 87000.0),
}

# 采样时刻
T_SIL = [400.0, 700.0, 900.0]                        # 复位后静音档 3 点
T_PHASE = [59000.0, 62000.0, 70000.0, 76000.0, 84000.0]   # 期望 phase = 0,1,2,3,4

# ============================================================
# 节点声明
# ============================================================
BURIED = {"cnt": 17, "wave": 1, "phase": 3, "prev": 3}
OBSERVE = (["i_clk", "i_rst", "i_en", "i_sel", "i_t2", "o_buzz"]
           + list(BURIED.keys()))


def _buried(b, name, width):
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def _decl(b, name, width):
    if width > 1:
        b.output_bus(name, width)
    else:
        b.output_bit(name)


def _t2_segments():
    segs = []
    cur = 0.0
    for t in T2_EDGES:
        segs.append((t - 10.0 - cur, 0))
        segs.append((20.0, 1))
        cur = t + 10.0
    segs.append((DURATION - cur, 0))
    return segs


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_en")
    b.input_bus("i_sel", 3)
    b.input_bit("i_t2")
    b.output_bit("o_buzz")
    for n, w in BURIED.items():
        _decl(b, n, w)
        _buried(b, n, w)

    b.clock("i_clk", CLK)
    # ⚠️ 时序模块必须显式复位（综合后网表寄存器初值不可依赖）
    b.segments("i_rst", [(100.0, 1), (DURATION - 100.0, 0)])
    b.bus_segments("i_sel", [(e - s, v) for (s, e, v, _en) in SCHED])
    b.segments("i_en", [(e - s, en) for (s, e, _v, en) in SCHED])
    b.segments("i_t2", _t2_segments())


# ============================================================
# 实测辅助
# ============================================================
def _toggles(vf, a, b, name="o_buzz"):
    """(a, b) 内**真正的 0↔1 跳变**时刻（两端都开区间）。

    ⚠️ 两个坑：
      1) 不能用 `vf.trace` 的原始跳变表：仿真开始/复位瞬间是 X→0，
         那也会被记成一次"跳变"，会把"静音"误判成"有声音"；
      2) 端点要开区间：本 tb 的时间线在某时刻**同时**换 i_sel，
         恰好落在端点上的那次跳变属于新窗口，算进旧窗口会把"静音"判成"有声"。
    """
    tr = vf.trace(name)
    out = []
    for i in range(1, len(tr)):
        t, lv = tr[i]
        pv = tr[i - 1][1]
        if lv in ("0", "1") and pv in ("0", "1") and lv != pv and a + 1e-6 < t < b - 1e-6:
            out.append(t)
    return out


def _intervals(ts):
    """相邻跳变间隔；**丢掉第一个**（换码/换音调后的第一个半周期可能不完整）。"""
    return [round(ts[i + 1] - ts[i], 3) for i in range(1, len(ts) - 1)]


def _steady(iv):
    """稳定段半周期 = 间隔里**出现次数最多**的那个（要求至少出现 2 次）。

    为什么不能要求"所有间隔都相等"：每个测量窗口的**最后一个**间隔会被
    窗口末尾的换码（例如 i_sel 从 111 切到 010 → 输出被静音门拉低）截短，
    那不是振荡器的半周期。取众数并要求 ≥2 次即可避开首尾两个不完整间隔。
    """
    if not iv:
        return None
    cnt = {}
    for x in iv:
        cnt[x] = cnt.get(x, 0) + 1
    val, n = max(cnt.items(), key=lambda kv: (kv[1], -kv[0]))
    return val if n >= 2 else None


def _ticks(ns):
    return int(round(ns / CLK))


def _freq_hz(interval_ns):
    """把（补丁后的）半周期换算成**真实**频率：先乘回 PATCH_DIV 再按 CLK_HZ 算。"""
    half_real = (_ticks(interval_ns) - 1) * PATCH_DIV
    return CLK_HZ / (2.0 * half_real) if half_real else None


def _high_time(vf, a, b, name="o_buzz"):
    """(a, b] 内 name 为 '1' 的总时长。"""
    tr = [(t, lv) for (t, lv) in vf.trace(name) if t <= b + 1e-6]
    tot = 0.0
    for i, (t, lv) in enumerate(tr):
        nxt = tr[i + 1][0] if i + 1 < len(tr) else b
        if lv == "1" and t >= a - 1e-6:
            tot += max(0.0, min(nxt, b) - max(t, a))
    return tot


def _hex(v, width):
    return "X" if v is None else ("0x%0*X" % (width, v))


# ============================================================
# 断言
# ============================================================
def check(vf):
    res = []

    # ---- ① i_en='0' → o_buzz 恒 0；静音档 000 → 恒 0 ----
    a, b = W["Wen0"][0], W["Wen0"][1]
    ed_en0 = _toggles(vf, a, b)
    ed_000 = _toggles(vf, *W["Wsil000"][:2])
    ed_rst = _toggles(vf, 0.0, W["RST_sil000"][1])
    ok = (not ed_en0 and not ed_000 and not ed_rst
          and all(vf.value_at("o_buzz", t) == "0" for t in T_SIL))
    res.append((
        "① i_en='0'（SW7 静音）时 o_buzz 恒 '0'（此时 i_sel=011，本来该响）；"
        "i_sel=000 静音档同样恒 '0'",
        ok,
        "en=0 窗口 [%.0f,%.0f] 翻转 %d 次；sel=000 窗口翻转 %d 次；"
        "复位后静音档 3 个采样点 = %s"
        % (a, b, len(ed_en0), len(ed_000),
           [vf.value_at("o_buzz", t) for t in T_SIL]),
    ))

    # ---- ② 相位不通的音效码（phase=0 时）→ 静音 ----
    e010 = _toggles(vf, *W["W010off"][:2])
    e110 = _toggles(vf, *W["W110off"][:2])
    res.append((
        "② i_sel=010（预览音：只在 phase 奇数步响）与 i_sel=110（胜利音：只在 phase(2)=1 响）"
        "在 phase=0 时不发声 —— o_buzz 全程无翻转",
        not e010 and not e110,
        "sel=010 翻转 %d 次；sel=110 翻转 %d 次（都应 0）" % (len(e010), len(e110)),
    ))

    # ---- ③ 各音效码实测半周期（拍）→ 换算真实频率 vs 文档频率 ----
    meas = {}
    for key, sel in (("W011", 3), ("W001", 1), ("W101", 5), ("W100", 4), ("W111", 7)):
        ts = _toggles(vf, W[key][0], W[key][1])
        iv = _intervals(ts)
        meas[key] = (ts, iv, _steady(iv),
                     DOC[format(sel, "03b")][0], DOC[format(sel, "03b")][1])
    # 节奏段里的 500 Hz（i_sel=010 在 phase=1 时才响）
    ts_r = _toggles(vf, *RHY_PHASE_WINS["phase1"])
    iv_r = _intervals(ts_r)
    meas["W010on"] = (ts_r, iv_r, _steady(iv_r), "10", 500)

    bad = []
    detail = []
    for key in ("W011", "W001", "W101", "W100", "W111", "W010on"):
        _ts, iv, steady, tone, doc_hz = meas[key]
        if steady is None:
            bad.append("%s: 没能量到重复出现的半周期（实测间隔 = %s）" % (key, iv))
            continue
        want_ticks = PATCHED_HALF[tone] + 1
        got_ticks = _ticks(steady)
        f = _freq_hz(steady)
        detail.append("%s(音调 %s): 稳定段半周期 %d 拍 = %.0f ns → 换算真实频率 %.1f Hz"
                      "（文档 %d Hz）；期望 half+1 = %d 拍；全部实测间隔 = %s"
                      % (key, tone, got_ticks, steady, f, doc_hz, want_ticks, iv))
        if got_ticks != want_ticks:
            bad.append("%s: 半周期实测 %d 拍 ≠ half+1 = %d 拍（分频结构不符）"
                       % (key, got_ticks, want_ticks))
        if f is None or abs(f - doc_hz) > 0.5:
            bad.append("%s: 换算真实频率 %s Hz ≠ 文档 %d Hz" % (key, f, doc_hz))
    res.append((
        "③ 6 个实测窗口的稳定段半周期拍数都恰等于查表 half+1；按 CLK_HZ 与补丁倍数换算回"
        "真实频率后 == 文档频率（2 kHz / 1 kHz / 500 Hz / 250 Hz）",
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ④ 音效码变 → 频率变；文档上同音调的两对 → 半周期完全相同 ----
    def steady_of(k):
        return meas[k][2]

    i011, i001, i101, i100, i111, i010 = (steady_of("W011"), steady_of("W001"),
                                          steady_of("W101"), steady_of("W100"),
                                          steady_of("W111"), steady_of("W010on"))
    ok = (None not in (i011, i001, i101, i100, i111, i010)
          and i011 < i001 < i100                       # 2 kHz < 1 kHz < 250 Hz（按周期）
          and i011 < i001 < i010 < i100                # 500 Hz 的周期夹在 1 kHz 与 250 Hz 之间
          and i001 == i101                             # 001 与 101 同为 1 kHz
          and i100 == i111)                            # 100 与 111 同为 250 Hz
    res.append((
        "④ 音效码一变、半周期随之改变：按周期排序 2 kHz(520) < 1 kHz(1020) < 500 Hz(2020)"
        " < 250 Hz(4020) 的音调阶梯正确；文档上同音调的两对（001/101 = 1 kHz、"
        "100/111 = 250 Hz）实测半周期完全相等",
        ok,
        "半周期(ns)：sel011=%.0f  sel010(响)=%.0f  sel001=%.0f  sel101=%.0f  "
        "sel100=%.0f  sel111=%.0f"
        % (i011 or -1, i010 or -1, i001 or -1, i101 or -1, i100 or -1, i111 or -1),
    ))

    # ---- ⑤ 占空比 50%：稳定段内高电平总时长 == 低电平总时长 ----
    a = W["W011"][0] + 3 * (PATCHED_HALF["00"] + 1) * CLK
    b = W["W011"][1]
    ts = [t for t in _toggles(vf, a, b)]
    t0, t1 = (ts[0], ts[-1]) if ts else (a, b)
    high, low = 0.0, 0.0
    tr = [(t, lv) for (t, lv) in vf.trace("o_buzz") if t0 <= t <= t1]
    for i, (t, lv) in enumerate(tr):
        nxt = tr[i + 1][0] if i + 1 < len(tr) else t1
        (high, low) = (high + nxt - t, low) if lv == "1" else (high, low + nxt - t)
    ok = abs(high - low) <= CLK and (high + low) > 0
    res.append((
        "⑤ 方波占空比 50%%：稳定段 [%.0f, %.0f] ns 内高电平总时长 == 低电平总时长（容差 1 拍）"
        % (t0, t1),
        ok,
        "高 = %.0f ns，低 = %.0f ns，占空比 = %.1f%%"
        % (high, low, 100.0 * high / (high + low) if (high + low) else 0.0),
    ))

    # ---- ⑥ 中间信号 cnt：每次翻转前的计数值恰为查表 half ----
    bad = []
    detail = []
    for key, sel in (("W011", 3), ("W001", 1), ("W100", 4)):
        ts = _toggles(vf, W[key][0], W[key][1])
        tone = DOC[format(sel, "03b")][0]
        want = PATCHED_HALF[tone]
        vals = [vf.bus_value_at("cnt", t - 5.0) for t in ts[1:]]
        detail.append("sel=%d(音调 %s): 各次翻转前 cnt = %s（期望恒为 half = %d）"
                      % (sel, tone, vals, want))
        if any(v != want for v in vals):
            bad.append("sel=%d: cnt 实测 %s ≠ half = %d" % (sel, vals, want))
    res.append((
        "⑥ 中间信号 cnt[16:0]（半周期计数器）：每次翻转前的计数值恰为查表 half"
        "（补丁后 25/50/200）—— 音调分频在波形上可直接读出来",
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑦ 中间信号 wave：静音时振荡器仍在翻转（静音是最后一级门掉的）----
    ed_w_en0 = _toggles(vf, *W["Wen0"][:2], name="wave")
    ed_o_en0 = _toggles(vf, *W["Wen0"][:2])
    ed_w_010 = _toggles(vf, *W["W010off"][:2], name="wave")
    ed_o_010 = _toggles(vf, *W["W010off"][:2])
    wv = [vf.value_at("wave", t) for t in (54000.0, 55000.0, 56000.0)]
    res.append((
        "⑦ 中间信号 wave：i_en=0 静音段（%d 次翻转）与 i_sel=010 相位不通段（%d 次翻转）里"
        "wave 一直在翻，而 o_buzz 一动不动 —— 静音是输出级门掉的，不是停振荡器"
        % (len(ed_w_en0), len(ed_w_010)),
        len(ed_w_en0) > 0 and len(ed_w_010) > 0 and not ed_o_en0 and not ed_o_010
        and all(x in ("0", "1") for x in wv),
        "en=0 段：wave 翻转 %d 次 / o_buzz 翻转 %d 次；010 段：wave 翻转 %d 次 / o_buzz %d 次；"
        "wave 采样 = %s"
        % (len(ed_w_en0), len(ed_o_en0), len(ed_w_010), len(ed_o_010), wv),
    ))

    # ---- ⑧ 节奏：i_t2 每来一个脉冲 phase 走一步，声音按 phase 位通/断 ----
    ph = [vf.bus_value_at("phase", t) for t in T_PHASE]
    snd = {k: _high_time(vf, a, b) for k, (a, b) in RHY_PHASE_WINS.items()}
    loud = {k: (v > 0.1 * (RHY_PHASE_WINS[k][1] - RHY_PHASE_WINS[k][0])) for k, v in snd.items()}
    ok = (ph == [0, 1, 2, 3, 4]
          and not loud["phase0"] and loud["phase1"] and not loud["phase2"]
          and loud["phase3"] and not loud["phase4"])
    res.append((
        "⑧ 节奏：4 个 i_t2 脉冲把 phase 推成 0→1→2→3→4；i_sel=010 时只有 phase 为奇数"
        "才发声（实测有声的相位 = %s）—— 「短促提示音重复响」的语义"
        % [k for k in ("phase0", "phase1", "phase2", "phase3", "phase4") if loud[k]],
        ok,
        "phase 实测 = %s（期望 [0,1,2,3,4]）；各相位窗口内 o_buzz 的高电平时长 = %s"
        % (ph, {k: round(v) for k, v in snd.items()}),
    ))

    # ---- ⑨ 换音效码 → phase 清零、节奏重来（并立刻响）----
    ph_new = vf.bus_value_at("phase", 88000.0)
    ed_new = _toggles(vf, *W["Wnewcode"][:2])
    res.append((
        "⑨ 音效码改变（010 → 100，换码前 phase 已到 4）→ phase 立刻清零（实测 %s）"
        "并立刻开始发声（换码窗口内 %d 次翻转）—— 「新事件总是从头播」"
        % (_hex(ph_new, 1), len(ed_new)),
        ph_new == 0 and len(ed_new) >= 1,
        "88000 ns 处 phase = %s（期望 0）；换码窗口 [%.0f,%.0f] 内翻转 %d 次"
        % (ph_new, W["Wnewcode"][0], W["Wnewcode"][1], len(ed_new)),
    ))

    # ---- ⑩ i_sel 覆盖 / 输出电平确定性 ----
    badlv = [(t, lv) for (t, lv) in vf.trace("o_buzz") if t > 100.0 and lv not in ("0", "1")]
    used = sorted({s for (_a, _b, s, _e) in SCHED})
    res.append((
        "⑩ 8 个音效码全部驱动过；复位后 o_buzz 全程为确定值（0/1，无 X/Z）",
        used == list(range(8)) and not badlv,
        "驱动过的 i_sel = %s；非 0/1 电平 = %s" % (used, badlv or "无"),
    ))

    return res
