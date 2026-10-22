#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fig1_layout.py —— 「系统总体框图」的布局引擎（数据来自 arch_data，本文件只管画）

【设计目标】
    1. **与代码一致**：方框集合、连线、网名、位宽、全局网络全部来自 `scripts/arch_data.py`，
       本文件一个网名都不手写。
    2. **零穿框**：走线只在「列间空通道」与「顶部干线带」里走，绝不穿过任何方框内部。
    3. **可读**：每个箭头一个网名标签（可多行），标签自动避让（不压框、不互相重叠）。
    4. **层次清楚**：11 个 entity（实线框）+ 2 个顶层胶合块（虚线框）+ 7 个板载器件（浅灰框）；
       子系统用竖直虚线分区带表达；每个模块左下角标出它消费的全局网络。

【布局结构】
    6 个竖直列：板载输入 → 时钟/采集 → 主控与存储 → 引擎与胶合 → 显示/音频 → 板载输出。
    列与列之间是**没有任何方框的空通道**，走线只在这里拐弯。
    跨列（跳过至少一列）的信号走顶部**干线带**：同一个源、同一组网名的长途信号
    共用一条干线（= 一根总线出线），到各自的目的地再分开下潜。

【三种走线】
    · 相邻列 / 同列：源侧出 → 通道内专用竖直 lane → 目标侧入（同列则 U 形回折）。
    · 跨列：源侧出 → 通道 lane → 顶部干线 → 目标侧通道 lane → 目标侧入。
    每一段都落在空通道或干线带里 ⇒ 结构上不可能穿过方框。

【自检】
    python scripts/fig1_layout.py --dump .tmp/cand/layout_new.json --svg .tmp/cand/fig1_new.svg
    python scripts/arch_data.py --verify-layout .tmp/cand/layout_new.json
    python scripts/audit_diagram.py .tmp/cand/layout_new.json --fidelity
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arch_data as AD  # noqa: E402

NAME = "new"
DESC = "六列分层 + 空通道正交走线 + 顶部干线带 + 自动标签避让"

# ---------------------------------------------------------------- 画布与字号
W, H = 1490, 1180
FONT = "Microsoft YaHei, SimSun, sans-serif"
MONO = "Consolas, Courier New, monospace"

TITLE_SIZE = 26
SUBTITLE_SIZE = 14
ZONE_SIZE = 14
ENT_TITLE = 19
ENT_SUB = 13
GLUE_TITLE = 15
GLUE_SUB = 11.5
EXT_TITLE = 14
EXT_SUB = 11.5
TAG_SIZE = 11
LABEL_SIZE = 18
NOTE_SIZE = 13

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
COL_X = [24, 196, 476, 830, 1140, 1366]
COL_W = [104, 150, 158, 156, 156, 100]
COL_TITLE = ["板载输入器件", "时钟与输入采集", "主控 · 存储 · 随机源",
             "核心引擎与顶层胶合", "显示与音频输出", "板载输出器件"]

BOX_GEO = {
    "ext_clk":         (0, 360, 70),
    "ext_btn":         (0, 490, 70),
    "ext_sw":          (0, 620, 70),
    "ext_kp":          (0, 900, 70),
    "clk_gen":         (1, 330, 124),
    "keypad_scan":     (1, 880, 84),
    "game_fsm":        (2, 300, 200),
    "piece_rom":       (2, 600, 84),
    "pattern_rom":     (2, 730, 84),
    "rng_lfsr":        (2, 860, 84),
    "glue_pat":        (3, 300, 80),
    "glue_row":        (3, 430, 80),
    "puzzle_ctrl":     (3, 640, 210),
    "disp_format":     (4, 300, 84),
    "seg_scan":        (4, 430, 84),
    "dot_matrix_scan": (4, 560, 84),
    "buzzer_ctrl":     (4, 790, 84),
    "ext_seg":         (5, 320, 70),
    "ext_dot":         (5, 570, 70),
    "ext_buzz":        (5, 800, 70),
}

