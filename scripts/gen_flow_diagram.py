#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_flow_diagram.py —— 生成「游戏流程框图」（规范流程图：起止/处理/判断三种图形）

【为什么要有它】
    交付材料里一直缺一张**游戏决策流程**图。老师看现有的架构图时也反馈"更像流程图" ——
    那就把两件事分开：**架构**用模块框图（`gen_design_diagram.py`），
    **流程**用这张规范流程图，图形语义严格区分：
        圆角框 = 起止    矩形 = 处理    菱形 = 判断    箭头 = 流向（判断分支标 是/否）
    对局阶段是一个循环，所以单独用一个「循环区」容器框起来，回边都汇到一条总线上，
    不拉长线、也不穿过任何方框。

【事实来源】（图里每个判断/处理都必须在代码或报告里有依据）
    · `rtl/game_fsm.vhd`      六个状态与全部跳转条件（S_SELF_TEST / S_IDLE / S_PREVIEW /
                              S_PLAYING / S_WIN / S_FAIL，以及 i_solved / i_all_lock /
                              i_shuf_busy / i_press / i_key 的用法）
    · `rtl/puzzle_ctrl.vhd`   散落重采样上限、碰撞拦截、全图判据（frm_ok + alllock_r）
    · `rtl/puzzle_pkg.vhd`    关卡限时常量 T_PREVIEW / T_LEVEL1 / T_LEVEL2 / T_LEVEL3
    · `docs/report/实验报告_题目4_简易拼图游戏.typ` §2.4（六个状态的文字定义）
    `--check` 会把图里引用的常量与状态名与源码逐条核对。

【用法】
    python scripts/gen_flow_diagram.py            # 写 SVG + 渲染 PNG
    python scripts/gen_flow_diagram.py --check    # 只对账，不写盘
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "rtl", "puzzle_pkg.vhd")
OUT_SVG = os.path.join(ROOT, "docs", "report", "fig_game_flow.svg")
OUT_PNG = os.path.join(ROOT, "docs", "report", "fig_game_flow.png")

W, H = 1740, 2850
FONT = "Microsoft YaHei, SimSun, sans-serif"
LINE = "#334155"          # 统一线条色（不用花花绿绿）
FILL = "#ffffff"
FILL_DEC = "#f8fafc"
FILL_IO = "#f1f5f9"
ACCENT = "#b45309"        # 唯一强调色：循环容器与三个结局
FILL_ACCENT = "#fffbeb"

