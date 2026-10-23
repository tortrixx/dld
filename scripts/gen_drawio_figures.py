#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_drawio_figures.py —— 把三张图输出成 .drawio（mxGraph），再用 draw.io 渲染。

为什么改成 draw.io：
    · 箭头统一用 draw.io 的 block 三角、连线统一走正交折线，拐角与端点吸附到框边；
    · .drawio 可直接在 draw.io 里打开继续改，不再只有"脚本 + SVG"一条路。

分工（内容仍由事实源保证，draw.io 只负责"怎么画"）：
    · 功能总览 —— 6 个核心块 + 1 个时钟块，块内列 entity 名（gen_overview 的 ENTITIES_OF）；
    · 模块级框图 —— 20 个方框 / 32 条框间连接（arch_data → fig1_layout 的几何）；
    · 游戏流程 —— 21 个节点 / 27 条箭头（gen_flow_diagram 的 NODES/EDGES）。

用法：
    python scripts/gen_drawio_figures.py            # 写三个 .drawio + 渲染 PNG
    python scripts/gen_drawio_figures.py --only overview
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drawio_lib as DL  # noqa: E402
import drawio_render as DR  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPT = os.path.join(ROOT, "docs", "report")


# ---------------------------------------------------------------- 功能总览
def build_overview():
    import gen_overview_diagram as G

    cells, ids = [], {}
    # 容器
    cx, cy, cw, ch, ctitle = G.CONTAINER
    cells.append(DL.box("zone", cx, cy, cw, ch, "", fill="#F8FAFC",
                        stroke="#CBD5E1", sw=1.6, bold=False, dashed=True,
                        rounded=True))
    cells.append(DL.label("zone_title", 430, cy + 6,
                          "内部核心功能框图（6 块 · 10 个 entity）", fs=15,
                          color=DL.MUTED, bold=True, w=230))
    # 时钟分配（虚线）在方框之前画，穿过方框的部分会被框挡住
    rail = DL.label("clknote", 0, 0, "", fs=1)
    taps = {"kbd": 200, "fsm": 650, "core": 1000, "dsp": 1350, "rom": 830, "aud": 1170}
    for bid, tx in taps.items():
        ty = G.block(bid)[2]
        if bid in ("rom", "aud"):          # 第二排：沿两列之间的空隙下去，再横着进左边缘
            by = G.block(bid)[2] + G.block(bid)[4] // 2
            cells.append(DL.edge("clk_" + bid, "clk", bid,
                                 [(tx, G.RAIL_Y), (tx, by)], color=DL.CLK, sw=1.6,
                                 dashed=True, fs=15))
        else:
            cells.append(DL.edge("clk_" + bid, "clk", bid,
                                 [(tx, G.RAIL_Y)], color=DL.CLK, sw=1.6,
                                 dashed=True, fs=15))
    del rail

    # 方框
    for bid, x, y, w, h, title, sub in G.BLOCKS:
        is_clk = bid == "clk"
        names = G.ENTITIES_OF[bid] if not is_clk else []
        text = '<b style="font-size:22px">%s</b>' % title
        if sub:
            text += '<br><span style="font-size:15.5px;color:#475569">%s</span>' % sub
        for nm in names:
            text += ('<br><span style="font-family:Consolas;font-size:16px;'
                     'color:#0F766E">%s</span>' % nm)
        cells.append(DL.box(bid, x, y, w, h, text,
                            fill="#FEF2F2" if is_clk else "#FFFFFF",
                            stroke=DL.CLK if is_clk else DL.LINE,
                            sw=2.2, fs=22, bold=True, rounded=True))

    # 板载器件
    for bid, x, y, w, h, lines in G.EXT:
        text = "<br>".join('<b style="font-size:20px">%s</b>' % t for t in lines)
        cells.append(DL.box(bid, x, y, w, h, text, fill="#EEF2F7",
                            stroke="#94A3B8", sw=1.8, fs=20, bold=True, rounded=True))

    # 数据流（这里按"箭头别乱拐"重排了三条线的走法）
    flows = [
        ("kbd", "r", "fsm", "l", "按键", []),
        ("fsm", "r", "core", "l", "控制", []),
        ("core", "r", "dsp", "l", "帧平面", []),
        ("dsp", "r", "dev_disp", "l", "", []),
        ("fsm", "b", "rom", "t", "关卡号", [(700, 412), (700, 440), (920, 440)]),
        ("rom", "t", "core", "b", "掩码/图案", []),
        # 音效码：从"游戏控制"底部下到 y=650，右行，再**从下往上**进"音效输出"底边
        ("fsm", "b", "aud", "b", "音效码", [(620, 412), (620, 650), (1330, 650)]),
        ("aud", "r", "dev_buzz", "l", "", []),
    ]
    for i, (frm, fs, to, ts, lab, extra) in enumerate(flows):
        pts = G.pts_of(frm, fs, to, ts, extra)
        # pts_of 会把两端也算进去；draw.io 只需要中间拐点
        mid = [p for p in pts[1:-1]]
        cells.append(DL.edge("e%d" % i, frm, to, mid, lab, fs=15))

    # 键盘行列（板外）
    for name, yy, direction in G.KP:
        cells.append(DL.label("kp_" + name, 12, yy - 11, name, fs=16, color=DL.ACCENT,
                              font="Consolas", bold=True, w=82))
        if direction == "in":
            cells.append(DL.free_edge("kpe_" + name, 96, yy, 118, yy, color=DL.ACCENT))
        else:
            cells.append(DL.free_edge("kpe_" + name, 118, yy, 96, yy, color=DL.ACCENT))

    # 标题
    cells.append(DL.label("title", G.W // 2 - 320, 18,
                          "题目 4：简易拼图游戏 —— 功能总览框图", fs=27, bold=True, w=640))
    cells.append(DL.label("subtitle", G.W // 2 - 620, 52,
                          "按功能划分的 6 个核心功能块 + 1 个时钟块（块内等宽小字 = 它包含的 "
                          "rtl/&lt;同名&gt;.vhd 实体，共 11 个）；模块级连线与端口见下一张图",
                          fs=15.5, color="#475569", w=1240))
    return cells, G.W, G.H


import drawio_flow  # noqa: E402
import drawio_arch  # noqa: E402

BUILDERS = {
    "overview": ("fig_overview", build_overview),
    "flow": ("fig_game_flow", drawio_flow.build_flow),
    "arch": ("fig1_system_architecture", drawio_arch.run),
}


def main(argv):
    ap = argparse.ArgumentParser(description="生成 .drawio 并用 draw.io 渲染")
    ap.add_argument("--only", choices=sorted(BUILDERS), help="只做一张")
    ap.add_argument("--scale", type=float, default=2.4)
    a = ap.parse_args(argv)

    ok_all = True
    for key, (name, fn) in BUILDERS.items():
        if a.only and key != a.only:
            continue
        cells, w, h = fn()
        src = os.path.join(RPT, name + ".drawio")
        DL.write_mxfile(src, cells, name=name, width=int(w), height=int(h))
        print("%-22s %d 个 cell → %s" % (name, len(cells), os.path.basename(src)))
        png = os.path.join(RPT, name + ".png")
        ok, msg = DR.render(src, png, scale=a.scale)
        if not ok:
            print("  渲染失败:", msg)
            ok_all = False
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
