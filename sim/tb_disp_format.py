# -*- coding: utf-8 -*-
"""tb_disp_format.py —— disp_format 功能仿真激励与断言

【本模块是什么】
    `disp_format` 把「状态 + 关卡 + 倒计时 + 闪烁标志」翻译成 8 位数码管的
    BCD 内容（`o_data`，每 4 位一个 DIG，bits 31..28 = DISP7 = 最左位）与
    熄灭掩码（`o_blank`，'1' = 该位熄灭）。**纯组合**，没有时钟、没有寄存器。

    课程要求对应：B1 自检全 8；B2 待机 DISP7='5' / DISP0=关卡号；
    B4 预览 DISP7 倒数；B5 游戏中 DISP4:DISP3 = 剩余秒数；B3 关卡号只由 DISP0 显示。

    ⚠️ **口径 C（2026-10-12 用户裁决）**：题目要求 9（B9）"进入第二关，数码管
    DISP2 显示 2" 与要求 3（B3）"游戏关数由数码管 DISP0 显示" 冲突，用户裁定
    B9 为笔误、取 B3 —— **DISP2 全程熄灭**，第二关的关卡号只走 DISP0。
    本 tb 断言 ⑥c 就是这条口径的全局钉子（除 B1 自检态外，每个窗口 DISP2 必须灭）。

【判据的独立来源（不许自证）】
    · 状态编码 / 关卡数 / 各状态该显示什么：来自课程要求 B1/B2/B3/B4/B5 的**文字描述**
      与 `rtl/puzzle_pkg.vhd`（唯一真值源）里的 `S_*` 常量。tb 直接**读** pkg 取常量，
      不在 tb 里抄 "001"/"010" 这类字面量。
    · 倒计时的两位拆分：tb 用 `t // 10` 与 `t % 10` **独立算**，
      再把 16 个"进位边界"值（0/9/10/19/20/29/30/39/40/49/50/59/60/63 + 1/11）
      逐点比对。
      ⚠️ **覆盖范围（2026-10-15 起已补全，如实说明）**：本注释早先写"RTL 里那张
      64 项 case 表只要错一项就会挂"，那是夸大的 —— 当时真正进到那张 case 表的 `t`
      只有 **17 个**（LUT_T 的 16 个进位边界 + 对局常规值 27），40 条显式臂
      （`when 0` .. `when 39`）里**还有 29 条从未被激励**（2~8 / 12~18 / 21~26 /
      28 / 31~38），`when others` 的三段（40~49 / 50~59 / 60~63）也只有端点被覆盖。
      **现在把 t = 0..63 全部 64 个取值都激励到**（新增 47 个窗口），由断言 ⑦b
      逐项验收：期望值①**逐条抄自 `rtl/disp_format.vhd` 的 case 表**（硬写在
      `LIT_TENS_ONES` 里，表被改动而这里没跟着改就会挂）、②再用**独立算出的
      `t//10`、`t%10`** 交叉核对（这条与 RTL 的查表实现无关，能抓出"抄错/表本身写错"）。
    · 熄灭掩码：由"哪些位应该亮"**推导**（例如待机只有 DISP7/DISP0 亮 → 0x7E），
      不是从 RTL 抄。

【中间信号】（课件 p59 / docs/03 §3.1：波形里必须有中间信号）
    `disp_format` 是纯组合模块，VHDL 里的 `d`/`bl`/`tens`/`ones` 是进程变量，
    综合后网表里**没有**叫这些名字的节点。真实存在的内部节点名从仿真报告的
    覆盖率表里读出（报告里列的是网表节点名，形如 `|disp_format|tens~0`）：
        `tens~1:tens~0`  —— 倒计时那张 64 项 case 表里 **`others` 分支的两位段译码**
                            （实测取值：40≤t<50 → 00、50≤t<60 → 10、其余 → 01）
        `ones~3:ones~0`  —— 个位译码网络的中间项
    ⚠️ 本注释早先把它们写成"十位/个位的组合译码结果，正是 DISP4/DISP3 的数据来源"，
    **与实测不符**（也与本文件下面「节点声明」一节自相矛盾）：实测的数据线是
    `LessThan2~2`（== o_data[18]，即 DISP4 的 bit2）与 `r~9`（== o_data[13]，
    即 DISP3 的 bit1）—— 见下面 115-128 行的说明与断言 ⑪。断言 ⑫ 只检查这两个
    case 表中间项"取值确定、且随 i_state/i_time 变化"，**不是**反推显示内容的依据。

【时间线】（单位 ns，每段 100 ns，采样点 = 段中点；DURATION = 100 × 窗口数）
    0~100      S_SELF_TEST  blink=0
    100~200    S_SELF_TEST  blink=1
    200~300    S_IDLE       level=1（第一关）
    300~400    S_IDLE       level=2（第二关）
    400~500    S_PREVIEW    t=4  level=1
    500~600    S_PREVIEW    t=5  level=2
    600~700    S_PLAYING    t=27 level=1
    700~800    S_PLAYING    t=27 level=2（口径 C：DISP2 必须灭，与第一关同形）
    800~2400   S_PLAYING    level=1，t 依次取 16 个进位边界值（LUT_T，断言 ⑦）
    2400~7100  S_PLAYING    level=1，t 依次取**其余 47 个取值**（T*，断言 ⑦b）
                            —— 与 LUT_T + {27} 合起来即 t = 0..63 全覆盖
    7100~7200  S_WIN
    7200~7300  S_FAIL
    7300~7400  S="110"（未定义态）
    7400~7500  S="111"（未定义态）
    7500~7600  S_IDLE       level=3（lvl3=1）—— D2 第三关
    7600~7700  S_PREVIEW    t=4  level=3（lvl3=1）
    7700~7800  S_PLAYING    t=27 level=3（lvl3=1）
"""