# ---------------------------------------------------------------- 图形
# (id, 类型, x, y, 宽, 高, [文字行])
# ⚠️ **所有菱形与矩形的中心 x 一律取 830**（画布坐标 520..1140 的中线）：
#    这样"矩形底边 → 菱形顶点"的竖线不需要横向折点，draw.io 的箭头才会正落在
#    菱形顶点上。原先 start/sw/gokey/lupd/lvlq/again 的中心分别是 870/870/870/790/870/870，
#    与下方矩形的 830 错开 ⇒ `lupd→lwin`、`win→lvlq` 两支箭头的尖端悬在菱形斜边
#    上方 ~24 px 的空白里（第二轮独立验收 R2 实测）。对齐后这些边都是纯竖线。
NODES = [
    ("start",   "stadium", 660, 66, 340, 58, ["上电 / 复位"]),
    ("sw",      "dec",     620, 166, 420, 150, ["SW7 = 1 ？", "（系统使能开关）"]),
    # ⚠️ 框高按"三行文字的墨迹块高 ≈ 1.4×字号 × 行数 ≈ 73.5 px"反推：74 只够"不溢出"，
    #    第三行距框底边只剩 1.3 px。要拿到 ≥10 px 上下留白，框高需要 ≈ 73.5 + 2×10 ≈ 94，
    #    这里取 113（pre-YS）×0.78 ≈ 88，实测上下留白各 ~7 / ~7（渲染级复看确认）。
    ("quiet",   "proc",    60, 196, 500, 113, ["全系统静默熄灭", "（低功耗，所有显示器件不显示）", "SW7 重新置 1 后回到上方判定"]),
    ("self",    "proc",    520, 372, 620, 82, ["自检 S_SELF_TEST（约 2 s）",
                                               "点阵 64 点全亮黄闪 2 Hz · 数码管 88888888 · POST 短鸣"]),
    ("idle",    "proc",    520, 496, 620, 76, ["待机 S_IDLE",
                                               "DISP7 显示 5 · DISP0 显示当前关卡"]),
    ("gokey",   "dec",     620, 614, 420, 150, ["按【开始】？"]),
    ("preview", "proc",    520, 806, 620, 82, ["预览 S_PREVIEW（约 5 s）",
                                               "点阵红光显示目标图案 · DISP7 倒计时 5→1"]),
    ("shuffle", "proc",    520, 930, 620, 82, ["散落（LFSR 取锚点）",
                                               "与已落位零片重叠则重新采样，最多 15 次"]),
    # ---- 对局循环（容器内） ----
    ("lk",      "dec",     620, 1128, 420, 150, ["有按键？"]),
    ("ltime",   "dec",    1120, 1128, 420, 150, ["剩余 ≤ 1 s ？"]),
    ("ldec",    "proc",    520, 1320, 620, 82, ["译码并执行按键",
                                                "选择 / 上 / 下 / 左 / 右 / 旋转 / 确认"]),
    ("lhit",    "dec",     620, 1444, 420, 150, ["碰撞或越界？"]),
    ("lblock",  "proc",   1120, 1470, 420, 76, ["拦截：零片不动", "（硬件实时拒绝非法指令）"]),
    ("lupd",    "proc",    520, 1636, 620, 82, ["更新零片位置 / 朝向",
                                                "按【确认】则锁定并并入已锁定平面"]),
    # ⚠️ 这里原来是**一个**复合判据「全图并集 == 目标图案 且全部零片已锁定？」，
    #    与 RTL 不符：`game_fsm.vhd:337-352` 里 i_solved（并集==目标 且 全锁）→ 过关，
    #    而 i_all_lock（全锁 但 并集≠目标）→ **立刻判负 S_FAIL**（B9 拼装错误）。
    #    拆成两级判据后，"全锁但拼错" 才会走到失败，而不是空转到超时。
    ("lall",    "dec",     604, 1760, 452, 150, ["全部零片已锁定？"]),
    ("lsolved", "dec",     604, 1990, 452, 150, ["全图并集 ==", "目标图案？"]),
    # ---- 循环之后 ----
    # ⚠️ 语义按 RTL 校正：`game_fsm.vhd:337-349` 只有**第三关**拼对才 `st <= S_WIN`，
    #    第一、二关拼对是 `level/lvl3` 置位后直接 `st <= S_PREVIEW`。所以
    #    「过关 S_WIN」= 终局状态，画在「关卡 < 3？」的**否**分支上。
    ("win",     "proc",    520, 2200, 620, 82, ["本关拼合成功",
                                                "并集 == 目标图案 且全部零片已锁定"]),
    ("lvlq",    "dec",     620, 2320, 420, 150, ["关卡 < 3 ？"]),
    ("nextlvl", "proc",   1260, 2357, 460, 76, ["关卡 +1", "→ 进入下一关预览"]),
    ("final",   "proc",    520, 2540, 620, 82, ["过关 S_WIN（第三关）",
                                                "显示 PASS · 奏通关号角 · 结算先闪 2 周期后常亮"]),
    ("again",   "dec",     620, 2660, 420, 150, ["按【开始】重开？"]),
    # 失败在循环之外（一局结束），所以画在容器右侧
    ("fail",    "proc",   1150, 2030, 500, 90, ["失败 S_FAIL",
                                                "显示 FAIL · 奏失败乐句 · 结算先闪后常亮"]),
]