CN = {
    "clk_gen": "分频 / 复位",
    "keypad_scan": "键盘扫描 / 消抖",
    "game_fsm": "游戏主状态机",
    "piece_rom": "零片掩码表",
    "pattern_rom": "目标图案库",
    "rng_lfsr": "8 位 LFSR 随机源",
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
GLUE_CN = {"glue_pat": "图案选择锁存", "glue_row": "行计数器 + 行切片"}
# 画在浅灰框里的引脚小字（比 arch_data 里的更短，免得撑破窄框）
EXT_SUB_TEXT = {"ext_clk": "PIN_18", "ext_btn": "PIN_61", "ext_sw": "PIN_125",
                "ext_kp": "kp_row/kp_col", "ext_seg": "seg / cat",
                "ext_dot": "ROW/COLR/COLG", "ext_buzz": "PIN_60"}

BAND_Y0, BAND_DY = 132, 20
NOTE_Y = 1078
NOTE_LINES = [
    "图例：实线框 = rtl/&lt;同名&gt;.vhd 中的一个 entity（共 11 个，与 puzzle_top.vhd 的 11 条 component 声明、11 个 u_* 例化三方一致）；"
    "虚线框 = puzzle_top.vhd 内的顶层胶合逻辑（不是独立 entity）；浅灰框 = 板载器件",
    "箭头 = puzzle_top.vhd 例化时的端口连接（formal ← actual 网名），标注位宽 [MSB:LSB]；"
    "方框左下角角标 = 该模块消费的全局网络：clk 50 MHz（← 有源晶振）、rst（← clk_gen）、sw7 使能（← SW7）",
    "如实说明：clk_gen 的 t_100 / t_40 / o_tick_2hz 三路输出在顶层无人消费（仅板级诊断顶层使用）；"
    "piece_rom.o_n（piece_n）未被消费 —— 与 Quartus “assigned a value but never read” 警告一致",
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
    """与 scripts/audit_diagram.py 完全一致的标签宽度估值。"""
    t = 0.0
    for ch in text:
        t += (1.0 if ord(ch) > 0x2E7F else 0.62) * size
    return t + 12.0


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

    # ---------- 0. 分区带（虚线大框 + 标题） ----------
    zones = []
    for c in range(6):
        ys = [BOX_GEO[b][1] for b in AD.BOX_IDS if BOX_GEO[b][0] == c]
        ye = [BOX_GEO[b][1] + BOX_GEO[b][2] for b in AD.BOX_IDS if BOX_GEO[b][0] == c]
        zones.append({"id": "zone%d" % c, "x": COL_X[c] - 3, "y": min(ys) - 40,
                      "w": COL_W[c] + 6, "h": (max(ye) - min(ys)) + 54,
                      "title": COL_TITLE[c]})

    # ---------- 1. 连线分类 ----------
    wires = []
    for frm, to, nets in AD.WIRE_GROUPS:
        cf, ct = col_of(frm), col_of(to)
        if ct > cf:
            out_side, in_side = "right", "left"
        elif ct < cf:
            out_side, in_side = "left", "right"
        else:
            out_side, in_side = "right", "right"
        wires.append({"id": "w%02d" % len(wires), "from": frm, "to": to, "nets": list(nets),
                      "cf": cf, "ct": ct, "out_side": out_side, "in_side": in_side,
                      "span": abs(ct - cf)})

    # ---------- 1b. 同一对 (源,目标) 的多根线合并成一根总线 ----------
    # 目的：game_fsm → puzzle_ctrl 本来有 3 根（命令脉冲 / 方向 / 关卡），
    # 三根并排会把中段通道塞满；合并成一根、标签分 3 行列出全部网名，
    # 三元组覆盖不变（fidelity 仍然逐个对账）。
    merged, order = {}, []
    for w in wires:
        k = (w["from"], w["to"])
        if k not in merged:
            merged[k] = dict(w)
            order.append(k)
        else:
            for n in w["nets"]:
                if n not in merged[k]["nets"]:
                    merged[k]["nets"].append(n)
    wires = [merged[k] for k in order]
    for i, w in enumerate(wires):
        w["id"] = "w%02d" % i

    # ---------- 2. 干线分组 ----------
    band_groups = {}
    for w in wires:
        if w["span"] >= 2:
            key = (w["from"], w["out_side"], tuple(sorted(w["nets"])))
            band_groups.setdefault(key, []).append(w)
    for i, (key, ws) in enumerate(sorted(band_groups.items(),
                                         key=lambda kv: (kv[0][0], kv[0][2]))):
        for w in ws:
            w["band_y"] = BAND_Y0 + i * BAND_DY
            w["band_key"] = key

    # ---------- 3. 出口 / 入口在方框边上的 y ----------
    def slots(n, lo, hi, gap=30.0, min_gap=11.0):
        """把 n 个接线点铺满整条边（间距不超过 gap，太挤才压到 min_gap）。"""
        if n <= 0:
            return []
        g = min(gap, (hi - lo) / (n - 1)) if n > 1 else 0.0
        g = max(g, min_gap)
        if (n - 1) * g > hi - lo:
            g = max(min_gap, (hi - lo) / max(1, n - 1))
        need = (n - 1) * g
        start = lo + ((hi - lo) - need) / 2.0
        return [start + i * g for i in range(n)]

    out_items, in_items = {}, {}
    for w in wires:
        out_items.setdefault((w["from"], w["out_side"]), []).append(w)
        in_items.setdefault((w["to"], w["in_side"]), []).append(w)

    def other_cy(w, at_source):
        return boxes[w["to"] if at_source else w["from"]].cy

    out_y, in_y = {}, {}
    for (bid, side), items in out_items.items():
        groups, seen = [], {}
        for w in items:
            k = w.get("band_key") if w.get("band_key") else ("one", w["id"])
            seen.setdefault(k, []).append(w)
            if len(seen[k]) == 1:
                groups.append(seen[k])
        groups.sort(key=lambda g: other_cy(g[0], True))
        b = boxes[bid]
        lo, hi = (b.y + 15, b.y1 - 15)
        for g, y in zip(groups, slots(len(groups), lo, hi)):
            for w in g:
                out_y[w["id"]] = y
    for (bid, side), items in in_items.items():
        items = sorted(items, key=lambda w: other_cy(w, False))
        b = boxes[bid]
        for w, y in zip(items, slots(len(items), b.y + 15, b.y1 - 15)):
            in_y[w["id"]] = y

    # ---------- 4. 通道 lane 分配 ----------
    # 每个通道把竖直 lane 分到三个区：L（方框在通道左侧）/ M（相邻列 Z 形）/ R（方框在通道右侧）
    reqs = {}          # channel -> list of dict(w, tag, bucket, key)
    for w in wires:
        cf, ct, span = w["cf"], w["ct"], w["span"]
        if span >= 2:
            sc = cf if w["out_side"] == "right" else cf - 1
            tc = ct - 1 if w["in_side"] == "left" else ct
            reqs.setdefault(sc, []).append(
                {"w": w, "tag": "a", "bucket": "L" if w["out_side"] == "right" else "R",
                 "key": out_y[w["id"]]})
            reqs.setdefault(tc, []).append(
                {"w": w, "tag": "b", "bucket": "R" if w["in_side"] == "left" else "L",
                 "key": in_y[w["id"]]})
        else:
            c = min(cf, ct)
            y0 = out_y[w["id"]] if w["out_side"] == "right" else in_y[w["id"]]
            y1 = in_y[w["id"]] if ct >= cf else out_y[w["id"]]
            reqs.setdefault(c, []).append(
                {"w": w, "tag": "m", "bucket": "M", "key": (y0 + y1) / 2.0})

    lane_x = {}
    for c, rs in reqs.items():
        x0, x1 = channel(c)
        lo, hi = x0 + 13.0, x1 - 13.0
        total = hi - lo
        buckets = {"L": [], "M": [], "R": []}
        # 同一条干线的 a-lane 合并成一个 lane
        merged, seen = [], {}
        for r in rs:
            if r["tag"] == "a" and r["w"].get("band_key"):
                k = ("band", r["w"]["band_key"])
            else:
                k = ("one", r["w"]["id"], r["tag"])
            seen.setdefault(k, []).append(r)
            if len(seen[k]) == 1:
                merged.append(seen[k])
        for grp in merged:
            grp.sort(key=lambda r: r["key"])
            buckets[grp[0]["bucket"]].append(grp)
        nL, nM, nR = len(buckets["L"]), len(buckets["M"]), len(buckets["R"])
        n = nL + nM + nR
        if n == 0:
            continue
        # 按数量比例切三段
        spanL = total * (nL / n) if n else 0
        spanM = total * (nM / n) if n else 0
        spanR = total - spanL - spanM
        for name, grps, a, width in (("L", buckets["L"], lo, spanL),
                                     ("M", buckets["M"], lo + spanL, spanM),
                                     ("R", buckets["R"], lo + spanL + spanM, spanR)):
            grps.sort(key=lambda g: g[0]["key"])
            k = len(grps)
            for i, grp in enumerate(grps):
                x = (a + width / 2.0) if k == 1 else (a + 3 + i * (width - 6) / (k - 1))
                for r in grp:
                    lane_x[(r["w"]["id"], r["tag"])] = x

    # ---------- 5. 折线 ----------
    for w in wires:
        bf, bt = boxes[w["from"]], boxes[w["to"]]
        y_o, y_i = out_y[w["id"]], in_y[w["id"]]
        x_o = bf.x1 if w["out_side"] == "right" else bf.x
        x_i = bt.x if w["in_side"] == "left" else bt.x1
        pts = [(x_o, y_o)]
        if w["span"] >= 2:
            seq = ((lane_x[(w["id"], "a")], y_o), (lane_x[(w["id"], "a")], w["band_y"]),
                   (lane_x[(w["id"], "b")], w["band_y"]), (lane_x[(w["id"], "b")], y_i),
                   (x_i, y_i))
        else:
            xm = lane_x[(w["id"], "m")]
            seq = ((xm, y_o), (xm, y_i), (x_i, y_i))
        for p in seq:
            if abs(p[0] - pts[-1][0]) > 0.5 or abs(p[1] - pts[-1][1]) > 0.5:
                pts.append(p)
        w["pts"] = pts

    # ---------- 6. 标签文本 ----------
    def wrap(nets, per_line=16):
        parts = [AD.net_label(n, widths) for n in nets]
        lines, cur = [], ""
        for p in parts:
            cand = p if not cur else cur + "/" + p
            if not cur or len(cand) <= per_line:
                cur = cand
            else:
                lines.append(cur)
                cur = p
        if cur:
            lines.append(cur)
        return lines

    for w in wires:
        w["label_lines"] = wrap(w["nets"])
        w["label_text"] = AD.wire_label(w["nets"], widths)

    # ---------- 7. 标签摆放 ----------
    obstacles = [R(b.x, b.y, b.w, b.h) for b in boxes.values()]
    obstacles.append(R(0, 0, W, 116))                       # 标题区
    obstacles.append(R(0, NOTE_Y - 18, W, H - NOTE_Y + 18))  # 图例区
    for z in zones:                                          # 分区标题不许被标签压住
        tw = text_w(z["title"], ZONE_SIZE)
        obstacles.append(R(z["x"] + z["w"] / 2 - tw / 2, z["y"] + 6, tw, 22))
    placed = []

    def lrect(lines, x, y, anchor):
        wdt = max(text_w(t, LABEL_SIZE) for t in lines)
        hgt = 22.0 * len(lines)
        x0 = x if anchor == "start" else (x - wdt if anchor == "end" else x - wdt / 2)
        return R(x0, y - hgt / 2, wdt, hgt)

    def penalty(r):
        """0 = 完全放得下。障碍留 3 px 余量、已放标签留 2 px，避免"擦边"。"""
        p = 0.0
        for o in obstacles:
            o = R(o.x - 3, o.y - 3, o.w + 6, o.h + 6)
            if overlap(r, o, 0.0):
                p += (min(r.x1, o.x1) - max(r.x, o.x)) * (min(r.y1, o.y1) - max(r.y, o.y))
        for o in placed:
            o = R(o.x - 2, o.y - 2, o.w + 4, o.h + 4)
            if overlap(r, o, 0.0):
                p += 3.0 * (min(r.x1, o.x1) - max(r.x, o.x)) * (min(r.y1, o.y1) - max(r.y, o.y))
        return p

    def dist_to_wire(w, x, y):
        best = 1e18
        for (p0, p1) in zip(w["pts"][:-1], w["pts"][1:]):
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - p0[0]) * dx + (y - p0[1]) * dy) / L2))
            best = min(best, ((x - (p0[0] + t * dx)) ** 2 + (y - (p0[1] + t * dy)) ** 2) ** 0.5)
        return best

    FRACS = (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9)
    for w in wires:
        lines = w["label_lines"]
        hgt = 22.0 * len(lines)
        segs = list(zip(w["pts"][:-1], w["pts"][1:]))
        segs.sort(key=lambda s: -((s[1][0] - s[0][0]) ** 2 + (s[1][1] - s[0][1]) ** 2))
        # ① 贴着自己那根线的候选位
        cands = []
        for (p0, p1) in segs:
            horiz = abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1])
            for fr in FRACS:
                mx = p0[0] + (p1[0] - p0[0]) * fr
                my = p0[1] + (p1[1] - p0[1]) * fr
                if horiz:
                    for k in (6, 18, 32, 48, 68, 92):
                        cands.append((mx, my - (hgt / 2 + k), "middle"))
                        cands.append((mx, my + (hgt / 2 + k), "middle"))
                else:
                    for k in (11, 24, 38, 56, 78, 104):
                        cands.append((mx + k, my, "start"))
                        cands.append((mx - k, my, "end"))
        # ② 线的邻域网格（让标签能在旁边空地上"就位"，而不是被迫飘到很远）
        xs = [p[0] for p in w["pts"]]
        ys = [p[1] for p in w["pts"]]
        gx = int(min(xs)) - 130
        while gx <= int(max(xs)) + 130:
            gy = int(min(ys)) - 130
            while gy <= int(max(ys)) + 130:
                cands.append((gx, gy, "middle"))
                gy += 9
            gx += 9
        # ③ 选"零遮挡 + 离自己那根线近 + 偏靠目标端"的位置
        tx, ty = w["pts"][-1]

        def score(r):
            return (dist_to_wire(w, r.cx, r.cy)
                    + 0.5 * ((r.cx - tx) ** 2 + (r.cy - ty) ** 2) ** 0.5)

        best, bests = None, None
        for (x, y, anc) in cands:
            r = lrect(lines, x, y, anc)
            if r.x < 6 or r.x1 > W - 6 or r.y < 6 or r.y1 > H - 6:
                continue
            if penalty(r) == 0.0:
                s = score(r)
                if bests is None or s < bests:
                    best, bests = (x, y, anc, r), s
        if best is None:                          # 兜底：遮挡最小
            bp = None
            for (x, y, anc) in cands:
                r = lrect(lines, x, y, anc)
                if r.x < 6 or r.x1 > W - 6 or r.y < 6 or r.y1 > H - 6:
                    continue
                p = penalty(r)
                if bp is None or p < bp:
                    bp, best = p, (x, y, anc, r)
        if best is None:
            x, y = w["pts"][0][0], w["pts"][0][1] - 20
            best = (x, y, "middle", lrect(lines, x, y, "middle"))
        w["label"] = {"text": w["label_text"], "lines": lines,
                      "x": round(best[0], 2), "y": round(best[1], 2),
                      "anchor": best[2], "size": LABEL_SIZE}
        placed.append(best[3])

    # ---------- 8. layout JSON ----------
    lay_boxes = []
    for bid in AD.BOX_IDS:
        c, y, h = BOX_GEO[bid]
        b = {"id": bid, "x": COL_X[c], "y": y, "w": COL_W[c], "h": h}
        if bid in AD.ENTITIES:
            b.update({"kind": "entity", "file": AD.ENTITIES[bid]["file"],
                      "title": AD.ENTITIES[bid]["title"], "sub": CN[bid],
                      "title_size": ENT_TITLE, "sub_size": ENT_SUB,
                      "globals": AD.GLOBALS[bid]})
        elif bid in AD.EXTERNAL:
            b.update({"kind": "ext", "title": AD.EXTERNAL[bid]["title"],
                      "sub": AD.EXTERNAL[bid]["sub"],
                      "title_size": EXT_TITLE, "sub_size": EXT_SUB, "globals": []})
        else:
            b.update({"kind": "glue", "title": GLUE_CN[bid], "sub": "非 entity",
                      "title_size": GLUE_TITLE, "sub_size": GLUE_SUB,
                      "globals": AD.GLOBALS[bid]})
        lay_boxes.append(b)

    lay_wires = [{"id": w["id"], "from": w["from"], "to": w["to"],
                  "from_side": w["out_side"], "to_side": w["in_side"],
                  "pts": [[round(p[0], 2), round(p[1], 2)] for p in w["pts"]],
                  "nets": w["nets"], "label": w["label"], "width_px": 1.9}
                 for w in wires]

    zones = []
    for c in range(6):
        ys = [BOX_GEO[b][1] for b in AD.BOX_IDS if BOX_GEO[b][0] == c]
        ye = [BOX_GEO[b][1] + BOX_GEO[b][2] for b in AD.BOX_IDS if BOX_GEO[b][0] == c]
        zones.append({"id": "zone%d" % c, "x": COL_X[c] - 3, "y": min(ys) - 40,
                      "w": COL_W[c] + 6, "h": (max(ye) - min(ys)) + 54,
                      "title": COL_TITLE[c]})

    layout = {"id": NAME, "canvas": {"w": W, "h": H}, "boxes": lay_boxes,
              "zones": zones, "wires": lay_wires}
    return {"svg": svg(lay_boxes, zones, lay_wires), "layout": layout, "w": W, "h": H}


