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
DESC = "六列分层 + 总线主干与分支 + 主干命名 + 底部连接明细表"

# ---------------------------------------------------------------- 画布与字号
W, H = 1516, 1430
FONT = "Microsoft YaHei, SimSun, sans-serif"
MONO = "Consolas, Courier New, monospace"

TITLE_SIZE = 27
SUBTITLE_SIZE = 15
ZONE_SIZE = 14
ENT_TITLE = 18.5
ENT_SUB = 12.5
GLUE_TITLE = 15
GLUE_SUB = 11.5
EXT_TITLE = 14
EXT_SUB = 11.5
TAG_SIZE = 11
BUS_SIZE = 16
LEGEND_SIZE = 13
NOTE_SIZE = 12.5

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
COL_X = [24, 192, 462, 806, 1104, 1372]
COL_W = [104, 146, 180, 164, 190, 104]
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
    "disp_format": "数码管段码",
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
EXT_SUB_TEXT = {"ext_clk": "PIN_18", "ext_btn": "PIN_61", "ext_sw": "PIN_125",
                "ext_kp": "kp_row/col", "ext_seg": "seg / cat",
                "ext_dot": "ROW/COL", "ext_buzz": "PIN_60"}

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
    ("glue_pat", "right"): "图案选择",
    ("glue_pat", "left"): "图案选择",
    ("glue_row", "right"): "行切片",
    ("disp_format", "right"): "段码",
    ("seg_scan", "right"): "段/位选",
    ("buzzer_ctrl", "right"): "蜂鸣",
}