# 对局循环容器（把"散落之后、判定之前"的决策圈在一个框里，回边汇到一条总线）
# ⚠️ 标题拆两行：单行「对局循环  S_PLAYING（限时 30 / 40 / 60 s）」宽约 430 px，
#    从容器左内边起排会一直伸到 x≈854 —— 正好被「散落 → 有按键?」的竖箭头（x=830）
#    从「60」与「s)」之间穿过。拆成两行后每行 ≤210 px，与箭头、圆角都留足净距。
LOOP_BOX = (400, 1050, 1220, 900, "对局循环  S_PLAYING")
LOOP_SUBTITLE = "（限时 30 / 40 / 60 s）"
LOOP_ARC = 14        # 容器圆角半径（画布 px）；draw.io 默认按短边比例给到 100+ px

# ---------------------------------------------------------------- 图例
# ⚠️ 图例**不能横跨整幅**：「上电 / 复位」框在 canvas x 700..1040 / y 51..109，
#    原来那条居中长图例（x 150..1550）正好压在该框的上边框上（净距 0，已实测）。
#    改成左上角空白区的三行短句（x 20..≈620，y 42..102），与首框水平错开。
SUBTITLE_LINES = [
    "圆角框 = 起止　矩形 = 处理　菱形 = 判断",
    "箭头 = 流向（判断分支标 是 / 否）",
    "「失败 S_FAIL」按【开始】重开；「关卡 +1」进入下一关预览；二者不画长回边",
]
SUBTITLE_X, SUBTITLE_Y0, SUBTITLE_DY = 20, 52, 20

BUS_X = 470          # 「回循环」总线竖线的 x
BUS_TOP_Y = 1203     # 进循环起点的高度（lk 垂直中心）

# ---------------------------------------------------------------- 标签定位（两个渲染器共用）
# ⚠️ 这两个常量与下面的 LABEL_POS 必须由 **SVG 版（build_svg）与 draw.io 版
#    （drawio_flow.build_flow）共用**：同一张图有两个交付物（报告用 PNG、实际设计方案
#    用 SVG），早先两边各算一套，结果 SVG 里还留着"待机 S_IDLE 框内侧的否标签"这类
#    已经修掉的缺陷（第二轮独立验收 docspkg-F5 实测）。
# 默认落点离线的距离（画布 px）：水平段上方 24 / 竖直段右侧 32。
LABEL_DY, LABEL_DX = 24, 32
# 键 = (源, 目标, 标签文字)，值 = (tx, ty) 画布坐标 —— 用于默认落点会压线/压框的边。
LABEL_POS = {
    ("gokey", "idle", "否"): (632, 510),
    ("ltime", "bus", "否"): (1400, 1018),
    ("ltime", "fail", "是"): (1650, 968),
    ("lk", "ldec", "是"): (874, 1008),
    ("gokey", "preview", "是"): (890, 606),
    ("lhit", "lupd", "否"): (880, 1252),
    ("lall", "lsolved", "是"): (900, 1545),
    ("lvlq", "final", "否"): (859, 1954),
}


def label_xy(frm, fs, to, ts, label, extra):
    """标签中心（画布坐标）：手工表优先，否则贴最长水平段上方 / 最长竖直段右侧。"""
    if (frm, to, label) in LABEL_POS:
        return LABEL_POS[(frm, to, label)]
    pts = pts_of(frm, fs, to, ts, extra)
    segs = list(zip(pts[:-1], pts[1:]))
    horiz = [s for s in segs if abs(s[1][0] - s[0][0]) >= abs(s[1][1] - s[0][1])]
    if horiz:
        (x0, y0), (x1, y1) = max(horiz, key=lambda s: abs(s[1][0] - s[0][0]))
        return (x0 + x1) / 2.0, min(y0, y1) - LABEL_DY
    (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][1] - s[0][1]))
    return max(x0, x1) + LABEL_DX, (y0 + y1) / 2.0