import pathlib
import re

GRID_PERIOD = 10.0
WIN = 100.0


# ============================================================
# 从 puzzle_pkg 读状态编码（唯一真值源）
# ============================================================
def _pkg_states():
    p = pathlib.Path(__file__).resolve().parent.parent / "rtl" / "puzzle_pkg.vhd"
    txt = p.read_text(encoding="utf-8", errors="replace")
    out = {}
    for name in ("S_SELF_TEST", "S_IDLE", "S_PREVIEW", "S_PLAYING", "S_WIN", "S_FAIL"):
        m = re.search(r'constant\s+%s\s*:\s*state_t\s*:=\s*"([01]{3})"' % name, txt)
        if not m:
            raise RuntimeError("puzzle_pkg 里找不到 %s" % name)
        out[name] = int(m.group(1), 2)
    return out


S = _pkg_states()

# 倒计时进位边界：0/9/10/19/20/29/30/39/40/49/50/59/60/63 + 两个常规值
LUT_T = [0, 1, 9, 10, 11, 19, 20, 29, 30, 39, 40, 49, 50, 59, 60, 63]

# ============================================================================
# ⭐ 2026-10-15：倒计时 case 表的**逐项硬编码期望表**
#
#   来源：**逐条抄自 `rtl/disp_format.vhd:153-192` 的 40 条显式臂
#   （`when 0` .. `when 39`）与 `:193-200` 的 `when others` 三段
#   （40≤t<50 → tens=4 / 50≤t<60 → tens=5 / 60≤t≤63 → tens=6）**，
#   键 = `t`，值 = `(DISP4 的 BCD, DISP3 的 BCD)` = (十位, 个位)。
#
#   ⚠️ 为什么硬写一张表而不是用 `t // 10`、`t % 10` 现算：那样等于把 RTL
#      用查表实现的同一条**公式**在 tb 里再写一遍（同义反复），RTL 的表里
#      某一臂被改错时判据不会响。硬编码表是**变更探测器**：RTL 的 case 表
#      改了而这里没跟着改，断言 ⑦b 立刻失败。
#   ⚠️ 反过来，硬编码表也可能"把 RTL 的错抄成期望值"——所以断言 ⑦b **同时**
#      用独立算出的 `t//10`、`t%10` 交叉核对（那条与 RTL 的查表实现无关）。
# ============================================================================
LIT_TENS_ONES = {
    0: (0, 0), 1: (0, 1), 2: (0, 2), 3: (0, 3), 4: (0, 4),
    5: (0, 5), 6: (0, 6), 7: (0, 7), 8: (0, 8), 9: (0, 9),
    10: (1, 0), 11: (1, 1), 12: (1, 2), 13: (1, 3), 14: (1, 4),
    15: (1, 5), 16: (1, 6), 17: (1, 7), 18: (1, 8), 19: (1, 9),
    20: (2, 0), 21: (2, 1), 22: (2, 2), 23: (2, 3), 24: (2, 4),
    25: (2, 5), 26: (2, 6), 27: (2, 7), 28: (2, 8), 29: (2, 9),
    30: (3, 0), 31: (3, 1), 32: (3, 2), 33: (3, 3), 34: (3, 4),
    35: (3, 5), 36: (3, 6), 37: (3, 7), 38: (3, 8), 39: (3, 9),
    # ---- when others（40..63）----
    40: (4, 0), 41: (4, 1), 42: (4, 2), 43: (4, 3), 44: (4, 4),
    45: (4, 5), 46: (4, 6), 47: (4, 7), 48: (4, 8), 49: (4, 9),
    50: (5, 0), 51: (5, 1), 52: (5, 2), 53: (5, 3), 54: (5, 4),
    55: (5, 5), 56: (5, 6), 57: (5, 7), 58: (5, 8), 59: (5, 9),
    60: (6, 0), 61: (6, 1), 62: (6, 2), 63: (6, 3),
}

