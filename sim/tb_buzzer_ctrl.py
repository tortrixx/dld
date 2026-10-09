# -*- coding: utf-8 -*-
"""tb_buzzer_ctrl.py —— buzzer_ctrl v2（**升八度 + 预分频的旋律播放器**）激励与断言

【本模块现在是什么（2026-10-09 第 14 工作阶段：修"游戏过程中没有声音"）】
    `buzzer_ctrl` 是"真正的旋律播放器"，v2 相对 v1 只有三处改动：
      · 音域整体上移：**C6..C7 = 1046.5..2093 Hz**（旧版 G4..C6 = 392..1047 Hz，
        板载蜂鸣器在 392 Hz 几乎推不动 —— 这就是实机"没声音"的原因）；
      · 音效码 **3 位 → 4 位**（16 个码：静音 / 自检 / 预览 / 过关 / 拼错 / 按键 /
        通关 / 失败 / **背景音乐** / 旋转 / 确认 / 选中 / 移动 / 非法 / 时间警告 / 备用）；
      · 50 MHz 板钟先 **64 分频** → tick = 781.25 kHz，半周期 = round(390625/f) 拍，
        最大 373 → 方波计数器 **16 位 → 9 位**（旧版 68 LE，器件满到 1260/1270）。
    架构没变：一个 3 位 `step` 计数器，每个 **i_t4**（4 Hz，250 ms）脉冲走一步
    → 一句 = 8 步 × 250 ms = **2 秒**，计满回绕；每个音效码 = 8 步的常量旋律表
    MEL_*，每步 4 位（bit3 = 这一步响不响，bit2..0 = 音高索引）；
    8 个音高共用**一个**方波发生器。

【判据的独立来源（不许自证）】
    · 旋律表 MEL 抄自**模块头部注释**（= docs/02 的 A1 要求），不是从 RTL 逻辑反推；
    · 音高→频率抄自模块头部注释的音名/频率（C6 1046.5 Hz ... C7 2093 Hz）；
      再由 f = (CLK_HZ/64) / (2*half) 反推半周期常量 NOTE_HALF，并在模块加载时
      **自检 "注释里的频率" 与 "注释里的 half" 互相一致**（差 < 0.2%）。
      `CLK_HZ` 从 `rtl/puzzle_pkg.vhd`（唯一真值源）读，不写死；64 分频同理。
    · tb 只从**实测** o_buzz 的跳变间隔量半周期，再与上面两条独立来源比对。

【⚠️ 隔离工程专用的 RTL 补丁（sim.py 会自动记进轮次记录）】
    真实半周期 = (373..187 个 tick) × 64 拍 = 23936..11968 个板钟，一句要上百万个时钟。
    `RTL_PATCHES` 同时打两个补丁（**按比例压缩时间轴，比例关系不变**）：
      · `constant PRE_DIV : integer := 64;` → **2**（预分频也一起缩，否则 tick 太慢）；
      · `note_half()` 的 8 个常量**同时除以 PATCH_DIV = 5 后取整**
        → 75/67/59/56/50/44/40/37。
    于是实测的**翻转间隔拍数** = (补丁后的 half + 1) × 补丁后的 PRE_DIV，
    断言用 `(实测拍数 / PRE_PATCH - 1) * PATCH_DIV` 换算回**真实**的半周期常量。
    补丁**只作用于 `.tmp/sim_buzzer_ctrl/` 里的 RTL 副本**，仓库 `rtl/` 一个字节没动。
    【容差】取整误差最大 1.07%（B6：198/5 → 40，40*5=200），所以
      · "实测翻转间隔 == (查表 half + 1) * PRE_PATCH" —— **精确**判据，不设容差；
      · "换算回的真实频率 == (CLK_HZ/64)/(2*half)" —— 容差 **FREQ_TOL = 1.5%**。

【时间线（单位 ns，CLK 周期 20）】
    0 ~ 10010        复位（i_rst 高 1000 ns）+ 静音码 0000 的前 10000 ns
    T0 = 10010       第 0 个"乐句窗口"起点；窗口 k = [T0+k*PHRASE, T0+(k+1)*PHRASE)
    STEP  = 20000 ns （板上 250 ms 的**仿真折算**：模块只数 i_t4 脉冲，不关心真实时长）
    PHRASE = 8 * STEP = 160000 ns
    i_t4 脉冲在 T0 + m*STEP（m = 1..167）各一个时钟宽，覆盖该上升沿
      → 每个窗口里 step 恰好是 0,1,...,7（8 个脉冲自然回绕），窗口起点 step=0
    窗口 0..15    i_sel = 0000..1111，i_en = 1 —— 16 个音效码各**一整句**（判据 ②~⑤、⑭）
    窗口 16       i_sel = 0011 但 i_en = 0   —— SW7 强制静音（判据 ⑦）
    窗口 17       前 3 步 i_sel=0001、之后换成 0011 —— 换码**不清零** step（判据 ⑨）
    窗口 18~20    i_en = 0，每一步换一个音效码（窗口 18/19/20 合起来把 15 个发声码
                  各验一次，且每一步都挑该码**本来会响**的步）—— 判据 ⑦ 不空跑
    窗口 0 的静音码整句、以及全部休止步 —— 判据 ①⑧
    ⚠️ i_sel/i_en 的切换点比步边界**早 10 ns**（落在时钟下降沿、即 t≡0 (mod 20) 上），
       避开"输入与上升沿同刻变化"的竞争；i_t4 脉冲仍按 ±10 ns 包住上升沿。

【中间信号】（课件 p59 / docs/03 §3.1：波形里必须有中间信号）
    综合后网表里**真实存在**的内部寄存器（探针按名字查，缺失即报错）：
        `pre_cnt[5:0]` —— 64 分频预分频计数器（本轮新增；判据 ⑮ 由它量 tick 周期）
        `cnt[8:0]`     —— 半周期计数器（9 位，旧版 16 位）
        `wave`         —— 方波内部寄存器（一直在翻转，与 o_buzz 差一个静音门）
        `step[2:0]`    —— 旋律步计数器（每个 i_t4 走一步）
        `tone_sel[2:0]`/`on_now` —— 旋律查表结果（**寄存**一拍）
"""