# ---------------------------------------------------------------- 连线
# (起点id, 起点方位, 终点id, 终点方位, 标签, [额外拐点])
# 方位：l/r/t/b；终点写 "bus" 表示汇入「回循环」总线
EDGES = [
    ("start", "b", "sw", "t", "", []),
    ("sw", "l", "quiet", "r", "否", []),
    
    ("sw", "b", "self", "t", "是", []),
    ("self", "b", "idle", "t", "", []),
    ("idle", "b", "gokey", "t", "", []),
    ("gokey", "l", "idle", "l", "否", [(600, 689), (600, 534)]),
    ("gokey", "b", "preview", "t", "是", []),
    ("preview", "b", "shuffle", "t", "", []),
    ("shuffle", "b", "lk", "t", "", []),
    ("lk", "r", "ltime", "l", "否", []),
    ("ltime", "r", "fail", "t", "是", [(1680, 1203), (1680, 1980), (1400, 1980)]),
    ("lk", "b", "ldec", "t", "是", []),
    ("ldec", "b", "lhit", "t", "", []),
    ("lhit", "r", "lblock", "l", "是", []),
    ("lblock", "b", "bus", "b", "", [(1330, 1740)]),
    # ⚠️ 缺陷 5：原折点 [(1330,1300)] 让回边沿 y=1014 横穿「有按键?→译码」的竖箭头，
    #    交叉点离「是」字只有 9 px。改成先向右出到 x=1560（lblock 右缘 1540 之外），
    #    沿容器内右侧空白下到容器底部空白带（y=BUS_BOT_Y），再向左汇入「回循环」总线。
    ("ltime", "b", "bus", "b", "否", [(1560, 1278), (1560, 1930)]),
    ("lhit", "b", "lupd", "t", "否", []),
    ("lupd", "b", "lall", "t", "", []),
    ("lall", "b", "lsolved", "t", "是", []),
    ("lall", "l", "bus", "b", "否", [(470, 1835)]),
    ("lsolved", "b", "win", "t", "是", []),
    # 「全锁但拼错」→ 立刻失败（RTL `game_fsm.vhd:350-352` 的 i_all_lock 分支，B9）
    ("lsolved", "r", "fail", "l", "否", []),
    ("win", "b", "lvlq", "t", "", []),
    ("lvlq", "r", "nextlvl", "l", "是", []),
    ("lvlq", "b", "final", "t", "否", []),
    ("final", "b", "again", "t", "", []),
    # 重开 → 回**预览**（不是待机）：`game_fsm.vhd:361-366` 对 S_WIN | S_FAIL 统一处理，
    # 按【开始】直接 `st <= S_PREVIEW`（并把 level/lvl3 清零）；而 S_IDLE 需要再按一次
    # 【开始】才进预览（`:281-287`），所以这里回 idle 会多出一次按键、与 RTL 不符。
    ("again", "l", "preview", "l", "是", [(360, 2735), (360, 845)]),
    # 「否」= 不重开 → 停留在通关结算画面（图例声明"判断分支标 是/否"，原来这个菱形漏了否）
    ("again", "r", "final", "r", "否", [(1160, 2735), (1160, 2581)]),
]

# ---------------------------------------------------------------- 纵向压缩
# 画布宽度受 S_FAIL 位置影响（原本挂最右边，把画布撑到 2320）；把它挪到循环下方后
# 宽度降到 1700，但高度 2680 反而成了瓶颈 —— 按 A4 版心宽高比，图会被"宽"卡住。
# 这里把所有**纵向坐标**（节点 y/高度、拐点 y、容器、总线、画布高）统一乘 YS，
# 字号不动 ⇒ 图变矮、字相对变大。横向一律不动。
YS = 0.78
NODES = [(nid, kind, x, int(y * YS), w, max(58, int(h * YS)), lines)
         for (nid, kind, x, y, w, h, lines) in NODES]
EDGES = [(a, b, c, d, lab, [(px, int(py * YS)) for px, py in ex])
         for (a, b, c, d, lab, ex) in EDGES]
