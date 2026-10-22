#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_overview_diagram.py —— 生成「功能总览框图」（子系统级，放在模块级框图之前）

【它和 fig1_system_architecture 的分工】
    · 本图（功能总览）：**5 个功能子系统 + 时钟**，一眼看清"数据怎么流、谁管谁"；
      每个方框里用等宽小字列出它包含的 `rtl` 实体名，框内注明职责。
    · `fig1_system_architecture`（模块级）：11 个 entity 逐个成框、逐根端口连接 —— 查细节用。

【与代码一致的保证】
    本图的每个功能块都用 `ENTITIES_OF` 显式声明它包含哪些 entity；`--check` 会把
    这些集合与 `scripts/arch_data.py` 的 `ENTITIES`（从 facts.json + puzzle_top.vhd 现算）
    做**划分校验**：每个 entity 恰好出现一次、且没有多出来的名字。
    所以"总览里的功能划分"不是口头说法，是可对账的。

【用法】
    python scripts/gen_overview_diagram.py            # 写 SVG + PNG
    python scripts/gen_overview_diagram.py --check    # 只对账
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arch_data as AD  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_SVG = os.path.join(ROOT, "docs", "report", "fig_overview.svg")
OUT_PNG = os.path.join(ROOT, "docs", "report", "fig_overview.png")
OUT_PNG_SITE = os.path.join(ROOT, "docs", "assets", "images", "fig_overview.png")

W, H = 1740, 772
FONT = "Microsoft YaHei, SimSun, sans-serif"
MONO = "Consolas, Courier New, monospace"
INK = "#0f172a"
LINE = "#334155"
MUTED = "#64748b"
ACCENT = "#b45309"
CLK = "#b91c1c"

# ---- 功能块：id, x, y, w, h, 中文名, 职责, 包含的 entity ----
ENTITIES_OF = {
    "kbd": ["keypad_scan"],
    "fsm": ["game_fsm"],
    "core": ["puzzle_ctrl"],
    "dsp": ["disp_format", "seg_scan", "dot_matrix_scan"],
    "rom": ["piece_rom", "pattern_rom", "rng_lfsr"],
    "aud": ["buzzer_ctrl"],
    "clk": ["clk_gen"],
}
BLOCKS = [
    ("kbd",  120, 276, 300, 136, "键盘输入", "列扫描 · 40 ms 消抖"),
    ("fsm",  500, 276, 300, 136, "游戏控制", "六态状态机 · 倒计时 · 关卡"),
    ("core", 860, 276, 280, 136, "拼图核心", "锚点 · 钳位 · 锁定 · 全图判定"),
    ("dsp",  1200, 276, 300, 136, "显示系统", "段码 · 数码管扫描 · 点阵行扫描"),
    ("rom",  860, 470, 280, 136, "图案与随机数据", "零片掩码 · 目标图案 · LFSR"),
    ("aud",  1200, 470, 260, 136, "音效输出", "16 步乐句 · 数控分频"),
    ("clk",  660, 96, 320, 68, "时钟与节拍（clk_gen）", "50 MHz 分频 → rst + 7 路单周期节拍"),
]
EXT = [
    ("dev_disp", 1560, 270, 150, 150, ["数码管", "8×8 双色点阵"]),
    ("dev_buzz", 1560, 470, 150, 90, ["蜂鸣器"]),
]
CONTAINER = (100, 210, 1420, 492, "内部核心功能框图（6 个功能块 · 10 个 entity）")
RAIL_Y = 190

# ---- 连线：(源, 源侧, 目标, 目标侧, 标签, 额外拐点) ----
EDGES = [
    ("kbd", "r", "fsm", "l", "按键", []),
    ("fsm", "r", "core", "l", "控制", []),
    ("core", "r", "dsp", "l", "帧平面", []),
    ("dsp", "r", "dev_disp", "l", "", []),
    ("fsm", "b", "rom", "t", "关卡号", [(740, 412), (740, 440), (920, 440), (920, 470)]),
    ("rom", "t", "core", "b", "掩码/图案", []),
    ("fsm", "b", "aud", "l", "音效码", [(620, 412), (620, 640), (1160, 640), (1160, 538)]),
    ("aud", "r", "dev_buzz", "l", "", []),
]
KP = [("kp_row", 300, "in"), ("kp_col", 350, "out")]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tw(text, size):
    return sum((1.0 if ord(ch) > 0x2E7F else 0.62) * size for ch in text)


def block(bid):
    for b in BLOCKS:
        if b[0] == bid:
            return b
    raise KeyError(bid)


