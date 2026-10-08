# -*- coding: utf-8 -*-
"""tb_seg_scan.py —— seg_scan（8 位数码管动态扫描 + 共阴段码译码）功能仿真激励与断言

【seg_scan 应该做什么】（板上接线见 rtl/seg_scan.vhd 头部：段 = 高电平点亮，
   位选 CATn = 低电平选中；段位序 o_seg(0)=AA(a) … o_seg(6)=AG(g)、o_seg(7)=AP）
      · 8 个位选**轮流出现且互不重叠**：任一时刻最多一位被选中，且每位独占一个
        i_tick 周期；
      · 选中第 k 位时，段码必须 = i_data 第 k 个半字节（BCD）的共阴段码，
        **位选与段码同源**（错位/镜像/差一拍必被抓）；
      · 0~9 正常译码；A~F 等非法 BCD 全灭；AP（bit7）恒 0；
      · i_blank(k)='1' → 第 k 位强制全灭，不影响其他位；
      · i_raw_en='1' → 旁路译码器，i_raw 原样上段线（仍受 i_blank / i_en 约束）；
      · i_en='0' → 全部熄灭（段线全 0），位选照常扫描；
      · i_rst → o_seg=0、o_cat=0xFF。

【判据是独立推出来的，没有抄 RTL 常量】
    段码表由**段集合**（a~g 各段亮不亮）按板上位序 AA→bit0 … AG→bit6、AP→bit7
    现场生成，而不是把 RTL 里的 8 位字面量抄一遍 —— 段表错一个数字、位序写反
    （这正是 RTL 头部记录的"历史 bug"形态）都会立刻挂。

【激励时间线】clk 20ns、i_tick 每 40ns 一拍（1 clk 高），rst 前 40ns 为高。
    每窗口 640ns = 16 个 i_tick = 2 整帧，窗口边界都是 i_tick 的整数倍：
      W1 80~720     data=0x12345678 blank=0            8 位八个互异段码
      W2 720~1360   data=0x00000090 blank=0            补数字 0 与 9
      W3 1360~2000  data=0xF2345678 blank=0            DISP7 未定义字位码(F) → 全灭
      W4 2000~2640  data=0x12345678 blank=0x08         熄灭 DISP3
      W5 2640~3280  data=0x12345678 blank=0x81         熄灭两端 DISP0/DISP7
      W6 3280~3920  data=0xF2345678 blank=0  raw_en=1 raw=0x5A   raw 直通
      W7 3920~4560  data=0x12345678 blank=0x10 raw_en=1 raw=0xC3 熄灭压过 raw
      W8 4560~5200  data=0x12345678 en=0               整体熄灭（位选仍在扫）
      W9 5200~5840  data=0x12345678 en=1               恢复显示（两个方向都测）
      W10 5840~6480 data=0xBACC0000 blank=0x0F         结算拼字 "PASS"（P A S S）
      W11 6480~7120 data=0xDA1E0000 blank=0x0F         结算拼字 "FAIL"（F A I L）

⚠️ **复位必须显式给**：综合后网表寄存器初值是 X，idx / seg_r / cat_r 不复位即永远 X。
"""

CLK_PERIOD = 20.0
TICK_PERIOD = 40.0       # i_tick：1 clk 高 + 1 clk 低
RST_END = 40.0
DURATION = 7160.0        # = 11 窗口 × 640ns + 40ns（且是 clk 周期的整数倍）
GRID_PERIOD = 10.0
SAMPLE_STEP = 10.0
SAMPLE_OFFSET = 5.0      # 采样点取 ≡5 mod 10，避开 clk 沿