BAND_Y0, BAND_DY = 128, 20
LEGEND_Y = 1010
NOTE_Y = 1340
NOTE_LINES = [
    "图例：实线框 = rtl/&lt;同名&gt;.vhd 中的一个 entity（共 11 个，与 puzzle_top.vhd 的 11 条 component 声明、11 个 u_* 例化三方一致）；"
    "虚线框 = 顶层胶合逻辑（非 entity）；浅灰框 = 板载器件",
    "方框左下角角标 = 该模块消费的全局网络：clk 50 MHz ← 有源晶振、rst ← clk_gen、sw7 使能 ← SW7；"
    "这三路是一对多分配（消费者 8 / 8 / 4 个），逐根画会得到 20 根长线，故用角标表达",
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
            if w["span"] >= 2:
                w["band_y"] = BAND_Y0 + (i % 5) * BAND_DY

    # 通道内分配主干 x
    trunk_x = {}
    per_channel = {}
    for key, ws in trunk_list:
        per_channel.setdefault(ws[0]["trunk_ch"], []).append(key)
    for ch, keys in per_channel.items():
        x0, x1 = channel(ch)
        lo, hi = x0 + 18.0, x1 - 18.0
        keys.sort(key=lambda k: boxes[k[0]].cy)
        n = len(keys)
        step = (hi - lo) / (n - 1) if n > 1 else 0.0
        for i, k in enumerate(keys):
            trunk_x[k] = lo + i * step if n > 1 else (lo + hi) / 2.0

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

    # 长途分叉：目标侧通道里每个目标一个 lane x
    lane_b = {}
    by_target_ch = {}
    for w in wires:
        if w["span"] >= 2:
            tc = w["ct"] - 1 if w["in_side"] == "left" else w["ct"]
            by_target_ch.setdefault(tc, []).append(w)
    for tc, ws in by_target_ch.items():
        x0, x1 = channel(tc)
        lo, hi = x0 + 18.0, x1 - 18.0
        n = len(ws)
        step = (hi - lo) / (n - 1) if n > 1 else 0.0
        for i, w in enumerate(sorted(ws, key=lambda w: in_y[w["id"]])):
            lane_b[w["id"]] = lo + i * step if n > 1 else (lo + hi) / 2.0

    # ---------- 4. 折线（全部从主干分叉） ----------
    for w in wires:
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

    # ---------- 5. 主干标签（贴在主干起点旁边） ----------
    all_segs = []
    for w in wires:
        for i in range(len(w["pts"]) - 1):
            all_segs.append((w["pts"][i], w["pts"][i + 1]))

    obstacles = [R(b.x, b.y, b.w, b.h) for b in boxes.values()]
    obstacles.append(R(0, 0, W, 104))
    obstacles.append(R(0, LEGEND_Y - 12, W, H - LEGEND_Y + 12))
    for z in zones:
        tw = text_w(z["title"], ZONE_SIZE)
        obstacles.append(R(z["x"] + z["w"] / 2 - tw / 2, z["y"] + 6, tw, 20))
    placed = []

    def lrect(txt, x, y, anchor):
        wdt = text_w(txt, BUS_SIZE) + 10
        hgt = 22.0
        x0 = x if anchor == "start" else (x - wdt if anchor == "end" else x - wdt / 2)
        return R(x0, y - hgt / 2, wdt, hgt)

    def penalty(r):
        p = 0.0
        for o in obstacles:
            oo = R(o.x - 3, o.y - 3, o.w + 6, o.h + 6)
            if overlap(r, oo, 0.0):
                p += (min(r.x1, oo.x1) - max(r.x, oo.x)) * (min(r.y1, oo.y1) - max(r.y, oo.y))
        for o in placed:
            oo = R(o.x - 2, o.y - 2, o.w + 4, o.h + 4)
            if overlap(r, oo, 0.0):
                p += 3.0 * (min(r.x1, oo.x1) - max(r.x, oo.x)) * (min(r.y1, oo.y1) - max(r.y, oo.y))
        for (p0, p1) in all_segs:
            if seg_rect(p0, p1, r):
                p += 5000.0
        return p

    for key, ws in trunk_list:
        txt = TRUNK_CN.get(key, "")
        if not txt:
            continue
        w0 = ws[0]
        src = key[0]
        b = boxes[src]
        xg = trunk_x[key]
        y_o = w0["y_exit"]
        x_out = b.x1 if key[1] == "right" else b.x
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
        # 兜底：源方框周围的网格
        for gx in range(int(b.x) - 130, int(b.x1) + 131, 12):
            for gy in range(int(b.y) - 60, int(b.y1) + 61, 12):
                cands.append((gx, gy, "middle"))
        best, bestp = None, None
        for (x, y, anc) in cands:
            r = lrect(txt, x, y, anc)
            if r.x < 6 or r.x1 > W - 6 or r.y < 6 or r.y1 > LEGEND_Y - 14:
                continue
            p = penalty(r)
            if p == 0.0:
                best = (x, y, anc, r)
                break
            if bestp is None or p < bestp:
                best, bestp = (x, y, anc, r), p
        if best is None:
            continue
        w0["label"] = {"text": txt, "x": round(best[0], 2), "y": round(best[1], 2),
                       "anchor": best[2], "size": BUS_SIZE}
        placed.append(best[3])

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
            b.update({"kind": "ext", "title": AD.EXTERNAL[bid]["title"],
                      "sub": AD.EXTERNAL[bid]["sub"],
                      "title_size": EXT_TITLE, "sub_size": EXT_SUB, "globals": [],
                      "text_w": round(max(text_w(EXT_LINES[bid][0], EXT_TITLE),
                                          text_w(EXT_LINES[bid][1], EXT_TITLE),
                                          text_w(EXT_SUB_TEXT[bid], EXT_SUB)), 2)})
        else:
            b.update({"kind": "glue", "title": GLUE_CN[bid], "sub": "非 entity",
                      "title_size": GLUE_TITLE, "sub_size": GLUE_SUB,
                      "globals": AD.GLOBALS[bid],
                      "text_w": round(max(text_w(GLUE_CN[bid], GLUE_TITLE),
                                          text_w("非 entity", GLUE_SUB)), 2)})
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
             '同一个源模块出去的线共用一条主干（箭头旁为信号组名），'
             '主干上的每条连接见下方明细表</text>' % (W // 2, FONT, SUBTITLE_SIZE))

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

    # ---- 底部：主干明细表（源 → 目标：网名[位宽]） ----
    p.append('<text x="18" y="%d" font-family="%s" font-size="14" font-weight="bold" '
             'fill="%s">主干明细（每条连接 = puzzle_top.vhd 例化时的一行端口映射；'
             '「源 → 目标：网名[位宽]」）</text>' % (LEGEND_Y, FONT, INK))
    rows = []
    for w in wires:
        rows.append("%s → %s：%s" % (w["from"], w["to"],
                                     "/".join(AD.net_label(n, None) for n in w["nets"])))
    ncol = 2
    per = (len(rows) + ncol - 1) // ncol
    colw = (W - 36) // ncol
    for i, txt in enumerate(rows):
        cx0 = 18 + (i // per) * colw
        cy = LEGEND_Y + 26 + (i % per) * 18
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%.1f" fill="#334155">%s</text>'
                 % (cx0, cy, MONO, LEGEND_SIZE, esc(txt)))

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