import pathlib
import re

CLK = 20.0
STEP = 20000.0                 # 一个旋律步（板上 250 ms 的仿真折算）
PHRASE = 8 * STEP              # 一句 = 8 步
T0 = 10010.0                   # 第 0 个乐句窗口起点（复位已释放；与 i_t4 脉冲同相位）
N_CODE = 16                    # 16 个音效码各一整句
W_EN0_PHRASE = 16              # 整句 i_en=0
W_CHG = 17                     # 一句中途换码
W_EN0A, W_EN0B, W_EN0C = 18, 19, 20   # 逐码 i_en=0（每步一个码，都挑会响的步）
NWIN = 21
DURATION = T0 + NWIN * PHRASE + 300.0
GRID_PERIOD = 10.0

# ============================================================
# 独立真值源 1：旋律表（模块头部注释）
#   None = 这一步是休止；数字 = 音高索引（NOTE_NAME 的下标）
# ============================================================
NOTE_NAME = ["C6", "D6", "E6", "F6", "G6", "A6", "B6", "C7"]
NOTE_HZ = [1046.5, 1174.7, 1318.5, 1396.9, 1568.0, 1760.0, 1975.5, 2093.0]
MEL = {
    0:  [None, None, None, None, None, None, None, None],   # 0000 静音
    1:  [0, 2, 4, 7, None, None, None, None],               # 0001 自检（上行号角）
    2:  [1, None, 1, None, 1, None, None, None],            # 0010 预览（三声短提示）
    3:  [2, 3, 4, 5, 2, 3, 4, 5],                           # 0011 过关（短上行循环）
    4:  [5, 4, 3, 2, 5, 4, 3, 2],                           # 0100 拼错（短下行循环）
    5:  [7, 7, 7, 7, 7, 7, 7, 7],                           # 0101 按键（极短高音）
    6:  [0, 2, 4, 7, 4, 7, 7, None],                        # 0110 通关（长号角）
    7:  [7, 6, 5, 4, 3, 2, 0, None],                        # 0111 失败（下行）
    8:  [0, 2, 4, 2, 3, 5, 4, 4],                           # 1000 背景音乐（循环）
    9:  [4, 5, 6, 7, 4, 5, 6, 7],                           # 1001 旋转 90°（上扫循环）
    10: [4, 0, 4, 0, 4, 0, 4, 0],                           # 1010 确认 / 锁定（咔哒交替）
    11: [2, 2, 2, 2, 2, 2, 2, 2],                           # 1011 选中棋子（轻提示）
    12: [0, 0, 0, 0, 0, 0, 0, 0],                           # 1100 移动棋子（轻触）
    13: [1, 0, 1, 0, 1, 0, 1, 0],                           # 1101 非法走子（低沉交替）
    14: [0, 1, 0, 1, 0, 1, 0, 1],                           # 1110 时间警告（滴答交替）
    15: [1, 3, 5, 7, 7, None, None, None],                  # 1111 备用 / 第三关（上行琶音）
}

