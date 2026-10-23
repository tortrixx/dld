#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「模块级总体框图」也改成 .drawio 输出。

几何（方框位置、32 条连线的折点、标签位置）全部来自 scripts/fig1_layout.py 的
布局 JSON —— 那份布局已经过 audit_diagram.py 的 16 项几何体检（0 ERROR），
这里只把它翻译成 mxGraph，让 draw.io 负责箭头与线型的最终呈现。

图内不再画"32 行明细表"，网名/位宽在报告 §2.3 的模块接口表里。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drawio_lib as DL  # noqa: E402


def text_w(text, size):
    """与 fig1_layout.text_w 同一套字符宽度估值（CJK 1.0、其余 0.62）。

    用来把标题 / 副标题真正居中：drawio 的 label 是 align="left"，
    原来写死 `W//2 - 330` 会让墨迹中心偏左 168 px（T1 返工 E）。
    """
    t = 0.0
    for ch in text:
        t += (1.0 if ord(ch) > 0x2E7F else 0.62) * size
    return t


def centered_x(text, fs, canvas_w):
    """返回"左对齐 label"的 x，使墨迹中心正好落在画布中线上。"""
    return (canvas_w - text_w(text, fs)) / 2.0


def build_arch(lay):
    cells = []
    # 分区虚线框（只画框，标题单独放）
    for z in lay.get("zones", []):
        cells.append(DL.box(z["id"], z["x"], z["y"], z["w"], z["h"], "",
                            fill="none", stroke="#CBD5E1", sw=1.3, bold=False,
                            dashed=True, rounded=True))
        cells.append(DL.label(z["id"] + "_t", z["x"] + 10, z["y"] + 6, z["title"],
                              fs=14, color=DL.MUTED, bold=True, w=420))
    # 连线（先画，方框后画会压住线头）
    for w in lay["wires"]:
        cells.append(DL.polyline(w["id"], [tuple(p) for p in w["pts"]],
                                 arrow=True, color=DL.LINE, sw=2))
    # 分组标签
    # 【必须按 anchor 还原布局算出的矩形】drawio_lib.label 是 align="left"，
    # 若把 lb["x"] 直接当左边喂进去，而布局 / 体检是按"居中"算的，两者会差
    # w/2 ≈ 40 px —— 标签会被推到别的干线上，甚至整块压到方框底下（T1 缺陷 1/2）。
    for w in lay["wires"]:
        if w.get("label"):
            lb = w["label"]
            wdt = lb.get("w", 160)
            if lb.get("anchor") == "start":
                lx = lb["x"]
            elif lb.get("anchor") == "end":
                lx = lb["x"] - wdt
            else:
                lx = lb["x"] - wdt / 2.0
            cells.append(DL.label(w["id"] + "_l", lx, lb["y"] - 11, lb["text"],
                                  fs=lb.get("size", 17), color=DL.LINE, bold=True,
                                  w=max(wdt, 24), h=22))
    # 方框
    for b in lay["boxes"]:
        title = b["title"]
        sub = b.get("sub") or ""
        kind = b.get("kind")
        fill = {"entity": "#FFFFFF", "ext": "#EEF2F7", "glue": "#FFFFFF"}[kind]
        stroke = {"entity": DL.LINE, "ext": "#94A3B8", "glue": DL.LINE}[kind]
        text = "<b>%s</b>" % title
        if kind == "ext" and b.get("lines"):
            # 【T1 返工 D】三行自己给死，禁止 draw.io 自动换行：
            # 原来 "50 MHz 有源晶振" 被断成 "50 MHz 有源晶" / "振"。
            l1, l2, l3 = b["lines"][:3]
            text = ('<b>%s</b><br><b>%s</b>'
                    '<br><span style="font-size:%spx;color:#64748B">%s</span>'
                    % (l1, l2, b.get("sub_size", 12), l3))
        elif sub:
            ssz = b.get("sub_size", 13)
            if kind == "ext":
                ssz = min(ssz, 13)
            text += '<br><span style="font-size:%spx">%s</span>' % (ssz, sub)
        fs = b.get("title_size", 19)
        if kind == "ext":
            fs = min(fs, 14)
        cells.append(DL.box(b["id"], b["x"], b["y"], b["w"], b["h"], text,
                            fill=fill, stroke=stroke, sw=2.2,
                            dashed=(kind == "glue"), rounded=(kind == "glue"),
                            fs=fs))
        g = b.get("globals") or []
        if g:
            cells.append(DL.label(b["id"] + "_g", b["x"] + 6, b["y"] + b["h"] - 20,
                                  "·".join(g), fs=13.5, color="#94A3B8", w=b["w"] - 10))
    # 标题与脚注
    cv = lay.get("canvas", {})
    W, H = cv.get("w", 1520), cv.get("h", 1032)
    t_title = "题目 4：简易拼图游戏 —— 系统总体框图"
    t_sub = ("每个实线框 = rtl/&lt;同名&gt;.vhd 中的一个 entity；同一个源模块出去的线"
             "共用一条主干，箭头旁为信号组名（网名与位宽见报告 §2.3）")
    # ⚠️ 用 align="center" 而不是"算字宽再左对齐"：`text_w()` 对副标题会高估约 100 px，
    #    左对齐时误差全堆到右侧，墨迹整体左移（实测副标题偏左 56 画布 px）。
    cells.append(DL.label("title", (W - 900) / 2, 4, t_title,
                          fs=27, bold=True, w=900, align="center"))
    cells.append(DL.label("subtitle", (W - 1300) / 2, 40, t_sub,
                          fs=15, color="#475569", w=1300, align="center"))
    cells.append(DL.label("note1", 16, H - 44,
                          "图例：实线框 = entity（11 个）· 虚线框 = 顶层胶合逻辑（非 entity）"
                          " · 浅灰框 = 板载器件；方框左下角 = 该模块消费的全局网络；"
                          "纯组合模块（disp_format / piece_rom / pattern_rom）不消费"
                          "全局网络，故无角标（不是漏画）",
                          fs=13, color="#334155", w=W - 40))
    return cells, W, H


def run():
    """现算一份 fig1 布局 JSON（调 fig1_layout 的 --dump），再翻译成 mxGraph。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = os.path.join(tempfile.mkdtemp(prefix="fig1lay_"), "layout.json")
    subprocess.run([sys.executable, os.path.join(root, "scripts", "fig1_layout.py"),
                    "--dump", tmp, "--svg", tmp + ".svg"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    lay = json.load(open(tmp, encoding="utf-8"))
    return build_arch(lay)