def anchor(bid, side):
    if bid.startswith("dev_"):
        for e in EXT:
            if e[0] == bid:
                _, x, y, w, h, _lines = e
                break
        else:
            raise KeyError(bid)
    else:
        _, x, y, w, h, _t, _s = block(bid)
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2),
            "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def pts_of(frm, fs, to, ts, extra):
    seq = [anchor(frm, fs)] + [tuple(q) for q in extra] + [anchor(to, ts)]
    out = [seq[0]]
    for q in seq[1:]:
        a = out[-1]
        if abs(a[0] - q[0]) > 1 and abs(a[1] - q[1]) > 1:
            out.append((q[0], a[1]) if fs in ("l", "r") else (a[0], q[1]))
        out.append(q)
    return out


def build():
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (W, H, W, H),
         '<defs>'
         '<marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.2" '
         'markerHeight="6.2" orient="auto-start-reverse">'
         '<path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker>'
         '<marker id="ac" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5.6" '
         'markerHeight="5.6" orient="auto-start-reverse">'
         '<path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>'
         % (LINE, CLK),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H)]

    # 标题
    p.append('<text x="%d" y="46" font-family="%s" font-size="27" font-weight="bold" '
             'fill="%s" text-anchor="middle">题目 4：简易拼图游戏 —— 功能总览框图</text>'
             % (W // 2, FONT, INK))
    p.append('<text x="%d" y="72" font-family="%s" font-size="15" fill="#475569" '
             'text-anchor="middle">按功能划分的 6 个功能块（每块内等宽小字 = 它包含的 '
             'rtl/&lt;同名&gt;.vhd 实体，共 11 个）；模块级连线与端口见下一张图</text>'
             % (W // 2, FONT))

    # ② 容器
    cx, cy, cw, ch, ctitle = CONTAINER
    p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="#f8fafc" stroke="#cbd5e1" '
             'stroke-width="1.6" stroke-dasharray="9 6"/>' % (cx, cy, cw, ch))
    p.append('<text x="%d" y="%d" font-family="%s" font-size="15" font-weight="bold" '
             'fill="%s">%s</text>' % (cx + 14, cy + 26, FONT, MUTED, esc(ctitle)))

    # ① 先画时钟分配（虚线）—— 后面的方框会压住穿过它们的部分
    p.append('<path d="M 820 90 L 820 %d" fill="none" stroke="%s" stroke-width="1.6" '
             'stroke-dasharray="6 5"/>' % (RAIL_Y, CLK))
    p.append('<path d="M 200 %d L 1400 %d" fill="none" stroke="%s" stroke-width="1.6" '
             'stroke-dasharray="6 5"/>' % (RAIL_Y, RAIL_Y, CLK))
    taps = {"kbd": 200, "fsm": 650, "core": 1000, "dsp": 1350, "rom": 950, "aud": 1300}
    for bid, tx in taps.items():
        ty = block(bid)[2]
        p.append('<path d="M %d %d L %d %d" fill="none" stroke="%s" stroke-width="1.6" '
                 'stroke-dasharray="6 5" marker-end="url(#ac)"/>'
                 % (tx, RAIL_Y, tx, ty, CLK))

    # ③ 实线数据流（先画线、后方框压住线头）
    for frm, fs, to, ts, label, extra in EDGES:
        pts = pts_of(frm, fs, to, ts, extra)
        d = "M " + " L ".join("%.1f %.1f" % q for q in pts)
        p.append('<path d="%s" fill="none" stroke="%s" stroke-width="2" '
                 'stroke-linejoin="round" marker-end="url(#ar)"/>' % (d, LINE))
        if label:
            segs = list(zip(pts[:-1], pts[1:]))
            horiz = [s for s in segs if abs(s[1][0] - s[0][0]) >= abs(s[1][1] - s[0][1])]
            if horiz:
                (x0, y0), (x1, y1) = max(horiz, key=lambda s: abs(s[1][0] - s[0][0]))
                lx, ly = (x0 + x1) / 2.0, min(y0, y1) - 16
            else:
                (x0, y0), (x1, y1) = max(segs, key=lambda s: abs(s[1][1] - s[0][1]))
                lx, ly = max(x0, x1) + 26, (y0 + y1) / 2.0
            wd = tw(label, 15) + 8
            p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="20" rx="3" fill="#ffffff"/>'
                     % (lx - wd / 2, ly - 16, wd))
            p.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="15" fill="%s" '
                     'text-anchor="middle">%s</text>' % (lx, ly, FONT, "#334155", esc(label)))

    # ④ 方框
    for bid, x, y, w, h, title, sub in BLOCKS:
        is_clk = bid == "clk"
        fill, stroke = ("#fef2f2", CLK) if is_clk else ("#ffffff", LINE)
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="%s" stroke="%s" '
                 'stroke-width="2.2"/>' % (x, y, w, h, fill, stroke))
        p.append('<text x="%.0f" y="%d" font-family="%s" font-size="21" font-weight="bold" '
                 'fill="%s" text-anchor="middle">%s</text>'
                 % (x + w / 2, y + 34, FONT, CLK if is_clk else INK, esc(title)))
        p.append('<text x="%.0f" y="%d" font-family="%s" font-size="13.5" fill="#475569" '
                 'text-anchor="middle">%s</text>'
                 % (x + w / 2, y + 58, FONT, esc(sub)))
        # 内含实体名（与代码对账的那一行）
        names = [] if bid == "clk" else ENTITIES_OF[bid]
        for i, nm in enumerate(names):
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="15" fill="%s" '
                     'text-anchor="middle">%s</text>'
                     % (x + w / 2, y + 84 + i * 19, MONO,
                        "#94a3b8" if is_clk else "#0f766e", esc(nm)))

    for bid, x, y, w, h, lines in EXT:
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="#eef2f7" stroke="#94a3b8" '
                 'stroke-width="1.8"/>' % (x, y, w, h))
        for i, t in enumerate(lines):
            p.append('<text x="%.0f" y="%d" font-family="%s" font-size="20" font-weight="bold" '
                     'fill="%s" text-anchor="middle">%s</text>'
                     % (x + w / 2, y + 36 + i * 30, FONT, INK, esc(t)))

    # ⑤ 键盘行列（板外）
    for name, yy, direction in KP:
        if direction == "in":
            p.append('<text x="20" y="%d" font-family="%s" font-size="15" font-weight="bold" '
                     'fill="%s">%s</text>' % (yy + 5, MONO, "#b45309", esc(name)))
            p.append('<path d="M 88 %d L 118 %d" fill="none" stroke="%s" stroke-width="2" '
                     'marker-end="url(#ar)"/>' % (yy, yy, "#b45309"))
        else:
            p.append('<text x="20" y="%d" font-family="%s" font-size="15" font-weight="bold" '
                     'fill="%s">%s</text>' % (yy + 5, MONO, "#b45309", esc(name)))
            p.append('<path d="M 118 %d L 88 %d" fill="none" stroke="%s" stroke-width="2" '
                     'marker-end="url(#ar)"/>' % (yy, yy, "#b45309"))

    p.append('</svg>')
    return "\n".join(p) + "\n"


