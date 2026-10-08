# -*- coding: utf-8 -*-
"""tb_dot_matrix_scan.py —— dot_matrix_scan（8x8 双色点阵行驱动）功能仿真激励与断言

【dot_matrix_scan 应该做什么】（板上接线见 rtl/dot_matrix_scan.vhd 头部：
   行 ROW0..ROW7 **低有效**；红 COLRn / 绿 COLGn **高有效**；红绿同时低 = 灭）
      · 每一相（每个 i_row 取值）o_row **恰好一位为低**，其余全高；
      · 行号 → 位号的映射是**实测反序**的（RTL 头部：ROW0 是物理最下一行，
        逻辑行 0 = 顶行 → 拉低 bit7；逻辑行 7 = 底行 → 拉低 bit0）；
      · 8 个行号必须全部扫到（不重不漏，双射）；
      · o_colr / o_colg 分别直通 i_colr / i_colg（**不改位序、不合色**）；
      · 单色内容下 o_colr 与 o_colg **逐列互斥**（同一列同时为高 = 显示黄色，
        本该红色的点会变黄）—— 用 0xAA/0x55、0x81/0x42、0x24/0x18 这类
        交错图案，任何一位错位/取反/复制都会立刻出现同列为高；
      · i_en='0' 或 i_rst='1' → 整屏熄灭：o_row 全高、o_colr/o_colg 全 0；
      · 行号与列数据同拍寄存（同一 clk 沿一起更新）→ 不会把上一行的数据
        打到下一行（防鬼影）。

【判据是独立推出来的】
    "低位 = 7 - i_row" 来自 RTL 头部记录的**上板实测**结论（ROW0 在最下），
    不是抄 RTL 的位串；这条同时把"8 行全部扫到且不重不漏（双射）"钉死。

【激励时间线】clk 20ns，rst 前 60ns 为高；每窗口 200ns = 10 个 clk，
    窗口起点都是 clk 周期的整数倍，采样从窗口起点 +40ns（2 拍）开始：
      W0 row=0 colr=0xAA colg=0x55   交错图案（任何错位即同列为高）
      W1 row=1 colr=0x0F colg=0x00   纯红
      W2 row=2 colr=0x00 colg=0xF0   纯绿
      W3 row=3 colr=0x00 colg=0x00   选中行但全灭
      W4 row=4 colr=0xFF colg=0x00   整行红
      W5 row=5 colr=0x00 colg=0xFF   整行绿
      W6 row=6 colr=0x81 colg=0x42   两端/中间交错
      W7 row=7 colr=0x24 colg=0x18   交错
      W8 en=0  → 整屏熄灭（行仍给 row=2，必须被 i_en 压成全灭）
      W9 en=1 回  → 恢复显示（两个方向都测）

⚠️ **复位必须显式给**：综合后网表寄存器初值是 X，本模块三个输出寄存器
   不复位会永远停在 X。

⚠️ 观测点说明：本模块 RTL 里**只有一个**内部信号 row_sel，而它是纯组合的
   行译码（综合后变成 8 个 lpm_mux，网表里没有 row_sel 这个节点，实测
   quartus_sim 报 Can't find corresponding node name）。因此中间信号取
   **综合后网表里真实存在的内部寄存器节点** `o_row[n]~reg0` / `o_colr[n]~reg0`
   / `o_colg[n]~reg0`（名字取自 db/*.hier_info），它们才是驱动引脚的那个寄存器，
   断言要求它们与端口逐点一致。
"""

CLK_PERIOD = 20.0
DURATION = 2200.0
GRID_PERIOD = 10.0
SAMPLE_STEP = 10.0
SETTLE = 40.0            # 每窗口跳变后等 2 拍再采样
RST_END = 60.0

WINDOWS = [
    dict(name="W0", start=80.0,   end=280.0,  en=1, row=0, colr=0xAA, colg=0x55),
    dict(name="W1", start=280.0,  end=480.0,  en=1, row=1, colr=0x0F, colg=0x00),
    dict(name="W2", start=480.0,  end=680.0,  en=1, row=2, colr=0x00, colg=0xF0),
    dict(name="W3", start=680.0,  end=880.0,  en=1, row=3, colr=0x00, colg=0x00),
    dict(name="W4", start=880.0,  end=1080.0, en=1, row=4, colr=0xFF, colg=0x00),
    dict(name="W5", start=1080.0, end=1280.0, en=1, row=5, colr=0x00, colg=0xFF),
    dict(name="W6", start=1280.0, end=1480.0, en=1, row=6, colr=0x81, colg=0x42),
    dict(name="W7", start=1480.0, end=1680.0, en=1, row=7, colr=0x24, colg=0x18),
    dict(name="W8", start=1680.0, end=1880.0, en=0, row=2, colr=0xFF, colg=0xFF),
    dict(name="W9", start=1880.0, end=2080.0, en=1, row=2, colr=0x11, colg=0x22),
]


