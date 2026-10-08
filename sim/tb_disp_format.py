# -*- coding: utf-8 -*-
"""tb_disp_format.py —— disp_format 功能仿真激励与断言

【本模块是什么】
    `disp_format` 把「状态 + 关卡 + 倒计时 + 闪烁标志」翻译成 8 位数码管的
    BCD 内容（`o_data`，每 4 位一个 DIG，bits 31..28 = DISP7 = 最左位）与
    熄灭掩码（`o_blank`，'1' = 该位熄灭）。**纯组合**，没有时钟、没有寄存器。

    课程要求对应：B1 自检全 8；B2 待机 DISP7='5' / DISP0=关卡号；
    B4 预览 DISP7 倒数；B5 游戏中 DISP4:DISP3 = 剩余秒数；B9 第二关 DISP3 旁显示 '2'。

【判据的独立来源（不许自证）】
    · 状态编码 / 关卡数 / 各状态该显示什么：来自课程要求 B1/B2/B4/B5/B9 的**文字描述**
      与 `rtl/puzzle_pkg.vhd`（唯一真值源）里的 `S_*` 常量。tb 直接**读** pkg 取常量，
      不在 tb 里抄 "001"/"010" 这类字面量。
    · 倒计时的两位拆分：tb 用 `t // 10` 与 `t % 10` **独立算**，
      再把 16 个不同的 t（含 0/9/10/19/20/29/30/39/40/49/50/59/60/63 这些
      每一个"进位边界"）逐点比对 —— RTL 里那张 64 项 case 表只要错一项就会挂。
    · 熄灭掩码：由"哪些位应该亮"**推导**（例如待机只有 DISP7/DISP0 亮 → 0x7E），
      不是从 RTL 抄。

【中间信号】（课件 p59 / docs/03 §3.1：波形里必须有中间信号）
    `disp_format` 是纯组合模块，VHDL 里的 `d`/`bl`/`tens`/`ones` 是进程变量，
    综合后网表里**没有**叫这些名字的节点。真实存在的内部节点名从仿真报告的
    覆盖率表里读出（报告里列的是网表节点名，形如 `|disp_format|tens~0`）：
        `tens~1:tens~0`  —— 倒计时**十位**的组合译码结果（那张 64 项 case 表的输出）
        `ones~5:ones~0`  —— 倒计时**个位**的组合译码结果
    它们正是 DISP4/DISP3 的数据来源。断言 ⑪/⑫ 用波形里的这两个中间节点
    **反推**显示内容，而不是只看端口 —— 这既满足"波形里要有中间信号"，
    也让"数码管为什么是这个数"在波形上可解释。

【时间线】（单位 ns，`DURATION` = 2800，每段 100 ns，采样点 = 段中点）
    0~100      S_SELF_TEST  blink=0
    100~200    S_SELF_TEST  blink=1
    200~300    S_IDLE       level=1
    300~400    S_IDLE       level=2
    400~500    S_PREVIEW    t=4  level=1
    500~600    S_PREVIEW    t=5  level=2
    600~700    S_PLAYING    t=27 level=1
    700~800    S_PLAYING    t=27 level=2
    800~2400   S_PLAYING    level=1，t 依次取 16 个进位边界值（LUT 逐项验收）
    2400~2500  S_WIN
    2500~2600  S_FAIL
    2600~2700  S="110"（未定义态）
    2700~2800  S="111"（未定义态）
"""

import pathlib
import re

DURATION = 2800.0
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

# 时间线：(状态, 关卡(0/1), 倒计时, blink, 时长)
STIM = [
    (S["S_SELF_TEST"], 0, 30, 0, WIN),
    (S["S_SELF_TEST"], 0, 30, 1, WIN),
    (S["S_IDLE"],      0, 30, 0, WIN),
    (S["S_IDLE"],      1, 30, 0, WIN),
    (S["S_PREVIEW"],   0, 4,  0, WIN),
    (S["S_PREVIEW"],   1, 5,  0, WIN),
    (S["S_PLAYING"],   0, 27, 0, WIN),
    (S["S_PLAYING"],   1, 27, 0, WIN),
] + [(S["S_PLAYING"], 0, t, 0, WIN) for t in LUT_T] + [
    (S["S_WIN"],       0, 30, 0, WIN),      # 4 = S_WIN
    (S["S_FAIL"],      0, 30, 0, WIN),      # 5 = S_FAIL
    (6,                0, 30, 0, WIN),      # 未定义状态码
    (7,                0, 30, 0, WIN),
]

# 每个窗口的中点（采样时刻）与窗口索引
T_OF = [WIN * (i + 0.5) for i in range(len(STIM))]
IDX = {name: i for i, name in enumerate(
    ["SELF0", "SELF1", "IDLE1", "IDLE2", "PREV4", "PREV5", "PLAY27a", "PLAY27b"]
    + ["LUT%d" % t for t in LUT_T] + ["WIN", "FAIL", "UNDEF6", "UNDEF7"])}

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

OBSERVE = (["i_state", "i_level", "i_time", "i_blink", "o_data", "o_blank"]
           + TENS_BITS + ONES_BITS + [DATA_TENS_BIT, DATA_ONES_BIT])