# ---- 段集合（物理段 a~g 亮不亮）→ 共阴高位段码（AA→bit0 … AG→bit6，AP=bit7=0）----
#      **键是"字位码"**，与 puzzle_pkg 的 DIG_* 常量、seg_scan 的 case 一一对应：
#        0x0..0x9 = 数字，0xA..0xE = 结算画面的字母，0xF = 灭（不在表里 → 全灭）。
#      ⚠️ 7 段管的固有限制（如实记录）：'S' 与 '5' 的段码**完全相同**、
#         'I' 借用 '1' 的形状 → 板上 "PASS" 看着像 "PA55"、"FAIL" 像 "FA1L"。
CODE_SEGS = {
    0x0: "abcdef", 0x1: "bc",    0x2: "abdeg",  0x3: "abcdg", 0x4: "bcfg",
    0x5: "acdfg",  0x6: "acdefg", 0x7: "abc",   0x8: "abcdefg", 0x9: "abcdfg",
    0xA: "abcefg",      # 'A'
    0xB: "abefg",       # 'P'
    0xC: "acdfg",       # 'S'（与 '5' 同形）
    0xD: "aefg",        # 'F'
    0xE: "def",         # 'L'
}
SEG_BIT = {c: i for i, c in enumerate("abcdefg")}     # 板上位序 AA→0 … AG→6


def code_of(d):
    """字位码 d 的共阴段码；不在表里（含 0xF 灭码）→ 全灭 0x00。"""
    segs = CODE_SEGS.get(d)
    if segs is None:
        return 0x00
    v = 0
    for c in segs:
        v |= (1 << SEG_BIT[c])
    return v


def _nib(v, k):
    return (v >> (4 * k)) & 0xF


# ---- 激励窗口 ----
WINDOWS = [
    dict(name="W1", start=80.0,   end=720.0,  data=0x12345678, blank=0x00, en=1, raw_en=0, raw=0x00),
    dict(name="W2", start=720.0,  end=1360.0, data=0x00000090, blank=0x00, en=1, raw_en=0, raw=0x00),
    dict(name="W3", start=1360.0, end=2000.0, data=0xF2345678, blank=0x00, en=1, raw_en=0, raw=0x00),
    dict(name="W4", start=2000.0, end=2640.0, data=0x12345678, blank=0x08, en=1, raw_en=0, raw=0x00),
    dict(name="W5", start=2640.0, end=3280.0, data=0x12345678, blank=0x81, en=1, raw_en=0, raw=0x00),
    dict(name="W6", start=3280.0, end=3920.0, data=0xF2345678, blank=0x00, en=1, raw_en=1, raw=0x5A),
    dict(name="W7", start=3920.0, end=4560.0, data=0x12345678, blank=0x10, en=1, raw_en=1, raw=0xC3),
    dict(name="W8", start=4560.0, end=5200.0, data=0x12345678, blank=0x00, en=0, raw_en=0, raw=0x00),
    dict(name="W9", start=5200.0, end=5840.0, data=0x12345678, blank=0x00, en=1, raw_en=0, raw=0x00),
    # W10/W11：**结算画面的拼字**（2026-10-08 由 "75"/"00" 改为 "PASS"/"FAIL"）
    #   字位码 = puzzle_pkg 的 DIG_*（P=0xB A=0xA S=0xC / F=0xD A=0xA I=0x1 L=0xE）
    dict(name="W10", start=5840.0, end=6480.0, data=0xBACC0000, blank=0x0F, en=1, raw_en=0, raw=0x00),
    dict(name="W11", start=6480.0, end=7120.0, data=0xDA1E0000, blank=0x0F, en=1, raw_en=0, raw=0x00),
]


def exp_seg(w, k):
    """窗口 w 下第 k 位数码管应显示的段码。"""
    if not w["en"] or ((w["blank"] >> k) & 1):
        return 0x00
    if w["raw_en"]:
        return w["raw"]
    return code_of(_nib(w["data"], k))


def win_at(t):
    for w in WINDOWS:
        if w["start"] <= t < w["end"]:
            return w
    return None


# ---- 端口 + 中间信号（课件 p59：波形里必须有中间信号）----
PORTS = ["i_data", "i_blank", "i_raw_en", "i_raw", "o_seg", "o_cat"]
# ⚠️ 实测：nib / decoded 这两个**纯组合**内部信号被综合器合并进译码逻辑锥，
#    综合后网表里不存在（quartus_sim 报 Can't find corresponding node name）
#    → 不能进 OBSERVE。留下的 idx / seg_r / cat_r 都是真寄存器，实测存在。
BURIED = {"idx": 3, "seg_r": 8, "cat_r": 8}
OBSERVE = ["i_clk", "i_rst", "i_tick", "i_en"] + PORTS + list(BURIED.keys())