# 除 LUT_T（16 个边界值）与 27（PLAY27a 已经覆盖）之外**其余全部取值**：
# 这些正是原来"从未被激励"的那 47 个 t（其中 29 个落在 40 条显式臂里）。
SWEEP_T = [t for t in range(64) if t not in LUT_T and t != 27]

# 时间线：(状态, 关卡(0/1), 第三关标志 lvl3(0/1), 倒计时, blink, 时长)
STIM = [
    (S["S_SELF_TEST"], 0, 0, 30, 0, WIN),
    (S["S_SELF_TEST"], 0, 0, 30, 1, WIN),
    (S["S_IDLE"],      0, 0, 30, 0, WIN),   # IDLE1：待机 · 第一关
    (S["S_IDLE"],      1, 0, 30, 0, WIN),   # IDLE2：待机 · 第二关
    (S["S_PREVIEW"],   0, 0, 4,  0, WIN),   # PREV4：预览 · 第一关（DISP7 倒数到 4）
    (S["S_PREVIEW"],   1, 0, 5,  0, WIN),   # PREV5：预览 · 第二关
    (S["S_PLAYING"],   0, 0, 27, 0, WIN),   # PLAY27a：第一关对局 → DISP2 必须灭
    (S["S_PLAYING"],   1, 0, 27, 0, WIN),   # PLAY27b：第二关对局 → 口径 C：DISP2 必须灭（B9 已于 2026-10-12 作废）
] + [(S["S_PLAYING"], 0, 0, t, 0, WIN) for t in LUT_T] + [
    # ⭐ 2026-10-15：t = 0..63 里剩下的全部取值（47 个窗口）—— 把倒计时 case 表
    #    的每一条臂都激励到（原来 40 条显式臂里有 29 条从未进过）。
    (S["S_PLAYING"], 0, 0, t, 0, WIN) for t in SWEEP_T
] + [
    (S["S_WIN"],       0, 0, 30, 0, WIN),   # 4 = S_WIN
    (S["S_FAIL"],      0, 0, 30, 0, WIN),   # 5 = S_FAIL
    (6,                0, 0, 30, 0, WIN),   # 未定义状态码
    (7,                0, 0, 30, 0, WIN),
    # ---- D2（2026-10-09 第 12 工作阶段）：**第三关**（A2"增加游戏关数"）--------
    (S["S_IDLE"],      1, 1, 30, 0, WIN),   # IDLE3：待机 · 第三关 → DISP0='3'
    (S["S_PREVIEW"],   1, 1, 4,  0, WIN),   # PREV3：预览 · 第三关（DISP7 倒数到 4）
    (S["S_PLAYING"],   1, 1, 27, 0, WIN),   # PLAY27c：第三关对局 → DISP0='3'、DISP2 **灭**
]

# DURATION 由 STIM 推出（每窗口 WIN ns），不要在文件头写死 —— 加窗口时忘改会静默截断
DURATION = WIN * len(STIM)

