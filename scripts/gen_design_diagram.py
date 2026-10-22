#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_design_diagram.py —— 生成《实际设计方案》用的「模块级系统总体框图」

【为什么要有它】
    课程平台「实际设计方案（10 分）」的原文要求里有一句硬话：
        「**总体框图中的模块要求与实现电路(代码)一致**」。
    而报告里原来的 `fig1_system_architecture.*` 是**功能级**示意图 ——
    七个方框写的是「时钟 / 键盘输入 / 游戏控制 / 拼图核心 / 显示子系统 /
    图案与随机数据 / 音效输出」，**一个 RTL 实体名都没有**，严格讲不满足那一条。

    这一版把方框**直接绑到实体**：每个方框 = `rtl/<文件>.vhd` 里的一个 `entity`，
    每根箭头 = `puzzle_top.vhd` 例化时的一条端口连接（formal ← actual 网名）。
    而且**方框集合、文件名、网名、位宽都不是手写的**，是从
    `facts/facts.json` 的 `entities.puzzle_top`（含 instantiations 的 port_map）
    与 `rtl/puzzle_top.vhd` 的 signal 声明现算的 ⇒ 想和代码对不上都难。

【用法】（在仓库根执行）
    python scripts/gen_design_diagram.py            # 写 SVG + 渲染 PNG
    python scripts/gen_design_diagram.py --check    # 只对账，不写盘

【依赖】
    纯标准库；渲染 PNG 用无头 Chrome / Edge（找不到就只出 SVG 并提示）。

【已知边界】
    · **方框坐标与走线 lane 是人工排的**（图才好看），但"有哪些方框、叫什么名字、
      每根箭头的网名与位宽"全部来自事实源，并在 `--check` 里逐条核对。
    · 数组型端口（`o_mask`/`o_h`/`o_w` 是 `mask_arr_t`/`dim_arr_t`）在 facts.json 里
      宽度记为 1，所以在 `ARRAY_WIDTH` 里显式给出人可读口径。
    · 顶层胶合逻辑（行切片 + 行计数器）不是 entity，用**虚线框**区分，并注明出处。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = os.path.join(ROOT, "facts", "facts.json")
OUT_SVG = os.path.join(ROOT, "docs", "report", "fig1_system_architecture.svg")
OUT_PNG = os.path.join(ROOT, "docs", "report", "fig1_system_architecture.png")
# 站点页用的是 docs/assets/images/ 下那一份（内容相同，另存一份便于 docsify 引用）
OUT_PNG_SITE = os.path.join(ROOT, "docs", "assets", "images", "fig1_system_architecture.png")
OUT_SVG2 = os.path.join(ROOT, "docs", "report", "实际设计方案-模块设计一览.svg")
OUT_PNG2 = os.path.join(ROOT, "docs", "report", "实际设计方案-模块设计一览.png")

W, H = 2560, 1560
DIAG_BOTTOM = 900                 # 图区下边界；图例从这下面开始
FONT = "Microsoft YaHei, SimSun, sans-serif"
MONO = "Consolas, Courier New, monospace"
LBL_FONT = 13.5                   # 箭头标签字号（列间距按它留够）
LBL_PX = 8.0                      # 每字符宽度估值（用于白底衬垫与压框自检）

ARRAY_WIDTH = {"shapes": "4×64", "shape_h": "4×3", "shape_w": "4×3"}

