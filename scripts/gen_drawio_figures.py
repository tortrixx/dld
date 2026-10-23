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
def _tw(text, size):
    """与 fig1_layout / audit_diagram 同一套字宽估值（用来把标题真正居中）。"""
    return sum((1.0 if ord(ch) > 0x2E7F else 0.62) * size for ch in text)


def _centered_x(text, size, W):
    return (W - _tw(text, size)) / 2.0 - 2


def build_overview():
    import gen_overview_diagram as G

    cells, ids = [], {}
    # 容器
    cx, cy, cw, ch, ctitle = G.CONTAINER
    cells.append(DL.box("zone", cx, cy, cw, ch, "", fill="#F8FAFC",
                        stroke="#CBD5E1", sw=1.6, bold=False, dashed=True,
                        rounded=True))
    # 容器标题：cy+9（不是 cy+6）—— 原来墨迹顶缘距容器顶虚线内缘只有 9.2 画布 px。
    # 容器标题用 G.CONTAINER[4]（不要重抄字符串）：SVG 版与 drawio 版必须逐字一致
    # （早先 drawio 侧硬编码成「6 块」、SVG 是「6 个功能块」，同一张图两个交付件不同）。
    cells.append(DL.label("zone_title", G.ZONE_TITLE_X, cy + 9, ctitle, fs=15,
                          color=DL.MUTED, bold=True, w=300))
    # 时钟分配（虚线）在方框之前画，穿过方框的部分会被框挡住
    rail = DL.label("clknote", 0, 0, "", fs=1)
    # ⚠️ tap 的 x 选择有一条硬规则：**不能落在"连线标签要用的空隙"里**。
    #   · kbd 200 / fsm 650 / core 1000 / dsp 1365 都是块的水平中心，直接从 rail 下到块顶，
    #     中间穿过别的方框（方框后画、把线压住）—— 安全；
    #   · rom 1100 / aud 1330 同理（穿过 core / dsp 方框被压住），把 800..860 与
    #     1140..1215 两个空隙完整让给「控制」「帧平面」标签。
    #   这一份 x 值现在是 `gen_overview_diagram.TAPS`，两边共用。
    for bid, tx in G.TAPS.items():
        ty = G.block(bid)[2]
        cells.append(DL.edge("clk_" + bid, "clk", bid, [(tx, G.RAIL_Y)],
                             color=DL.CLK, sw=1.6, dashed=True, fs=15))
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
        ("fsm", "b", "rom", "t", "关卡号", [(700, 412), (700, 428), (920, 428)]),
        ("rom", "t", "core", "b", "掩码/图案", []),
        # 音效码：从"游戏控制"底部下到 y=650，右行，再**从下往上**进"音效输出"底边
        ("fsm", "b", "aud", "b", "音效码", [(620, 412), (620, 650), (1330, 650)]),
        ("aud", "r", "dev_buzz", "l", "", []),
    ]
    # 六条连线标签全部改成**独立 label 钉死坐标**（`e%d` 传 lab=""），坐标表与
    # SVG 版（`gen_overview_diagram.LABEL_POS`）同源。
    detached = G.LABEL_POS
    for i, (frm, fs, to, ts, lab, extra) in enumerate(flows):
        pts = G.pts_of(frm, fs, to, ts, extra)
        # pts_of 会把两端也算进去；draw.io 只需要中间拐点
        mid = [p for p in pts[1:-1]]
        det = detached.get(i)
        cells.append(DL.edge("e%d" % i, frm, to, mid, "" if det else lab, fs=15))
        if det:
            cid, lx, ly, lw, lh = det
            cells.append(DL.label(cid, lx, ly, lab, fs=15, color=DL.LINE,
                                  w=lw, h=lh))

    # 键盘行列（板外）
    for name, yy, direction in G.KP:
        cells.append(DL.label("kp_" + name, 12, yy - 11, name, fs=16, color=DL.ACCENT,
                              font="Consolas", bold=True, w=82))
        if direction == "in":
            cells.append(DL.free_edge("kpe_" + name, 96, yy, 118, yy, color=DL.ACCENT))
        else:
            cells.append(DL.free_edge("kpe_" + name, 118, yy, 96, yy, color=DL.ACCENT))

    # 标题（用 align="center" 真正居中 —— 靠字宽估算会偏：`_tw()` 把副标题估宽约 138 px，
    # 左对齐时误差全堆到右边，墨迹整体左移 65 px）
    t_title = "题目 4：简易拼图游戏 —— 功能总览框图"
    cells.append(DL.label("title", (G.W - 700) / 2, 18, t_title, fs=27, bold=True,
                          w=700, align="center"))
    t_sub = ("按功能划分的 6 个核心功能块 + 1 个时钟块（块内等宽小字 = 它包含的 "
             "rtl/&lt;同名&gt;.vhd 实体，共 11 个）；模块级连线与端口见下一张图")
    cells.append(DL.label("subtitle", (G.W - 1100) / 2, 52, t_sub, fs=15.5,
                          color="#475569", w=1100, align="center"))
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
