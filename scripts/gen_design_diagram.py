#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_design_diagram.py —— 生成《实际设计方案》用的两张图

    ① `docs/report/fig1_system_architecture.{svg,png}` —— 系统总体框图（模块级）
       布局引擎在 `scripts/fig1_layout.py`，数据事实源在 `scripts/arch_data.py`。
       本文件只负责：**写盘 + 渲染 + 三重自检**。
    ② `docs/report/实际设计方案-模块设计一览.{svg,png}` —— 11 个模块的设计要点一览。

【为什么要有它】
    课程平台「实际设计方案（10 分）」的原文要求里有一句硬话：
        「**总体框图中的模块要求与实现电路(代码)一致**」。
    所以这张图的**方框集合、连线、网名、位宽、全局网络**全部从
    `facts/facts.json` 与 `rtl/*.vhd` 现算（见 `scripts/arch_data.py`），
    而且写盘之前要过三道关：

      ① 数据对账   `arch_data.verify_layout()`：方框集合 / 文件名 /
                   60 个 (源,目标,网名) 三元组 / 每个模块的全局网络 —— 一个都不许差；
      ② 几何体检   `audit_diagram`：线不许穿方框、标签不许压框或互相重叠、
                   不许越出画布安全区（ERROR 必须为 0）；
      ③ 端口名核对 `MODULES` 里列的每个端口名必须真的存在于该 entity 的声明里。

【用法】（在仓库根执行）
    python scripts/gen_design_diagram.py            # 写 SVG + 渲染 PNG + 站点副本
    python scripts/gen_design_diagram.py --check    # 只跑三重自检，不写盘

【依赖】
    纯标准库；渲染 PNG 用无头 Chrome / Edge（找不到就只出 SVG 并提示）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arch_data as AD          # noqa: E402
import audit_diagram as AUD     # noqa: E402
import fig1_layout as F1        # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_SVG = os.path.join(ROOT, "docs", "report", "fig1_system_architecture.svg")
OUT_PNG = os.path.join(ROOT, "docs", "report", "fig1_system_architecture.png")
# 站点页用的是 docs/assets/images/ 下那一份（内容相同，另存一份便于 docsify 引用）
OUT_PNG_SITE = os.path.join(ROOT, "docs", "assets", "images", "fig1_system_architecture.png")
OUT_SVG2 = os.path.join(ROOT, "docs", "report", "实际设计方案-模块设计一览.svg")
OUT_PNG2 = os.path.join(ROOT, "docs", "report", "实际设计方案-模块设计一览.png")


def render_png(svg_path, png_path, w, h):
    for exe in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.isfile(exe):
            url = "file:///" + os.path.abspath(svg_path).replace("\\", "/").replace(" ", "%20")
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--force-device-scale-factor=1.4", "--window-size=%d,%d" % (w, h),
                            "--screenshot=" + os.path.abspath(png_path), url],
                           capture_output=True)
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
MFONT = "Microsoft YaHei, SimSun, sans-serif"
MMONO = "Consolas, Courier New, monospace"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_modules_svg(facts):
    pw, ph, gap = 600, 470, 28
    p = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
         % (MW, MH, MW, MH),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (MW, MH),
         '<text x="%d" y="42" font-family="%s" font-size="30" font-weight="bold" fill="#0f172a" '
         'text-anchor="middle">各模块设计一览（11 个子模块 · 端口名与位宽取自 rtl/*.vhd 的 entity 声明）</text>'
         % (MW // 2, MFONT),
         '<text x="%d" y="70" font-family="%s" font-size="16.5" fill="#475569" text-anchor="middle">'
         '每格 = 一个 entity；框内左列输入、右列输出；下方是该模块的设计意图（完整端口清单见源码）</text>'
         % (MW // 2, MFONT)]
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
                 'fill="#0f172a" text-anchor="middle">%s</text>'
                 % (x + pw / 2, y + 30, MMONO, esc(mod)))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="13" fill="#64748b" '
                 'text-anchor="middle">rtl/%s.vhd</text>' % (x + pw / 2, y + 64, MMONO, esc(mod)))
        for cx, head, items, colr in ((x + 18, "输入（i_*）", ins, "#0369a1"),
                                      (x + pw / 2 + 8, "输出（o_*）", outs, "#b91c1c")):
            p.append('<text x="%d" y="%d" font-family="%s" font-size="14" font-weight="bold" '
                     'fill="%s">%s</text>' % (cx, y + 92, MFONT, colr, head))
            for k, it in enumerate(items):
                p.append('<text x="%d" y="%d" font-family="%s" font-size="14.5" fill="#1e293b">%s</text>'
                         % (cx, y + 116 + k * 24, MMONO, esc(it)))
        p.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#e2e8f0" stroke-width="1.5"/>'
                 % (x + 14, y + 250, x + pw - 14, y + 250))
        p.append('<text x="%d" y="%d" font-family="%s" font-size="14" font-weight="bold" '
                 'fill="#0f172a">设计要点</text>' % (x + 18, y + 274, MFONT))
        for k, nt in enumerate(notes):
            p.append('<text x="%d" y="%d" font-family="%s" font-size="14.5" fill="#334155">· %s</text>'
                     % (x + 18, y + 300 + k * 52, MFONT, esc(nt)))
    p.append('</svg>')
    return "\n".join(p) + "\n"


