# -*- coding: utf-8 -*-
"""tb_buzzer_ctrl.py —— buzzer_ctrl（**旋律播放器**）功能仿真激励与断言

【本模块现在是什么（2026-10-09 第 13 工作阶段重写，提高要求 A1）】
    `buzzer_ctrl` 已从"4 个固定音 + 每 500 ms 换一次"改成**真正的旋律播放器**：
      · 一个 3 位 `step` 计数器，每个 **i_t4**（4 Hz，250 ms）脉冲走一步
        → 一句 = 8 步 × 250 ms = **2 秒**，计满回绕；
      · 每个音效码 = 8 步的**常量旋律表** MEL_*，每步 4 位：
        bit3 = "这一步响不响"，bit2..0 = 音高索引；
      · 8 个音高（G4 A4 B4 C5 D5 E5 G5 C6）共用**一个**方波发生器，
        半周期常数 NOTE_HALF  = 25e6 / f（50 MHz 板钟下的拍数）；
      · `o_buzz = wave AND i_en AND on_now`，(tone_sel, on_now) 是**寄存器**
        → 与 (i_sel, step) 的组合相比**晚一拍**出现。
    ⚠️ 与旧版的两个行为差异（本轮断言专门覆盖）：
      · 端口 `i_t2`（2 Hz）→ **`i_t4`**（4 Hz），位置不变、只改名；
      · `step` **不再**因音效码改变而清零（旧的 `prev` 逻辑已删除）。

【判据的独立来源（不许自证）】
    · 旋律表 MEL 抄自**模块头部注释**（= docs/02 的 A1 要求），不是从 RTL 逻辑反推；
    · 音高→频率抄自模块头部注释的音名/频率（G4 392 Hz ... C6 1047 Hz）；
      再由 f = CLK_HZ / (2 * half) 反推半周期常量 NOTE_HALF，并在模块加载时
      **自检 "注释里的频率" 与 "注释里的 half" 互相一致**（差 < 0.2%）。
      `CLK_HZ` 从 `rtl/puzzle_pkg.vhd`（唯一真值源）读，不写死。
    · tb 只从**实测** o_buzz 的跳变间隔量半周期，再与上面两条独立来源比对。

【⚠️ 隔离工程专用的 RTL 补丁（sim.py 会自动记进轮次记录）】
    真实半周期是 23878~63776 拍，一句 8 步要几十万个时钟，没必要。
    `RTL_PATCHES` 把 `note_half()` 的 8 个常量**同时除以 PATCH_DIV = 1000 后取整**
    → 64/57/51/48/43/38/32/24（比例不变，句子时长不变），断言再用
    `(实测拍数 - 1) * PATCH_DIV` 换算回**真实**半周期/频率。
    补丁**只作用于 `.tmp/sim_buzzer_ctrl/` 里的 RTL 副本**，仓库 `rtl/` 一个字节没动。
    【容差】取整误差最大 0.97%（E5：42589 → 43*1000 = 43000），所以
       · "半周期拍数 == 查表 half + 1" —— **精确**判据，不设容差；
       · "换算回的真实频率 == 25e6/half" —— 容差 **FREQ_TOL = 1.5%**。

【时间线（单位 ns，CLK 周期 20）】
    0 ~ 10010        复位（i_rst 高 1000 ns）+ 静音码 000 的前 10000 ns
    T0 = 10010       第 0 个"乐句窗口"起点；窗口 k = [T0+k*PHRASE, T0+(k+1)*PHRASE)
    STEP  = 20000 ns （板上 250 ms 的**仿真折算**：模块只数 i_t4 脉冲，不关心真实时长）
    PHRASE = 8 * STEP = 160000 ns
    i_t4 脉冲在 T0 + m*STEP（m = 1..79）各一个时钟宽，覆盖该上升沿
      → 每个窗口里 step 恰好是 0,1,...,7（8 个脉冲自然回绕），窗口起点 step=0
    窗口 0..7   i_sel = 000..111, i_en = 1   —— 8 个音效码各**一整句**（判据 ①~⑨）
    窗口 8      i_sel = 011 但 i_en = 0      —— SW7 强制静音（判据 ⑩⑪）
    窗口 9      前 3 步 i_sel=001、之后换成 011 —— 换码**不清零** step（判据 ⑫）
    窗口 10     i_en = 0，但**每一步换一个音效码**（8 个码各验一次，且每一步都挑
                该码本来会响的步）—— "i_en=0 对每个码都静音"不空跑（判据 ⑩）
    ⚠️ i_sel/i_en 的切换点比步边界**早 10 ns**（落在时钟下降沿前），
       避开"输入与上升沿同刻变化"的竞争；i_t4 脉冲仍按 ±10 ns 包住上升沿。

【中间信号】（课件 p59 / docs/03 §3.1：波形里必须有中间信号）
    综合后网表里**真实存在**的内部寄存器（探针按名字查，缺失即报错）：
        `cnt[15:0]`   —— 半周期计数器（16 位，旧版是 17 位）
        `wave`        —— 方波内部寄存器（一直在翻转，与 o_buzz 差一个静音门）
        `step[2:0]`   —— 旋律步计数器（每个 i_t4 走一步）
        `tone_sel[2:0]`/`on_now` —— 旋律查表结果（**寄存**一拍）
"""