# 每个窗口的中点（采样时刻）与窗口索引
T_OF = [WIN * (i + 0.5) for i in range(len(STIM))]
IDX = {name: i for i, name in enumerate(
    ["SELF0", "SELF1", "IDLE1", "IDLE2", "PREV4", "PREV5", "PLAY27a", "PLAY27b"]
    + ["LUT%d" % t for t in LUT_T] + ["T%d" % t for t in SWEEP_T]
    + ["WIN", "FAIL", "UNDEF6", "UNDEF7", "IDLE3", "PREV3", "PLAY27c"])}

# ============================================================
# 节点声明
# ============================================================
# 中间信号：网表里**真实存在**的节点名。
#   综合后网表里没有 `d`/`bl`/`tens`/`ones` 这些变量名，真名要去仿真报告的覆盖率
#   表里读（报告里列的是 `|disp_format|xxx` 形式的网表节点名）。本 tb 收录：
#     tens~1:tens~0  —— 倒计时那张 64 项 case 表里 `others` 分支的两位段译码
#                       （实测取值：40≤t<50 → 00，50≤t<60 → 10，其余 → 01）
#     ones~3:ones~0  —— 个位译码网络的中间项
#     LessThan2~2    —— 实测 == o_data 的 bit18（DISP4 的 bit2），即"十位"数据线
#     r~9            —— 实测 == o_data 的 bit13（DISP3 的 bit1），即"个位"数据线
#   （这些对应关系不是猜的：tb 用一次探针跑把每个候选中间节点的 28 点波形与
#     o_data/o_blank 的每一位逐点相关，唯一命中的就是这两条 —— 见断言 ⑪。）
TENS_BITS = ["tens~0", "tens~1"]
ONES_BITS = ["ones~0", "ones~1", "ones~2", "ones~3"]
DATA_TENS_BIT = "LessThan2~2"      # == o_data[18] (DISP4 的 bit2)
DATA_ONES_BIT = "r~9"              # == o_data[13] (DISP3 的 bit1)

OBSERVE = (["i_state", "i_level", "i_lvl3", "i_time", "i_blink", "o_data", "o_blank"]
           + TENS_BITS + ONES_BITS + [DATA_TENS_BIT, DATA_ONES_BIT])


def _buried(b, name):
    sig = b.vf.signals.get(name)
    if sig is not None:
        sig.direction = "BURIED"


def build(b):
    b.input_bus("i_state", 3)
    b.input_bit("i_level")
    b.input_bit("i_lvl3")
    b.input_bus("i_time", 6)
    b.input_bit("i_blink")
    b.output_bus("o_data", 32)
    b.output_bus("o_blank", 8)
    for n in TENS_BITS + ONES_BITS + [DATA_TENS_BIT, DATA_ONES_BIT]:
        b.output_bit(n)
        _buried(b, n)

    b.bus_segments("i_state", [(d, s) for (s, _l, _l3, _t, _k, d) in STIM])
    b.segments("i_level", [(d, l) for (_s, l, _l3, _t, _k, d) in STIM])
    b.segments("i_lvl3", [(d, l3) for (_s, _l, l3, _t, _k, d) in STIM])
    b.bus_segments("i_time", [(d, t) for (_s, _l, _l3, t, _k, d) in STIM])
    b.segments("i_blink", [(d, k) for (_s, _l, _l3, _t, k, d) in STIM])


# ============================================================
# 辅助
# ============================================================
def _hex(v, width):
    return "X" if v is None else ("0x%0*X" % (width, v))


def disp(o_data, k):
    """第 k 位数码管（0 = 最右 DISP0，7 = 最左 DISP7）的 BCD 值。"""
    if o_data is None:
        return None
    return (o_data >> (4 * k)) & 0xF


def _render(vf, t):
    d = vf.bus_value_at("o_data", t)
    bl = vf.bus_value_at("o_blank", t)
    return d, bl