def render_png(svg_path, png_path, w, h):
    import subprocess
    for exe in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.isfile(exe):
            url = "file:///" + os.path.abspath(svg_path).replace("\\", "/").replace(" ", "%20")
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=1.6", "--window-size=%d,%d" % (w, h),
                            "--screenshot=" + os.path.abspath(png_path), url],
                           capture_output=True)
            return exe
    return None


def check():
    bad = []
    seen = {}
    for bid, names in ENTITIES_OF.items():
        for nm in names:
            if nm not in AD.ENTITIES:
                bad.append("功能块 %s 里写了不存在的 entity：%s" % (bid, nm))
            if nm in seen:
                bad.append("entity %s 同时出现在 %s 和 %s（划分必须互斥）" % (nm, seen[nm], bid))
            seen[nm] = bid
    miss = sorted(set(AD.ENTITIES) - set(seen))
    if miss:
        bad.append("有 entity 没被任何功能块覆盖：%s" % miss)
    print("== 功能划分 vs facts/arch_data ==")
    print("  entity 总数 %d，已划分 %d 个功能块" % (len(AD.ENTITIES), len(ENTITIES_OF)))
    for bid, names in ENTITIES_OF.items():
        print("    %-5s ← %s" % (bid, "、".join(names)))
    if bad:
        for b in bad:
            print("  [FAIL] %s" % b)
        return 1
    print("  OK：11 个 entity 被 6 个功能块 + 1 个时钟块恰好划分一次")
    return 0


def main():
    ap = argparse.ArgumentParser(description="功能总览框图")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rc = check()
    if rc or args.check:
        return rc
    svg = build()
    with open(OUT_SVG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    print("\n写出 %s（%d B）" % (os.path.relpath(OUT_SVG, ROOT), len(svg.encode())))
    exe = render_png(OUT_SVG, OUT_PNG, W, H)
    if exe:
        print("写出 %s（%d B，%s 渲染）"
              % (os.path.relpath(OUT_PNG, ROOT), os.path.getsize(OUT_PNG),
                 os.path.basename(exe)))
    import shutil
    shutil.copy2(OUT_PNG, OUT_PNG_SITE)
    print("写出 %s（站点副本）" % os.path.relpath(OUT_PNG_SITE, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