# ⚠️ 2026-10-09 第 14 工作阶段：**瞬时事件乐句不允许有休止步**。
#    理由见 rtl/buzzer_ctrl.vhd 的 step 计数器注释：game_fsm 只把这些码保持
#    2 个旋律步，而 step 是自由走的（换码不清零）→ 若事件落在休止步上，
#    玩家"按了没反应"。修法是让这 9 个码的 8 步全部发声（0 LE，只改常量），
#    而不是加 prev 寄存器把 step 清零（实测整机 +10 LE，装不下）。
#    常驻码（0001 自检 / 0010 预览 / 0110 通关 / 0111 失败 / 1000 背景 / 1111 备用）
#    会被保持好几秒、整句 2 s 循环播放，所以**允许**休止。
EVENT_CODES = [3, 4, 5, 9, 10, 11, 12, 13, 14]
MEL_LABEL = {0: "静音", 1: "自检", 2: "预览", 3: "过关", 4: "拼错", 5: "按键",
             6: "通关", 7: "失败", 8: "背景音乐", 9: "旋转90°", 10: "确认锁定",
             11: "选中棋子", 12: "移动棋子", 13: "非法走子", 14: "时间警告", 15: "备用/第三关"}


def _desc(c):
    return " ".join(NOTE_NAME[i] if i is not None else "-" for i in MEL[c])


MEL_DESC = {c: ("全休止" if c == 0 else _desc(c)) for c in MEL}

# 设计规则自检（写进 tb，免得以后改表时把"循环的背景音乐"改断）
assert all(x is not None for x in MEL[8]), \
    "背景音乐（1000）必须 8 步全部发声 —— 否则循环会出现静音裂缝"
assert all(len(MEL[c]) == 8 for c in MEL), "每个旋律必须恰好 8 步"
assert all(all(x is not None for x in MEL[c]) for c in EVENT_CODES), \
    "瞬时事件乐句（0011/0100/0101/1001/1010/1011/1100/1101/1110）必须 8 步全部发声 —— " \
    "否则事件落在休止步上就听不见（见 rtl/buzzer_ctrl.vhd 的 step 注释）"


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
#   注释里的频率与 half 必须互相自洽（f = (CLK_HZ/PRE_DIV) / (2*half)）
# ============================================================
PRE_DIV = 64                            # 与 rtl/buzzer_ctrl.vhd 的 PRE_DIV 一致
TICK_HZ = CLK_HZ / PRE_DIV              # 781_250 Hz
NOTE_HALF = [373, 333, 296, 280, 249, 222, 198, 187]
for _i, (_f, _h) in enumerate(zip(NOTE_HZ, NOTE_HALF)):
    _want = TICK_HZ / (2.0 * _f)
    assert abs(_want - _h) / _h < 0.002, \
        "模块注释自相矛盾：%s 的注释频率 %g Hz 对应 %.1f 拍，但注释写 half=%d" \
        % (NOTE_NAME[_i], _f, _want, _h)

# ============================================================
# 隔离工程专用的 RTL 补丁：预分频 64 -> 2，8 个半周期常量同时 /5 取整
# ============================================================
PATCH_PRE = 2
PATCH_DIV = 5
PATCHED_HALF = [int(round(h / PATCH_DIV)) for h in NOTE_HALF]
EXPECT_CLK = [(h + 1) * PATCH_PRE for h in PATCHED_HALF]   # 实测的翻转间隔（板钟拍数）
FREQ_TOL = 0.015                        # 1.5%（补丁取整误差实测最大 1.07%）
assert len(set(EXPECT_CLK)) == 8, "补丁后 8 个音的间隔必须两两不同，否则认不出音高"
assert max(abs(PATCHED_HALF[i] * PATCH_DIV - NOTE_HALF[i]) / NOTE_HALF[i]
           for i in range(8)) < FREQ_TOL, "补丁取整误差已超过断言容差"

# ⚠️ 锚点必须与 rtl/buzzer_ctrl.vhd **逐字一致**（sim.py 要求恰出现 1 次）。
_PRE_ANCHOR = "constant PRE_DIV : integer := 64;"
_NOTE_ARMS = ['when "000"  => v := to_unsigned(373, 9);',
              'when "001"  => v := to_unsigned(333, 9);',
              'when "010"  => v := to_unsigned(296, 9);',
              'when "011"  => v := to_unsigned(280, 9);',
              'when "100"  => v := to_unsigned(249, 9);',
              'when "101"  => v := to_unsigned(222, 9);',
              'when "110"  => v := to_unsigned(198, 9);',
              'when others => v := to_unsigned(187, 9);']
RTL_PATCHES = [("buzzer_ctrl.vhd", _PRE_ANCHOR,
                "constant PRE_DIV : integer := %d;" % PATCH_PRE)]
RTL_PATCHES += [("buzzer_ctrl.vhd", arm,
                 re.sub(r"to_unsigned\(\d+, 9\)",
                        "to_unsigned(%d, 9)" % new, arm))
                for arm, new in zip(_NOTE_ARMS, PATCHED_HALF)]