# ---------------------------------------------------------------- 方框（人工排布）
# id, 标题, 副标题, x, y, 宽, 高, 分区
# 列间距刻意留到 ~186px：箭头标签贴在列间空隙里，不会被方框压住（自检会验）。
BOXES = [
    # 外部世界（左）
    ("ext_clk", "50 MHz 有源晶振", "PIN_18", 40, 104, 172, 64, "ext"),
    ("ext_sw", "SW7 使能", "PIN_125", 40, 204, 172, 64, "ext"),
    ("ext_btn", "BTN0 复位", "PIN_61", 40, 304, 172, 64, "ext"),
    ("ext_kp", "4×4 矩阵键盘", "kp_row / kp_col", 40, 462, 172, 64, "ext"),
    # 时钟 / 输入层
    ("clk_gen", "clk_gen", "rtl/clk_gen.vhd", 396, 96, 204, 80, "clk"),
    ("keypad_scan", "keypad_scan", "rtl/keypad_scan.vhd", 396, 462, 204, 80, "in"),
    # 存储层
    ("piece_rom", "piece_rom", "rtl/piece_rom.vhd", 786, 108, 204, 76, "mem"),
    ("pattern_rom", "pattern_rom", "rtl/pattern_rom.vhd", 786, 214, 204, 76, "mem"),
    # 控制层
    ("game_fsm", "game_fsm", "rtl/game_fsm.vhd", 786, 430, 204, 100, "ctl"),
    # 核心层
    ("puzzle_ctrl", "puzzle_ctrl", "rtl/puzzle_ctrl.vhd", 1176, 380, 216, 190, "core"),
    # 顶层胶合逻辑（非 entity）
    ("glue_slice", "顶层行切片 + 行计数器", "puzzle_top.vhd 内（非独立 entity）", 1176, 622, 216, 66, "glue"),
    # 随机源 / 音频
    ("rng_lfsr", "rng_lfsr", "rtl/rng_lfsr.vhd", 1176, 744, 216, 76, "mem"),
    ("buzzer_ctrl", "buzzer_ctrl", "rtl/buzzer_ctrl.vhd", 1578, 744, 204, 76, "out"),
    # 输出层
    ("disp_format", "disp_format", "rtl/disp_format.vhd", 1578, 96, 204, 76, "out"),
    ("seg_scan", "seg_scan", "rtl/seg_scan.vhd", 1968, 96, 196, 76, "out"),
    ("dot_matrix_scan", "dot_matrix_scan", "rtl/dot_matrix_scan.vhd", 1968, 220, 196, 88, "out"),
    # 外部世界（右）
    ("ext_seg", "8 位共阴数码管", "seg / cat", 2350, 104, 170, 64, "ext"),
    ("ext_dot", "8×8 双色点阵", "ROW / COLR / COLG", 2350, 232, 170, 64, "ext"),
    ("ext_buzz", "无源蜂鸣器", "PIN_60", 2350, 750, 170, 64, "ext"),
]

# ---------------------------------------------------------------- 连线
# (源, 目标, 网名, 源侧, 目标侧, 走线 lane, 标签纵向微调)
EDGES = [
    ("ext_clk", "clk_gen", "clk", "right", "left", None, 0),
    ("ext_btn", "clk_gen", "btn", "right", "left", 258, 22),
    ("clk_gen", "keypad_scan", "t_200", "bottom", "top", None, 0),
    ("clk_gen", "game_fsm", "t_1hz", "right", "top", 540, -34),
    ("clk_gen", "game_fsm", "t_4hz", "right", "top", 556, -12),
    ("clk_gen", "glue_slice", "t_1k", "right", "left", 860, -30),
    ("ext_sw", "game_fsm", "sw7", "right", "left", None, 0),
    ("ext_kp", "keypad_scan", "kp_row", "right", "left", None, -15),
    ("keypad_scan", "ext_kp", "kp_col", "left", "right", None, 15),
    ("keypad_scan", "game_fsm", "key", "right", "left", None, -12),
    ("keypad_scan", "game_fsm", "press", "right", "left", 552, 22),
    ("game_fsm", "piece_rom", "level", "right", "left", 560, -10),
    ("game_fsm", "pattern_rom", "level", "right", "left", 576, 16),
    ("piece_rom", "puzzle_ctrl", "shapes", "right", "left", 1044, -112),
    ("pattern_rom", "puzzle_ctrl", "tgt_mask", "right", "left", 1076, -160),
    ("rng_lfsr", "puzzle_ctrl", "rnd_val", "top", "bottom", None, 0),
    ("puzzle_ctrl", "rng_lfsr", "rnd_step", "bottom", "left", 1140, 0),
    # 主控 → 引擎 / 引擎 → 主控：单拍按键脉冲与状态回授各 5+3 条。
    # 逐条画会把中间空隙塞满，所以**分组**成 4 根箭头，标签把网名逐个列全
    # （《实际设计方案》正文表格里再逐条给方向与位宽）。
    ("game_fsm", "puzzle_ctrl", "go/sel/move/conf", "right", "left", None, -80),
    ("game_fsm", "puzzle_ctrl", "mv_rot/level", "right", "left", 1060, -34),
    ("puzzle_ctrl", "game_fsm", "solved/all_lock", "left", "right", None, 34),
    ("puzzle_ctrl", "game_fsm", "shuf_busy", "left", "right", 1100, 80),
    ("game_fsm", "disp_format", "state", "right", "left", 1180, -20),
    ("game_fsm", "disp_format", "gtime", "right", "left", 1180, 2),
    ("game_fsm", "disp_format", "gblink", "right", "left", 1180, 24),
    ("disp_format", "seg_scan", "disp_data", "right", "left", None, -10),
    ("disp_format", "seg_scan", "disp_blank", "right", "left", 1480, 18),
    ("seg_scan", "ext_seg", "seg", "right", "left", None, -10),
    ("seg_scan", "ext_seg", "cat", "right", "left", 1770, 18),
    ("puzzle_ctrl", "glue_slice", "eng_fr", "bottom", "top", 1010, -14),
    ("puzzle_ctrl", "glue_slice", "eng_fg", "bottom", "top", 1060, 8),
    ("glue_slice", "dot_matrix_scan", "mat_r", "right", "left", 1470, -12),
    ("glue_slice", "dot_matrix_scan", "mat_g", "right", "left", 1470, 10),
    ("glue_slice", "dot_matrix_scan", "mrow", "right", "left", 1452, 30),
    ("dot_matrix_scan", "ext_dot", "dot_row", "right", "left", None, -12),
    ("dot_matrix_scan", "ext_dot", "dot_colr", "right", "left", 1770, 10),
    ("dot_matrix_scan", "ext_dot", "dot_colg", "right", "left", 1770, 32),
    ("game_fsm", "buzzer_ctrl", "sound", "right", "left", 1180, 0),
    ("buzzer_ctrl", "ext_buzz", "buzz", "right", "left", None, 0),
]