import pathlib
import re

CLK = 20.0
STEP = 20000.0                 # 一个旋律步（板上 250 ms 的仿真折算）
PHRASE = 8 * STEP              # 一句 = 8 步
T0 = 10010.0                   # 第 0 个乐句窗口起点（复位已释放；与 i_t4 脉冲同相位）
NWIN = 11                      # 8 个音效码 + 1 个 i_en=0 + 1 个中途换码 + 1 个"每码静音"
DURATION = T0 + NWIN * PHRASE + 300.0
GRID_PERIOD = 10.0

# ============================================================
# 独立真值源 1：旋律表（模块头部注释）
#   None = 这一步是休止；数字 = 音高索引（NOTE_NAME 的下标）
# ============================================================
NOTE_NAME = ["G4", "A4", "B4", "C5", "D5", "E5", "G5", "C6"]
NOTE_HZ = [392, 440, 494, 523, 587, 659, 784, 1047]
MEL = {
    0: [None, None, None, None, None, None, None, None],       # 000 静音
    1: [0, 1, 2, 3, 3, None, None, None],                      # 001 自检
    2: [1, 1, 1, None, 1, 1, None, None],                      # 010 预览
    3: [3, 3, 5, 5, 6, None, None, None],                      # 011 过关
    4: [5, 5, 3, 3, 1, None, None, None],                      # 100 拼错
    5: [4, None, None, None, None, None, None, None],          # 101 按键
    6: [3, 5, 6, 7, 6, 7, 7, None],                            # 110 通关
    7: [2, 1, 0, 0, 0, None, None, None],                      # 111 超时
}
MEL_DESC = {0: "静音（全休止）",
            1: "自检上行号角 G4 A4 B4 C5 C5 - - -",
            2: "预览 A4 A4 A4 - A4 A4 - -",
            3: "过关上行 C5 C5 E5 E5 G5 - - -",
            4: "拼错下行 E5 E5 C5 C5 A4 - - -",
            5: "按键单击 D5 - - - - - - -",
            6: "通关长号角 C5 E5 G5 C6 G5 C6 C6 -",
            7: "超时下行 B4 A4 G4 G4 G4 - - -"}
MEL_LABEL = {0: "静音", 1: "自检", 2: "预览", 3: "过关",
             4: "拼错", 5: "按键", 6: "通关", 7: "超时"}


def _clk_hz():
    p = pathlib.Path(__file__).resolve().parent.parent / "rtl" / "puzzle_pkg.vhd"
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"constant\s+CLK_HZ\s*:\s*integer\s*:=\s*([0-9_]+)", txt)
    if not m:
        raise RuntimeError("puzzle_pkg 里没找到 CLK_HZ")
    return int(m.group(1).replace("_", ""))


CLK_HZ = _clk_hz()

