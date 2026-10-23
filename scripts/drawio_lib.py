#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""drawio_lib.py —— 极小的 mxGraph(.drawio) 写出器。

为什么要它：
    报告里的三张图原本由自家渲染器直出 SVG。用户要求改用 **draw.io** 维护与导出
    （箭头样式统一、可在 draw.io 里直接编辑）。这里把"方框 / 连线 / 标签"翻译成
    mxCell，交给 draw.io 的命令行导出去出 PNG/SVG。

只做三件事：
    · box()  一个矩形节点（可带虚线/底色/字号）
    · edge() 一条折线（给定 waypoints，箭头统一 block 实心三角）
    · write_mxfile() 拼成标准 .drawio 文件
坐标与自家布局同单位（1 单位 = 1 pt），导出时乘 scale。
"""
from __future__ import annotations

import os
import subprocess
import tempfile

FONT = "Microsoft YaHei"
MONO = "Consolas"

# 主题色（与报告里其它插图保持一致）
INK = "#0F172A"
LINE = "#334155"
MUTED = "#64748B"
ACCENT = "#B45309"
CLK = "#B91C1C"
ZONE_FILL = "#F8FAFC"
ZONE_LINE = "#CBD5E1"


def _style(**kw):
    return "".join("%s=%s;" % (k, v) for k, v in kw.items())


def box(cid, x, y, w, h, text="", *, fill="#FFFFFF", stroke=LINE, sw=2,
        fs=19, bold=True, dashed=False, rounded=False, font=FONT, color=INK,
        shape=""):
    st = _style(**{"shape": shape}) if shape else ""
    st += _style(rounded=1 if rounded else 0, whiteSpace="wrap", html=1,
                fillColor=fill, strokeColor=stroke, strokeWidth=sw,
                fontSize=fs, fontFamily=font, fontColor=color,
                fontStyle=1 if bold else 0, align="center", verticalAlign="middle",
                dashed=1 if dashed else 0)
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace('"', "&quot;").replace("\n", "<br>"))
    return (f'<mxCell id="{cid}" value="{esc}" style="{st}" vertex="1" parent="1">'
            f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'as="geometry"/></mxCell>')


def edge(eid, src, tgt, points, text="", *, color=LINE, sw=2, fs=16,
         dashed=False, label_pos=None, start_arrow=False, font=FONT):
    """points 是中间拐点（不含两端）。label_pos = (x, y) 额外标签位置（相对几何）。"""
    st = _style(edgeStyle="orthogonalEdgeStyle", rounded=0, html=1,
                endArrow="block", endFill=1, endSize=8,
                startArrow="block" if start_arrow else "none",
                startFill=1 if start_arrow else 0,
                strokeColor=color, strokeWidth=sw,
                fontSize=fs, fontFamily=font, fontColor=color,
                labelBackgroundColor="#FFFFFF", dashed=1 if dashed else 0,
                jettySize="auto", orthogonalLoop=1, fixDash=1)
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    arr = ""
    if points:
        ps = "".join('<mxPoint x="%.1f" y="%.1f"/>' % (p[0], p[1]) for p in points)
        arr = f'<Array as="points">{ps}</Array>'
    lab = ""
    if text:
        if label_pos:
            lab = (f'<mxCell id="{eid}_l" value="{esc}" style="'
                   f'edgeLabel;html=1;fontSize={fs};fontFamily={font};'
                   f'fontColor={color};labelBackgroundColor=#FFFFFF;resizable=0;'
                   f'points=[];align=center;verticalAlign=middle;" vertex="1" '
                   f'connectable="0" parent="{eid}">'
                   f'<mxGeometry x="%.2f" relative="1" as="geometry">'
                   f'<mxPoint x="%.1f" y="%.1f" as="offset"/></mxGeometry></mxCell>'
                   % (label_pos[0], label_pos[1], label_pos[2]))
        else:
            lab = (f'<mxCell id="{eid}_l" value="{esc}" style="edgeLabel;html=1;'
                   f'fontSize={fs};fontFamily={font};fontColor={color};'
                   f'labelBackgroundColor=#FFFFFF;resizable=0;points=[];" '
                   f'vertex="1" connectable="0" parent="{eid}">'
                   f'<mxGeometry relative="1" as="geometry"/></mxCell>')
    ends = ''
    if src and tgt:
        ends = f' source="{src}" target="{tgt}"'
    return (f'<mxCell id="{eid}" value="" style="{st}" edge="1" parent="1"{ends}>'
            f'<mxGeometry relative="1" as="geometry">{arr}</mxGeometry></mxCell>{lab}')


def label(cid, x, y, text, *, fs=15, color=INK, font=FONT, bold=False, w=200, h=20,
          bg=False, align="left"):
    # bg=True：白底，用来遮住从标签下面穿过的连线（报告里其它插图也是这么处理的）
    # align：默认 "left"（x 即文字左边缘）；"center" 时 x 是标签框左边、文字在框内居中
    #        —— 用来让"标题/副标题"真正居中，不依赖字宽估算。
    st = _style(text="", html=1, align=align, verticalAlign="middle",
                fontSize=fs, fontFamily=font, fontColor=color,
                fontStyle=1 if bold else 0, strokeColor="none",
                fillColor="#FFFFFF" if bg else "none", spacing=2)
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return (f'<mxCell id="{cid}" value="{esc}" style="{st}" vertex="1" parent="1">'
            f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w}" height="{h}" as="geometry"/>'
            f'</mxCell>')


def write_mxfile(path, cells, name="diagram", width=1600, height=1200):
    xml = ['<mxfile host="dsh" type="device">',
           f'  <diagram id="d1" name="{name}">',
           f'    <mxGraphModel dx="1200" dy="900" grid="0" gridSize="10" guides="1" '
           f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
           f'pageWidth="{width}" pageHeight="{height}" math="0" shadow="0">',
           '      <root>', '        <mxCell id="0"/>', '        <mxCell id="1" parent="0"/>']
    xml += ["        " + c for c in cells]
    xml += ['      </root>', '    </mxGraphModel>', '  </diagram>', '</mxfile>', '']
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(xml))


def find_drawio():
    """找 draw.io 可执行文件（桌面版）。"""
    for c in (r"C:\Program Files\draw.io\draw.io.exe",
              r"C:\Program Files (x86)\draw.io\draw.io.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Programs\draw.io\draw.io.exe"),
              r"C:\ProgramData\chocolatey\bin\draw.io.exe",
              r"C:\ProgramData\chocolatey\lib\drawio\tools\draw.io.exe"):
        if os.path.isfile(c):
            return c
    return None


def export(drawio_exe, src, dst, *, fmt="png", scale=2.5, border=8, timeout=180):
    """调 draw.io 命令行导出。返回 (ok, 消息)。"""
    out = os.path.abspath(dst)
    args = [drawio_exe, "--export", "--format", fmt, "--output", out,
            "--scale", str(scale), "--border", str(border), "--no-sandbox",
            os.path.abspath(src)]
    # Electron 在无显示环境需要 --no-sandbox；另外它会把日志打到 stderr
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    ok = os.path.exists(out) and os.path.getsize(out) > 0
    return ok, (r.stdout or "") + (r.stderr or "")

def free_edge(eid, x1, y1, x2, y2, *, color=LINE, sw=2, dashed=False, arrow=True):
    """没有端子的直线段（两端用 sourcePoint/targetPoint 指定）。"""
    st = _style(edgeStyle="none", rounded=0, html=1,
                endArrow="block" if arrow else "none", endFill=1 if arrow else 0,
                endSize=8, startArrow="none", strokeColor=color, strokeWidth=sw,
                dashed=1 if dashed else 0)
    return (f'<mxCell id="{eid}" value="" style="{st}" edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint"/>'
            f'<mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint"/>'
            f'</mxGeometry></mxCell>')

def polyline(eid, pts, *, color=LINE, sw=2, arrow=True, dashed=False):
    """任意折线（无端子）：pts 含起点与终点。"""
    st = _style(edgeStyle="none", rounded=0, html=1,
                endArrow="block" if arrow else "none", endFill=1 if arrow else 0,
                endSize=8, startArrow="none", strokeColor=color, strokeWidth=sw,
                dashed=1 if dashed else 0, lineJoin="round")
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    mid = "".join('<mxPoint x="%.1f" y="%.1f"/>' % (p[0], p[1]) for p in pts[1:-1])
    arr = f'<Array as="points">{mid}</Array>' if mid else ""
    return (f'<mxCell id="{eid}" value="" style="{st}" edge="1" parent="1">'
            f'<mxGeometry relative="1" as="geometry">{arr}'
            f'<mxPoint x="{x1:.1f}" y="{y1:.1f}" as="sourcePoint"/>'
            f'<mxPoint x="{x2:.1f}" y="{y2:.1f}" as="targetPoint"/>'
            f'</mxGeometry></mxCell>')