def low_bit(row):
    """行低有效：返回 o_row 中被拉低的那一位（逻辑行 row 应拉低 bit = 7-row）。"""
    return 7 - row


def expected(w):
    """窗口 w 稳态下应有的 (o_row, o_colr, o_colg)。"""
    if not w["en"]:
        return 0xFF, 0x00, 0x00
    return 0xFF ^ (1 << low_bit(w["row"])), w["colr"], w["colg"]


# ---- 端口 + 中间信号（内部寄存器节点，名字来自综合后网表的 db/*.hier_info）----
PORTS = ["i_row", "i_colr", "i_colg", "o_row", "o_colr", "o_colg"]
BURIED = ["o_row[7]~reg0", "o_row[0]~reg0", "o_colr[0]~reg0", "o_colg[7]~reg0",
          "process_0~0"]
OBSERVE = ["i_clk", "i_rst", "i_en"] + PORTS + BURIED
REG_MAP = [("o_row[7]~reg0", "o_row", 7), ("o_row[0]~reg0", "o_row", 0),
           ("o_colr[0]~reg0", "o_colr", 0), ("o_colg[7]~reg0", "o_colg", 7)]


def _buried(b, name):
    for n in [name, name + "[0]"]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_en")
    b.input_bus("i_row", 3)
    b.input_bus("i_colr", 8)
    b.input_bus("i_colg", 8)
    b.output_bus("o_row", 8)
    b.output_bus("o_colr", 8)
    b.output_bus("o_colg", 8)
    for n in BURIED:
        b.output_bit(n)
        _buried(b, n)

    b.clock("i_clk", CLK_PERIOD)
    b.segments("i_rst", [(RST_END, 1), (DURATION - RST_END, 0)])

    def ramp(key):
        segs, prev_v, prev_t = [], WINDOWS[0][key], 0.0
        for w in WINDOWS:
            if w[key] != prev_v:
                segs.append((w["start"] - prev_t, prev_v))
                prev_t, prev_v = w["start"], w[key]
        segs.append((DURATION - prev_t, prev_v))
        return [s for s in segs if s[0] > 0]

    for key, name, width in (("en", "i_en", 1), ("row", "i_row", 3),
                             ("colr", "i_colr", 8), ("colg", "i_colg", 8)):
        if width > 1:
            b.bus_segments(name, ramp(key))
        else:
            b.segments(name, ramp(key))


# ============================================================
# 辅助
# ============================================================
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


def _samples(vf):
    """逐窗口采样稳态输出：返回 [(窗口, 时刻, o_row, o_colr, o_colg)]。"""
    out = []
    for w in WINDOWS:
        t = w["start"] + SETTLE
        while t < w["end"]:
            row = _busv(vf, "o_row", t)
            colr = _busv(vf, "o_colr", t)
            colg = _busv(vf, "o_colg", t)
            if None not in (row, colr, colg):
                out.append((w, t, row, colr, colg))
            t += SAMPLE_STEP
    return out


def _hex(v):
    return "X" if v is None else "0x%02X" % v