# 配色刻意克制：模块一律白底细黑边，只有"外部器件"用浅灰、"顶层胶合"用虚线，
# 唯一的强调色留给核心引擎 puzzle_ctrl —— 目标是"教科书式框图"，不靠颜色区分模块
# （子系统归属由分区虚线框 + 分区标题表达）。
GROUP_FILL = {
    "ext": ("#f1f5f9", "#94a3b8"),
    "clk": ("#ffffff", "#334155"), "in": ("#ffffff", "#334155"),
    "ctl": ("#ffffff", "#334155"), "mem": ("#ffffff", "#334155"),
    "core": ("#fffbeb", "#b45309"), "out": ("#ffffff", "#334155"),
    "glue": ("#f8fafc", "#64748b"),
}
GLUE = {"glue"}

ZONES = [
    ("外部世界（板载器件）", 28, 92, 196, 480),
    ("时钟与输入", 384, 92, 228, 500),
    ("图案 / 零片存储", 774, 100, 228, 206),
    ("游戏控制", 774, 426, 228, 200),
    ("拼图核心引擎", 1164, 376, 240, 500),
    ("显示与音频输出", 1566, 92, 610, 760),
]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load_facts():
    with open(FACTS, encoding="utf-8") as fh:
        return json.load(fh)


def top_signals() -> dict:
    """解析 rtl/puzzle_top.vhd 里声明的顶层内部信号 → 位宽。

    `eng_fr` / `mat_r` / `mrow` 是 `puzzle_top` 架构体里的信号，不属于任何子模块端口，
    所以 port_map 里查不到；但图里要用，而且宽度必须是真的 ⇒ 从 VHDL 原文解析。
    """
    src = open(os.path.join(ROOT, "rtl", "puzzle_top.vhd"), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"^\s*signal\s+(\w+)\s*:\s*([^;]+);", src, re.M):
        name, typ = m.group(1), m.group(2)
        rng = re.search(r"(\d+)\s+downto\s+(\d+)", typ)
        if rng:
            out[name] = (abs(int(rng.group(1)) - int(rng.group(2))) + 1, "puzzle_top.vhd signal")
        elif re.search(r"\bstd_logic\b|\bunsigned\b|\bsigned\b", typ):
            out[name] = (1, "puzzle_top.vhd signal")
    return out


def net_widths(facts) -> dict:
    ent = facts["entities"]
    widths: dict[str, tuple[int, str]] = {}
    for inst in ent["puzzle_top"]["instantiations"]:
        pmap = {p["name"]: p for p in ent[inst["entity"]].get("ports", [])}
        for m in inst["port_map"]:
            actual, formal = m.get("actual"), m.get("formal")
            if not actual or actual == "open" or actual in widths:
                continue
            p = pmap.get(formal)
            if p:
                widths[actual] = (int(p.get("width") or 1), "%s.%s" % (inst["entity"], formal))
    for p in ent["puzzle_top"].get("ports", []):
        widths.setdefault(p["name"], (int(p.get("width") or 1), "puzzle_top.%s" % p["name"]))
    for k, v in top_signals().items():
        widths.setdefault(k, v)
    return widths