LOOP_BOX = (LOOP_BOX[0], int(LOOP_BOX[1] * YS), LOOP_BOX[2],
            int(LOOP_BOX[3] * YS), LOOP_BOX[4])
H = int(H * YS)

# 缩放后重算总线端点：竖线顶端 = lk 菱形中心，底端 = 容器底部空白带（缺陷 5 的回边走这里）
_lk = [n for n in NODES if n[0] == "lk"][0]
BUS_TOP_Y = _lk[3] + _lk[5] // 2
BUS_BOT_Y = int(1930 * YS)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def node(nid):
    for n in NODES:
        if n[0] == nid:
            return n
    raise KeyError(nid)


def anchor(nid, side):
    _, _kind, x, y, w, h, _ = node(nid)
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2),
            "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


# ---------------------------------------------------------------- 无端子折线（带箭头）
# 缺陷 8：「全系统静默熄灭」原来是框内注记、没有回边。这里补一条回边 —— 从 quiet 底边
# 下到 y=270 的空白带，向右到 x=700（避开 sw→self 那条竖线，它现在在 sw 的中心 x=830），
# 再向上进 sw 菱形。
# ⚠️ 终点必须落在**菱形的斜边**上，不能落在外接矩形的底边：sw 是菱形（中心 x=830、
#    半宽 210、半高 58.5），底顶点在 (830, 246)，而 x=700 处的左下斜边只有
#    y≈209.8 —— 写 (700,246) 会让箭头悬空 36 px。所以终点用 dec_edge_y() 现算。
# 用「自由折线」而不是 EDGES 的原因：EDGES 的 ts 方位只能给到方框中心/顶点，
# 而这里要正好落在斜边的 x=700 处。
def dec_edge_y(nid, x):
    """菱形下侧斜边在给定 x 处的 y（nid 必须是 dec 类型）。"""
    _, _kind, bx, by, bw, bh, _lines = node(nid)
    cx, cy = bx + bw / 2.0, by + bh / 2.0
    t = (x - bx) / (cx - bx)
    return cy + t * (bh / 2.0)


FREE_EDGES = [
    ("quiet_return", [anchor("quiet", "b"), (310, 270), (700, 270),
                      (700, dec_edge_y("sw", 700))], ""),
]


def pts_of(frm, fs, to, ts, extra):
    """返回直角折线的点串。"""
    if to == "bus":
        pts = [anchor(frm, fs)] + [tuple(q) for q in extra] + [(BUS_X, extra[-1][1])]
        # ⚠️ 去重：extra[-1] 本来就可能是 (BUS_X, …)（如 lall→bus），不去重会留下
        #    零长度末段（`(470,1431) -> (470,1431)`），一旦加 marker 就会出问题。
        ded = [pts[0]]
        for q in pts[1:]:
            if abs(q[0] - ded[-1][0]) > 1 or abs(q[1] - ded[-1][1]) > 1:
                ded.append(q)
        return ded
    if frm == "bus":
        return [(BUS_X, BUS_TOP_Y)] + [tuple(q) for q in extra] + [anchor(to, ts)]
    seq = [anchor(frm, fs)] + [tuple(q) for q in extra] + [anchor(to, ts)]
    out = [seq[0]]
    for q in seq[1:]:
        a = out[-1]
        if abs(a[0] - q[0]) > 1 and abs(a[1] - q[1]) > 1:
            out.append((q[0], a[1]) if fs in ("l", "r") else (a[0], q[1]))
        out.append(q)
    ded = [out[0]]
    for q in out[1:]:
        if abs(q[0] - ded[-1][0]) > 1 or abs(q[1] - ded[-1][1]) > 1:
            ded.append(q)
    return ded


