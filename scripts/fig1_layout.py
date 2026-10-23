#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fig1_layout.py —— 「系统总体框图」的布局引擎（数据来自 arch_data，本文件只管画）

【v3：为什么必须换画法】
    v2 想"每根端口连接画一根箭头、各带一个 '网名[位宽]' 标签"。32 根箭头 × 32 个
    100~190 px 宽的标签，在任何 A4 尺寸的通道里都放不下 —— 体检（audit_diagram 的
    E-LABEL-WIRE）一跑就是 **102 处"标签压在连线上"**；把标签推远又会让它跟自己的线
    彻底失去关联（"浮动标签"比压线更不直观）。

    结论：**32 条带各自标签的连接 = 信息设计错误，不是排版问题**。
    v3 改成工程界通用的画法 —— **一根总线 + 分支**：

      · 同一个源模块出去的线**共用一条主干**（同一个出线点、同一条通道里的竖直干线），
        到各自目标再分叉 ⇒ 32 根线在图上只剩十几条可见的主干；
      · 每条主干在**起点处**标一个 2~8 字的信号组名（"节拍 / 复位""控制 / 状态 / 关卡"…），
        标签就在源模块旁边，关联明确、不压任何线；
      · **32 条连接的完整明细（源 → 目标：网名[位宽]）全部落在图底部的对照表里**，
        图仍然自洽且可逐条核对。

【布局结构】
    6 个竖直列（板载输入 → 时钟/采集 → 主控与存储 → 引擎与胶合 → 显示/音频 → 板载输出）。
    相邻列之间是无方框的空通道；跨列长途信号走顶部干线带。
    全局网络（clk / rst / sw7）是一对多分配，用方框左下角角标表达，不画长线。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arch_data as AD  # noqa: E402

NAME = "new"
DESC = "六列分层 + 总线主干与分支 + 只标重要信号组名（明细表见文档）"

# ---------------------------------------------------------------- 画布与字号
W, H = 1516, 1032
FONT = "Microsoft YaHei, SimSun, sans-serif"
MONO = "Consolas, Courier New, monospace"

TITLE_SIZE = 27
SUBTITLE_SIZE = 15
ZONE_SIZE = 14
ENT_TITLE = 19.5
ENT_SUB = 13
GLUE_TITLE = 15
GLUE_SUB = 13.5
EXT_TITLE = 13
EXT_SUB = 12
TAG_SIZE = 14
BUS_SIZE = 17
LEGEND_SIZE = 13
NOTE_SIZE = 13.5

INK = "#0f172a"
LINE = "#334155"
MUTED = "#64748b"
ZONE_LINE = "#cbd5e1"
ZONE_FILL = "#f8fafc"
EXT_FILL = "#eef2f7"
EXT_LINE = "#94a3b8"
CORE_FILL = "#fffbeb"
CORE_LINE = "#b45309"
GLUE_FILL = "#f8fafc"
GLUE_LINE = "#64748b"

# ---------------------------------------------------------------- 六列
COL_X = [24, 192, 462, 806, 1104, 1358]
# COL_W[0] 由 104 加到 122：原来 104 宽装不下「50 MHz 有源晶振」，draw.io 会在
# "有源晶" 与 "振" 之间断行（T1 返工 D）。加宽后 channel(0) 仍有 46 px，
# 两根主干竖线（ext_btn / ext_kp）分到 10 px，够用。
COL_W = [122, 146, 180, 164, 190, 122]
COL_TITLE = ["板载输入器件", "时钟与输入采集", "主控 · 存储 · 随机源",
             "核心引擎与顶层胶合", "显示与音频输出", "板载输出器件"]

BOX_GEO = {
    "ext_clk":         (0, 330, 66),
    "ext_btn":         (0, 450, 66),
    "ext_sw":          (0, 570, 66),
    "ext_kp":          (0, 880, 66),
    "clk_gen":         (1, 300, 126),
    "keypad_scan":     (1, 866, 76),
    "game_fsm":        (2, 290, 196),
    "piece_rom":       (2, 600, 76),
    "pattern_rom":     (2, 712, 76),
    "rng_lfsr":        (2, 824, 76),
    "glue_pat":        (3, 290, 74),
    "glue_row":        (3, 400, 74),
    "puzzle_ctrl":     (3, 560, 208),
    "disp_format":     (4, 290, 76),
    "seg_scan":        (4, 400, 76),
    "dot_matrix_scan": (4, 510, 76),
    "buzzer_ctrl":     (4, 760, 76),
    "ext_seg":         (5, 294, 66),
    "ext_dot":         (5, 516, 66),
    "ext_buzz":        (5, 766, 66),
}

CN = {
    "clk_gen": "分频 / 复位",
    "keypad_scan": "键盘扫描",
    "game_fsm": "游戏主状态机",
    "piece_rom": "零片掩码表",
    "pattern_rom": "目标图案库",
    "rng_lfsr": "8 位 LFSR",
    "puzzle_ctrl": "拼图引擎",
    "disp_format": "数码管 BCD 内容",
    "seg_scan": "数码管扫描",
    "dot_matrix_scan": "点阵行扫描",
    "buzzer_ctrl": "音效 / 乐句",
}
EXT_LINES = {
    "ext_clk": ("50 MHz", "有源晶振"),
    "ext_btn": ("BTN0", "复位按键"),
    "ext_sw": ("SW7", "全局使能"),
    "ext_kp": ("4×4", "矩阵键盘"),
    "ext_seg": ("8 位", "共阴数码管"),
    "ext_dot": ("8×8", "双色点阵"),
    "ext_buzz": ("无源", "蜂鸣器"),
}
GLUE_CN = {"glue_pat": "图案选择锁存", "glue_row": "行计数器+行切片"}
# 两个虚线胶合框的副标题原来都写「非 entity」，逐字重复（T1 返工 B）；改成
# 各自说明它"锁存/计数什么"，虚线框的含义已由图例统一解释。
GLUE_SUBTITLE = {"glue_pat": "锁存 · 组合", "glue_row": "计数 · 切片"}
# ext_* 框内的三行文字（标题 / 器件名 / 引脚）——自己控制换行，
# 不让 draw.io 在词中间断行（T1 返工 D）。
EXT_SUB_TEXT = {"ext_clk": "PIN_18", "ext_btn": "PIN_61", "ext_sw": "PIN_125",
                "ext_kp": "kp_row / kp_col", "ext_seg": "seg / cat",
                "ext_dot": "ROW/COLR/COLG", "ext_buzz": "PIN_60"}