# ============================================================
# 独立真值源 2：模块头部注释的"音高 -> 半周期拍数"
#   注释里的频率与 half 必须互相自洽（f = CLK_HZ / (2*half)）
# ============================================================
NOTE_HALF = [63776, 56818, 50607, 47778, 42589, 37936, 31888, 23878]
for _i, (_f, _h) in enumerate(zip(NOTE_HZ, NOTE_HALF)):
    _want = CLK_HZ / (2.0 * _f)
    assert abs(_want - _h) / _h < 0.002, \
        "模块注释自相矛盾：%s 的注释频率 %d Hz 对应 %.1f 拍，但注释写 half=%d" \
        % (NOTE_NAME[_i], _f, _want, _h)

# ============================================================
# 隔离工程专用的 RTL 补丁：8 个半周期常量同时 /1000 取整
# ============================================================
PATCH_DIV = 1000
PATCHED_HALF = [int(round(h / PATCH_DIV)) for h in NOTE_HALF]
FREQ_TOL = 0.015                        # 1.5%（取整误差实测最大 0.97%）
assert max(abs(PATCHED_HALF[i] * PATCH_DIV - NOTE_HALF[i]) / NOTE_HALF[i]
           for i in range(8)) < FREQ_TOL, "补丁取整误差已超过断言容差"

# ⚠️ 锚点必须与 rtl/buzzer_ctrl.vhd 的 note_half() **逐字一致**（sim.py 要求恰出现 1 次）。
#    只改注释臂里的数字；signal half 的初值不参与（half 是组合量，由 note_half 驱动）。
_NOTE_ARMS = ['when "000"  => v := to_unsigned(63776, 16);',
              'when "001"  => v := to_unsigned(56818, 16);',
              'when "010"  => v := to_unsigned(50607, 16);',
              'when "011"  => v := to_unsigned(47778, 16);',
              'when "100"  => v := to_unsigned(42589, 16);',
              'when "101"  => v := to_unsigned(37936, 16);',
              'when "110"  => v := to_unsigned(31888, 16);',
              'when others => v := to_unsigned(23878, 16);']
RTL_PATCHES = [("buzzer_ctrl.vhd", arm,
                re.sub(r"to_unsigned\(\d+, 16\)",
                       "to_unsigned(%d, 16)" % new, arm))
               for arm, new in zip(_NOTE_ARMS, PATCHED_HALF)]

# ============================================================
# 时间线：每个窗口的 8 步 (i_sel, i_en)
# ============================================================
WINS = [[(c, 1)] * 8 for c in range(8)]          # 窗口 0..7：8 个音效码各一整句
WINS.append([(3, 0)] * 8)                        # 窗口 8：码 011 但 i_en=0（强制静音）
WINS.append([(1, 1)] * 3 + [(3, 1)] * 5)         # 窗口 9：第 3 步中途换码 001 -> 011
# 窗口 10：i_en 仍为 0，但**每一步换一个音效码**，而且每一步都专门挑"该码本来会响"的那一步
#   （step0→101、step1→001、step2→011、step3→100、step4→111、step5→010、step6→110、
#     step7→000 本来就是全休止）—— 这样「i_en=0 对**每一个**码都强制静音」不是空跑：
#   每一步的旋律表期望值都非 None（判据 ⑩ 会核对这一点）。
EN0_BY_STEP = [5, 1, 3, 4, 7, 2, 6, 0]
WINS.append([(EN0_BY_STEP[j], 0) for j in range(8)])


def _win_bounds(i, j):
    a = T0 + i * PHRASE + j * STEP
    return a, a + STEP


def _transitions():
    """[(时刻, i_sel, i_en)]：切换点比步边界早 10 ns（时钟下降沿之前）。"""
    out = [(0.0, 0, 1)]
    for i, steps in enumerate(WINS):
        for j, (sel, en) in enumerate(steps):
            a, _b = _win_bounds(i, j)
            t = a - 10.0
            if t <= out[-1][0]:
                continue
            if (sel, en) != (out[-1][1], out[-1][2]):
                out.append((t, sel, en))
    t_end = T0 + len(WINS) * PHRASE - 10.0
    if t_end > out[-1][0]:
        out.append((t_end, 0, 1))
    return out


