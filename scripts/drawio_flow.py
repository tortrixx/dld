#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「游戏流程框图」也改成 .drawio 输出（箭头由 draw.io 统一画）。

节点几何、连线折点全部复用 scripts/gen_flow_diagram.py 里已经调好、且通过
文字宽度检查的那份布局；这里只负责翻译成 mxGraph 并让 draw.io 渲染。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drawio_lib as DL  # noqa: E402

# ---------------------------------------------------------------- 标签手工定位
# ⚠️ 为什么需要它：标签默认贴「最长水平段中点上方 16 px」。对局循环里有几条边的
#    默认落点会压到方框或别的线（实测缺陷 5 / 6 / 7）：
#      · gokey→idle 的「否」：默认 tx/ty=(560,400) 落在 S_IDLE 框内（框 x 520..1140 / y 387..446）；
#      · lwin→win 的「是」：默认落在容器底虚线上（y≈1497，容器底 1521）；
#      · ltime→fail 的「是」：默认落在 y≈1520 的横段上，与缺陷 5 的新回边只差几 px。
#    键 = (源, 目标, 标签文字)，值 = (tx, ty) 画布坐标（与 G.NODES 同一坐标系）。
LABEL_POS = {
    ("gokey", "idle", "否"): (632, 515),
    ("ltime", "bus", "否"): (1400, 1018),
    ("lwin", "win", "是"): (860, 1545),
    ("ltime", "fail", "是"): (1650, 968),
    # 默认落点（竖段中点右侧）会让「是」的底缘离「译码并执行按键」框顶边只剩 ~5 px，
    # 且顶缘擦到 lk 菱形的右下斜边 —— 往右下挪到斜边外侧（左右各留 ≥14 px）。
    ("lk", "ldec", "是"): (874, 1008),
    # 「否」默认落在 lvlq 菱形下尖与「通关结算」框之间那条 32 px 窄带的正中，
    # 到菱形左下斜边的**欧氏**净距只有 9.5 px —— 往左下让 6 px 后为 ~12 px。
    ("lvlq", "final", "否"): (844, 1809),
}

# 默认落点离线的距离（画布 px）。原来是「水平段上方 16 / 竖直段右侧 24」，
# 实测文字墨迹到线只有 6.2~9.6 px（低于 10 px 口径），统一再外移 5 px。
LABEL_DY = 21
LABEL_DX = 29


def _tw(text, size):
    """与 fig1_layout / audit_diagram 同一套字宽估值。"""
    return sum((1.0 if ord(ch) > 0x2E7F else 0.62) * size for ch in text)


def build_flow():
    import gen_flow_diagram as G

    cells = []
    # 循环容器（虚线框 + 左上角标题）
    lx, ly, lw, lh, ltitle = G.LOOP_BOX
    cells.append(DL.box("loop", lx, ly, lw, lh, "", fill=G.FILL_ACCENT,
                        stroke=G.ACCENT, sw=2.2, dashed=True, rounded=True))
    cells.append(DL.label("loop_title", lx + 16, ly + 8, ltitle, fs=18,
                          color=G.ACCENT, bold=True, w=560))

    # 节点
    for nid, kind, x, y, w, h, lines in G.NODES:
        title, subs = lines[0], lines[1:]
        shape = "rhombus" if kind == "dec" else ""
        rounded = kind in ("stadium",)
        fs = 17 if kind == "dec" else 19.5
        text = "<b>%s</b>" % title
        for s in subs:
            text += '<br><span style="font-size:16.5px">%s</span>' % s
        fill = G.FILL_DEC if kind == "dec" else (
            G.FILL_IO if kind == "stadium" else
            (G.FILL_ACCENT if nid in ("win", "fail", "final") else G.FILL))
        cells.append(DL.box(nid, x, y, w, h, text, shape=shape, rounded=rounded,
                            fill=fill, stroke=G.LINE, sw=2, fs=fs, bold=True))

    # 连线
    for i, (frm, fs, to, ts, label, extra) in enumerate(G.EDGES):
        pts = G.pts_of(frm, fs, to, ts, extra)
        if frm == "bus" or to == "bus":
            cells.append(DL.polyline("e%d" % i, pts, arrow=(to != "bus")))
        else:
            cells.append(DL.edge("e%d" % i, frm, to, pts[1:-1]))
        if label:
            # 手工定位优先；否则贴最长水平段上方，没有水平段就贴最长垂直段右侧
            if (frm, to, label) in LABEL_POS:
                tx, ty = LABEL_POS[(frm, to, label)]
            else:
                segs = list(zip(pts[:-1], pts[1:]))
                horiz = [s for s in segs if abs(s[1][0] - s[0][0]) >= abs(s[1][1] - s[0][1])]
                if horiz:
                    (x0, y0), (x1, y1) = max(horiz, key=lambda s: abs(s[1][0] - s[0][0]))
                    tx, ty = (x0 + x1) / 2.0, min(y0, y1) - LABEL_DY
                else:
                    (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][1] - s[0][1]))
                    tx, ty = max(x0, x1) + LABEL_DX, (y0 + y1) / 2.0
            # ⚠️ DL.label 是 align="left"：x 就是文字左边缘（还带 spacing=2）。
            #    原来写死 tx-22 / w=44（按居中算），单字标签会整体左偏约 12 px，
            #    与手工定位的意图对不上。这里按实测字宽反推左边缘。
            lw = max(28.0, _tw(label, 16) + 8)
            cells.append(DL.label("lb%d" % i, tx - lw / 2.0 - 2, ty - 10, label, fs=16,
                                  color=G.ACCENT, bold=True, w=int(round(lw))))

    # 「回循环」总线：竖线汇齐所有回边，再横着进循环起点（只画一个箭头）
    cells.append(DL.polyline("bus", [(G.BUS_X, G.BUS_BOT_Y), (G.BUS_X, G.BUS_TOP_Y),
                                      G.anchor("lk", "l")], arrow=True, color=G.LINE))
    cells.append(DL.label("bus_label", G.BUS_X + 12, G.BUS_TOP_Y - 40, "回循环",
                          fs=16, color=G.ACCENT, w=80))

    # 无端子回边（缺陷 8：「全系统静默熄灭」补回边）
    for eid, fpts, lab in G.FREE_EDGES:
        cells.append(DL.polyline(eid, fpts, arrow=True, color=G.LINE))
        if lab:
            cells.append(DL.label(eid + "_l", fpts[1][0] + 12, fpts[1][1] - 30, lab,
                                  fs=16, color=G.ACCENT, w=120))

    # 标题 + 图例（图例三行放左上角空白区，避开「上电 / 复位」框；见 gen_flow_diagram 注释）
    cells.append(DL.label("title", G.W // 2 - 330, 14,
                          "题目 4：简易拼图游戏 —— 游戏流程框图", fs=30, bold=True, w=660))
    for i, line in enumerate(G.SUBTITLE_LINES):
        cells.append(DL.label("subtitle%d" % i, G.SUBTITLE_X,
                              G.SUBTITLE_Y0 + i * G.SUBTITLE_DY - 10, line,
                              fs=16, color="#475569", w=720))
    return cells, G.W, G.H