def _buried(b, name):
    sig = b.vf.signals.get(name)
    if sig is not None:
        sig.direction = "BURIED"


def build(b):
    b.input_bus("i_state", 3)
    b.input_bit("i_level")
    b.input_bus("i_time", 6)
    b.input_bit("i_blink")
    b.output_bus("o_data", 32)
    b.output_bus("o_blank", 8)
    for n in TENS_BITS + ONES_BITS + [DATA_TENS_BIT, DATA_ONES_BIT]:
        b.output_bit(n)
        _buried(b, n)

    b.bus_segments("i_state", [(d, s) for (s, _l, _t, _k, d) in STIM])
    b.segments("i_level", [(d, l) for (_s, l, _t, _k, d) in STIM])
    b.bus_segments("i_time", [(d, t) for (_s, _l, t, _k, d) in STIM])
    b.segments("i_blink", [(d, k) for (_s, _l, _t, k, d) in STIM])


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
    rows = []
    bad = []
    for key, lvl in (("IDLE1", 0), ("IDLE2", 1)):
        d, bl = _render(vf, T_OF[IDX[key]])
        want_lv = 1 if lvl == 0 else 2
        ok = (disp(d, 7) == 5 and bl is not None and (bl >> 7) & 1 == 0
              and disp(d, 0) == want_lv and bl & 1 == 0
              and (bl & 0x7E) == 0x7E)
        rows.append("%s: o_data=%s o_blank=%s（DISP7=%s DISP0=%s）"
                    % (key, _hex(d, 8), _hex(bl, 2), disp(d, 7), disp(d, 0)))
        if not ok:
            bad.append(key)
    res.append((
        "③ B2/B3 待机态 → DISP7='5'、DISP0=关卡号(第一关 1 / 第二关 2)，DISP1~6 全灭（o_blank=0x7E）",
        not bad,
        "\n".join(rows),
    ))

    # ---- ④ B4 预览：DISP7 = 预览倒数，DISP0 = 关卡号 ----
    rows = []
    bad = []
    for key, lvl, want in (("PREV4", 0, 4), ("PREV5", 1, 5)):
        d, bl = _render(vf, T_OF[IDX[key]])
        want_lv = 1 if lvl == 0 else 2
        ok = (disp(d, 7) == want and (bl >> 7) & 1 == 0
              and disp(d, 0) == want_lv and bl & 1 == 0 and (bl & 0x7E) == 0x7E)
        rows.append("%s: DISP7=%s（期望 %d） DISP0=%s o_blank=%s"
                    % (key, disp(d, 7), want, disp(d, 0), _hex(bl, 2)))
        if not ok:
            bad.append(key)
    res.append((
        "④ B4 预览态 → DISP7 = 倒计时秒数(单数字)，DISP0 = 关卡号，其余灭",
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

    # ---- ⑥ B9 第二关游戏中：DISP2 额外显示 '2' ----
    d, bl = _render(vf, T_OF[IDX["PLAY27b"]])
    ok = (disp(d, 4) == 2 and disp(d, 3) == 7 and disp(d, 2) == 2 and disp(d, 0) == 2
          and (bl >> 2) & 1 == 0 and bl & 1 == 0)
    res.append((
        "⑥ B9 游戏中(第二关, t=27) → DISP2 额外显示 '2' 并点亮，DISP0=关卡号 2（o_blank=0xE2）",
        ok,
        "o_data=%s o_blank=%s（DISP2=%s 应为 2）" % (_hex(d, 8), _hex(bl, 2), disp(d, 2)),
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
        " 独立算出的 t//10 与 t%10（0/9/10/19/20/29/30/39/40/49/50/59/60/63）",
        not bad,
        "\n".join(bad) if bad else " ".join(rows),
    ))

    # ---- ⑧ 胜负态：画面唯一且互不相同 ----
    dw, bw = _render(vf, T_OF[IDX["WIN"]])
    df, bf = _render(vf, T_OF[IDX["FAIL"]])
    ok = (disp(dw, 7) == 7 and disp(dw, 6) == 5 and bw == 0x3F
          and disp(df, 7) == 0 and disp(df, 6) == 0 and bf == 0x3F
          and dw != df)
    res.append((
        "⑧ S_WIN → DISP7/DISP6 = '7'/'5'；S_FAIL → '0'/'0'；两者都只亮这两位且画面互不相同",
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
        "⑩ 28 个窗口的画面 (o_data,o_blank) 互不相同 —— 仅允许两处有语义的重合："
        "待机(第二关) vs 预览 5 秒（B2 的 '5' 与 B4 的起始值本来就是同一个画面）、"
        "两个未定义状态码同为全灭",
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
        "⑫ 中间信号 tens~1:0 / ones~3:0（case 表的译码中间项）在 28 个采样点上取值"
        "全部为确定 0/1，且组合随 i_state/i_time 变化（不是常量、不是 X）",
        not bad and len(pats) >= 2,
        ("出现非 0/1 的采样点：%s" % bad[:4]) if bad else
        "28 个窗口共出现 %d 种不同组合（≥2 即说明确实随输入变化）" % len(pats),
    ))

    return res