def label_for(net: str, widths: dict) -> str:
    """箭头标签。`a/b/c` 形式表示"一根箭头代表这组网名"（逐条列全，不省略）。"""
    if "/" in net:
        return net
    if net in ARRAY_WIDTH:
        return "%s[%s]" % (net, ARRAY_WIDTH[net])
    w, _ = widths.get(net, (1, "?"))
    return net if w <= 1 else "%s[%d:0]" % (net, w - 1)


def rect(bid):
    for b in BOXES:
        if b[0] == bid:
            return b
    raise KeyError(bid)


def anchor(bid, side):
    _, _, _, x, y, w, h, _ = rect(bid)
    return {"left": (x, y + h / 2), "right": (x + w, y + h / 2),
            "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}[side]


def route(frm, to, sside, dside, lane):
    """正交走线：源侧出 → 走 lane → 目标侧入。"""
    p0, p1 = anchor(frm, sside), anchor(to, dside)
    if sside in ("left", "right"):
        mx = lane if lane else (p0[0] + p1[0]) / 2
        pts = [p0, (mx, p0[1]), (mx, p1[1]), p1]
    else:
        my = lane if lane else (p0[1] + p1[1]) / 2
        pts = [p0, (p0[0], my), (p1[0], my), p1]
    out = [pts[0]]
    for q in pts[1:]:
        if abs(q[0] - out[-1][0]) > 0.5 or abs(q[1] - out[-1][1]) > 0.5:
            out.append(q)
    return out


def gap_center(to, dside, y):
    """把标签放到「目标方框」与「它前面/后面最近的方框」之间的空隙中心。

    这样标签既贴着自己的箭头，又不会压到任何方框（压框由 main() 的自检兜底）。
    """
    _, _, _, x, y0, w, h, _ = rect(to)
    if dside == "left":
        edge, tx = 0.0, x
        for b in BOXES:
            bx2 = b[3] + b[5]
            if bx2 <= x and b[4] <= y <= b[4] + b[6]:
                edge = max(edge, bx2)
        return (edge + tx) / 2 if edge else tx - 80
    if dside == "right":
        edge, tx = float(W), x + w
        for b in BOXES:
            if b[3] >= tx and b[4] <= y <= b[4] + b[6]:
                edge = min(edge, b[3])
        return (tx + edge) / 2 if edge < W else tx + 80
    return x + w / 2


def label_xy(to, dside, ldy):
    """标签位置：左右入线贴列间空隙中心；上下入线贴方框外侧。"""
    _, _, _, x, y, w, h, _ = rect(to)
    if dside == "left":
        return gap_center(to, "left", y + h / 2 + ldy), y + h / 2 + ldy, "middle"
    if dside == "right":
        return gap_center(to, "right", y + h / 2 + ldy), y + h / 2 + ldy, "middle"
    if dside == "top":
        return x + w / 2, y - 16 + ldy, "middle"
    return x + w / 2, y + h + 30 + ldy, "middle"


def build_svg(widths):
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#334155"/></marker></defs>',
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<text x="%d" y="40" font-family="%s" font-size="29" font-weight="bold" fill="#0f172a" '
         'text-anchor="middle">题目 4：简易拼图游戏 —— 系统总体框图（模块与实现电路一致）</text>'
         % (W // 2, FONT),
         '<text x="%d" y="66" font-family="%s" font-size="16.5" fill="#475569" text-anchor="middle">'
         '每个方框 = rtl/&lt;文件&gt;.vhd 中的一个 entity；每根箭头 = puzzle_top.vhd 例化时的端口连接'
         '（formal ← actual 网名）；位宽口径 [MSB:LSB]</text>' % (W // 2, FONT)]

    for name, x, y, w, h in ZONES:
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="12" fill="#f8fafc" stroke="#cbd5e1" '
                 'stroke-dasharray="7 6"/>' % (x, y, w, h))
        # 分区标题画在框**上方**：画在框内会被第一个方框压住（踩过）
        p.append('<text x="%d" y="%d" font-family="%s" font-size="15" font-weight="bold" '
                 'fill="#64748b">%s</text>' % (x + 12, y - 8, FONT, esc(name)))

    # 先线后方框（方框压住线头）
    for frm, to, net, sside, dside, lane, ldy in EDGES:
        pts = route(frm, to, sside, dside, lane)
        d = "M " + " L ".join("%.1f %.1f" % q for q in pts)
        p.append('<path d="%s" fill="none" stroke="#334155" stroke-width="1.9" marker-end="url(#ar)"/>' % d)

    for bid, title, sub, x, y, w, h, grp in BOXES:
        fill, stroke = GROUP_FILL[grp]
        dash = ' stroke-dasharray="7 5"' if grp in GLUE else ''
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="%s" stroke="%s" '
                 'stroke-width="2.2"%s/>' % (x, y, w, h, fill, stroke, dash))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%s" font-weight="bold" fill="#0f172a" '
                 'text-anchor="middle">%s</text>'
                 % (x + w / 2, y + 30, MONO, "15.5" if grp in GLUE else "19", esc(title)))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%s" fill="#475569" text-anchor="middle">'
                 '%s</text>' % (x + w / 2, y + 52, MONO, "12.5" if grp in GLUE else "13.5", esc(sub)))

    # 标签最后画（白底衬垫，保证压线也看得清）
    for frm, to, net, sside, dside, lane, ldy in EDGES:
        lx, ly, anc = label_xy(to, dside, ldy)
        txt = label_for(net, widths)
        tw = LBL_PX * len(txt) + 12
        rx = lx - tw if anc == "end" else (lx if anc == "start" else lx - tw / 2)
        p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="20" rx="4" fill="#ffffff" '
                 'fill-opacity="0.94" stroke="#e2e8f0"/>' % (rx, ly - 15, tw))
        p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" fill="#1e293b" '
                 'text-anchor="%s">%s</text>' % (lx, ly, MONO, LBL_FONT, anc, esc(txt)))

    # 图例（在图区下方，不遮挡任何方框）
    lx, ly, lw = 28, DIAG_BOTTOM + 10, W - 56
    p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="#ffffff" stroke="#cbd5e1"/>'
             % (lx, ly, lw, H - ly - 20))
    legend = [
        ("图例与对账口径（这张图是怎么保证「与代码一致」的）", True),
        ("· 方框 = rtl/&lt;文件&gt;.vhd 中的一个 entity。本图功能方框 11 个，与 puzzle_top.vhd 里 11 个 u_* 例化、"
         "以及 11 条 component 声明三方一致（scripts/gen_design_diagram.py --check 逐条核对）。", False),
        ("· 箭头标签 = 顶层例化时的端口连接网名（formal ← actual）；位宽取自各子模块 entity 的端口声明，"
         "顶层内部信号（eng_fr / mat_r / mrow）取自 puzzle_top.vhd 的 signal 声明。", False),
        ("· 数组型端口按人可读口径标注：shapes[4×64] = 4 块零片各 64 位掩码；shape_h / shape_w[4×3] = 4 块包围盒的高 / 宽。", False),
        ("· 虚线框「顶层行切片 + 行计数器」不是独立 entity，而是 puzzle_top.vhd 内的胶合逻辑："
         "把引擎输出的 64 位整帧平面按行号 mrow 切片成 8 位行数据 mat_r / mat_g 送点阵扫描（125 Hz）。", False),
        ("· 时钟与使能：clk_gen 由 50 MHz 产生 rst 与 7 路单周期 tick（t_1k / t_200 / t_100 / t_40 / t_4hz / t_1hz；"
         "o_tick_2hz 在顶层未接 open，2 Hz 方波由 t_4hz 翻转得到）。", False),
        ("· 另有 3 个板级诊断顶层（board_test_top / keypad_diag_top / keypad_raw_top）不属于本数据通路，未画出。", False),
        ("· ⚠️ 如实说明：`piece_rom.o_n`（网名 `piece_n`，本关零片数）在当前顶层**未被任何模块消费** —— "
         "引擎自己按关卡推导块数。这与编译报告里的 “assigned a value but never read” 警告一一对应，属已知遗留、不影响功能。", False),
        ("· 引脚号见报告 §1.3 引脚分配表（52 个用户引脚，与 quartus/puzzle.qsf 逐脚一致）；"
         "各模块的详细职责与完整端口清单见《实际设计方案》正文表格。", False),
    ]
    for i, (t, bold) in enumerate(legend):
        p.append('<text x="%d" y="%d" font-family="%s" font-size="%s" %s fill="#1e293b">%s</text>'
                 % (lx + 20, ly + 36 + i * 36, FONT, "20" if bold else "15.5",
                    'font-weight="bold"' if bold else '', t))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def render_png(svg_path, png_path, w, h):
    for exe in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.isfile(exe):
            url = "file:///" + svg_path.replace("\\", "/").replace(" ", "%20")
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=1.4", "--window-size=%d,%d" % (w, h),
                            "--screenshot=" + png_path, url], capture_output=True)
            return exe
    return None


