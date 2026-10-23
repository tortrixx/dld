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

# 标签定位表（LABEL_POS）、默认偏移（LABEL_DY/LABEL_DX）与 label_xy() 都在
# gen_flow_diagram 里，SVG 版与 draw.io 版共用同一套，避免两个交付物各算一套。


def _tw(text, size):
    """与 fig1_layout / audit_diagram 同一套字宽估值。"""
    return sum((1.0 if ord(ch) > 0x2E7F else 0.62) * size for ch in text)


def build_flow():
    import gen_flow_diagram as G

    cells = []
    # 循环容器（虚线框 + 左上角两行标题）
    lx, ly, lw, lh, ltitle = G.LOOP_BOX
    cells.append(DL.box("loop", lx, ly, lw, lh, "", fill=G.FILL_ACCENT,
                        stroke=G.ACCENT, sw=2.2, dashed=True, rounded=True,
                        arc=G.LOOP_ARC))
    cells.append(DL.label("loop_title", lx + 24, ly + 6, ltitle, fs=18,
                          color=G.ACCENT, bold=True, w=560))
    cells.append(DL.label("loop_sub", lx + 24, ly + 26, G.LOOP_SUBTITLE, fs=18,
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
            tx, ty = G.label_xy(frm, fs, to, ts, label, extra)
            # ⚠️ DL.label 是 align="left"：x 就是文字左边缘（还带 spacing=2）。
            #    原来写死 tx-22 / w=44（按居中算），单字标签会整体左偏约 12 px，
            #    与手工定位的意图对不上。这里按实测字宽反推左边缘。
            lw = max(28.0, _tw(label, 16) + 8)
            # align="center" + 盒心 = (tx,ty)，与 SVG 版（text-anchor=middle、y=ty+5.5）
            # 的墨迹中心一致；原来用 align="left" + 左边缘 tx-lw/2-2，会整体偏 (-6,+6)。
            cells.append(DL.label("lb%d" % i, tx - lw / 2.0, ty - 10, label, fs=16,
                                  color=G.ACCENT, bold=True, w=int(round(lw)),
                                  align="center"))

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
    # ⚠️ align="center"：DL.label 默认 align="left"，标题会左偏 48 画布 px，而 SVG 版
    #    用的是 text-anchor="middle" —— 两个交付件的标题必须同位（第三轮 FLOW-01）。
    cells.append(DL.label("title", (G.W - 700) / 2, 14,
                          "题目 4：简易拼图游戏 —— 游戏流程框图", fs=30, bold=True,
                          w=700, align="center"))
    for i, line in enumerate(G.SUBTITLE_LINES):
        cells.append(DL.label("subtitle%d" % i, G.SUBTITLE_X,
                              G.SUBTITLE_Y0 + i * G.SUBTITLE_DY - 10, line,
                              fs=16, color="#475569", w=720))
    return cells, G.W, G.H
