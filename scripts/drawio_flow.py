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
            # 贴最长水平段上方；没有水平段就贴最长垂直段右侧
            segs = list(zip(pts[:-1], pts[1:]))
            horiz = [s for s in segs if abs(s[1][0] - s[0][0]) >= abs(s[1][1] - s[0][1])]
            if horiz:
                (x0, y0), (x1, y1) = max(horiz, key=lambda s: abs(s[1][0] - s[0][0]))
                tx, ty = (x0 + x1) / 2.0, min(y0, y1) - 16
            else:
                (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][1] - s[0][1]))
                tx, ty = max(x0, x1) + 24, (y0 + y1) / 2.0
            cells.append(DL.label("lb%d" % i, tx - 22, ty - 11, label, fs=16,
                                  color=G.ACCENT, bold=True, w=44))

    # 「回循环」总线：竖线汇齐所有回边，再横着进循环起点（只画一个箭头）
    cells.append(DL.polyline("bus", [(G.BUS_X, G.BUS_BOT_Y), (G.BUS_X, G.BUS_TOP_Y),
                                      G.anchor("lk", "l")], arrow=True, color=G.LINE))
    cells.append(DL.label("bus_label", G.BUS_X + 12, G.BUS_TOP_Y - 40, "回循环",
                          fs=16, color=G.ACCENT, w=80))

    # 标题
    cells.append(DL.label("title", G.W // 2 - 330, 14,
                          "题目 4：简易拼图游戏 —— 游戏流程框图", fs=30, bold=True, w=660))
    cells.append(DL.label("subtitle", G.W // 2 - 620, 46,
                          "圆角框 = 起止    矩形 = 处理    菱形 = 判断    箭头 = 流向"
                          "（判断分支标 是 / 否）", fs=16, color="#475569", w=1240))
    return cells, G.W, G.H