def shape_svg(n):
    nid, kind, x, y, w, h, lines = n
    cx = x + w / 2
    if kind == "stadium":
        s = ('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" stroke="%s" '
             'stroke-width="2"/>' % (x, y, w, h, h // 2, FILL_IO, LINE))
    elif kind == "dec":
        s = ('<polygon points="%d,%d %d,%d %d,%d %d,%d" fill="%s" stroke="%s" stroke-width="2"/>'
             % (cx, y, x + w, y + h / 2, cx, y + h, x, y + h / 2, FILL_DEC, LINE))
    else:
        fill = FILL_ACCENT if nid in ("win", "fail", "final") else FILL
        s = ('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="%s" stroke="%s" '
             'stroke-width="2"/>' % (x, y, w, h, fill, LINE))
    out = [s]
    cnt = len(lines)
    for i, t in enumerate(lines):
        size = 19.5 if i == 0 else 17.5
        weight = ' font-weight="bold"' if i == 0 else ''
        yy = y + h / 2 - (cnt - 1) * 13 + i * 26 + 7
        out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s"%s fill="#0f172a" '
                   'text-anchor="middle">%s</text>' % (cx, yy, FONT, size, weight, esc(t)))
    return out


def build_svg():
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (W, H, W, H),
         '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" '
         'markerHeight="6.5" orient="auto-start-reverse">'
         '<path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % LINE,
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<text x="%d" y="34" font-family="%s" font-size="30" font-weight="bold" fill="#0f172a" '
         'text-anchor="middle">题目 4：简易拼图游戏 —— 游戏流程框图</text>' % (W // 2, FONT)]
    for i, line in enumerate(SUBTITLE_LINES):
        p.append('<text x="%d" y="%d" font-family="%s" font-size="18" fill="#475569" '
                 'text-anchor="start">%s</text>'
                 % (SUBTITLE_X, SUBTITLE_Y0 + i * SUBTITLE_DY, FONT, esc(line)))

    # 对局循环容器（先画，压在连线下面）
    lx, ly, lw, lh, ltitle = LOOP_BOX
    p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="#fffbeb" stroke="%s" '
             'stroke-width="2.2" stroke-dasharray="10 6"/>' % (lx, ly, lw, lh, LOOP_ARC, ACCENT))
    p.append('<text x="%d" y="%d" font-family="%s" font-size="18" font-weight="bold" fill="%s">%s</text>'
             % (lx + 24, ly + 26, FONT, ACCENT, esc(ltitle)))
    p.append('<text x="%d" y="%d" font-family="%s" font-size="18" font-weight="bold" fill="%s">%s</text>'
             % (lx + 24, ly + 46, FONT, ACCENT, esc(LOOP_SUBTITLE)))

    # 连线
    for frm, fs, to, ts, label, extra in EDGES:
        pts = pts_of(frm, fs, to, ts, extra)
        d = "M " + " L ".join("%.1f %.1f" % q for q in pts)
        head = "" if to == "bus" else ' marker-end="url(#ar)"'
        p.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"%s/>' % (d, LINE, head))
        if label:
            # ⚠️ 与 draw.io 版**共用** label_xy()：早先这里自己算一套（偏移 18/27 + 白底
            #    矩形），结果 SVG 交付件里还留着"待机框内侧的否标签"等已修缺陷。现在两边
            #    同源；白底矩形一并去掉（draw.io 版就是无底色的，靠挪标签让路）。
            tx, ty = label_xy(frm, fs, to, ts, label, extra)
            p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="17" font-weight="bold" '
                     'fill="%s" text-anchor="middle">%s</text>' % (tx, ty, FONT, ACCENT, esc(label)))

    # 回循环总线：一条竖线汇齐所有回边，再横着进循环起点（只画一个箭头）
    p.append('<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" '
             'stroke-width="2" marker-end="url(#ar)"/>'
             % (BUS_X, BUS_BOT_Y, BUS_X, BUS_TOP_Y, anchor("lk", "l")[0], BUS_TOP_Y, LINE))
    p.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s"/>' % (BUS_X, BUS_BOT_Y, LINE))
    p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="17.5" fill="%s" '
             'text-anchor="start">回循环</text>' % (BUS_X + 12, BUS_TOP_Y - 24, FONT, ACCENT))

    # 无端子回边（缺陷 8）
    for _eid, fpts, _lab in FREE_EDGES:
        d = "M " + " L ".join("%.1f %.1f" % q for q in fpts)
        p.append('<path d="%s" fill="none" stroke="%s" stroke-width="2" '
                 'stroke-linejoin="round" marker-end="url(#ar)"/>' % (d, LINE))

    # 图形
    for n in NODES:
        p += shape_svg(n)
    p.append('</svg>')
    return "\n".join(p) + "\n"