# ============================================================
# 时间线：每个窗口的 8 步 (i_sel, i_en)
# ============================================================
WINS = [[(c, 1)] * 8 for c in range(N_CODE)]     # 窗口 0..15：16 个音效码各一整句
WINS.append([(3, 0)] * 8)                        # 窗口 16：码 0011 但 i_en=0（强制静音）
WINS.append([(1, 1)] * 3 + [(3, 1)] * 5)         # 窗口 17：第 3 步中途换码 0001 -> 0011
# 窗口 18~20：i_en 仍为 0，但**每一步换一个音效码**，而且每一步都专门挑"该码本来会响"
#   的那一步（否则就是空跑：静音本来就没声）。三个窗口合起来覆盖全部 15 个发声码。
EN0_A = [5, 13, 10, 9, 15, 6, 7, 8]
EN0_B = [11, 3, 2, 4, 6, 7, 14, 8]
EN0_C = [12, 1, 2, 4, 6, 7, 14, 8]
for _row in (EN0_A, EN0_B, EN0_C):
    WINS.append([(c, 0) for c in _row])
assert len(WINS) == NWIN, (len(WINS), NWIN)
for _row in (EN0_A, EN0_B, EN0_C):
    for _j, _c in enumerate(_row):
        assert MEL[_c][_j] is not None, \
            "窗口 18~20 的码 %d 在第 %d 步本来就是休止 —— 该断言会空跑" % (_c, _j)
assert sorted({c for r in (EN0_A, EN0_B, EN0_C) for c in r}) == list(range(1, 16)), \
    "逐码静音窗口必须覆盖 0001..1111 全部 15 个发声码"


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
        # 收尾：回到"空闲"，但 i_en 也一起拉低 —— 否则最后 10 ns 里 (i_en=1 且
        # 上一步寄存的 on_now 仍为 1) 会让 o_buzz 冒出一个 10 ns 的假上升沿，
        # 被判据 ⑦（"i_en=0 全程无上升沿"）当成"静音失效"。
        out.append((t_end, 0, 0))
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


# i_t4 脉冲：t ≡ 10 (mod 20)（时钟上升沿）→ 脉冲 [t-10, t+10) 恰好只包住那一个上升沿
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
BURIED = {"pre_cnt": 6, "cnt": 9, "wave": 1, "step": 3, "tone_sel": 3, "on_now": 1}
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
    b.input_bus("i_sel", 4)
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
     20 ns 宽的门控边沿。所有"逐步"测量都缩到步窗口内部，正是为了不把这种边沿
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


def _rises(vf, a, b, name="o_buzz"):
    """(a, b) 内**由非 1 变成 1** 的时刻（"真的发声了"的判据）。

    i_en 在窗口边界掉到 0 时，o_buzz 会有一个 1→0 的下降沿（那是"停声"，不是"发声"），
    所以强制静音的判据只看**上升沿**。
    """
    tr = vf.trace(name)
    out = []
    for i in range(1, len(tr)):
        t, lv = tr[i]
        pv = tr[i - 1][1]
        if lv == "1" and pv != "1" and a + 1e-6 < t < b - 1e-6:
            out.append(t)
    return out


def _ticks(ns):
    return int(round(ns / CLK))


def _intervals(ts):
    return [round(ts[i + 1] - ts[i], 3) for i in range(len(ts) - 1)]


def _bus_trace(vf, name, width):
    """总线的 [(时刻, 值)]（与 scripts/sim.py 的 _bus_trace 同一套做法）。"""
    times = set()
    for b in range(width):
        for (t, _lv) in vf.trace("%s[%d]" % (name, b)):
            times.add(round(t, 3))
    out = []
    for t in sorted(times):
        v = vf.bus_value_at(name, t + 1e-9)
        if v is None:
            v = "X"
        if not out or out[-1][1] != v:
            out.append((t, v))
    return out


def _measure(vf):
    """逐步测量（只取每步的内部 [a+GUARD, b-GUARD]）。"""
    out = []
    for (i, j, sel, en, a, b, exp) in STEPS_EXP:
        ts = _toggles(vf, a + GUARD, b - GUARD)
        iv = _intervals(ts)
        ticks = sorted({_ticks(x) for x in iv})
        note = None
        if len(ticks) == 1 and ticks[0] in EXPECT_CLK:
            note = EXPECT_CLK.index(ticks[0])
        out.append({"win": i, "step": j, "sel": sel, "en": en, "a": a, "b": b,
                    "exp": exp, "edges": len(ts), "iv": iv, "ticks": ticks,
                    "sounding": len(ts) > 0, "note": note})
    return out