# ---------------------------------------------------------------- SVG
def svg(lay_boxes, zones, lay_wires):
    core_ids = {"puzzle_ctrl"}
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
             '每根箭头 = puzzle_top.vhd 例化时的一条端口连接（formal ← actual 网名），标注位宽 [MSB:LSB]</text>'
             % (W // 2, FONT, SUBTITLE_SIZE))

    for z in zones:
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s" '
                 'stroke-width="1.3" stroke-dasharray="7 6"/>'
                 % (z["x"], z["y"], z["w"], z["h"], ZONE_FILL, ZONE_LINE))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%d" font-weight="bold" '
                 'fill="%s" text-anchor="middle">%s</text>'
                 % (z["x"] + z["w"] // 2, z["y"] + 20, FONT, ZONE_SIZE, MUTED, esc(z["title"])))

    for lw in lay_wires:
        col = CORE_LINE if lw["from"] in core_ids else LINE
        d = "M " + " L ".join("%.1f %.1f" % (q[0], q[1]) for q in lw["pts"])
        mk = "ar2" if lw["from"] in core_ids else "ar"
        p.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" '
                 'stroke-linejoin="round" marker-end="url(#%s)"/>' % (d, col, lw["width_px"], mk))

    for b in lay_boxes:
        bid = b["id"]
        if b["kind"] == "ext":
            fill, stroke, dash, sw = EXT_FILL, EXT_LINE, '', 1.8
        elif b["kind"] == "glue":
            fill, stroke, dash, sw = GLUE_FILL, GLUE_LINE, ' stroke-dasharray="7 5"', 2.0
        elif bid in core_ids:
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
                     % (cx, b["y"] + 24, FONT, EXT_TITLE, INK, esc(l1)))
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%d" fill="%s" '
                     'text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 43, FONT, EXT_TITLE, INK, esc(l2)))
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%.1f" fill="%s" '
                     'text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 60, MONO, EXT_SUB, MUTED, esc(EXT_SUB_TEXT[bid])))
        else:
            fam = FONT if b["kind"] == "entity" else FONT
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%.1f" font-weight="bold" '
                     'fill="%s" text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 30, fam, b["title_size"], INK, esc(b["title"])))
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="%.1f" fill="#475569" '
                     'text-anchor="middle">%s</text>'
                     % (cx, b["y"] + 52, FONT, b["sub_size"], esc(b["sub"])))
        g = b.get("globals") or []
        if g:
            p.append('<text x="%d" y="%d" font-family="%s" font-size="%.1f" fill="#94a3b8">%s</text>'
                     % (b["x"] + 7, b["y"] + b["h"] - 7, MONO, TAG_SIZE, esc("·".join(g))))

    for lw in lay_wires:
        lb = lw["label"]
        lines = lb["lines"]
        size = lb["size"]
        wdt = max(text_w(t, size) for t in lines)
        hgt = 22.0 * len(lines)
        x0 = lb["x"] if lb["anchor"] == "start" else (lb["x"] - wdt if lb["anchor"] == "end"
                                                      else lb["x"] - wdt / 2)
        y0 = lb["y"] - hgt / 2
        p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="#ffffff" '
                 'fill-opacity="0.9"/>' % (x0, y0, wdt, hgt))
        for i, t in enumerate(lines):
            p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%.1f" fill="#1e293b" '
                     'text-anchor="middle">%s</text>'
                     % (lb["x"], y0 + 16 + i * 22, MONO, size, esc(t)))

    for i, t in enumerate(NOTE_LINES):
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%.1f" fill="#334155">%s</text>'
                 % (16, NOTE_Y + i * 23, FONT, NOTE_SIZE, t))
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
        print("画布 %dx%d，方框 %d，连线 %d" % (W, H, len(res["layout"]["boxes"]),
                                              len(res["layout"]["wires"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