TRANS = _transitions()


def _seg(idx):
    """TRANS -> [(时长, 值)]，覆盖 [0, DURATION)。idx=1 -> i_sel，idx=2 -> i_en。"""
    segs = []
    for k, tr in enumerate(TRANS):
        t = tr[0]
        nxt = TRANS[k + 1][0] if k + 1 < len(TRANS) else DURATION
        if nxt > t:
            segs.append((nxt - t, tr[idx]))
    return segs


# i_t4 脉冲：t ≡ 10 (mod 20) → 脉冲 [t-10, t+10) 恰好只包住 t 处的那一个上升沿
T4_EDGES = [T0 + m * STEP for m in range(1, NWIN * 8)]


def _t4_segments():
    segs, cur = [], 0.0
    for t in T4_EDGES:
        segs.append((t - 10.0 - cur, 0))
        segs.append((20.0, 1))
        cur = t + 10.0
    segs.append((DURATION - cur, 0))
    return segs


# 期望表：每个窗口每一步的（时刻、码、期望音高）
STEPS_EXP = []
for _i, _steps in enumerate(WINS):
    for _j, (_sel, _en) in enumerate(_steps):
        _a, _b = _win_bounds(_i, _j)
        STEPS_EXP.append((_i, _j, _sel, _en, _a, _b, MEL[_sel][_j]))