def check_modules(facts) -> list:
    """模块一览里列出的端口名必须真的存在于该 entity 的端口声明里。"""
    bad = []
    for mod, ins, outs, _notes in MODULES:
        names = {q["name"] for q in facts["entities"][mod].get("ports", [])}
        for it in list(ins) + list(outs):
            core = re.split(r"[\[（(]", it)[0]
            for part in re.split(r"[…/]", core):
                part = part.strip()
                if part and part not in names:
                    bad.append("模块一览里 %s 的端口 %r 不在 entity 声明里" % (mod, part))
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="生成《实际设计方案》的系统总体框图与模块设计一览")
    ap.add_argument("--check", action="store_true", help="只跑三重自检，不写盘")
    args = ap.parse_args()

    facts = AD.load_facts()
    widths = AD.net_widths(facts)
    res = F1.build(widths, facts)
    layout = res["layout"]

    print("== ① 数据对账（方框 / 文件名 / 连线三元组 / 全局网络）==")
    tmpd = tempfile.mkdtemp(prefix="fig1chk_")
    tmp_json = os.path.join(tmpd, "layout.json")
    with open(tmp_json, "w", encoding="utf-8") as fh:
        json.dump(layout, fh, ensure_ascii=False)
    rc1 = AD.verify_layout(tmp_json)

    print("\n== ② 几何体检（穿框 / 标签 / 越界）==")
    rc2 = AUD.main([tmp_json, "--fidelity", "--quiet"])

    print("\n== ③ 模块一览端口名核对 ==")
    bad3 = check_modules(facts)
    for b in bad3:
        print("  [FAIL] %s" % b)
    if not bad3:
        print("  OK：%d 个模块列出的输入/输出端口名全部存在于 entity 声明" % len(MODULES))

    shutil.rmtree(tmpd, ignore_errors=True)

    print("\n== 小结 ==")
    print("  ① 数据对账 %s ｜ ② 几何体检 %s ｜ ③ 端口名 %s"
          % ("PASS" if rc1 == 0 else "FAIL", "PASS" if rc2 == 0 else "FAIL",
             "PASS" if not bad3 else "FAIL"))
    if rc1 or rc2 or bad3:
        return 1
    if args.check:
        return 0

    # 注意：fig1_system_architecture.png 现在由 draw.io 渲染（scripts/gen_drawio_figures.py），
    # 这里只写 SVG 和「模块设计一览」；若再从 SVG 截一次 PNG 会把 draw.io 的图覆盖掉。
    for svg_path, png_path, w, h, svg in (
            (OUT_SVG, None, res["w"], res["h"], res["svg"]),
            (OUT_SVG2, OUT_PNG2, MW, MH, build_modules_svg(facts))):
        with open(svg_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(svg)
        print("\n写出 %s（%d B）" % (os.path.relpath(svg_path, ROOT), len(svg.encode())))
        if png_path is None:
            print("       （该图的 PNG 由 scripts/gen_drawio_figures.py 用 draw.io 渲染）")
            continue
        exe = render_png(svg_path, png_path, w, h)
        if exe and os.path.isfile(png_path):
            print("写出 %s（%d B，用 %s 渲染）"
                  % (os.path.relpath(png_path, ROOT), os.path.getsize(png_path),
                     os.path.basename(exe)))
        else:
            print("[提示] 没找到 Chrome/Edge，只出了 SVG；PNG 请手动截。")
    shutil.copy2(OUT_PNG2, os.path.join(ROOT, "docs", "assets", "images",
                                        os.path.basename(OUT_PNG2)))
    print("写出站点副本：%s" % os.path.basename(OUT_PNG2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