def _seq_str(rows):
    out = []
    for m in rows:
        if not m["sounding"]:
            out.append("-")
        elif m["note"] is not None:
            out.append("%s(%d拍)" % (NOTE_NAME[m["note"]], m["ticks"][0]))
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

    # ---- ① 复位期间 + 静音码 0000 的一整句 → o_buzz 恒 0 ----
    w0a, w0b = _win_bounds(0, 0)[0], _win_bounds(0, 7)[1]
    ed_rst = _toggles(vf, 0.0, 1000.0)
    ed_000 = _toggles(vf, w0a + GUARD, w0b - GUARD)
    lv_rst = [vf.value_at("o_buzz", t) for t in (200.0, 500.0, 900.0)]
    res.append((
        "① 复位期间（i_rst=1）与 i_sel=0000 静音码（idle）的一整句：o_buzz 恒 '0'"
        "（无任何翻转）",
        not ed_rst and not ed_000 and all(x == "0" for x in lv_rst),
        "复位窗口 [0,1000] 翻转 %d 次、3 个采样点 = %s；静音码整句 [%.0f,%.0f] 翻转 %d 次"
        % (len(ed_rst), lv_rst, w0a, w0b, len(ed_000)),
    ))

    # ---- ②~⑤ 16 个音效码各一整句（8 步）的"响/停 + 音高"必须等于旋律表 ----
    def _mel_group(codes):
        bad, got = [], []
        for code in codes:
            rows = [m for m in meas if m["win"] == code]
            for m in rows:
                if m["exp"] is None:
                    if m["sounding"]:
                        bad.append("码 %s 第 %d 步应为休止，实测 %d 次翻转（间隔 %s）"
                                   % (format(code, "04b"), m["step"], m["edges"], m["iv"]))
                elif not m["sounding"]:
                    bad.append("码 %s 第 %d 步应为 %s，实测**无翻转**（被当成休止）"
                               % (format(code, "04b"), m["step"], NOTE_NAME[m["exp"]]))
                elif m["note"] != m["exp"]:
                    bad.append("码 %s 第 %d 步应为 %s，实测 %s（间隔 %s）"
                               % (format(code, "04b"), m["step"], NOTE_NAME[m["exp"]],
                                  "无法识别" if m["note"] is None else NOTE_NAME[m["note"]],
                                  m["iv"]))
            got.append("码 %s「%s」%s：%s" % (format(code, "04b"), MEL_LABEL[code],
                                            MEL_DESC[code], _seq_str(rows)))
        return bad, got

    for _k, _codes in enumerate((range(1, 5), range(5, 9), range(9, 13), range(13, 16))):
        bad, got = _mel_group(_codes)
        res.append((
            "②~⑤ 码 %s..%s 各一整句 8 步的响/停与音高 == 旋律表"
            % (format(min(_codes), "04b"), format(max(_codes), "04b")),
            not bad,
            ("；".join(bad) + " | " if bad else "") + " ｜ ".join(got),
        ))

    # ---- ⑥ 8 个音高的实测间隔 == (查表 half+1)*PRE_PATCH（精确）；频率换算（1.5%）----
    per_note = {}
    for m in meas:
        if m["sounding"] and m["note"] is not None:
            per_note.setdefault(m["note"], []).append(m)
    bad, detail = [], []
    for n in range(8):
        rows = per_note.get(n, [])
        if not rows:
            bad.append("音高 %s（%g Hz）一次都没测到" % (NOTE_NAME[n], NOTE_HZ[n]))
            continue
        tick_sets = sorted({tuple(m["ticks"]) for m in rows})
        half_est = PATCHED_HALF[n] * PATCH_DIV          # 补丁常量按倍数还原
        f_meas = TICK_HZ / (2.0 * half_est)             # 由还原常量算的频率
        f_hw = CLK_HZ / (2.0 * PRE_DIV * (NOTE_HALF[n] + 1))   # 真实硬件频率（含 +1）
        f_doc = NOTE_HZ[n]
        err = abs(f_meas - f_doc) / f_doc
        err_hw = abs(f_hw - f_doc) / f_doc
        detail.append(
            "%s：查表 half=%d tick → 补丁 half=%d；实测翻转间隔 %s 拍 = (half+1)*%d（精确）"
            "；按 ×%d 还原 half=%d → %.1f Hz（注释 %g Hz，差 %.2f%%）；"
            "真实硬件 f=CLK_HZ/(2*%d*(half+1))=%.1f Hz（差 %.2f%%）；出现 %d 次"
            % (NOTE_NAME[n], NOTE_HALF[n], PATCHED_HALF[n], tick_sets, PATCH_PRE,
               PATCH_DIV, half_est, f_meas, f_doc, 100 * err,
               PRE_DIV, f_hw, 100 * err_hw, len(rows)))
        if tick_sets != [(EXPECT_CLK[n],)]:
            bad.append("%s：实测拍数集合 %s ≠ {%d}（= (half+1)*PRE_PATCH，精确判据）"
                       % (NOTE_NAME[n], tick_sets, EXPECT_CLK[n]))
        if err > FREQ_TOL:
            bad.append("%s：由查表常量换算的 %.1f Hz 与注释 %g Hz 相差 %.2f%% > 容差 %.2f%%"
                       % (NOTE_NAME[n], f_meas, f_doc, 100 * err, 100 * FREQ_TOL))
        if err_hw > FREQ_TOL:
            bad.append("%s：真实硬件频率 %.1f Hz 与注释 %g Hz 相差 %.2f%% > 容差 %.2f%%"
                       % (NOTE_NAME[n], f_hw, f_doc, 100 * err_hw, 100 * FREQ_TOL))
    ladder = [PATCHED_HALF[n] for n in range(8)]
    if ladder != sorted(ladder, reverse=True):
        bad.append("音高阶梯不是严格递减：%s" % ladder)
    res.append((
        "⑥ 8 个音高逐一实测：翻转间隔恰等于 (查表 half+1)×PRE_PATCH（精确），"
        "且按 CLK_HZ/64 与补丁倍数换算回的真实频率 == 注释频率（容差 %.1f%%）；"
        "C6 最低 → C7 最高，阶梯严格递减" % (100 * FREQ_TOL),
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑦ i_en='0' → o_buzz 恒 0：整句 + **每一个发声码**都要验，而且不许空跑 ----
    w16a, w16b = _win_bounds(W_EN0_PHRASE, 0)[0], _win_bounds(W_EN0_PHRASE, 7)[1]
    ed16 = _toggles(vf, w16a, w16b)
    ri16 = _rises(vf, w16a, w16b)
    lv16 = [vf.value_at("o_buzz", t) for t in (w16a + 1000, w16a + 60000, w16b - 1000)]
    rows16 = [m for m in meas if m["win"] == W_EN0_PHRASE]

    en0wins = (W_EN0A, W_EN0B, W_EN0C)
    per_win, bad_en0, cov = [], [], set()
    for w in en0wins:
        a, b = _win_bounds(w, 0)[0], _win_bounds(w, 7)[1]
        per_win.append((w, len(_toggles(vf, a, b)), len(_rises(vf, a, b))))
    rows_en0 = [m for m in meas if m["win"] in en0wins]
    for m in rows_en0:
        cov.add(m["sel"])
        if m["edges"] != 0:
            bad_en0.append("码 %s 第 %d 步（该码本来该响 %s）实测 %d 次翻转"
                           % (format(m["sel"], "04b"), m["step"],
                              "休止" if m["exp"] is None else NOTE_NAME[m["exp"]],
                              m["edges"]))
    vac = ["码 %s 第 %d 步本身就是休止（空跑）" % (format(m["sel"], "04b"), m["step"])
           for m in rows_en0 if m["exp"] is None]
    res.append((
        "⑦ i_en='0'（SW7 静音）时 o_buzz 恒 '0'：① 码 0011 的**整整一句**"
        "（本来该响 %s）全程无上升沿；② 再加三整句、**每一步换一个码**"
        "（%d 个发声码各验一次，且每一步都是该码本来会响的步）也全程无上升沿"
        % (MEL_DESC[3], len(cov)),
        (not ed16 and not ri16 and all(x == "0" for x in lv16)
         and all(m["edges"] == 0 for m in rows16)
         and cov == set(range(1, 16)) and not vac and not bad_en0
         and all(nr == 0 and nt == 0 for (_w, nt, nr) in per_win)),
        "码 0011 整句 [%.0f,%.0f]：翻转 %d 次、上升沿 %d 次、采样点 = %s、8 步边沿数 = %s"
        " | 逐码句 %s（窗口, 翻转, 上升沿）；覆盖的码 = %s%s%s"
        % (w16a, w16b, len(ed16), len(ri16), lv16, [m["edges"] for m in rows16],
           per_win, sorted(format(c, "04b") for c in cov),
           ("；空跑 = %s" % vac) if vac else "",
           ("；" + "；".join(bad_en0)) if bad_en0 else ""),
    ))

    # ---- ⑧ 休止步真的静音；且静音时内部 wave 仍在翻转（门在输出级，不是停振荡器）----
    rests = [m for m in meas if m["exp"] is None and 1 <= m["win"] < N_CODE]
    noisy = [m for m in rests if m["edges"] != 0]
    ed_w_en0 = _toggles(vf, w16a + GUARD, w16b - GUARD, name="wave")
    r = [m for m in rests if m["win"] == 1 and m["step"] == 4]
    ed_w_rest = _toggles(vf, r[0]["a"] + GUARD, r[0]["b"] - GUARD, name="wave") if r else []
    res.append((
        "⑧ 休止步真的静音（%d 个休止步的 o_buzz 边沿数全为 0）；而静音时内部 `wave` "
        "仍在一路翻转 —— 静音是最后一级 (i_en AND on_now) 门掉的，不是停振荡器"
        % len(rests),
        len(rests) >= 1 and not noisy and len(ed_w_en0) > 0 and len(ed_w_rest) > 0,
        "休止步数=%d，其中有声的=%s；i_en=0 段 wave 翻转 %d 次 / o_buzz %d 次；"
        "正常句里的休止步（码 0001 第 4 步）wave 翻转 %d 次 / o_buzz 0 次"
        % (len(rests), [("码%s 步%d" % (format(m["win"], "04b"), m["step"]))
                        for m in noisy] or "无",
           len(ed_w_en0), len(ed16), len(ed_w_rest)),
    ))

    # ---- ⑨ 换码**不清零** step（旧实现的 prev 逻辑已删除）----
    t_chg = T0 + W_CHG * PHRASE + 3 * STEP      # 换码在它前 10 ns，步边界就在它
    step_after = vf.bus_value_at("step", t_chg + 10.0)
    rows17 = [m for m in meas if m["win"] == W_CHG]
    bad17 = []
    for m in rows17:
        if m["exp"] is None and m["sounding"]:
            bad17.append("第 %d 步应为休止，实测有声" % m["step"])
        elif m["exp"] is not None and (not m["sounding"] or m["note"] != m["exp"]):
            bad17.append("第 %d 步应为 %s，实测 %s"
                         % (m["step"], NOTE_NAME[m["exp"]],
                            "无声" if not m["sounding"] else str(m["note"])))
    res.append((
        "⑨ 换码**不清零** step：窗口 17 前 3 步用码 0001、第 3 步起换成 0011，"
        "换码后 step 必须接着走（=3，不是 0），发声也按**新码的当前步**取"
        "（= A6 - - - -，而不是新码的步 0..4）",
        step_after == 3 and not bad17 and len(rows17) == 8,
        "换码后一拍 step = %s（期望 3；若旧实现清零则为 0）| %s | 实测（步 0..7）：%s"
        % (step_after, "；".join(bad17) if bad17 else "8 步全部符合",
           _seq_str(rows17)),
    ))

    # ---- ⑩ 方波占空比 50% ----
    m = [x for x in meas if x["win"] == 1 and x["step"] == 0][0]
    ts = _toggles(vf, m["a"] + GUARD, m["b"] - GUARD)
    t0, t1 = (ts[0], ts[-1]) if ts else (m["a"] + GUARD, m["b"] - GUARD)
    high, low = _high_low(vf, t0, t1)
    res.append((
        "⑩ 方波占空比 50%%：码 0001 第 0 步（%s）稳定段 [%.0f, %.0f] ns 内"
        "高电平总时长 == 低电平总时长（容差 1 拍）" % (NOTE_NAME[0], t0, t1),
        (high + low) > 0 and abs(high - low) <= CLK,
        "高 = %.0f ns，低 = %.0f ns，占空比 = %.1f%%"
        % (high, low, 100.0 * high / (high + low) if (high + low) else 0.0),
    ))

    # ---- ⑪ 中间信号 cnt[8:0]：每次翻转前的计数值恰为查表 half ----
    bad, detail = [], []
    for n in (0, 3, 7):
        rows = per_note.get(n, [])
        if not rows:
            bad.append("%s 没测到，无法核对 cnt" % NOTE_NAME[n])
            continue
        mm = rows[0]
        ts = _toggles(vf, mm["a"] + GUARD, mm["b"] - GUARD)
        vals = [vf.bus_value_at("cnt", t - 5.0) for t in ts]
        detail.append("%s（补丁 half=%d）：各次翻转前 cnt = %s"
                      % (NOTE_NAME[n], PATCHED_HALF[n], vals))
        if any(v != PATCHED_HALF[n] for v in vals):
            bad.append("%s：cnt 实测 %s ≠ half = %d"
                       % (NOTE_NAME[n], vals, PATCHED_HALF[n]))
    res.append((
        "⑪ 中间信号 cnt[8:0]（**9 位**半周期计数器，旧版 16 位）：每次翻转前的计数值"
        "恰为查表 half（补丁后 75/56/37）—— 音调分频在波形上可直接读出来",
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑫ 旋律输出寄存一拍：(i_sel, step) 组合变了，tone_sel/on_now 仍是旧值 ----
    bad, detail = [], []
    for j in range(1, 8):
        tb = T0 + 1 * PHRASE + j * STEP          # 码 0001 句内的第 j 个步边界
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
        "⑫ 旋律输出是**寄存**的：每个步边界上 step 已经跳到新值，而 tone_sel/on_now "
        "**晚一拍**才跟上（旧值 → 新值）",
        not bad,
        "\n".join(bad) if bad else "\n".join(detail),
    ))

    # ---- ⑬ 16 个音效码全部驱动过；o_buzz 全程为确定值 ----
    used = sorted({s for steps in WINS for (s, _e) in steps})
    badlv = [(t, lv) for (t, lv) in vf.trace("o_buzz") if t > 100.0 and lv not in ("0", "1")]
    res.append((
        "⑬ 16 个音效码（0000..1111）全部驱动过；复位后 o_buzz 全程为确定值（0/1，无 X/Z）",
        used == list(range(16)) and not badlv,
        "驱动过的 i_sel = %s；非 0/1 电平 = %s"
        % ([format(c, "04b") for c in used], badlv or "无"),
    ))

    # ---- ⑭ 任意两个码的（音高/节奏）序列互不相同 —— "不同情况听得出区别" ----
    seqs, detail, bad = {}, [], []
    for c in range(16):
        rows = [m for m in meas if m["win"] == c]
        seqs[c] = tuple(m["note"] if m["sounding"] else None for m in rows)
        detail.append("码 %s「%s」：%s" % (format(c, "04b"), MEL_LABEL[c], _seq_str(rows)))
    dups = [(a, b) for a in range(16) for b in range(a + 1, 16) if seqs[a] == seqs[b]]
    if dups:
        bad.append("实测序列相同的码对（听不出区别）：%s"
                   % ["%s=%s" % (format(a, "04b"), format(b, "04b")) for a, b in dups])
    silent = [format(c, "04b") for c in range(1, 16)
              if all(x is None for x in seqs[c])]
    if silent:
        bad.append("这些码实测**整句无声**（等于静音码）：%s" % silent)
    res.append((
        "⑭ 16 个音效码的实测（音高/节奏）序列**两两不同**（%d 对全部比对过），"
        "且 0001..1111 没有一个是整句无声 —— 不同情况耳听可辨"
        % (16 * 15 // 2),
        not bad,
        "；".join(bad) if bad else " ｜ ".join(detail),
    ))

    # ---- ⑮ 预分频器：pre_cnt 回绕周期 == PRE_PATCH 拍（tick = 781.25 kHz）----
    a15, b15 = T0, T0 + 2 * PHRASE
    tr = _bus_trace(vf, "pre_cnt", BURIED["pre_cnt"])
    wraps = [tr[k][0] for k in range(1, len(tr))
             if a15 < tr[k][0] < b15 and tr[k][1] == 0 and tr[k - 1][1] not in (0, "X")]
    sp = sorted({round(wraps[k + 1] - wraps[k], 3) for k in range(len(wraps) - 1)})
    tick_sim_hz = (1e9 / sp[0]) if len(sp) == 1 else 0.0
    tick_real_hz = tick_sim_hz * PATCH_PRE / PRE_DIV
    res.append((
        "⑮ 预分频器真的在分频：中间信号 `pre_cnt[5:0]` 的回绕周期恒为 PRE_PATCH=%d 拍"
        "（%g ns），即补丁后 tick = %g MHz；按补丁比例 64→%d 换算回真实 tick = %.2f kHz"
        "（说明：%.1f kHz）"
        % (PATCH_PRE, PATCH_PRE * CLK, tick_sim_hz / 1e6, PATCH_PRE,
           tick_real_hz / 1e3, TICK_HZ / 1e3),
        len(wraps) > 100 and sp == [PATCH_PRE * CLK]
        and abs(tick_real_hz - TICK_HZ) / TICK_HZ < 1e-9,
        "窗口 [%.0f,%.0f] ns 内 pre_cnt 回绕 %d 次，相邻回绕间隔集合 = %s ns"
        "（期望 {%g}）；tick_sim=%g MHz → tick_real=%.4f kHz，注释 = %.4f kHz"
        % (a15, b15, len(wraps), sp, PATCH_PRE * CLK, tick_sim_hz / 1e6,
           tick_real_hz / 1e3, TICK_HZ / 1e3),
    ))

    # ---- ⑯ 一个 i_t4 脉冲恰走一步（mod 8 +1），步内不变 ----
    bad, n_ok = [], 0
    for m in range(1, NWIN * 8):
        t = T0 + m * STEP
        before = vf.bus_value_at("step", t - 5.0)
        after = vf.bus_value_at("step", t + 5.0)
        if before is None or after is None or (after - before) % 8 != 1:
            bad.append("脉冲 %d @ %.0f ns：step %s -> %s（期望 +1 mod 8）"
                       % (m, t, before, after))
        else:
            n_ok += 1
    for (i, j, sel, en, a, b, exp) in STEPS_EXP:
        v1 = vf.bus_value_at("step", a + 1000.0)
        v2 = vf.bus_value_at("step", b - 1000.0)
        if v1 != j or v2 != j:
            bad.append("窗口 %d 步 %d：步内 step 实测 %s / %s ≠ %d（步内不该变）"
                       % (i, j, v1, v2, j))
    res.append((
        "⑯ 每来一个 i_t4 脉冲 step 恰 +1（mod 8，7→0 回绕），步内保持不变；"
        "%d 个脉冲 + %d 个步窗口全部核对" % (NWIN * 8 - 1, len(STEPS_EXP)),
        not bad and n_ok == NWIN * 8 - 1,
        "；".join(bad) if bad else
        "%d/%d 个脉冲都是 +1；%d 个步窗口内 step 采样两次都等于步号"
        % (n_ok, NWIN * 8 - 1, len(STEPS_EXP)),
    ))

    return res