# ============================================================
# 节点声明
# ============================================================
BURIED = {"cnt": 16, "wave": 1, "step": 3, "tone_sel": 3, "on_now": 1}
OBSERVE = (["i_clk", "i_rst", "i_en", "i_sel", "i_t4", "o_buzz"]
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


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_en")
    b.input_bus("i_sel", 3)
    b.input_bit("i_t4")
    b.output_bit("o_buzz")
    for n, w in BURIED.items():
        _decl(b, n, w)
        _buried(b, n, w)

    b.clock("i_clk", CLK)
    # ⚠️ 时序模块必须显式复位（综合后网表寄存器初值不可依赖）
    b.segments("i_rst", [(1000.0, 1), (DURATION - 1000.0, 0)])
    b.bus_segments("i_sel", _seg(1))
    b.segments("i_en", _seg(2))
    b.segments("i_t4", _t4_segments())


# ============================================================
# 实测辅助
# ============================================================
GUARD = 20 * CLK               # 400 ns：躲开步边界那一拍的寄存延迟与门控边沿


def _toggles(vf, a, b, name="o_buzz"):
    """(a, b) 内**真正的 0↔1 跳变**时刻（两端都开区间）。

    ⚠️ 两个坑（沿用旧 tb 的结论）：
      1) 不能用 `vf.trace` 的原始跳变表：仿真开始/复位瞬间是 X→0，
         那也会被记成一次"跳变"，会把"静音"误判成"有声音"；
      2) 端点要开区间：换码/换步恰好落在端点上时，那次跳变属于新窗口。
    另外本 tb 还额外留了 GUARD（见上）：o_buzz 被 (i_en AND on_now) **门控**，
    而 (tone_sel, on_now) 是寄存的 → 步边界后**一拍**才换音，边界上可能有一个
    20 ns 宽的门控边沿。所有测量都缩到步窗口内部，正是为了不把这种边沿
    当成旋律的一部分（既不误判成"响"，也不漏判休止）。
    """
    tr = vf.trace(name)
    out = []
    for i in range(1, len(tr)):
        t, lv = tr[i]
        pv = tr[i - 1][1]
        if lv in ("0", "1") and pv in ("0", "1") and lv != pv and a + 1e-6 < t < b - 1e-6:
            out.append(t)
    return out


def _ticks(ns):
    return int(round(ns / CLK))


def _intervals(ts):
    return [round(ts[i + 1] - ts[i], 3) for i in range(len(ts) - 1)]


def _measure(vf):
    """逐步测量（只取每步的内部 [a+GUARD, b-GUARD]）。"""
    out = []
    for (i, j, sel, en, a, b, exp) in STEPS_EXP:
        ts = _toggles(vf, a + GUARD, b - GUARD)
        iv = _intervals(ts)
        ticks = sorted({_ticks(x) for x in iv})
        note = None
        if len(ticks) == 1 and (ticks[0] - 1) in PATCHED_HALF:
            note = PATCHED_HALF.index(ticks[0] - 1)
        out.append({"win": i, "step": j, "sel": sel, "en": en, "a": a, "b": b,
                    "exp": exp, "edges": len(ts), "iv": iv, "ticks": ticks,
                    "sounding": len(ts) > 0, "note": note})
    return out


def _seq_str(rows):
    out = []
    for m in rows:
        if not m["sounding"]:
            out.append("-")
        elif len(m["ticks"]) == 1 and 0 <= m["ticks"][0] - 1 < 65536 \
                and (m["ticks"][0] - 1) in PATCHED_HALF:
            out.append("%s(%d拍)" % (NOTE_NAME[PATCHED_HALF.index(m["ticks"][0] - 1)],
                                     m["ticks"][0]))
        else:
            out.append("?%s" % (m["iv"],))
    return " ".join(out)


def _high_low(vf, t0, t1, name="o_buzz"):
    """[t0, t1] 内 name 的高/低电平总时长。"""
    tr = [(t, lv) for (t, lv) in vf.trace(name) if t0 <= t <= t1]
    high = low = 0.0
    for i, (t, lv) in enumerate(tr):
        nxt = tr[i + 1][0] if i + 1 < len(tr) else t1
        if lv == "1":
            high += max(0.0, nxt - t)
        elif lv == "0":
            low += max(0.0, nxt - t)
    return high, low


# ============================================================
# 断言
# ============================================================
def check(vf):
    res = []
    meas = _measure(vf)

    # ---- ① 复位期间 + 静音码 000 的一整句 → o_buzz 恒 0 ----
    w0a, w0b = _win_bounds(0, 0)[0], _win_bounds(0, 7)[1]
    ed_rst = _toggles(vf, 0.0, 1000.0)
    ed_000 = _toggles(vf, w0a + GUARD, w0b - GUARD)
    lv_rst = [vf.value_at("o_buzz", t) for t in (200.0, 500.0, 900.0)]
    res.append((
        "① 复位期间（i_rst=1）与 i_sel=000 静音码的一整句：o_buzz 恒 '0'（无任何翻转）",
        not ed_rst and not ed_000 and all(x == "0" for x in lv_rst),
        "复位窗口 [0,1000] 翻转 %d 次、3 个采样点 = %s；静音码整句 [%.0f,%.0f] 翻转 %d 次"
        % (len(ed_rst), lv_rst, w0a, w0b, len(ed_000)),
    ))

    # ---- ②~⑧ 每个音效码一整句（8 步）的"响/停 + 音高"必须等于旋律表 ----
    for code in range(1, 8):
        rows = [m for m in meas if m["win"] == code]
        bad, got = [], []
        for m in rows:
            if m["exp"] is None:
                if m["sounding"]:
                    bad.append("第 %d 步应为休止，实测 %d 次翻转（间隔 %s）"
                               % (m["step"], m["edges"], m["iv"]))
                got.append("-")
            elif not m["sounding"]:
                bad.append("第 %d 步应为 %s，实测**无翻转**（被当成休止）"
                           % (m["step"], NOTE_NAME[m["exp"]]))
                got.append("无")
            elif m["note"] != m["exp"]:
                bad.append("第 %d 步应为 %s，实测 %s（间隔 %s）"
                           % (m["step"], NOTE_NAME[m["exp"]],
                              "无法识别" if m["note"] is None else NOTE_NAME[m["note"]],
                              m["iv"]))
                got.append("错")
            else:
                got.append(NOTE_NAME[m["exp"]])
        res.append((
            "②~⑧ 码 %s「%s」一整句 8 步的响/停与音高 == 旋律表（%s）"
            % (format(code, "03b"), MEL_LABEL[code], MEL_DESC[code]),
            not bad,
            ("；".join(bad) + " | " if bad else "") + "实测（步 0..7）：" + _seq_str(rows),
        ))

    # ---- ⑨ 8 个音高的实测半周期 == 查表 half+1（精确）；换算真实频率 == 25e6/half（1.5%）----
    per_note = {}
    for m in meas:
        if m["sounding"] and m["note"] is not None:
            per_note.setdefault(m["note"], []).append(m)
    bad, detail = [], []
    for n in range(8):
        rows = per_note.get(n, [])
        if not rows:
            bad.append("音高 %s（%d Hz）一次都没测到" % (NOTE_NAME[n], NOTE_HZ[n]))
            continue
        tick_sets = sorted({tuple(m["ticks"]) for m in rows})
        half_real = PATCHED_HALF[n] * PATCH_DIV
        f_meas = CLK_HZ / (2.0 * half_real)
        f_doc = CLK_HZ / (2.0 * NOTE_HALF[n])
        err = abs(f_meas - f_doc) / f_doc
        detail.append(
            "%s：实测半周期 %d 拍 = %.0f ns → ×%d 换算真实 %d 拍 → %.1f Hz"
            "（注释 %d Hz / half=%d，取整误差 %.2f%%）；出现 %d 次，实测拍数集合 %s"
            % (NOTE_NAME[n], PATCHED_HALF[n] + 1, (PATCHED_HALF[n] + 1) * CLK,
               PATCH_DIV, half_real, f_meas, NOTE_HZ[n], NOTE_HALF[n], 100 * err,
               len(rows), tick_sets))
        if tick_sets != [(PATCHED_HALF[n] + 1,)]:
            bad.append("%s：实测拍数集合 %s ≠ {%d}（= half+1，精确判据）"
                       % (NOTE_NAME[n], tick_sets, PATCHED_HALF[n] + 1))
        if err > FREQ_TOL:
            bad.append("%s：换算频率 %.1f Hz 与 %.1f Hz 相差 %.2f%% > 容差 %.2f%%"
                       % (NOTE_NAME[n], f_meas, f_doc, 100 * err, 100 * FREQ_TOL))
    ladder = [PATCHED_HALF[n] for n in range(8)]
    if ladder != sorted(ladder, reverse=True):
        bad.append("音高阶梯不是严格递减：%s" % ladder)
    res.append((
        "⑨ 8 个音高逐一实测：半周期拍数恰等于查表 half+1，且按 CLK_HZ 与补丁倍数"
        "换算回的真实频率 == 25e6/half（容差 %.1f%%）；G4 最低 → C6 最高，阶梯严格递减"
        % (100 * FREQ_TOL),
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑩ i_en='0' → o_buzz 恒 0：**每一个音效码**都要验，而且不许空跑 ----
    w8a, w8b = _win_bounds(8, 0)[0], _win_bounds(8, 7)[1]
    w10a, w10b = _win_bounds(10, 0)[0], _win_bounds(10, 7)[1]
    ed_en0 = _toggles(vf, w8a + GUARD, w8b - GUARD)
    ed_en0b = _toggles(vf, w10a + GUARD, w10b - GUARD)
    lv_en0 = [vf.value_at("o_buzz", t) for t in (w8a + 1000, w8a + 8000, w8b - 1000)]
    rows8 = [m for m in meas if m["win"] == 8]
    rows10 = [m for m in meas if m["win"] == 10]
    per_code = {}
    for m in rows10:
        per_code.setdefault(m["sel"], []).append(m)
    bad10 = ["码 %s 第 %d 步（该码本来该响 %s）实测 %d 次翻转"
             % (format(m["sel"], "03b"), m["step"],
                "休止" if m["exp"] is None else NOTE_NAME[m["exp"]], m["edges"])
             for m in rows10 if m["edges"] != 0]
    vac = [format(c, "03b") for c, rows in per_code.items()
           if c != 0 and all(m["exp"] is None for m in rows)]
    res.append((
        "⑩ i_en='0'（SW7 静音）时 o_buzz 恒 '0'：① 码 011 的**整整一句**"
        "（本来该响 C5 C5 E5 E5 G5）全程无翻转；② 再加一整句、**每一步换一个码**"
        "（8 个码各验一次，且每一步都是该码本来会响的步）也全程无翻转",
        not ed_en0 and not ed_en0b and all(x == "0" for x in lv_en0)
        and all(m["edges"] == 0 for m in rows8)
        and sorted(per_code) == list(range(8)) and not vac and not bad10,
        "码 011 整句 [%.0f,%.0f] 翻转 %d 次、采样点 = %s、8 步边沿数 = %s | "
        "逐码句 [%.0f,%.0f] 翻转 %d 次；逐码明细 = %s%s%s"
        % (w8a, w8b, len(ed_en0), lv_en0, [m["edges"] for m in rows8],
           w10a, w10b, len(ed_en0b),
           ", ".join("步%d→码%s(%s)" % (m["step"], format(m["sel"], "03b"),
                                        "休止" if m["exp"] is None else NOTE_NAME[m["exp"]])
                     for m in rows10),
           ("；空跑/漏码 = %s" % vac) if vac else "",
           ("；" + "；".join(bad10)) if bad10 else ""),
    ))

    # ---- ⑪ 休止步真的静音；且静音时内部 wave 仍在翻转（门在输出级，不是停振荡器）----
    rests = [m for m in meas if m["exp"] is None and m["win"] != 8]
    noisy = [m for m in rests if m["edges"] != 0]
    ed_w_en0 = _toggles(vf, w8a + GUARD, w8b - GUARD, name="wave")
    r = [m for m in rests if m["win"] == 1 and m["step"] == 5]
    ed_w_rest = _toggles(vf, r[0]["a"] + GUARD, r[0]["b"] - GUARD, name="wave") if r else []
    res.append((
        "⑪ 休止步真的静音（%d 个休止步的 o_buzz 边沿数全为 0）；而静音时内部 `wave` "
        "仍在一路翻转 —— 静音是最后一级 (i_en AND on_now) 门掉的，不是停振荡器"
        % len(rests),
        len(rests) >= 1 and not noisy and len(ed_w_en0) > 0 and len(ed_w_rest) > 0,
        "休止步数=%d，其中有声的=%s；i_en=0 段 wave 翻转 %d 次 / o_buzz %d 次；"
        "正常句里的休止步（码 001 第 5 步）wave 翻转 %d 次 / o_buzz 0 次"
        % (len(rests), [("码%s 步%d" % (format(m["win"], "03b"), m["step"]))
                        for m in noisy] or "无",
           len(ed_w_en0), len(ed_en0), len(ed_w_rest)),
    ))

    # ---- ⑫ 换码**不清零** step（旧实现的 prev 逻辑已删除）----
    t_chg = T0 + 9 * PHRASE + 3 * STEP          # 换码在它前 10 ns，步边界就在它
    step_after = vf.bus_value_at("step", t_chg + 10.0)
    rows9 = [m for m in meas if m["win"] == 9]
    bad9 = []
    for m in rows9:
        if m["exp"] is None and m["sounding"]:
            bad9.append("第 %d 步应为休止，实测有声" % m["step"])
        elif m["exp"] is not None and (not m["sounding"] or m["note"] != m["exp"]):
            bad9.append("第 %d 步应为 %s，实测 %s"
                        % (m["step"], NOTE_NAME[m["exp"]],
                           "无声" if not m["sounding"] else str(m["note"])))
    res.append((
        "⑫ 换码**不清零** step：窗口 9 前 3 步用码 001、第 3 步起换成 011，"
        "换码后 step 必须接着走（=3，不是 0），发声也按**新码的当前步**取"
        "（= E5 G5 - - -，而不是新码的步 0..4）",
        step_after == 3 and not bad9 and len(rows9) == 8,
        "换码后一拍 step = %s（期望 3；若旧实现清零则为 0）| %s | 实测（步 0..7）：%s"
        % (step_after, "；".join(bad9) if bad9 else "8 步全部符合",
           _seq_str(rows9)),
    ))

    # ---- ⑬ 方波占空比 50% ----
    m = [x for x in meas if x["win"] == 1 and x["step"] == 0][0]
    ts = _toggles(vf, m["a"] + GUARD, m["b"] - GUARD)
    t0, t1 = (ts[0], ts[-1]) if ts else (m["a"] + GUARD, m["b"] - GUARD)
    high, low = _high_low(vf, t0, t1)
    res.append((
        "⑬ 方波占空比 50%%：码 001 第 0 步（G4）稳定段 [%.0f, %.0f] ns 内"
        "高电平总时长 == 低电平总时长（容差 1 拍）" % (t0, t1),
        (high + low) > 0 and abs(high - low) <= CLK,
        "高 = %.0f ns，低 = %.0f ns，占空比 = %.1f%%"
        % (high, low, 100.0 * high / (high + low) if (high + low) else 0.0),
    ))

    # ---- ⑭ 中间信号 cnt[15:0]：每次翻转前的计数值恰为查表 half ----
    bad, detail = [], []
    for n in (0, 3, 7):
        rows = per_note.get(n, [])
        if not rows:
            bad.append("%s 没测到，无法核对 cnt" % NOTE_NAME[n])
            continue
        mm = rows[0]
        ts = _toggles(vf, mm["a"] + GUARD, mm["b"] - GUARD)
        vals = [vf.bus_value_at("cnt", t - 5.0) for t in ts]
        detail.append("%s（half=%d）：各次翻转前 cnt = %s"
                      % (NOTE_NAME[n], PATCHED_HALF[n], vals))
        if any(v != PATCHED_HALF[n] for v in vals):
            bad.append("%s：cnt 实测 %s ≠ half = %d" % (NOTE_NAME[n], vals, PATCHED_HALF[n]))
    res.append((
        "⑭ 中间信号 cnt[15:0]（16 位半周期计数器）：每次翻转前的计数值恰为查表 half"
        "（补丁后 64/48/24）—— 音调分频在波形上可直接读出来",
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑮ 旋律输出寄存一拍：(i_sel, step) 组合变了，tone_sel/on_now 仍是旧值 ----
    bad, detail = [], []
    for j in range(1, 8):
        tb = T0 + 1 * PHRASE + j * STEP          # 码 001 句内的第 j 个步边界
        old_n, new_n = MEL[1][j - 1], MEL[1][j]
        st_now = vf.bus_value_at("step", tb + 10.0)
        tone_late = vf.bus_value_at("tone_sel", tb + 10.0)
        on_late = vf.value_at("on_now", tb + 10.0)
        tone_new = vf.bus_value_at("tone_sel", tb + 30.0)
        want_late = 0 if old_n is None else old_n
        want_on = "0" if old_n is None else "1"
        want_new = 0 if new_n is None else new_n
        if (st_now != j or tone_late != want_late or on_late != want_on
                or tone_new != want_new):
            bad.append("步边界 %.0f：step=%s（期望 %d）、+10ns tone_sel=%s/on_now=%s"
                       "（期望旧值 %d/%s）、+30ns tone_sel=%s（期望新值 %d）"
                       % (tb, st_now, j, tone_late, on_late, want_late, want_on,
                          tone_new, want_new))
        detail.append("边界 %.0f：step 已=%d，而 tone_sel/on_now 仍是上一步的 %d/%s"
                      % (tb, st_now, tone_late, on_late))
    res.append((
        "⑮ 旋律输出是**寄存**的：每个步边界上 step 已经跳到新值，而 tone_sel/on_now "
        "**晚一拍**才跟上（旧值 → 新值）",
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑯ 8 个音效码全部驱动过；o_buzz 全程为确定值 ----
    used = sorted({s for steps in WINS for (s, _e) in steps})
    badlv = [(t, lv) for (t, lv) in vf.trace("o_buzz") if t > 100.0 and lv not in ("0", "1")]
    res.append((
        "⑯ 8 个音效码全部驱动过；复位后 o_buzz 全程为确定值（0/1，无 X/Z）",
        used == list(range(8)) and not badlv,
        "驱动过的 i_sel = %s；非 0/1 电平 = %s" % (used, badlv or "无"),
    ))

    return res