# ---------------------------------------------------------------- 模块设计一览
# (模块, 关键输入, 关键输出, [设计要点 1~3 条])
# 端口名与位宽全部来自各 entity 的端口声明（--check 会逐个核对）；
# "设计要点"是人工写的**设计意图**，不重复端口信息。
MODULES = [
    ("clk_gen", ["i_clk", "i_btn"], ["o_rst", "o_tick_1k…o_tick_1hz"],
     ["级联分频链 c1..c7：只产生单周期使能脉冲，不生成分频时钟",
      "bcnt 对 BTN0 做 20 ms 饱和计数消抖后输出同步复位"]),
    ("keypad_scan", ["i_clk", "i_rst", "i_tick", "i_row[3:0]"],
     ["o_col[3:0]", "o_key[3:0]", "o_press", "o_release"],
     ["列独热低电平轮询，两拍一轮 = 10 ms",
      "cnt 连续 4 轮读数一致才判稳（40 ms）；松开立即撤销"]),
    ("game_fsm", ["i_press", "i_key[3:0]", "i_sw", "i_solved"],
     ["o_state[2:0]", "o_time[5:0]", "o_sound[3:0]", "o_go…o_rot"],
     ["st 六态：自检 / 待机 / 预览 / 对局 / 过关 / 失败",
      "key_of() 单点译码 8 个功能键，全部输出为单拍脉冲",
      "倒计时用 t_1hz 递减，闪烁由 t_4hz 翻转得 2 Hz"]),
    ("puzzle_ctrl", ["i_tick", "i_target[63:0]", "i_sh0…i_sh3[63:0]", "rnd_val[7:0]"],
     ["o_rowr[63:0]", "o_rowg[63:0]", "o_solved", "rnd_step"],
     ["散落：按包围盒取锚点 + 重叠则重采样（最多 15 次）",
      "平移/旋转 = 单拍 64 位位运算；碰撞用 chk_slot/chk_crow/chk_hit 串行扫",
      "判定：全图并集 == 目标图案（frm_ok），不做坐标绑定"]),
    ("rng_lfsr", ["i_step"], ["o_val[7:0]"],
     ["8 位 Galois LFSR，抽头 sr(7)/sr(5)/sr(4)/sr(3) → x⁸+x⁶+x⁵+x⁴+1",
      "复位种子 x\"5A\"，满周期 2⁸−1 = 255"]),
    ("piece_rom", ["i_level"], ["o_mask（4×64 位）", "o_h / o_w（4×3 位）", "o_n[2:0]"],
     ["纯常量查找表：4 块零片掩码与包围盒并行输出，零额外逻辑",
      "面积严格 3+6+3（第一关）与 3+2+5+6（第二/三关）"]),
    ("pattern_rom", ["i_level", "i_pat[1:0]"], ["o_mask[63:0]"],
     ["三关目标图案库共 5 幅（第一关 1 幅 + 第二/三关 4 幅）",
      "每幅都做过连通性检查，保证一定可解"]),
    ("disp_format", ["i_state[2:0]", "i_time[5:0]", "i_blink"],
     ["o_data[31:0]", "o_blank[7:0]"],
     ["倒计时 /10 与 %10 展开为 64 项常量表 —— 全设计不含除法器",
      "PASS / FAIL 用字母段形直接拼装，不需额外字符发生器"]),
    ("seg_scan", ["i_data[31:0]", "i_blank[7:0]"], ["o_seg[7:0]", "o_cat[7:0]"],
     ["idx 独热位选，段选与位选**同拍寄存**（无错位、无鬼影）",
      "1 kHz 节拍 ⇒ 每位 125 Hz，远高于人眼临界闪烁频率"]),
    ("dot_matrix_scan", ["i_row[2:0]", "i_colr[7:0]", "i_colg[7:0]"],
     ["o_row[7:0]", "o_colr[7:0]", "o_colg[7:0]"],
     ["行选通低电平独热（与手册 ROW 编号相反，已在代码注释里标注）",
      "行索引与该行红/绿列数据同拍更新；整屏 125 Hz"]),
    ("buzzer_ctrl", ["i_en", "i_sel[3:0]", "i_t4"], ["o_buzz"],
     ["÷256 预分频 + 8 位半周期计数器产生方波（省面积）",
      "step 走 16 步乐句；换音码**不复位**计数器（避免换音爆音）"]),
]
MW, MH = 2560, 1580
# 模块设计一览用同一套克制配色（与总体框图一致）
MZ_FILL = {k: (("#fffbeb", "#b45309") if k == "core" else ("#ffffff", "#334155"))
           for k in ("clk", "in", "ctl", "core", "mem", "out")}