# ============================================================
# 断言
# ============================================================
def check(vf):
    res = []

    # ---- 激励自检：每个窗口中点读到的 i_state 必须等于该窗口期望的状态 ----
    bad = [(IDX[n], STIM[i][0], vf.bus_value_at("i_state", T_OF[i]))
           for n, i in IDX.items() if vf.bus_value_at("i_state", T_OF[i]) != STIM[i][0]]
    res.append((
        "⓪ 激励自检：16+ 个采样窗口的 i_state 实测值 == 期望值（防止`测错了对象`）",
        not bad,
        "全部一致（%d 个窗口）" % len(STIM) if not bad else "不一致：%s" % bad,
    ))

    # ---- ① 自检态 · blink=0：全 8 的 BCD 在，但整排熄灭 ----
    d, bl = _render(vf, T_OF[IDX["SELF0"]])
    res.append((
        "① B1 自检态 + i_blink='0' → o_data 八位全 '8'(0x88888888)，o_blank=0xFF（整排灭）",
        d == 0x88888888 and bl == 0xFF,
        "o_data=%s  o_blank=%s" % (_hex(d, 8), _hex(bl, 2)),
    ))

    # ---- ② 自检态 · blink=1：全 8 且全亮 ----
    d, bl = _render(vf, T_OF[IDX["SELF1"]])
    res.append((
        "② B1 自检态 + i_blink='1' → o_data 八位全 '8'，o_blank=0x00（整排亮）"
        "—— 与 ① 合起来即 2 Hz 闪烁（半周期亮/半周期灭）",
        d == 0x88888888 and bl == 0x00,
        "o_data=%s  o_blank=%s" % (_hex(d, 8), _hex(bl, 2)),
    ))

    # ---- ③ B2 待机：DISP7='5'、DISP0=关卡号、其余全灭 ----
    #      D2 之后有三个待机画面：第一关（DISP0=1）、第二关（2）、第三关（3）
    rows = []
    bad = []
    for key, want_lv in (("IDLE1", 1), ("IDLE2", 2), ("IDLE3", 3)):
        d, bl = _render(vf, T_OF[IDX[key]])
        ok = (disp(d, 7) == 5 and bl is not None and (bl >> 7) & 1 == 0
              and disp(d, 0) == want_lv and bl & 1 == 0
              and (bl & 0x7E) == 0x7E)
        rows.append("%s: o_data=%s o_blank=%s（DISP7=%s DISP0=%s）"
                    % (key, _hex(d, 8), _hex(bl, 2), disp(d, 7), disp(d, 0)))
        if not ok:
            bad.append(key)
    res.append((
        "③ B2/B3 待机态 → DISP7='5'、DISP0=关卡号(1 / 2 / 3)，DISP1~6 全灭（o_blank=0x7E）",
        not bad,
        "\n".join(rows),
    ))

    # ---- ④ B4 预览：DISP7 = 预览倒数，DISP0 = 关卡号 ----
    rows = []
    bad = []
    for key, want_lv, want in (("PREV4", 1, 4), ("PREV5", 2, 5), ("PREV3", 3, 4)):
        d, bl = _render(vf, T_OF[IDX[key]])
        ok = (disp(d, 7) == want and (bl >> 7) & 1 == 0
              and disp(d, 0) == want_lv and bl & 1 == 0 and (bl & 0x7E) == 0x7E)
        rows.append("%s: DISP7=%s（期望 %d） DISP0=%s o_blank=%s"
                    % (key, disp(d, 7), want, disp(d, 0), _hex(bl, 2)))
        if not ok:
            bad.append(key)
    res.append((
        "④ B4 预览态 → DISP7 = 倒计时秒数(单数字)，DISP0 = 关卡号(1/2/3)，其余灭",
        not bad,
        "\n".join(rows),
    ))

    # ---- ⑤ B5 游戏中：DISP4:DISP3 = 剩余秒数，DISP0 = 关卡号 ----
    d, bl = _render(vf, T_OF[IDX["PLAY27a"]])
    ok = (disp(d, 4) == 2 and disp(d, 3) == 7 and disp(d, 0) == 1
          and (bl >> 4) & 1 == 0 and (bl >> 3) & 1 == 0 and bl & 1 == 0
          and (bl >> 2) & 1 == 1)
    res.append((
        "⑤ B5 游戏中(第一关, t=27) → DISP4=2 DISP3=7（两位都亮）、DISP0=1，DISP2 灭"
        "（o_blank=0xE6）",
        ok,
        "o_data=%s o_blank=%s" % (_hex(d, 8), _hex(bl, 2)),
    ))

    # ---- ⑥ 口径 C（2026-10-12 用户裁决）：第二关对局时 DISP2 **必须灭** ----
    #     历史：2026-10-09 ~ 10-12 这里曾断言 DISP2 额外显示 '2'（严格照 B9 字面），
    #     用户 2026-10-12 裁定 B9（"进入第二关 DISP2 显示 2"）与 B3（"关数由
    #     DISP0 显示"）冲突、B9 属笔误，于是改成与第一关完全同形（o_blank=0xE6）。
    d, bl = _render(vf, T_OF[IDX["PLAY27b"]])
    ok = (disp(d, 4) == 2 and disp(d, 3) == 7 and disp(d, 0) == 2 and bl == 0xE6)
    res.append((
        "⑥ 口径 C 游戏中(第二关, t=27) → DISP4:DISP3=27、DISP0=关卡号 2、"
        "**DISP2 熄灭**（o_blank=0xE6，与第一关同形；B9 已按用户裁决作废）",
        ok,
        "o_data=%s o_blank=%s（DISP2=%s，bit2 掩码=%d 应为 1=灭）"
        % (_hex(d, 8), _hex(bl, 2), disp(d, 2), (bl >> 2) & 1),
    ))

    # ---- ⑥b 第三关游戏中：DISP0='3'，DISP2 同样熄灭 ----
    d, bl = _render(vf, T_OF[IDX["PLAY27c"]])
    ok = (disp(d, 4) == 2 and disp(d, 3) == 7 and disp(d, 0) == 3 and bl == 0xE6)
    res.append((
        "⑥b 游戏中(第三关, t=27) → DISP4:DISP3=27、DISP0=关卡号 3、**DISP2 熄灭**"
        "（o_blank=0xE6，与第一关同形）",
        ok,
        "o_data=%s o_blank=%s（DISP2=%s，bit2 掩码=%d 应为 1=灭）"
        % (_hex(d, 8), _hex(bl, 2), disp(d, 2), (bl >> 2) & 1),
    ))

    # ---- ⑥c ⭐ 口径 C 的**全局钉子**：除 B1 自检态（明文要求八位全显 '8'）外，
    #      每一个采样窗口的 DISP2 都必须熄灭。这一条把"只在第二关对局期不亮"
    #      升级成"任何状态、任何关卡都不亮"，防止将来某次改动把它又带回来。----
    bad = []
    for name, i in sorted(IDX.items(), key=lambda kv: kv[1]):
        if name.startswith("SELF"):
            continue
        _d, bl = _render(vf, T_OF[i])
        if bl is None or ((bl >> 2) & 1) != 1:
            bad.append("%s(o_blank=%s)" % (name, _hex(bl, 2)))
    res.append((
        "⑥c ⭐ 口径 C 全局：除自检态外，全部 %d 个窗口的 DISP2 恒为**熄灭**"
        "（o_blank bit2 == 1；自检态豁免 —— B1 明文要求八位全显 '8'）"
        % (len(IDX) - 2),
        not bad,
        "全部熄灭（%d 个窗口）" % (len(IDX) - 2) if not bad
        else "以下窗口 DISP2 未熄灭：%s" % bad,
    ))

    # ---- ⑦ 倒计时 64 项查表的进位边界逐项验收（独立算 t//10、t%10）----
    bad = []
    rows = []
    for t in LUT_T:
        d, bl = _render(vf, T_OF[IDX["LUT%d" % t]])
        got = (disp(d, 4), disp(d, 3))
        if got != (t // 10, t % 10):
            bad.append("t=%d 实测 DISP4:DISP3 = %s 期望 %s" % (t, got, (t // 10, t % 10)))
        if bl != 0xE6:
            bad.append("t=%d o_blank=%s ≠ 0xE6" % (t, _hex(bl, 2)))
        rows.append("t=%2d→%s%s" % (t, disp(d, 4), disp(d, 3)))
    res.append((
        "⑦ B5 倒计时十位/个位拆分（那张 64 项 case 表）：16 个进位边界值全部等于"
        " 独立算出的 t//10 与 t%10（0/9/10/19/20/29/30/39/40/49/50/59/60/63）"
        "—— 全表 64 个取值的逐项验收见 ⑦b",
        not bad,
        "\n".join(bad) if bad else " ".join(rows),
    ))

    # ---- ⑦b ⭐ 倒计时 case 表**逐项**验收（2026-10-15 补）----
    #     ⚠️ 原来只激励了 17 个 t（⑦ 的 16 个进位边界 + 27），40 条显式臂里
    #        29 条从未进过 → "表逐项全对"没有被证明（本文件头早先那句话是夸大的）。
    #     现在 t = 0..63 全部激励到，期望值**双轨**：
    #       · LIT_TENS_ONES —— 逐条抄自 RTL case 表的硬编码表（变更探测器）；
    #       · (t // 10, t % 10) —— 与 RTL 查表实现无关的独立算术模型。
    #     两条都必须成立；任一条不成立即失败。
    bad, rows, n_cov = [], [], 0
    for t in range(64):
        key = ("LUT%d" % t) if ("LUT%d" % t) in IDX else \
            ("PLAY27a" if t == 27 else "T%d" % t)
        d, bl = _render(vf, T_OF[IDX[key]])
        n_cov += 1
        got = (disp(d, 4), disp(d, 3))
        if got != LIT_TENS_ONES[t]:
            bad.append("t=%2d 实测 DISP4:DISP3 = %s 应 = %s（逐条抄自 RTL case 表）"
                       % (t, got, LIT_TENS_ONES[t]))
        if got != (t // 10, t % 10):
            bad.append("t=%2d 实测 DISP4:DISP3 = %s 应 = %s（独立算 t//10, t%%10）"
                       % (t, got, (t // 10, t % 10)))
        if bl != 0xE6:
            bad.append("t=%2d o_blank=%s ≠ 0xE6" % (t, _hex(bl, 2)))
        rows.append("%d→%d%d" % (t, got[0], got[1]))
    res.append((
        "⑦b ⭐ 倒计时 case 表**逐项**验收：t = 0..63 全部 %d 个取值（40 条显式臂 "
        "`when 0`..`when 39` + `when others` 的 40~49/50~59/60~63 三段）都等于"
        "**逐条抄自 rtl/disp_format.vhd case 表的硬编码期望**，且同时等于独立算出的"
        "t//10、t%%10；o_blank 全部 = 0xE6（原来只有 17 个 t 被激励、29 条臂从未进过）"
        % n_cov,
        (not bad) and n_cov == 64,
        "\n".join(bad[:8]) if bad else
        "64 个取值全部一致（硬编码表 + 独立算术模型）：" + " ".join(rows),
    ))

    # ---- ⑧ 胜负态：结算信息用数码管拼字（2026-10-08 由 "75"/"00" 改成 PASS/FAIL）----
    #    字位码 = puzzle_pkg.DIG_*：P=0xB A=0xA S=0xC / F=0xD A=0xA I=0x1 L=0xE
    dw, bw = _render(vf, T_OF[IDX["WIN"]])
    df, bf = _render(vf, T_OF[IDX["FAIL"]])
    ok = ([disp(dw, k) for k in (7, 6, 5, 4)] == [0xB, 0xA, 0xC, 0xC] and bw == 0x0F
          and [disp(df, k) for k in (7, 6, 5, 4)] == [0xD, 0xA, 0x1, 0xE] and bf == 0x0F
          and dw != df)
    res.append((
        "⑧ S_WIN → DISP7..DISP4 = \"PASS\"（P A S S）；S_FAIL → \"FAIL\"（F A I L）；"
        "两者都只亮这四位、画面互不相同（段形由 tb_seg_scan 断言 ③⑪ 校验；"
        "7 段管里 S 与 5 同形、I 用 1 的形状 → 板上像 PA55 / FA1L）",
        ok,
        "WIN: o_data=%s o_blank=%s | FAIL: o_data=%s o_blank=%s"
        % (_hex(dw, 8), _hex(bw, 2), _hex(df, 8), _hex(bf, 2)),
    ))

    # ---- ⑨ 未定义状态码（"110"/"111"）→ 确定行为：整排灭 ----
    du, bu = _render(vf, T_OF[IDX["UNDEF6"]])
    dv, bv = _render(vf, T_OF[IDX["UNDEF7"]])
    res.append((
        "⑨ 状态码 「110」/「111」（state_t 未定义值）→ 确定行为：o_blank 全 1（整排灭），"
        "不会误显示上一状态的内容",
        bu == 0xFF and bv == 0xFF,
        "110: o_blank=%s | 111: o_blank=%s" % (_hex(bu, 2), _hex(bv, 2)),
    ))

    # ---- ⑩ 各状态的 (o_data, o_blank) 组合互不相同（画面可区分）----
    #    允许的两处"重合"是有语义原因的，不算缺陷：
    #      · IDLE2 与 PREV5 都是 "5 ....2"：B2 规定待机画面就是 DISP7='5'，
    #        而 B4 的预览从 5 秒开始倒数 —— 第一个预览窗口与待机画面**本来就该一样**；
    #      · UNDEF6 与 UNDEF7 都是全灭：两个未定义状态码走同一个 `others` 分支。
    seen = {}
    for name, i in IDX.items():
        key = _render(vf, T_OF[i])
        seen.setdefault(key, []).append(name)
    ALLOWED = [frozenset(("IDLE2", "PREV5")), frozenset(("UNDEF6", "UNDEF7"))]
    dup = {k: v for k, v in seen.items() if len(v) > 1 and frozenset(v) not in ALLOWED}
    res.append((
        "⑩ %d 个窗口的画面 (o_data,o_blank) 互不相同 —— 仅允许两处有语义的重合："
        "待机(第二关) vs 预览 5 秒（B2 的 '5' 与 B4 的起始值本来就是同一个画面）、"
        "两个未定义状态码同为全灭" % len(IDX),
        not dup,
        "意料之外的重复画面：%s" % dup if dup else
        "%d 个窗口 → %d 种不同画面；重合的两组：%s"
        % (len(IDX), len(seen), [sorted(x) for x in ALLOWED]),
    ))

    # ---- ⑪ ⭐ 中间信号"解释"端口：DISP4/DISP3 的数据线就是这两个内部节点 ----
    bad = []
    for t in LUT_T + [27]:
        i = IDX["LUT%d" % t] if ("LUT%d" % t) in IDX else IDX["PLAY27a"]
        tt = T_OF[i]
        d, _bl = _render(vf, tt)
        n_t = vf.value_at(DATA_TENS_BIT, tt)
        n_o = vf.value_at(DATA_ONES_BIT, tt)
        if n_t != str((d >> 18) & 1):
            bad.append("t=%d %s=%s ≠ o_data[18]=%s"
                       % (t, DATA_TENS_BIT, n_t, (d >> 18) & 1))
        if n_o != str((d >> 13) & 1):
            bad.append("t=%d %s=%s ≠ o_data[13]=%s"
                       % (t, DATA_ONES_BIT, n_o, (d >> 13) & 1))
    res.append((
        "⑪ ⭐ 中间信号解释输出：网表内部节点 %s == o_data[18]（DISP4 的 bit2）、"
        "%s == o_data[13]（DISP3 的 bit1），在 17 个采样点上逐点相同"
        "（这两个数据线是从这两个中间节点送出去的；对应关系由探针跑逐点相关得到）"
        % (DATA_TENS_BIT, DATA_ONES_BIT),
        not bad,
        "\n".join(bad) if bad else
        "%s: %s | %s: %s（在 17 个采样点上与端口逐位一致）"
        % (DATA_TENS_BIT, [vf.value_at(DATA_TENS_BIT, T_OF[i]) for i in
                           (IDX["LUT20"], IDX["LUT40"], IDX["LUT60"])],
           DATA_ONES_BIT, [vf.value_at(DATA_ONES_BIT, T_OF[i]) for i in
                           (IDX["LUT20"], IDX["LUT40"], IDX["LUT60"])]),
    ))

    # ---- ⑫ 中间信号确定且非常量（decoder 节点随输入变化）----
    pats = set()
    bad = []
    for i in range(len(STIM)):
        bits = []
        for n in TENS_BITS + ONES_BITS:
            lv = vf.value_at(n, T_OF[i])
            if lv not in ("0", "1"):
                bad.append((i, n, lv))
            bits.append(lv)
        pats.add(tuple(bits))
    res.append((
        "⑫ 中间信号 tens~1:0 / ones~3:0（case 表的译码中间项）在 %d 个采样点上取值"
        "全部为确定 0/1，且组合随 i_state/i_time 变化（不是常量、不是 X）" % len(IDX),
        not bad and len(pats) >= 2,
        ("出现非 0/1 的采样点：%s" % bad[:4]) if bad else
        "%d 个窗口共出现 %d 种不同组合（≥2 即说明确实随输入变化）"
        % (len(IDX), len(pats)),
    ))

    return res