# ---------------------------------------------------------------- 主干（总线）名字
# 键 = (源模块, 出线侧)；同一个源的所有出线共用一条主干。
TRUNK_CN = {
    ("ext_btn", "right"): "复位键",
    ("ext_kp", "right"): "键盘行",
    ("keypad_scan", "right"): "按键码",
    ("keypad_scan", "left"): "键盘列",
    ("clk_gen", "right"): "节拍",
    ("game_fsm", "right"): "控制/状态",
    ("piece_rom", "right"): "零片掩码",
    ("pattern_rom", "right"): "目标图案",
    ("rng_lfsr", "right"): "随机数",
    ("puzzle_ctrl", "right"): "帧平面",
    ("puzzle_ctrl", "left"): "判定/推进",
    ("glue_pat", "right"): "选择→引擎",
    ("glue_pat", "left"): "选择→ROM",
    # 原为「行切片」——与 glue_row 框标题「行计数器+行切片」里的字面重复
    # （T1 返工 B）；这条线载的是 mat_r[7:0]/mat_g[7:0]/mrow[2:0]，改叫「行数据」。
    ("glue_row", "right"): "行数据",
    ("disp_format", "right"): "段码",
    ("seg_scan", "right"): "段/位选",
    ("buzzer_ctrl", "right"): "蜂鸣",
}

BAND_Y0, BAND_DY = 128, 20

# ---------------------------------------------------------------- 避让参数
# 主干标签必须与任何连线保持的最小间距（px）。draw.io 的标签没有底色，线一旦
# 贴近就会"切断"文字，所以判据不是"不穿过就行"，而是要求留白。
LABEL_CLEAR = 10.0
# 与方框 / 分区标题的间距：方框是**先画标签后画框**（框会盖住标签），只要不重叠
# 就不会切字；要求 10 px 会把标签挤到离源方框很远的地方（"浮动标签"更糟）。
LABEL_BOX_CLEAR = 10.0
# 关联项：标签离自己那根主干的出线段越远越贵，防止它为了躲线而飘走。
LABEL_NEAR = 8.0
# 硬口径：标签到自己主干出线段超过这个距离就基本判无效（T1 返工 C）。
LABEL_OWN_MAX = 30.0
# 通道内竖线之间的最小间距（不同 (源,出线侧) 主干 / 长途分支竖线都算）。
X_GAP = 8.0
X_INSET = 18.0
# 同一方框同一侧：入线附着点与出线主干口之间的最小间距。二者相等时两根线会在
# 同一水平线上完全重合，读者会把它看成"一个两端都带箭头的双向连接"。
LANE_GAP = 16.0
# 触发"错开"的阈值：入线口离出线口近于这个值就认为视觉上已经粘在一起。
LANE_MERGE = 8.0
# 附着点离方框上 / 下边缘的最小距离。
LANE_INSET = 14.0

LEGEND_Y = 986
NOTE_Y = 996
NOTE_LINES = [
    "图例：实线框 = rtl/&lt;同名&gt;.vhd 中的一个 entity（共 11 个，与 puzzle_top.vhd 的 11 条 component 声明、11 个 u_* 例化三方一致）；"
    "虚线框 = 顶层胶合逻辑（非 entity）；浅灰框 = 板载器件",
    "方框左下角角标 = 该模块消费的全局网络：clk 50 MHz ← 有源晶振、rst ← clk_gen、sw7 使能 ← SW7；"
    "这三路是一对多分配（消费者 10 / 8 / 4 个、共 22 根），逐根画会得到 22 根长线，故用角标表达；"
    "纯组合模块（disp_format / piece_rom / pattern_rom）不消费全局网络，因此没有角标（不是漏画）",
]


# ---------------------------------------------------------------- 几何小工具
class R:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = float(x), float(y), float(w), float(h)

    @property
    def x1(self):
        return self.x + self.w

    @property
    def y1(self):
        return self.y + self.h

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


def overlap(a, b, tol=0.0):
    return (min(a.x1, b.x1) - max(a.x, b.x) > tol) and (min(a.y1, b.y1) - max(a.y, b.y) > tol)


def text_w(text, size):
    t = 0.0
    for ch in text:
        t += (1.0 if ord(ch) > 0x2E7F else 0.62) * size
    return t


def seg_rect(p0, p1, r):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p0[0] - r.x), (dx, r.x1 - p0[0]),
                 (-dy, p0[1] - r.y), (dy, r.y1 - p0[1])):
        if abs(p) < 1e-15:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return False
                if t < t1:
                    t1 = t
    return t1 - t0 > 0.0


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def col_of(bid):
    return BOX_GEO[bid][0]


def rect_of(bid):
    c, y, h = BOX_GEO[bid]
    return R(COL_X[c], y, COL_W[c], h)


def channel(c):
    return COL_X[c] + COL_W[c], COL_X[c + 1]