MZONE = {"clk_gen": "clk", "keypad_scan": "in", "game_fsm": "ctl",
         "puzzle_ctrl": "core", "rng_lfsr": "mem", "piece_rom": "mem",
         "pattern_rom": "mem", "disp_format": "out", "seg_scan": "out",
         "dot_matrix_scan": "out", "buzzer_ctrl": "out"}


def build_modules_svg(widths, facts):
    pw, ph, gap = 600, 470, 28
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (MW, MH, MW, MH),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (MW, MH),
         '<text x="%d" y="42" font-family="%s" font-size="30" font-weight="bold" fill="#0f172a" '
         'text-anchor="middle">各模块设计一览（11 个子模块 · 端口名与位宽取自 rtl/*.vhd 的 entity 声明）</text>'
         % (MW // 2, FONT),
         '<text x="%d" y="70" font-family="%s" font-size="16.5" fill="#475569" text-anchor="middle">'
         '每格 = 一个 entity；框内左列输入、右列输出；下方是该模块的设计意图（完整端口清单见源码）</text>'
         % (MW // 2, FONT)]
    ents = facts["entities"]
    for i, (mod, ins, outs, notes) in enumerate(MODULES):
        col, row = i % 4, i // 4
        x = 28 + col * (pw + gap)
        y = 92 + row * (ph + gap)
        fill, stroke = MZ_FILL[MZONE[mod]]
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="#ffffff" stroke="%s" '
                 'stroke-width="2.2"/>' % (x, y, pw, ph, stroke))
        p.append('<rect x="%d" y="%d" width="%d" height="46" rx="10" fill="%s"/>'
                 % (x, y, pw, fill))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="21" font-weight="bold" '
                 'fill="#0f172a" text-anchor="middle">%s</text>' % (x + pw / 2, y + 30, MONO, esc(mod)))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="13" fill="#64748b" '
                 'text-anchor="middle">rtl/%s.vhd</text>' % (x + pw / 2, y + 64, MONO, esc(mod)))
        # 输入 / 输出两列
        for cx, head, items, colr in ((x + 18, "输入（i_*）", ins, "#0369a1"),
                                      (x + pw / 2 + 8, "输出（o_*）", outs, "#b91c1c")):
            p.append('<text x="%d" y="%d" font-family="%s" font-size="14" font-weight="bold" '
                     'fill="%s">%s</text>' % (cx, y + 92, FONT, colr, head))
            for k, it in enumerate(items):
                p.append('<text x="%d" y="%d" font-family="%s" font-size="14.5" fill="#1e293b">%s</text>'
                         % (cx, y + 116 + k * 24, MONO, esc(it)))
        p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#e2e8f0" stroke-width="1.5"/>'
                 % (x + 14, y + 250, x + pw - 14, y + 250))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="14" font-weight="bold" '
                 'fill="#0f172a">设计要点</text>' % (x + 18, y + 274, FONT))
        for k, nt in enumerate(notes):
            p.append('<text x="%d" y="%d" font-family="%s" font-size="14.5" fill="#334155">· %s</text>'
                     % (x + 18, y + 300 + k * 52, FONT, esc(nt)))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="生成《实际设计方案》的模块级系统总体框图与模块设计一览")
    ap.add_argument("--check", action="store_true", help="只校验图与事实源一致，不写盘")
    args = ap.parse_args()

    facts = load_facts()
    widths = net_widths(facts)
    declared = list(facts["entities"]["puzzle_top"]["components_declared"])
    instantiated = [i["entity"] for i in facts["entities"]["puzzle_top"]["instantiations"]]
    drawn = [b[0] for b in BOXES if b[7] not in GLUE and b[7] != "ext"]

    bad = []
    if sorted(drawn) != sorted(instantiated):
        bad.append("图里画的模块 %s ≠ 顶层例化的 %s" % (sorted(drawn), sorted(instantiated)))
    if sorted(declared) != sorted(instantiated):
        bad.append("component 声明 %s ≠ 例化 %s" % (sorted(declared), sorted(instantiated)))
    for frm, to, net, _s, _d, _l, _y in EDGES:
        for part in net.split("/"):          # `a/b/c` = 一根箭头代表一组网名，逐个都要存在
            if part not in widths:
                bad.append("网名 %s 既不在 puzzle_top 的端口映射里，也不是顶层 signal" % part)
        for bid in (frm, to):
            if bid not in [b[0] for b in BOXES]:
                bad.append("边 %s→%s 引用了不存在的方框 %s" % (frm, to, bid))
    for bid, _t, sub, *_ in BOXES:
        if sub.startswith("rtl/") and not os.path.isfile(os.path.join(ROOT, sub)):
            bad.append("%s 的副标题指向不存在的文件 %s" % (bid, sub))
    # 标签不许压进方框（横向留 6px 余量）
    for frm, to, net, _s, dside, _l, ldy in EDGES:
        lx, ly, anc = label_xy(to, dside, ldy)
        tw = LBL_PX * len(label_for(net, widths)) + 12
        x0 = lx - tw if anc == "end" else (lx if anc == "start" else lx - tw / 2)
        for bid, _t, _sub, bx, by, bw, bh, _g in BOXES:
            if x0 < bx + bw + 4 and x0 + tw > bx - 4 and ly - 15 < by + bh and ly + 5 > by:
                bad.append("标签 %s（贴 %s）压住了方框 %s" % (net, to, bid))

    # 模块设计一览：每个模块列出的端口名必须真的存在（`…`/`（…）`/`[..]` 是排版修饰，先剥掉）
    for mod, ins, outs, _notes in MODULES:
        names = {p["name"] for p in facts["entities"][mod].get("ports", [])}
        for it in list(ins) + list(outs):
            core = re.split(r"[\[（(]", it)[0]
            for part in re.split(r"[…/]", core):
                part = part.strip()
                if part and part not in names:
                    bad.append("模块一览里 %s 的端口 %r 不在 entity 声明里" % (mod, part))

    print("== 与事实源对账 ==")
    print("  顶层例化实体 %d 个：%s" % (len(instantiated), "、".join(instantiated)))
    print("  图中功能方框 %d 个（另有 %d 个虚线胶合框 + %d 个外部器件框）"
          % (len(drawn), sum(1 for b in BOXES if b[7] in GLUE),
             sum(1 for b in BOXES if b[7] == "ext")))
    print("  箭头 %d 根：%s" % (len(EDGES), "、".join(sorted({e[2] for e in EDGES}))))
    print("  模块设计一览 %d 格（与顶层例化集合一致：%s）"
          % (len(MODULES), sorted(m[0] for m in MODULES) == sorted(instantiated)))
    if bad:
        for b in bad:
            print("  [FAIL] %s" % b)
        return 1
    print("  OK：方框集合 / 文件名 / 网名 / 位宽 / 端口名 / 标签位置 全部自检通过")
    if args.check:
        return 0

    for svg_path, png_path, w, h, svg in (
            (OUT_SVG, OUT_PNG, W, H, build_svg(widths)),
            (OUT_SVG2, OUT_PNG2, MW, MH, build_modules_svg(widths, facts))):
        with open(svg_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        print("\n写出 %s（%d B）" % (os.path.relpath(svg_path, ROOT), len(svg.encode())))
        exe = render_png(svg_path, png_path, w, h)
        if exe and os.path.isfile(png_path):
            print("写出 %s（%d B，用 %s 渲染）"
                  % (os.path.relpath(png_path, ROOT), os.path.getsize(png_path), os.path.basename(exe)))
        else:
            print("[提示] 没找到 Chrome/Edge，只出了 SVG；PNG 请手动截。")
    # 站点页要一份 docs/assets/images/ 下的副本（与 docs/report/ 那份逐字节相同）
    shutil.copy2(OUT_PNG, OUT_PNG_SITE)
    print("写出 %s（站点副本，%d B）"
          % (os.path.relpath(OUT_PNG_SITE, ROOT), os.path.getsize(OUT_PNG_SITE)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