def pkg_const(name):
    src = open(PKG, encoding="utf-8").read()
    m = re.search(r"constant\s+%s\s*:\s*\w+\s*:=\s*(\d+)" % name, src)
    return int(m.group(1)) if m else None


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


def main() -> int:
    ap = argparse.ArgumentParser(description="生成「游戏流程框图」")
    ap.add_argument("--check", action="store_true", help="只校验与源码一致，不写盘")
    args = ap.parse_args()

    t_prev, t1, t2, t3 = (pkg_const("T_PREVIEW"), pkg_const("T_LEVEL1"),
                          pkg_const("T_LEVEL2"), pkg_const("T_LEVEL3"))
    print("== 与 puzzle_pkg.vhd 对账 ==")
    print("  T_PREVIEW=%s  T_LEVEL1=%s  T_LEVEL2=%s  T_LEVEL3=%s" % (t_prev, t1, t2, t3))
    bad = []
    if (t_prev, t1, t2, t3) != (5, 30, 40, 60):
        bad.append("关卡限时常量与图里写的（5 s / 30 / 40 / 60 s）不一致：%s"
                   % ((t_prev, t1, t2, t3),))
    fsm = open(os.path.join(ROOT, "rtl", "game_fsm.vhd"), encoding="utf-8").read()
    for st in ("S_SELF_TEST", "S_IDLE", "S_PREVIEW", "S_PLAYING", "S_WIN", "S_FAIL"):
        if st not in fsm:
            bad.append("game_fsm.vhd 里找不到状态 %s" % st)
    ctrl = open(os.path.join(ROOT, "rtl", "puzzle_ctrl.vhd"), encoding="utf-8").read()
    for sig in ("frm_ok", "alllock_r", "chk_hit"):
        if sig not in ctrl:
            bad.append("puzzle_ctrl.vhd 里找不到 %s" % sig)
    # 方框里的文字不许溢出边框（与 audit_diagram 的 E-TEXT-OVERFLOW 同一套宽度估值）
    def _tw(text, size):
        return sum((1.0 if ord(ch) > 0x2E7F else 0.62) * size for ch in text)

    for nid, _kind, x, y, w, h, lines in NODES:
        widest = max((_tw(t, 19.5 if i == 0 else 17.5) for i, t in enumerate(lines)), default=0.0)
        # 菱形可用的横向宽度只有框宽的一半左右（内接矩形）
        avail = (w * 0.52 if _kind == "dec" else w) - 20
        if widest > avail:
            bad.append("节点 %s 的文字宽 %.0f px 超过可用宽度 %.0f px（框宽 %d）"
                       % (nid, widest, avail, w))

    if bad:
        for b in bad:
            print("  [FAIL] %s" % b)
        return 1
    print("  OK：六个状态、三个判据信号、四个限时常量都能在源码里找到且取值一致")
    print("  OK：%d 个节点的文字都在框内（菱形按内接宽度算）" % len(NODES))
    if args.check:
        return 0

    svg = build_svg()
    with open(OUT_SVG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print("\n写出 %s（%d B）" % (os.path.relpath(OUT_SVG, ROOT), len(svg.encode())))
    exe = render_png(OUT_SVG, OUT_PNG, W, H)
    if exe and os.path.isfile(OUT_PNG):
        print("写出 %s（%d B，用 %s 渲染）"
              % (os.path.relpath(OUT_PNG, ROOT), os.path.getsize(OUT_PNG), os.path.basename(exe)))
    else:
        print("[提示] 没找到 Chrome/Edge，只出了 SVG。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