# ============================================================
# 断言
# ============================================================
def check(vf):
    res = []
    smp = _samples(vf)
    on = [s for s in smp if s[0]["en"]]

    # ---------------------------------------------------------
    # ① 显示相：o_row 恰好一位为低（低有效），行号与期望一致
    # ---------------------------------------------------------
    bad, rows_seen = [], {}
    for (w, t, row, _cr, _cg) in on:
        zeros = [b for b in range(8) if not (row >> b) & 1]
        if len(zeros) != 1:
            bad.append("%s t=%.0fns o_row=%s 低位=%r（应恰一位低）"
                       % (w["name"], t, _hex(row), zeros))
            continue
        rows_seen[w["row"]] = zeros[0]
        if zeros[0] != low_bit(w["row"]):
            bad.append("%s t=%.0fns row=%d o_row=%s 拉低位=%d 应=%d"
                       % (w["name"], t, w["row"], _hex(row), zeros[0], low_bit(w["row"])))
    res.append((
        "① 显示相 o_row **恰好一位为低**、且拉低位 = 7-row（%d 个采样点）" % len(on),
        (not bad) and len(on) > 100,
        "\n".join(bad[:5]) if bad else
        "全部 %d 个采样点都是「恰一位为低」且行号映射正确" % len(on),
    ))

    # ---------------------------------------------------------
    # ② 8 行全部扫到，且行号→位号是双射（不重不漏）
    # ---------------------------------------------------------
    res.append((
        "② 8 个行号全部扫到且映射不重不漏（行号→拉低位是双射 {0..7}→{7..0}）",
        sorted(rows_seen.keys()) == list(range(8))
        and sorted(rows_seen.values()) == list(range(8)),
        "行号→拉低位 = %s" % {k: rows_seen[k] for k in sorted(rows_seen)},
    ))

    # ---------------------------------------------------------
    # ③ 消隐/关闭：i_en='0' 与 i_rst='1' → o_row 全高、两色全 0
    # ---------------------------------------------------------
    dark = [(w, t, r, cr, cg) for (w, t, r, cr, cg) in smp if not w["en"]]
    dr, dcr, dcg = _busv(vf, "o_row", 30.0), _busv(vf, "o_colr", 30.0), \
        _busv(vf, "o_colg", 30.0)
    bad = ["%s t=%.0fns row=%s colr=%s colg=%s" % (w["name"], t, _hex(r), _hex(cr), _hex(cg))
           for (w, t, r, cr, cg) in dark if (r, cr, cg) != (0xFF, 0x00, 0x00)]
    res.append((
        "③ 消隐相全灭：i_en='0'（W8，%d 点）与 i_rst 期间 → o_row=0xFF、"
        "o_colr=0x00、o_colg=0x00" % len(dark),
        (not bad) and (dr, dcr, dcg) == (0xFF, 0x00, 0x00) and len(dark) >= 10,
        "\n".join(bad[:5]) if bad else
        "W8 的 %d 个采样点全灭；rst 期间 t=30ns：row=%s colr=%s colg=%s"
        % (len(dark), _hex(dr), _hex(dcr), _hex(dcg)),
    ))

    # ---------------------------------------------------------
    # ④ 单色内容下 o_colr / o_colg **逐列互斥**（同列为高 = 本该单色却显示黄色）
    #    激励特意用 0xAA/0x55、0x81/0x42、0x24/0x18 等交错图案：
    #    任何一位错位、取反、红绿互换后的复制都会造出同列为高。
    # ---------------------------------------------------------
    bad = ["%s t=%.0fns colr=%s colg=%s 同列为高掩码=%s"
           % (w["name"], t, _hex(cr), _hex(cg), _hex(cr & cg))
           for (w, t, _r, cr, cg) in smp if (cr & cg) != 0]
    res.append((
        "④ o_colr / o_colg 互斥：单色内容下任何一列都不同时为高"
        "（%d 个采样点，含 3 组交错图案）" % len(smp),
        (not bad) and len(smp) > 100,
        "\n".join(bad[:5]) if bad else "全部 %d 个采样点的 colr & colg = 0" % len(smp),
    ))

    # ---------------------------------------------------------
    # ⑤ 直通：o_colr == i_colr、o_colg == i_colg（不改位序、不合色）
    #    ＋ 三路输出同相：每个采样点的三元组必须整体等于该窗口的期望三元组
    #      （行号或列数据若与另一拍错位，就会出现"行 i + 行 j 的数据"混合态）
    # ---------------------------------------------------------
    bad = []
    for (w, t, row, colr, colg) in smp:
        er, ecr, ecg = expected(w)
        if (colr, colg) != (ecr, ecg):
            bad.append("%s t=%.0fns colr/colg=%s/%s 应=%s/%s"
                       % (w["name"], t, _hex(colr), _hex(colg), _hex(ecr), _hex(ecg)))
        if row != er:
            bad.append("%s t=%.0fns o_row=%s 应=%s（行数据不同拍 → 鬼影）"
                       % (w["name"], t, _hex(row), _hex(er)))
    res.append((
        "⑤ 直通与同拍更新：o_colr==i_colr、o_colg==i_colg，且 "
        "(o_row,o_colr,o_colg) 逐点等于期望三元组（无鬼影混合态）",
        not bad,
        "\n".join(bad[:5]) if bad else "全部 %d 个采样点三元组与期望完全一致" % len(smp),
    ))

    # ---------------------------------------------------------
    # ⑥ 中间信号：网表内部寄存器节点 o_row[n]~reg0 / o_colr[n]~reg0 / o_colg[n]~reg0
    #    必须逐点等于对应端口位（证明"引脚确实由这些内部寄存器驱动"），
    #    并在 i_en='0' 时被强制成熄灭值。process_0~0 是 rst/en 的熄灭控制节点。
    # ---------------------------------------------------------
    bad = []
    n_cmp = 0
    for (w, t, _row, _cr, _cg) in smp:
        for (node, port, bit) in REG_MAP:
            a = vf.value_at(node, t)
            b = vf.value_at("%s[%d]" % (port, bit), t)
            n_cmp += 1
            if a != b:
                bad.append("t=%.0fns %s=%s 而 %s[%d]=%s" % (t, node, a, port, bit, b))
    p0 = sorted({vf.value_at("process_0~0", t) for (_w, t, _r, _c, _g) in smp})
    res.append((
        "⑥ 中间信号：内部寄存器节点（o_row[7]~reg0 / o_row[0]~reg0 / o_colr[0]~reg0 / "
        "o_colg[7]~reg0）逐点 == 输出端口对应位（%d 次比对）" % n_cmp,
        (not bad) and n_cmp > 400 and p0 and set(p0) <= {"0", "1"},
        "\n".join(bad[:5]) if bad else
        "四个内部寄存器节点与端口逐点一致；process_0~0（rst/en 熄灭控制）取值 = %s"
        % p0,
    ))

    return res