def _buried(b, name, width):
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_tick")
    b.input_bit("i_en")
    b.input_bus("i_data", 32)
    b.input_bus("i_blank", 8)
    b.input_bit("i_raw_en")
    b.input_bus("i_raw", 8)
    b.output_bus("o_seg", 8)
    b.output_bus("o_cat", 8)
    for n, w in BURIED.items():
        if w > 1:
            b.output_bus(n, w)
        else:
            b.output_bit(n)
        _buried(b, n, w)

    b.clock("i_clk", CLK_PERIOD)
    # ⚠️ 显式复位（综合后网表寄存器初值 X）
    b.segments("i_rst", [(RST_END, 1), (DURATION - RST_END, 0)])

    n = int(DURATION // TICK_PERIOD)
    b.segments("i_tick", [(TICK_PERIOD - CLK_PERIOD, 0), (CLK_PERIOD, 1)] * n)

    def ramp(key):
        out, prev = [], WINDOWS[0][key]
        for w in WINDOWS:
            if w[key] != prev:
                out.append((w["start"], w[key]))
                prev = w[key]
        return out

    for key, width in (("data", 32), ("blank", 8), ("en", 1),
                       ("raw_en", 1), ("raw", 8)):
        name = {"data": "i_data", "blank": "i_blank", "en": "i_en",
                "raw_en": "i_raw_en", "raw": "i_raw"}[key]
        pairs = ramp(key)
        segs, prev_t, prev_v = [], 0.0, WINDOWS[0][key]
        for (t, v) in pairs:
            if t > prev_t:
                segs.append((t - prev_t, prev_v))
            prev_t, prev_v = t, v
        segs.append((DURATION - prev_t, prev_v))
        if width > 1:
            b.bus_segments(name, segs)
        else:
            b.segments(name, segs)


# ============================================================
# 辅助
# ============================================================
def _rises(vf, name):
    """上升沿（0→1）时刻列表。"""
    return [t for (t, lv) in vf.trace(name) if lv == "1"]


def _busv(vf, name, t):
    """安全取总线值：节点不在综合后网表里时返回 None（不抛 KeyError）。

    ⚠️ 变异测试实测：把 RTL 改坏可能让某个观测节点被综合器优化掉，
       此时 check() 必须如实报"断言失败"，而不是崩在 bus_value_at 上。
    """
    if name not in vf.signals:
        return None
    if vf.signals[name].is_bus:
        return vf.bus_value_at(name, t)
    return vf.value_at(name, t)


def _bus_trace(vf, name, width):
    """总线逐位拼成 [(时刻, 整数值), ...]（只留值变化点）。"""
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


def _digit_of(cat):
    """位选低有效：恰一位为低 → 该位号；否则 None。"""
    if cat is None:
        return None
    zeros = [b for b in range(8) if not (cat >> b) & 1]
    return zeros[0] if len(zeros) == 1 else None


def _hx(v):
    return "X" if v is None else "0x%02X" % v


# ============================================================
# 断言
# ============================================================
def check(vf):
    res = []
    cat_tr = _bus_trace(vf, "o_cat", 8)
    seg_tr = _bus_trace(vf, "o_seg", 8)
    live = [(t, v) for (t, v) in cat_tr if RST_END <= t < DURATION - TICK_PERIOD]
    seg_live = [(t, v) for (t, v) in seg_tr if RST_END <= t < DURATION - TICK_PERIOD]

    # ---------------------------------------------------------
    # ① 位选：恰一位为低（不重叠）—— 任何时刻不允许两位同时被选中
    # ---------------------------------------------------------
    bad = []
    n_low = 0
    for (t, v) in live:
        zeros = [b for b in range(8) if not (v >> b) & 1]
        if len(zeros) != 1:
            bad.append("t=%.0fns o_cat=%s 低位=%r" % (t, _hx(v), zeros))
        else:
            n_low += 1
    res.append((
        "① 位选低有效且**互不重叠**：复位后每个状态下 o_cat 恰一位为低（共 %d 个状态）"
        % len(live),
        (not bad) and len(live) >= 8 and n_low == len(live),
        "\n".join(bad[:5]) if bad else "%d 个状态全部恰一位低（不重叠）" % n_low,
    ))

    # ---------------------------------------------------------
    # ② 轮流出现：位号按 +1(mod 8) 循环推进，每次切换恰隔 1 个 i_tick
    #    （跳号 / 镜像 / 每位占 2 拍 → 挂）
    # ---------------------------------------------------------
    ds = [(t, _digit_of(v)) for (t, v) in live]
    ds = [(t, k) for (t, k) in ds if k is not None]
    order_bad = ["t=%.0f %d→%d" % (ds[i + 1][0], ds[i][1], ds[i + 1][1])
                 for i in range(len(ds) - 1) if ((ds[i + 1][1] - ds[i][1]) % 8) != 1]
    deltas = sorted({round(ds[i + 1][0] - ds[i][0], 6) for i in range(len(ds) - 1)})
    seen = sorted({k for (_t, k) in ds})
    res.append((
        "② 8 个位选轮流出现且不重叠：位号 +1(mod 8) 连续推进、每次切换恰隔 1 个 i_tick"
        "（= %.0f ns）、8 位全出现" % TICK_PERIOD,
        len(ds) >= 8 and not order_bad and deltas == [TICK_PERIOD]
        and seen == list(range(8)),
        "位号序列前 16 个 = %s；切换间隔集合 = %s ns；出现过的位号 = %s；异常相邻对 = %s"
        % ([k for (_t, k) in ds[:16]], deltas, seen, order_bad[:3] if order_bad else "无"),
    ))

    # ---------------------------------------------------------
    # ③ 位选↔段码同源：选中第 k 位时 o_seg == 第 k 个半字节的共阴段码
    #    （0x12345678 八位段码互异 → 位号错位/镜像/取错半字节必被抓）
    # ---------------------------------------------------------
    bad, n_ok = [], 0
    for (t, seg) in seg_live:
        w = win_at(t)
        if w is None:
            continue
        k = _digit_of(_busv(vf, "o_cat", t + 1e-9))
        if k is None:
            bad.append("t=%.0fns 位选不是一热，无法配对" % t)
            continue
        want = exp_seg(w, k)
        n_ok += 1
        if seg != want:
            bad.append("t=%.0fns(%s) DISP%d seg=%s 应=%s"
                       % (t, w["name"], k, _hx(seg), _hx(want)))
    res.append((
        "③ 位选↔段码同源：选中位 k 时 o_seg == 该窗口下 DISPk 的段码"
        "（%d 个显示状态逐点比对）" % n_ok,
        (not bad) and n_ok >= 50,
        "\n".join(bad[:5]) if bad else "全部 %d 个显示状态段码与位选一致" % n_ok,
    ))

    # ---------------------------------------------------------
    # ④ 段码表 0~9 逐值（共阴、高有效；由 a~g 段集合独立生成）
    #    ＋ 译码模式下 AP(bit7) 恒 0（本设计不用小数点）。
    #    ⚠️ raw 直通模式下 bit7 是 i_raw 的第 8 位、会照原样输出（W7 用 0xC3
    #       就是把 bit7 拉高，故 AP 恒 0 只在 raw_en=0 的窗口里断言）。
    # ---------------------------------------------------------
    rows, ok_all = [], True
    for d in range(10):
        hit = False
        for w in WINDOWS:
            if not w["en"] or w["raw_en"]:
                continue
            for k in range(8):
                if _nib(w["data"], k) == d and not ((w["blank"] >> k) & 1):
                    for (t, seg) in seg_live:
                        if w["start"] <= t < w["end"] and \
                                _digit_of(_busv(vf, "o_cat", t + 1e-9)) == k \
                                and seg == code_of(d):
                            hit = True
        ok_all &= hit
        rows.append("数字%d→0x%02X%s" % (d, code_of(d), "✓" if hit else "✗未见"))
    ap_bad = ["t=%.0fns(%s) seg=%s" % (t, win_at(t)["name"], _hx(seg))
              for (t, seg) in seg_live
              if win_at(t) is not None and not win_at(t)["raw_en"] and (seg >> 7) & 1]
    raw_ap = sorted({_hx(seg) for (t, seg) in seg_live
                     if win_at(t) is not None and win_at(t)["raw_en"]})
    res.append((
        "④ 段码表 0~9 逐值（共阴高有效，由 a~g 段集合独立生成）"
        "＋译码模式下 AP(bit7) 恒 0",
        ok_all and not ap_bad,
        "  ".join(rows) + "；译码模式下 seg(bit7)='1' 的状态 = %d；"
        "raw 模式下的段码集合 = %s（bit7 跟随 i_raw）"
        % (len(ap_bad), raw_ap),
    ))

    # ---------------------------------------------------------
    # ⑤ 未定义字位码 0xF → 该位全灭
    #    （0xA..0xE 从 2026-10-08 起是结算字母 A/P/S/F/L，不再算"非法 BCD"，
    #      它们的段形由断言 ③ 的独立模型 + 断言 ⑪ 的拼字结果校验）
    # ---------------------------------------------------------
    bad = []
    for w in WINDOWS:
        if w["raw_en"] or not w["en"]:
            continue
        for k in range(8):
            if _nib(w["data"], k) == 0xF and not ((w["blank"] >> k) & 1):
                for (t, seg) in seg_live:
                    if w["start"] <= t < w["end"] and \
                            _digit_of(_busv(vf, "o_cat", t + 1e-9)) == k and seg != 0:
                        bad.append("%s DISP%d nibble=F 未定义却 seg=%s"
                                   % (w["name"], k, _hx(seg)))
    res.append((
        "⑤ 未定义字位码 0xF 全灭：W3 的 DISP7=F → 该位段码恒 0x00"
        "（0xA..0xE 现为结算字母，见 ③⑪）",
        not bad,
        "\n".join(bad[:5]) if bad else "W3 DISP7（F）在整个窗口内段码恒 0x00，其余位正常",
    ))

    # ---------------------------------------------------------
    # ⑥ i_blank 熄灭掩码：置位的那一位全灭，其余位不受影响
    # ---------------------------------------------------------
    bad, detail = [], []
    for wname, off in (("W4", (3,)), ("W5", (0, 7))):
        w = next(x for x in WINDOWS if x["name"] == wname)
        for k in range(8):
            segs = {seg for (t, seg) in seg_live
                    if w["start"] <= t < w["end"]
                    and _digit_of(_busv(vf, "o_cat", t + 1e-9)) == k}
            if k in off:
                if segs - {0}:
                    bad.append("%s DISP%d 已熄灭却出现 %s" % (wname, k, [_hx(s) for s in segs]))
            elif code_of(_nib(w["data"], k)) not in segs:
                bad.append("%s DISP%d 未熄灭却未见段码 %s（实测 %s）"
                           % (wname, k, _hx(code_of(_nib(w["data"], k))),
                              [_hx(s) for s in segs]))
        detail.append("%s blank=%s → 熄灭位 %s" % (wname, _hx(w["blank"]), list(off)))
    res.append((
        "⑥ 熄灭掩码：W4 熄灭 DISP3、W5 熄灭 DISP0/DISP7 → 该位全灭、其余位段码照旧",
        not bad,
        "\n".join(bad[:5]) if bad else "；".join(detail) + "；其余位段码全部正确",
    ))

    # ---------------------------------------------------------
    # ⑦ i_raw_en 直通：o_seg == i_raw（逐位、含 bit7），且 i_blank 仍能压过 raw
    # ---------------------------------------------------------
    bad = []
    for wname in ("W6", "W7"):
        w = next(x for x in WINDOWS if x["name"] == wname)
        for (t, seg) in seg_live:
            if not (w["start"] <= t < w["end"]):
                continue
            k = _digit_of(_busv(vf, "o_cat", t + 1e-9))
            if k is None:
                continue
            want = 0x00 if (w["blank"] >> k) & 1 else w["raw"]
            if seg != want:
                bad.append("%s t=%.0fns DISP%d seg=%s 应=%s（raw=%s blank=%s）"
                           % (wname, t, k, _hx(seg), _hx(want), _hx(w["raw"]), _hx(w["blank"])))
    res.append((
        "⑦ i_raw_en 直通：o_seg == i_raw（8 位逐位，bit7=AP 也在内）；"
        "W7 里 i_blank(4) 仍把 DISP4 压成全灭",
        not bad,
        "\n".join(bad[:5]) if bad else "W6（raw=0x5A）全部 8 位 o_seg=0x5A；"
        "W7（raw=0xC3）除 DISP4 全灭外全部 0xC3",
    ))

    # ---------------------------------------------------------
    # ⑧ i_en='0' → 整体熄灭；恢复 i_en='1' → 恢复显示（两个方向都测）
    # ---------------------------------------------------------
    w8 = next(x for x in WINDOWS if x["name"] == "W8")
    w9 = next(x for x in WINDOWS if x["name"] == "W9")
    off_segs = {seg for (t, seg) in seg_live if w8["start"] <= t < w8["end"]}
    on_segs = {seg for (t, seg) in seg_live if w9["start"] <= t < w9["end"]}
    cats8 = {v for (t, v) in live if w8["start"] <= t < w8["end"]}
    res.append((
        "⑧ i_en='0' → 全灭（o_seg ≡ 0x00）但位选照常扫描；i_en 回 '1' → 段码恢复",
        off_segs == {0} and len(on_segs) >= 8 and len(cats8) == 8,
        "W8(en=0) 出现过的段码 = %s（应只有 0x00），同窗口位选出现 %d 种；"
        "W9(en=1) 恢复后出现过的段码种类 = %d"
        % ([_hx(s) for s in sorted(off_segs)], len(cats8), len(on_segs)),
    ))

    # ---------------------------------------------------------
    # ⑨ 复位：o_seg=0x00、o_cat=0xFF（位选全高 = 全灭）
    # ---------------------------------------------------------
    got = [(t, _busv(vf, "o_seg", t), _busv(vf, "o_cat", t))
           for t in (RST_END / 2, RST_END - SAMPLE_OFFSET)]
    res.append((
        "⑨ 复位：i_rst 期间 o_seg=0x00、o_cat=0xFF（位选低有效 → 全高 = 全灭）",
        all(s == 0 and c == 0xFF for (_t, s, c) in got),
        "；".join("t=%.0f o_seg=%s o_cat=%s" % (t, _hx(s), _hx(c)) for (t, s, c) in got),
    ))

    # ---------------------------------------------------------
    # ⑩ 中间信号（逐 clk 沿核对内部数据通路）：
    #      idx：每个 i_tick +1(mod 8)，8 个值全出现；
    #      cat_r = 该 idx 的一热译码（0xFF ^ (1<<idx)）—— 位选译码器内部逐拍核对；
    #      seg_r = 该 idx 对应半字节（按当时的 i_data/i_blank/i_en/i_raw_en）的段码
    #             —— 即"输出寄存器确实锁存了译码结果"，而不是别的什么。
    #    与端口断言相互独立：即使输出端口被外面接错，这一条只看模块内部。
    # ---------------------------------------------------------
    idx_tr = _bus_trace(vf, "idx", 3)
    idx_live = [(t, v) for (t, v) in idx_tr if RST_END <= t < DURATION - TICK_PERIOD]
    iv = [v for (_t, v) in idx_live]
    step_ok = all(((iv[i + 1] - iv[i]) % 8) == 1 for i in range(len(iv) - 1))
    edges = [e for e in _rises(vf, "i_clk") if RST_END + 2 * CLK_PERIOD <= e <= DURATION - 2 * CLK_PERIOD]
    bad, n_chk = [], 0
    for e in edges:
        k = _busv(vf, "idx", e - 1.0)          # 沿前的 idx（更新前的值）
        w = win_at(e + 1.0)                          # 该沿所用的输入
        if k is None or w is None:
            continue
        n_chk += 1
        want_cat = 0xFF ^ (1 << k)
        got_cat = _busv(vf, "cat_r", e + 1.0)
        want_seg = exp_seg(w, k)
        got_seg = _busv(vf, "seg_r", e + 1.0)
        if got_cat != want_cat:
            bad.append("t=%.0fns idx=%d cat_r=%s 应=%s" % (e, k, _hx(got_cat), _hx(want_cat)))
        if got_seg != want_seg:
            bad.append("t=%.0fns(%s) idx=%d seg_r=%s 应=%s"
                       % (e, w["name"], k, _hx(got_seg), _hx(want_seg)))
    res.append((
        "⑩ 中间信号：idx 按 +1(mod 8) 推进、8 值全出现；每个 clk 沿上 "
        "cat_r == 0xFF^(1<<idx)、seg_r == 该 idx 对应半字节的段码（共核对 %d 拍）" % n_chk,
        step_ok and sorted(set(iv)) == list(range(8)) and not bad and n_chk > 200,
        "\n".join(bad[:5]) if bad else
        "idx 取值 %s、每拍 +1（%s）；%d 个 clk 沿的 cat_r / seg_r 全部与 idx、输入一致"
        % (sorted(set(iv)), step_ok, n_chk),
    ))

    # ---------------------------------------------------------
    # ⑪ 结算画面拼字：把 W10/W11 里每位实际点亮的段**反解成字母**
    #    （不比对模型，直接把"板上会看到什么字"读出来 —— 这张 tb 里最直观的一条）
    # ---------------------------------------------------------
    LETTER = {0xA: "A", 0xB: "P", 0xC: "S", 0xD: "F", 0xE: "L", 0x1: "I"}
    SEG_OF = {frozenset(v): k for k, v in CODE_SEGS.items()}   # 段集合 -> 字位码
    SEG_OF[frozenset("bc")] = 0x1          # 'I' 借用 '1' 的段形
    words, bad = [], []
    for wname in ("W10", "W11"):
        w = next(x for x in WINDOWS if x["name"] == wname)
        # ⚠️ 必须按**位槽**取样，不能只看 o_seg 的跳变：相邻两位段码相同时（W10 的两个
        #    'S'）那一槽不会有跳变，靠跳变表就会漏掉一位（第一版正是这么漏的）。
        #    位槽边界从 o_cat 的转移表取，槽中点读 o_seg。
        per = {}
        for (t, catv) in live:
            k = _digit_of(catv)
            if k is None or not (w["start"] + 2 * TICK_PERIOD <= t < w["end"]):
                continue
            per.setdefault(k, set()).add(_busv(vf, "o_seg", t + TICK_PERIOD / 2))
        chars = []
        for k in range(7, 3, -1):              # DISP7..DISP4（左→右）
            codes = sorted(per.get(k, []))
            if len(codes) != 1:
                bad.append("%s DISP%d 段码不唯一：%s" % (wname, k, [_hx(s) for s in codes]))
                chars.append("?")
                continue
            names = frozenset(c for c in "abcdefg" if (codes[0] >> SEG_BIT[c]) & 1)
            chars.append(LETTER.get(SEG_OF.get(names), "?"))
        words.append("".join(chars))
    res.append((
        "⑪ ★ 结算画面拼字：W10（胜利）→ 数码管最左四位读作 **PASS**、"
        "W11（失败）→ **FAIL**（把每位实际点亮的段反解成字母；"
        "注：7 段管里 'S' 与 '5' 同形、'I' 用 '1' 的形状，故板上分别看着像 PA55 / FA1L）",
        words == ["PASS", "FAIL"],
        "W10 读作 %r、W11 读作 %r（期望 'PASS' / 'FAIL'）" % (words[0], words[1]),
    ))

    return res
