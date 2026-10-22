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

W, H = 2320, 2680
FONT = "Microsoft YaHei, SimSun, sans-serif"
LINE = "#334155"          # 统一线条色（不用花花绿绿）
FILL = "#ffffff"
FILL_DEC = "#f8fafc"
FILL_IO = "#f1f5f9"
ACCENT = "#b45309"        # 唯一强调色：循环容器与三个结局
FILL_ACCENT = "#fffbeb"

# ---------------------------------------------------------------- 图形
# (id, 类型, x, y, 宽, 高, [文字行])
NODES = [
    ("start",   "stadium", 700, 66, 340, 58, ["上电 / 复位"]),
    ("sw",      "dec",     660, 166, 420, 150, ["SW7 = 1 ？", "（系统使能开关）"]),
    ("quiet",   "proc",    60, 200, 460, 76, ["全系统静默熄灭", "（低功耗，所有显示器件不显示）"]),
    ("self",    "proc",    520, 372, 620, 82, ["自检 S_SELF_TEST（2 s）",
                                               "点阵 64 点全亮黄闪 2 Hz · 数码管 88888888 · POST 短鸣"]),
    ("idle",    "proc",    520, 496, 620, 76, ["待机 S_IDLE",
                                               "DISP7 显示 5 · DISP0 显示当前关卡"]),
    ("gokey",   "dec",     660, 614, 420, 150, ["按【开始】？"]),
    ("preview", "proc",    520, 806, 620, 82, ["预览 S_PREVIEW（5 s）",
                                               "点阵红光显示目标图案 · DISP7 倒计时 5→1"]),
    ("shuffle", "proc",    520, 930, 620, 82, ["散落（LFSR 取锚点）",
                                               "与已落位零片重叠则重新采样，最多 15 次"]),
    # ---- 对局循环（容器内） ----
    ("lk",      "dec",     620, 1128, 420, 150, ["有按键？"]),
    ("ltime",   "dec",    1120, 1128, 420, 150, ["倒计时 = 0 ？"]),
    ("ldec",    "proc",    480, 1320, 620, 82, ["译码并执行按键",
                                                "选择 / 上 / 下 / 左 / 右 / 旋转 / 确认"]),
    ("lhit",    "dec",     620, 1444, 420, 150, ["碰撞或越界？"]),
    ("lblock",  "proc",   1120, 1470, 420, 76, ["拦截：零片不动", "（硬件实时拒绝非法指令）"]),
    ("lupd",    "proc",    480, 1636, 620, 82, ["更新零片位置 / 朝向",
                                                "按【确认】则锁定并并入已锁定平面"]),
    ("lwin",    "dec",     620, 1760, 420, 150, ["全图并集 == 目标图案", "且全部零片已锁定？"]),
    # ---- 循环之后 ----
    ("win",     "proc",    520, 1990, 620, 82, ["过关 S_WIN",
                                                "显示 PASS · 奏通关号角 · 结算先闪 2 周期后常亮"]),
    ("lvlq",    "dec",     660, 2114, 420, 150, ["关卡 < 3 ？"]),
    ("nextlvl", "proc",   1260, 2140, 460, 76, ["关卡 +1", "→ 回到待机"]),
    ("final",   "proc",    520, 2306, 620, 82, ["通关结算",
                                                "显示胜利图案 · 奏通关乐句（按【开始】重开）"]),
    ("again",   "dec",     660, 2430, 420, 150, ["按【开始】重开？"]),
    # 失败在循环之外（一局结束），所以画在容器右侧
    ("fail",    "proc",   1740, 1160, 540, 90, ["失败 S_FAIL",
                                                "显示 FAIL · 奏失败乐句 · 结算先闪后常亮"]),
]

# 对局循环容器（把"散落之后、判定之前"的决策圈在一个框里，回边汇到一条总线）
LOOP_BOX = (400, 1050, 1220, 900, "对局循环  S_PLAYING（限时 30 / 40 / 60 s）")

BUS_X = 470          # 「回循环」总线竖线的 x
BUS_TOP_Y = 1203     # 进循环起点的高度（lk 垂直中心）