# ---------------------------------------------------------------- 主流程
def build(widths, facts):
    boxes = {bid: rect_of(bid) for bid in BOX_GEO}

    zones = []
    for c in range(6):
        ys = [BOX_GEO[b][1] for b in AD.BOX_IDS if BOX_GEO[b][0] == c]
        ye = [BOX_GEO[b][1] + BOX_GEO[b][2] for b in AD.BOX_IDS if BOX_GEO[b][0] == c]
        zones.append({"id": "zone%d" % c, "x": COL_X[c] - 3, "y": min(ys) - 38,
                      "w": COL_W[c] + 6, "h": (max(ye) - min(ys)) + 52,
                      "title": COL_TITLE[c]})

    # ---------- 1. 连接（同一对源/目标合并） ----------
    merged, order = {}, []
    for frm, to, nets in AD.WIRE_GROUPS:
        k = (frm, to)
        if k not in merged:
            merged[k] = {"from": frm, "to": to, "nets": list(nets)}
            order.append(k)
        else:
            for n in nets:
                if n not in merged[k]["nets"]:
                    merged[k]["nets"].append(n)
    wires = []
    for i, k in enumerate(order):
        m = merged[k]
        cf, ct = col_of(m["from"]), col_of(m["to"])
        if ct > cf:
            out_side, in_side = "right", "left"
        elif ct < cf:
            out_side, in_side = "left", "right"
        else:
            out_side, in_side = "right", "right"
        wires.append({"id": "w%02d" % i, "from": m["from"], "to": m["to"], "nets": m["nets"],
                      "cf": cf, "ct": ct, "out_side": out_side, "in_side": in_side,
                      "span": abs(ct - cf), "key": (m["from"], out_side)})

    # ---------- 2. 主干：每个 (源, 出线侧) 一条 ----------
    trunks = {}
    for w in wires:
        trunks.setdefault(w["key"], []).append(w)
    trunk_list = sorted(trunks.items())

    # 主干出线点 y = 源方框中心；竖直干线的 x 在"源侧第一个通道"里分配
    for i, (key, ws) in enumerate(trunk_list):
        src, side = key
        b = boxes[src]
        y_exit = b.cy
        cf = col_of(src)
        ch = cf if side == "right" else cf - 1
        for w in ws:
            w["y_exit"] = y_exit
            w["trunk_ch"] = ch

    # 顶部干线带：只有**真的用到带**的主干才占档位，否则两个不同源的主干会分到
    # 同一个 band_y，横段叠成一根（T1 返工 必修1：clk_gen|right 与 game_fsm|right
    # 原来都在 y=148）。
    band_keys = [key for key, ws in trunk_list if any(w["span"] >= 2 for w in ws)]
    for k, key in enumerate(band_keys):
        for w in trunks[key]:
            if w["span"] >= 2:
                w["band_y"] = BAND_Y0 + (k % 5) * BAND_DY

    # ---------- 3. 目标入口 y ----------
    def slots(n, lo, hi, gap=26.0):
        if n <= 0:
            return []
        g = min(gap, (hi - lo) / (n - 1)) if n > 1 else 0.0
        g = max(g, 14.0)
        if (n - 1) * g > hi - lo:
            g = max(9.0, (hi - lo) / max(1, n - 1))
        need = (n - 1) * g
        start = lo + ((hi - lo) - need) / 2.0
        return [start + i * g for i in range(n)]

    in_items = {}
    for w in wires:
        in_items.setdefault((w["to"], w["in_side"]), []).append(w)
    in_y = {}
    for (bid, side), items in in_items.items():
        items = sorted(items, key=lambda w: boxes[w["from"]].cy)
        b = boxes[bid]
        for w, y in zip(items, slots(len(items), b.y + 18, b.y1 - 18)):
            in_y[w["id"]] = y

    # ---------- 3b. 同一方框同一侧：入线口与出线口必须错开 ----------
    # 【T1 缺陷 4】某侧只有 1 条入线时 slots(1,...) 恰好取到方框中心，而主干出线口
    # 也正是方框中心 ⇒ 两根线在同一水平线上完全重合，读者看到的是"一个两端都带
    # 箭头的双向连接"（piece_rom↔puzzle_ctrl、glue_row↔seg_scan 都是这么来的）。
    # 数据本身是单向的，所以这里只挪附着点（lane / 端点），不改任何连线语义。
    lane_opts = {}      # (方框, 侧) -> [ (出线口 y, {线 id: 入线口 y}), ... ]
    for key in sorted(in_items):
        if key not in trunks:
            continue                       # 该侧没有出线主干，不可能重合
        bid, side = key
        b = boxes[bid]
        items = sorted(in_items[key], key=lambda w: boxes[w["from"]].cy)
        cur = [in_y[w["id"]] for w in items]
        if min(abs(y - b.cy) for y in cur) >= LANE_MERGE:
            continue                       # 本来就分得开
        lo, hi = b.y + LANE_INSET, b.y1 - LANE_INSET
        n = len(items)
        opts = []
        if n == 1:
            # 入线口与出线口各自可以在"原位 / 上移一格 / 下移一格"里挑，
            # 只要两者相距 >= LANE_GAP。给出全部组合，交给后面的贪心按
            # "全图交叉 + 视觉粘连"最少的准则挑。
            y_in = cur[0]
            lv = [y for y in (y_in - LANE_GAP, y_in, y_in + LANE_GAP) if lo <= y <= hi]
            for a in lv:
                for c in lv:
                    if abs(a - c) >= LANE_GAP - 1e-9:
                        opts.append((a, {items[0]["id"]: c}))
        else:
            # 入线口 + 出线口一起重新铺开，两两间距尽量 >= LANE_GAP
            gap = min(LANE_GAP, (hi - lo) / n) if n else 0.0
            start = lo + ((hi - lo) - n * gap) / 2.0
            pos = [start + i * gap for i in range(n + 1)]
            for k in range(n + 1):
                rest = [pos[i] for i in range(n + 1) if i != k]
                opts.append((pos[k], {w["id"]: y for w, y in zip(items, rest)}))
        lane_opts[key] = opts

    # ---------- 3c. 通道内 x 槽位：主干竖线与长途分支竖线**共用一套** ----------
    # 【T1 返工 必修1 / A2~A5】原来"主干 x"和"分支 lane x"各分一套、各自均分，
    # 两条不同源的竖线会算出同一个 x（788 / 988 / 1086 / 660），在图上叠成一根，
    # 读者顺着顶部 clk 主干下行会一路追到 rng_lfsr。现在同一个通道里的所有竖线
    # （不管是哪条主干的干线，还是某根长途线的分支 lane）统一排序、统一铺开，
    # 保证两两至少隔开 X_GAP。
    x_items = {}      # 通道号 -> [(排序键, 0=主干/1=分支, 对象), ...]
    for key, ws in trunk_list:
        x_items.setdefault(ws[0]["trunk_ch"], []).append((ws[0]["y_exit"], 0, key))
    for w in wires:
        if w["span"] >= 2:
            tc = w["ct"] - 1 if w["in_side"] == "left" else w["ct"]
            x_items.setdefault(tc, []).append((in_y[w["id"]], 1, w["id"]))
    trunk_x = {}
    lane_b = {}
    x_span = {}
    for ch, items in x_items.items():
        x0, x1 = channel(ch)
        lo, hi = x0 + X_INSET, x1 - X_INSET
        items.sort(key=lambda it: (it[0], it[1]))
        n = len(items)
        step = (hi - lo) / (n - 1) if n > 1 else 0.0
        for i, (yk, kind, obj) in enumerate(items):
            xv = lo + i * step if n > 1 else (lo + hi) / 2.0
            x_span[obj] = (lo, hi)
            if kind == 0:
                trunk_x[obj] = xv
            else:
                lane_b[obj] = xv

    # ---------- 4. 折线（全部从主干分叉） ----------
    def route(w):
        bf, bt = boxes[w["from"]], boxes[w["to"]]
        y_o = w["y_exit"]
        y_i = in_y[w["id"]]
        x_o = bf.x1 if w["out_side"] == "right" else bf.x
        x_i = bt.x if w["in_side"] == "left" else bt.x1
        xg = trunk_x[w["key"]]
        pts = [(x_o, y_o)]
        if w["span"] >= 2:
            xb = lane_b[w["id"]]
            seq = ((xg, y_o), (xg, w["band_y"]), (xb, w["band_y"]), (xb, y_i), (x_i, y_i))
        else:
            seq = ((xg, y_o), (xg, y_i), (x_i, y_i))
        for p in seq:
            if abs(p[0] - pts[-1][0]) > 0.5 or abs(p[1] - pts[-1][1]) > 0.5:
                pts.append(p)
        w["pts"] = pts

    for w in wires:
        route(w)

    def proper_cross(p0, p1, q0, q1):
        rx, ry = p1[0] - p0[0], p1[1] - p0[1]
        sx, sy = q1[0] - q0[0], q1[1] - q0[1]
        den = rx * sy - ry * sx
        if abs(den) < 1e-12:
            return False
        qpx, qpy = q0[0] - p0[0], q0[1] - p0[1]
        t = (qpx * sy - qpy * sx) / den
        u = (qpx * ry - qpy * rx) / den
        return 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9

    def cross_total():
        n = 0
        for i in range(len(wires)):
            pa = wires[i]["pts"]
            for j in range(i + 1, len(wires)):
                pb = wires[j]["pts"]
                for k in range(len(pa) - 1):
                    for m in range(len(pb) - 1):
                        if proper_cross(pa[k], pa[k + 1], pb[m], pb[m + 1]):
                            n += 1
        return n

    def merge_total():
        """跨主干、水平附着段"y 相近且 x 相邻/重叠"的线对数量。

        这种线对在图上会粘成**一根**连续的线：两端各有一个箭头时，读者会把它
        读成"双向连接"。所以它比一次普通交叉更糟，必须在选 lane 时一并避开。
        """
        segs = []
        for w in wires:
            pa = w["pts"]
            idx = {0, len(pa) - 2}
            for k in sorted(idx):
                (x0, y0), (x1, y1) = pa[k], pa[k + 1]
                if abs(y1 - y0) < 0.6 and abs(x1 - x0) > 2.0:
                    segs.append((w["key"], min(x0, x1), max(x0, x1), y0))
        n = 0
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                a, b = segs[i], segs[j]
                if a[0] == b[0]:
                    continue                       # 同一主干共用出线段，是有意的
                if abs(a[3] - b[3]) >= LANE_MERGE:
                    continue
                if min(a[2], b[2]) - max(a[1], b[1]) > -4.0:
                    n += 1
        return n

    def lane_cost():
        return cross_total() + 4 * merge_total()

    def apply_lane(key, idx):
        y_exit, ins = lane_opts[key][idx]
        for w in trunks[key]:
            w["y_exit"] = y_exit
            route(w)
        for w in in_items[key]:
            if w["id"] in ins:
                in_y[w["id"]] = ins[w["id"]]
                route(w)

    # 出线口"往上还是往下"是二选一，选哪个会影响全图交叉数与"视觉粘连"，所以
    # 以 (交叉数 + 4×粘连数) 为准则做一次贪心，确定性、不随机。
    lane_sel = {}
    for key, opts in sorted(lane_opts.items()):
        b = boxes[key[0]]
        lane_sel[key] = min(range(len(opts)),
                            key=lambda i: (abs(opts[i][0] - b.cy), opts[i][0]))
    for key in sorted(lane_opts):
        apply_lane(key, lane_sel[key])
    base = lane_cost()
    for key in sorted(lane_opts):
        best_i, best_c = lane_sel[key], base
        for i in range(len(lane_opts[key])):
            if i == lane_sel[key]:
                continue
            apply_lane(key, i)
            c = lane_cost()
            if c < best_c:
                best_i, best_c = i, c
            apply_lane(key, lane_sel[key])
        if best_i != lane_sel[key]:
            apply_lane(key, best_i)
            lane_sel[key], base = best_i, best_c

    # ---------- 4b. 跨主干"共线重合"清零（T1 返工 必修1 A1~A5） ----------
    # 两个不同源模块的水平段若 y 相差 < 8 px 且 x 相邻/重叠，draw.io 会把它画成
    # **一根连续直线**（"选择→引擎"的横段 970→988 与 w18 的 988→1104 就差 1 px）。
    # 3c 已经把竖线分开了，这里把剩下的水平级差逐对拉开：优先挪"入线口"，
    # 其次挪"出线口"、再挪"干线带档位"，每次只接受让重合对数下降的移动。
    by_id = {w["id"]: w for w in wires}

    def h_runs():
        runs = []
        for w in wires:
            pa = w["pts"]
            for k in range(len(pa) - 1):
                (x0, y0), (x1, y1) = pa[k], pa[k + 1]
                if abs(y1 - y0) >= 0.6 or abs(x1 - x0) <= 2.0:
                    continue
                if k == 0:
                    ctrl = ("exit", w["key"])
                elif k == len(pa) - 2:
                    ctrl = ("entry", w["id"])
                else:
                    ctrl = ("band", w["key"])
                runs.append((w["key"], min(x0, x1), max(x0, x1), y0, ctrl))
        return runs

    def h_conflicts():
        runs = h_runs()
        out = []
        for i in range(len(runs)):
            for j in range(i + 1, len(runs)):
                a, b = runs[i], runs[j]
                if a[0] == b[0]:
                    continue                       # 同一主干共用出线段，是有意的
                if abs(a[3] - b[3]) >= LANE_MERGE:
                    continue
                if min(a[2], b[2]) - max(a[1], b[1]) > -4.0:
                    out.append((a, b))
        return out

    def level_range(ctrl):
        kind, ref = ctrl
        if kind == "entry":
            b = boxes[by_id[ref]["to"]]
            return (b.y + LANE_INSET, b.y1 - LANE_INSET)
        if kind == "exit":
            b = boxes[ref[0]]
            return (b.y + LANE_INSET, b.y1 - LANE_INSET)
        return (BAND_Y0, BAND_Y0 + 4 * BAND_DY)

    def level_get(ctrl):
        kind, ref = ctrl
        if kind == "entry":
            return in_y[ref]
        if kind == "exit":
            return trunks[ref][0]["y_exit"]
        return trunks[ref][0]["band_y"]

    def level_set(ctrl, v):
        kind, ref = ctrl
        if kind == "entry":
            in_y[ref] = v
            route(by_id[ref])
        elif kind == "exit":
            for w in trunks[ref]:
                w["y_exit"] = v
                route(w)
        else:
            for w in trunks[ref]:
                if w["span"] >= 2:
                    w["band_y"] = v
                route(w)

    for _ in range(60):
        conf = h_conflicts()
        if not conf:
            break
        base_cross = cross_total()
        done = False
        for (a, b) in conf:
            for seg in (a, b):
                ctrl = seg[4]
                lo, hi = level_range(ctrl)
                cur = level_get(ctrl)
                for dv in (LANE_MERGE, -LANE_MERGE, 2 * LANE_MERGE, -2 * LANE_MERGE):
                    nv = cur + dv
                    if nv < lo or nv > hi or abs(nv - cur) < 1e-9:
                        continue
                    level_set(ctrl, nv)
                    nc = len(h_conflicts())
                    if nc < len(conf) or (nc == len(conf) and cross_total() < base_cross):
                        done = True
                        break
                    level_set(ctrl, cur)
                if done:
                    break
            if done:
                break
        if not done:
            break
    h_left = len(h_conflicts())

    # ---------- 5. 主干标签（贴在主干起点旁边） ----------
    all_segs = []
    for w in wires:
        for i in range(len(w["pts"]) - 1):
            all_segs.append((w["pts"][i], w["pts"][i + 1]))

    obstacles = [R(b.x, b.y, b.w, b.h) for b in boxes.values()]
    obstacles.append(R(0, 0, W, 104))
    obstacles.append(R(0, H - 40, W, 40))
    for z in zones:
        # 分区标题在 drawio 里是**左对齐**画在 z.x+10 的，这里必须用同一位置，
        # 否则障碍物与实际渲染错位。
        tw = text_w(z["title"], ZONE_SIZE)
        obstacles.append(R(z["x"] + 10, z["y"] + 6, tw, 20))
    placed = []

    def lrect(txt, x, y, anchor):
        wdt = text_w(txt, BUS_SIZE) + 10
        hgt = 22.0
        x0 = x if anchor == "start" else (x - wdt if anchor == "end" else x - wdt / 2)
        return R(x0, y - hgt / 2, wdt, hgt)

    def intrude(r, o, clear):
        """r 侵入"外扩 clear 的 o"有多深；0 表示两者间距 >= clear。

        这是"贴近惩罚"的核心：只有 0 和"穿过去"两档是不够的 —— 标签与线只差
        1~2 px 时，draw.io 渲染出来就是线切字（T1 缺陷 1/2 就是这么来的）。
        """
        ox0, oy0 = o.x - clear, o.y - clear
        ox1, oy1 = o.x1 + clear, o.y1 + clear
        ow = min(r.x1, ox1) - max(r.x, ox0)
        oh = min(r.y1, oy1) - max(r.y, oy0)
        if ow <= 0.0 or oh <= 0.0:
            return 0.0
        return min(ow, oh)

    def seg_box(p0, p1):
        return R(min(p0[0], p1[0]), min(p0[1], p1[1]),
                 abs(p1[0] - p0[0]), abs(p1[1] - p0[1]))

    seg_boxes = [(p0, p1, seg_box(p0, p1)) for (p0, p1) in all_segs]

    # 【T1 返工 必修A】分区虚线框的四条边：标签矩形必须离它们 >= LABEL_CLEAR
    # 且不许跨越。6 个 zone 只比模块框外扩 3 px，所以按"模块框边"定位的线名
    # 很容易贴到甚至跨到虚线上 —— 这里把四条边与连线同等对待。
    zone_edges = []
    for z in zones:
        zx0, zy0 = z["x"], z["y"]
        zx1, zy1 = z["x"] + z["w"], z["y"] + z["h"]
        for p0, p1 in (((zx0, zy0), (zx1, zy0)), ((zx0, zy1), (zx1, zy1)),
                       ((zx0, zy0), (zx0, zy1)), ((zx1, zy0), (zx1, zy1))):
            zone_edges.append((p0, p1, seg_box(p0, p1)))

    def rect_seg_dist(r, p0, p1):
        """矩形到线段的最短距离（0 = 相交）。"""
        if seg_rect(p0, p1, r):
            return 0.0
        bx = seg_box(p0, p1)
        dx = max(bx.x - r.x1, 0.0, r.x - bx.x1)
        dy = max(bx.y - r.y1, 0.0, r.y - bx.y1)
        d = (dx * dx + dy * dy) ** 0.5
        if d > 0.0:
            return d
        # 包围盒相交但线段本身没穿过矩形：退化成"矩形到线段端点"的估计
        best = 1e18
        for p in (p0, p1):
            ex = max(r.x - p[0], 0.0, p[0] - r.x1)
            ey = max(r.y - p[1], 0.0, p[1] - r.y1)
            best = min(best, (ex * ex + ey * ey) ** 0.5)
        return best

    def penalty(r, anchor, others=()):
        """分层罚分（量级差开，保证优先级严格）：

          1e9 · 真穿过 / 真重叠（线、分区虚线、方框、别的标签）
          1e6 · 10 px 净距的"亏欠深度"之和（线 / 分区虚线 / 方框 / 标签）
          1e3 · 到自己主干超过 LABEL_OWN_MAX 的部分
          8   · 到自己主干的距离本身（越小越贴）

        这样"宁可浮动也不能压线"是被量级保证的，而不是靠调系数碰运气。
        """
        hard = 0
        deficit = 0.0
        for o in obstacles:
            if intrude(r, o, 0.0) > 0.0:
                hard += 1
            d = intrude(r, o, LABEL_BOX_CLEAR)
            if d > 0.0:
                deficit += d
        for o in others:
            if intrude(r, o, 0.0) > 0.0:
                hard += 1
            d = intrude(r, o, LABEL_CLEAR)
            if d > 0.0:
                deficit += d
        for (p0, p1, bx) in seg_boxes:
            if seg_rect(p0, p1, r):
                hard += 1
            else:
                d = intrude(r, bx, LABEL_CLEAR)
                if d > 0.0:
                    deficit += d
        for (p0, p1, bx) in zone_edges:
            if seg_rect(p0, p1, r):
                hard += 1
            else:
                d = intrude(r, bx, LABEL_CLEAR)
                if d > 0.0:
                    deficit += d
        d_own = rect_seg_dist(r, anchor[0], anchor[1])
        excess = max(0.0, d_own - LABEL_OWN_MAX)
        return 1e9 * hard + 1e6 * deficit + 1e3 * excess + LABEL_NEAR * d_own

    def refine(txt, x, y, anc, anchor, others, span):
        """在粗网格最优点附近再细扫一遍（步长 3），找窄缝里的落点。"""
        best, bestp = None, None
        steps = int(span // 3)
        for dx in range(-steps, steps + 1):
            for dy in range(-steps, steps + 1):
                xx, yy = x + dx * 3.0, y + dy * 3.0
                r = lrect(txt, xx, yy, anc)
                if r.x < 6 or r.x1 > W - 6 or r.y < 6 or r.y1 > H - 26:
                    continue
                p = penalty(r, anchor, others)
                if bestp is None or p < bestp:
                    best, bestp = (xx, yy, anc, r), p
        return best, bestp

    def make_cands(b, x_out, xg, y_o):
        cands = []
        # 优先贴在"源方框与竖直干线之间那段水平出线"的上方 / 下方
        for fr in (0.5, 0.3, 0.7, 0.15, 0.85):
            x = x_out + (xg - x_out) * fr
            for k in (13, 24, 38, 54, 72, 92):
                cands.append((x, y_o - k, "middle"))
                cands.append((x, y_o + k, "middle"))
        # 贴着源方框的外侧上 / 下
        for k in (16, 30, 46, 64):
            cands.append((b.x1 + 8, b.y + k, "start"))
            cands.append((b.x1 + 8, b.y1 - k, "start"))
            cands.append((b.x - 8, b.y + k, "end"))
            cands.append((b.x - 8, b.y1 - k, "end"))
        # 兜底：源方框周围的网格（比 v3 扩大一圈，给"必须留 10 px"留出落点）
        for gx in range(int(b.x) - 170, int(b.x1) + 171, 12):
            for gy in range(int(b.y) - 100, int(b.y1) + 101, 12):
                cands.append((gx, gy, "middle"))
        return cands

    def place_label(key, others):
        """为某根主干找标签落点（others = 其它已放标签的矩形）。

        返回 (x, y, anchor, rect, penalty)；找不到返回 None。
        """
        txt = TRUNK_CN.get(key, "")
        if not txt:
            return None
        w0 = trunks[key][0]
        b = boxes[key[0]]
        xg = trunk_x[key]
        y_o = w0["y_exit"]
        x_out = b.x1 if key[1] == "right" else b.x
        anchor = ((x_out, y_o), (xg, y_o))      # 该主干自己的出线段
        best, bestp = None, None
        for (x, y, anc) in make_cands(b, x_out, xg, y_o):
            r = lrect(txt, x, y, anc)
            if r.x < 6 or r.x1 > W - 6 or r.y < 6 or r.y1 > H - 26:
                continue
            p = penalty(r, anchor, others)
            if bestp is None or p < bestp:
                best, bestp = (x, y, anc, r), p
        if best is None:
            return None
        # 粗网格步长 10 px，窄缝（例如通道净宽 38 px）可能正好被跨过，
        # 所以在最优点附近按 2 px 再扫一遍。
        fine, finep = refine(txt, best[0], best[1], best[2], anchor, others, 12.0)
        if fine is not None and finep is not None and finep < bestp:
            best, bestp = fine, finep
        return (best[0], best[1], best[2], best[3], bestp)

    def d_own_of(key, r):
        w0 = trunks[key][0]
        b = boxes[key[0]]
        x_out = b.x1 if key[1] == "right" else b.x
        return rect_seg_dist(r, (x_out, w0["y_exit"]), (trunk_x[key], w0["y_exit"]))

    label_order = [k for k, _ws in trunk_list if TRUNK_CN.get(k)]
    labels_sel = {}
    for key in label_order:
        others = [labels_sel[k][3] for k in label_order if k in labels_sel]
        got = place_label(key, others)
        if got is not None:
            labels_sel[key] = got

    # ---------- 5b. 关联精修（T1 返工 C） ----------
    # 有的主干出线口正好卡在分区虚线框边（例如 game_fsm 的 y=388 距 zone2 右边
    # 只有 3 px），标签为了躲虚线只能飘到 100 px 外。把"出线口 y"也当成可调量：
    # 在方框内试几个位置，谁能让标签既守住所有净距、又贴回自己那根线，就用谁。
    # 判据必须包含 penalty 本身（它才是"零跨越 + 10 px 净距"的保证），
    # 否则会出现"标签压在自己线上但 d_own=0"这种假优胜。
    for _pass in range(2):
      for key in label_order:
        if key not in labels_sel:
            continue
        cur_r = labels_sel[key][3]
        if d_own_of(key, cur_r) <= LABEL_OWN_MAX:
            continue                       # 已经贴上了，不用动
        cur_y = trunks[key][0]["y_exit"]
        b = boxes[key[0]]
        lo, hi = b.y + LANE_INSET, b.y1 - LANE_INSET
        best_score, best_sel = (len(h_conflicts()), labels_sel[key][4]), None
        for yv in sorted({cur_y - 48, cur_y - 32, cur_y - 16,
                          cur_y + 16, cur_y + 32, cur_y + 48}):
            if yv < lo or yv > hi:
                continue
            for w in trunks[key]:
                w["y_exit"] = yv
                route(w)
            others = [labels_sel[k][3] for k in label_order
                      if k != key and k in labels_sel]
            got = place_label(key, others)
            if got is not None:
                score = (len(h_conflicts()), got[4])
                if score < best_score:
                    best_score, best_sel = score, (yv, got)
            for w in trunks[key]:
                w["y_exit"] = cur_y
                route(w)
        if best_sel is not None:
            yv, got = best_sel
            for w in trunks[key]:
                w["y_exit"] = yv
                route(w)
            labels_sel[key] = got

    for key in label_order:
        if key not in labels_sel:
            continue
        x, y, anc, r, _p = labels_sel[key]
        w0 = trunks[key][0]
        txt = TRUNK_CN[key]
        w0["label"] = {"text": txt, "x": round(x, 2), "y": round(y, 2),
                       "anchor": anc, "size": BUS_SIZE,
                       "w": round(text_w(txt, BUS_SIZE) + 10, 2)}
        placed.append(r)

    # ---------- 6. layout JSON ----------
    lay_boxes = []
    for bid in AD.BOX_IDS:
        c, y, h = BOX_GEO[bid]
        b = {"id": bid, "x": COL_X[c], "y": y, "w": COL_W[c], "h": h}
        if bid in AD.ENTITIES:
            b.update({"kind": "entity", "file": AD.ENTITIES[bid]["file"],
                      "title": AD.ENTITIES[bid]["title"], "sub": CN[bid],
                      "title_size": ENT_TITLE, "sub_size": ENT_SUB,
                      "globals": AD.GLOBALS[bid],
                      "text_w": round(max(text_w(AD.ENTITIES[bid]["title"], ENT_TITLE),
                                          text_w(CN[bid], ENT_SUB)), 2)})
        elif bid in AD.EXTERNAL:
            # 【T1 返工 D】ext_* 框内固定三行（器件名 / 中文名 / 引脚），换行由
            # 这里给定，draw.io 不许自己断行（原来 "50 MHz 有源晶振" 被断成
            # "50 MHz 有源晶" / "振"）。title/sub 仍填第 1/2 行，lines 给全三行。
            b.update({"kind": "ext",
                      "title": EXT_LINES[bid][0], "sub": EXT_LINES[bid][1],
                      "lines": [EXT_LINES[bid][0], EXT_LINES[bid][1], EXT_SUB_TEXT[bid]],
                      "title_size": EXT_TITLE, "sub_size": EXT_SUB, "globals": [],
                      "text_w": round(max(text_w(EXT_LINES[bid][0], EXT_TITLE),
                                          text_w(EXT_LINES[bid][1], EXT_TITLE),
                                          text_w(EXT_SUB_TEXT[bid], EXT_SUB)), 2)})
        else:
            b.update({"kind": "glue", "title": GLUE_CN[bid], "sub": GLUE_SUBTITLE[bid],
                      "title_size": GLUE_TITLE, "sub_size": GLUE_SUB,
                      "globals": AD.GLOBALS[bid],
                      "text_w": round(max(text_w(GLUE_CN[bid], GLUE_TITLE),
                                          text_w(GLUE_SUBTITLE[bid], GLUE_SUB)), 2)})
        lay_boxes.append(b)

    lay_wires = []
    for w in wires:
        rec = {"id": w["id"], "from": w["from"], "to": w["to"],
               "from_side": w["out_side"], "to_side": w["in_side"],
               "pts": [[round(p[0], 2), round(p[1], 2)] for p in w["pts"]],
               "nets": w["nets"], "width_px": 1.9,
               "trunk": "%s|%s" % w["key"]}
        if w.get("label"):
            rec["label"] = w["label"]
        lay_wires.append(rec)
    layout = {"id": NAME, "canvas": {"w": W, "h": H}, "boxes": lay_boxes,
              "zones": zones, "wires": lay_wires}
    return {"svg": svg(lay_boxes, zones, lay_wires, wires), "layout": layout,
            "w": W, "h": H}


# ---------------------------------------------------------------- SVG
def svg(lay_boxes, zones, lay_wires, wires):
    core = {"puzzle_ctrl"}
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (W, H, W, H),
         '<defs>'
         '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.2" '
         'markerHeight="6.2" orient="auto-start-reverse">'
         '<path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker>'
         '<marker id="ar2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.2" '
         'markerHeight="6.2" orient="auto-start-reverse">'
         '<path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>'
         % (LINE, CORE_LINE),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H)]

    p.append('<text x="%d" y="44" font-family="%s" font-size="%d" font-weight="bold" fill="%s" '
             'text-anchor="middle">题目 4：简易拼图游戏 —— 系统总体框图</text>'
             % (W // 2, FONT, TITLE_SIZE, INK))
    p.append('<text x="%d" y="72" font-family="%s" font-size="%d" fill="#475569" '
             'text-anchor="middle">每个实线框 = rtl/&lt;同名&gt;.vhd 中的一个 entity；'
             '同一个源模块出去的线共用一条主干，箭头旁标的是信号组名（网名与位宽见正文模块接口表）</text>'
             % (W // 2, FONT, SUBTITLE_SIZE))

    for z in zones:
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" '
                 'stroke-width="1.3" stroke-dasharray="7 6"/>'
                 % (z["x"], z["y"], z["w"], z["h"], ZONE_FILL, ZONE_LINE))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%d" font-weight="bold" '
                 'fill="%s" text-anchor="middle">%s</text>'
                 % (z["x"] + z["w"] // 2, z["y"] + 20, FONT, ZONE_SIZE, MUTED, esc(z["title"])))

    for lw in lay_wires:
        col = CORE_LINE if lw["from"] in core else LINE
        d = "M " + " L ".join("%.1f %.1f" % (q[0], q[1]) for q in lw["pts"])
        mk = "ar2" if lw["from"] in core else "ar"
        p.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" '
                 'stroke-linejoin="round" marker-end="url(#%s)"/>' % (d, col, lw["width_px"], mk))

    for b in lay_boxes:
        bid = b["id"]
        if b["kind"] == "ext":
            fill, stroke, dash, sw = EXT_FILL, EXT_LINE, '', 1.8
        elif b["kind"] == "glue":
            fill, stroke, dash, sw = GLUE_FILL, GLUE_LINE, ' stroke-dasharray="7 5"', 2.0
        elif bid in core:
            fill, stroke, dash, sw = CORE_FILL, CORE_LINE, '', 2.4
        else:
            fill, stroke, dash, sw = "#ffffff", LINE, '', 2.2
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="7" fill="%s" stroke="%s" '
                 'stroke-width="%.1f"%s/>' % (b["x"], b["y"], b["w"], b["h"], fill, stroke, sw, dash))
        cx = b["x"] + b["w"] / 2
        if b["kind"] == "ext":
            l1, l2 = EXT_LINES[bid]
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%d" font-weight="bold" '
                     'fill="%s" text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 23, FONT, EXT_TITLE, INK, esc(l1)))
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%d" fill="%s" '
                     'text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 41, FONT, EXT_TITLE, INK, esc(l2)))
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%.1f" fill="%s" '
                     'text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 57, MONO, EXT_SUB, MUTED, esc(EXT_SUB_TEXT[bid])))
        else:
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%.1f" font-weight="bold" '
                     'fill="%s" text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 30, FONT, b["title_size"], INK, esc(b["title"])))
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%.1f" fill="#475569" '
                     'text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 50, FONT, b["sub_size"], esc(b["sub"])))
        g = b.get("globals") or []
        if g:
            p.append('<text x="%d" y="%d" font-family="%s" font-size="%.1f" fill="#94a3b8">%s</text>'
                     % (b["x"] + 6, b["y"] + b["h"] - 6, MONO, TAG_SIZE, esc("·".join(g))))

    for lw in lay_wires:
        lb = lw.get("label")
        if not lb:
            continue
        wdt = text_w(lb["text"], lb["size"]) + 10
        x0 = lb["x"] if lb["anchor"] == "start" else (lb["x"] - wdt if lb["anchor"] == "end"
                                                      else lb["x"] - wdt / 2)
        y0 = lb["y"] - 11
        p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="22" rx="3" fill="#ffffff" '
                 'fill-opacity="0.93"/>' % (x0, y0, wdt))
        p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" fill="#1e293b" '
                 'text-anchor="middle">%s</text>'
                 % (lb["x"], lb["y"] + 6, FONT, lb["size"], esc(lb["text"])))

    for i, t in enumerate(NOTE_LINES):
        p.append('<text x="16" y="%d" font-family="%s" font-size="%.1f" fill="#334155">%s</text>'
                 % (NOTE_Y + i * 20, FONT, NOTE_SIZE, t))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def main():
    argv = sys.argv[1:]
    res = build(AD.net_widths(), AD.load_facts())
    if "--dump" in argv:
        dst = argv[argv.index("--dump") + 1]
        with open(dst, "w", encoding="utf-8") as fh:
            json.dump(res["layout"], fh, ensure_ascii=False, indent=1)
        print("layout -> %s" % dst)
    if "--svg" in argv:
        dst = argv[argv.index("--svg") + 1]
        with open(dst, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(res["svg"])
        print("svg -> %s (%d B)" % (dst, len(res["svg"].encode("utf-8"))))
    if not argv:
        print("画布 %dx%d，方框 %d，连线 %d，主干标签 %d"
              % (W, H, len(res["layout"]["boxes"]), len(res["layout"]["wires"]),
                 sum(1 for w in res["layout"]["wires"] if w.get("label"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