# ---------------------------------------------------------------- 连线
# (起点id, 起点方位, 终点id, 终点方位, 标签, [额外拐点])
# 方位：l/r/t/b；终点写 "bus" 表示汇入「回循环」总线
EDGES = [
    ("start", "b", "sw", "t", "", []),
    ("sw", "l", "quiet", "r", "否", []),
    ("quiet", "t", "sw", "l", "", [(290, 120), (610, 120), (610, 241)]),
    ("sw", "b", "self", "t", "是", []),
    ("self", "b", "idle", "t", "", []),
    ("idle", "b", "gokey", "t", "", []),
    ("gokey", "l", "idle", "l", "否", [(600, 689), (600, 534)]),
    ("gokey", "b", "preview", "t", "是", []),
    ("preview", "b", "shuffle", "t", "", []),
    ("shuffle", "b", "lk", "t", "", []),
    ("lk", "r", "ltime", "l", "否", []),
    ("ltime", "r", "fail", "l", "是", []),
    ("lk", "b", "ldec", "t", "是", []),
    ("ldec", "b", "lhit", "t", "", []),
    ("lhit", "r", "lblock", "l", "是", []),
    ("lblock", "b", "bus", "b", "", [(1330, 1740)]),
    ("ltime", "b", "bus", "b", "", [(1330, 1300)]),
    ("lhit", "b", "lupd", "t", "否", []),
    ("lupd", "b", "lwin", "t", "", []),
    ("lwin", "l", "bus", "b", "否", [(470, 1835)]),
    ("lwin", "b", "win", "t", "是", []),
    ("win", "b", "lvlq", "t", "", []),
    ("lvlq", "r", "nextlvl", "l", "是", []),
    ("lvlq", "b", "final", "t", "否", []),
    ("final", "b", "again", "t", "", []),
    # 重开 → 回待机：走容器**左侧外面**的通道（x=360），不穿任何方框
    ("again", "l", "idle", "l", "是", [(360, 2505), (360, 534)]),
]


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


def pts_of(frm, fs, to, ts, extra):
    """返回直角折线的点串。"""
    if to == "bus":
        return [anchor(frm, fs)] + [tuple(q) for q in extra] + [(BUS_X, extra[-1][1])]
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
        size = 19 if i == 0 else 15.5
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
         'text-anchor="middle">题目 4：简易拼图游戏 —— 游戏流程框图</text>' % (W // 2, FONT),
         '<text x="%d" y="56" font-family="%s" font-size="16" fill="#475569" text-anchor="middle">'
         '圆角框 = 起止　矩形 = 处理　菱形 = 判断　箭头 = 流向（判断分支标 是 / 否）；'
         '对局阶段为循环，已用容器框圈出</text>' % (W // 2, FONT)]

    # 对局循环容器（先画，压在连线下面）
    lx, ly, lw, lh, ltitle = LOOP_BOX
    p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="#fffbeb" stroke="%s" '
             'stroke-width="2.2" stroke-dasharray="10 6"/>' % (lx, ly, lw, lh, ACCENT))
    p.append('<text x="%d" y="%d" font-family="%s" font-size="18" font-weight="bold" fill="%s">%s</text>'
             % (lx + 18, ly + 32, FONT, ACCENT, esc(ltitle)))

    # 连线
    for frm, fs, to, ts, label, extra in EDGES:
        pts = pts_of(frm, fs, to, ts, extra)
        d = "M " + " L ".join("%.1f %.1f" % q for q in pts)
        head = "" if to == "bus" else ' marker-end="url(#ar)"'
        p.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"%s/>' % (d, LINE, head))
        if label:
            ax, ay = pts[0]
            dx, dy = pts[1][0] - ax, pts[1][1] - ay
            if abs(dx) >= abs(dy):
                tx, ty = ax + dx * 0.42, ay - 12
            else:
                tx, ty = ax + (26 if dx >= 0 else -26), ay + dy * 0.42
            p.append('<rect x="%.1f" y="%.1f" width="34" height="24" rx="4" fill="#ffffff"/>'
                     % (tx - 17, ty - 17))
            p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="16" font-weight="bold" '
                     'fill="%s" text-anchor="middle">%s</text>' % (tx, ty, FONT, ACCENT, esc(label)))

    # 回循环总线：一条竖线汇齐所有回边，再横着进循环起点（只画一个箭头）
    p.append('<path d="M %.1f 1835 L %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" '
             'stroke-width="2" marker-end="url(#ar)"/>'
             % (BUS_X, BUS_X, BUS_TOP_Y, anchor("lk", "l")[0], BUS_TOP_Y, LINE))
    p.append('<circle cx="%.1f" cy="1835" r="5" fill="%s"/>' % (BUS_X, LINE))
    p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="15" fill="%s" '
             'text-anchor="start">回循环</text>' % (BUS_X + 12, BUS_TOP_Y - 24, FONT, ACCENT))

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
    if bad:
        for b in bad:
            print("  [FAIL] %s" % b)
        return 1
    print("  OK：六个状态、三个判据信号、四个限时常量都能在源码里找到且取值一致")
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
