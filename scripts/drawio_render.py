#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""drawio_render.py —— 用 draw.io 官方 viewer 把 .drawio 渲成 PNG（不装桌面版）。

原理：draw.io 的渲染器 `viewer-static.min.js` 是纯前端库。本地起一个 HTML 把
`.drawio` 的 XML 塞进 `data-mxgraph`，再用 headless Chrome 截图 —— 出来的就是
draw.io 自己的渲染结果（箭头样式、折线拐角、字体都与桌面版一致）。

（页面模板与官方 embed 示例一致：script 必须放在图形 div 之后，图形 div 必须带
`style="max-width:100%;"`；两者缺一都会渲染成空白 —— 这是踩过的坑。）

用法：
    python scripts/drawio_render.py <in.drawio> <out.png> [--scale 2.4] [--pad 16]
    python scripts/drawio_render.py --check
"""
from __future__ import annotations

import argparse
import html as H
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER = os.path.join(ROOT, ".tmp", "tools", "drawio", "viewer.min.js")
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
          r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]

PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:0;background:#fff}#wrap{padding:__PAD__px}</style>
</head><body>
<div id="wrap"><div class="mxgraph" style="max-width:100%;border:none;" data-mxgraph="__CFG__"></div></div>
<script src="viewer.min.js"></script>
</body></html>
"""


def pick_chrome():
    for c in CHROME:
        if os.path.isfile(c):
            return c
    return None


def png_size(path):
    with open(path, "rb") as fh:
        head = fh.read(24)
    return struct.unpack(">II", head[16:24])


def diagram_bbox(xml):
    xs, ys = [0.0], [0.0]
    for m in re.finditer(r'<mxGeometry[^>]*?x="(-?[\d.]+)"[^>]*?y="(-?[\d.]+)"'
                         r'[^>]*?width="([\d.]+)"[^>]*?height="([\d.]+)"', xml):
        x, y, w, h = (float(v) for v in m.groups())
        xs.append(x + w)
        ys.append(y + h)
    for m in re.finditer(r'<mxPoint x="(-?[\d.]+)" y="(-?[\d.]+)"', xml):
        xs.append(float(m.group(1)))
        ys.append(float(m.group(2)))
    return max(xs) + 40, max(ys) + 40


def render(src, dst, scale=2.4, pad=16, verbose=True):
    chrome = pick_chrome()
    if not chrome:
        return False, "找不到 chrome/edge"
    if not os.path.isfile(VIEWER):
        return False, "缺少 viewer.min.js（%s）" % VIEWER

    xml = open(src, encoding="utf-8").read()
    w, h = diagram_bbox(xml)
    cfg = json.dumps({"highlight": "#0000ff", "nav": False, "resize": True,
                      "toolbar": "", "xml": xml}, ensure_ascii=False)
    page = PAGE.replace("__PAD__", str(pad)).replace("__CFG__", H.escape(cfg, quote=True))

    tmpdir = tempfile.mkdtemp(prefix="drawio_")
    html_path = os.path.join(tmpdir, "page.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    shutil.copy2(VIEWER, os.path.join(tmpdir, "viewer.min.js"))

    shot = os.path.join(tmpdir, "shot.png")
    win_w = int(w) + 2 * pad
    win_h = int(h) + 2 * pad
    args = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--force-device-scale-factor=%s" % (scale,),
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=15000",
            "--window-size=%d,%d" % (win_w, win_h),
            "--screenshot=" + shot,
            "file:///" + html_path.replace("\\", "/")]
    subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
    if not os.path.isfile(shot):
        return False, "截图失败（未生成 %s）" % shot
    try:
        from PIL import Image, ImageChops
        im = Image.open(shot).convert("RGB")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        box = ImageChops.difference(im, bg).getbbox()
        if box:
            m = 4 * pad
            box = (max(0, box[0] - m), max(0, box[1] - m),
                   min(im.size[0], box[2] + m), min(im.size[1], box[3] + m))
            im = im.crop(box)
        im.save(dst, optimize=True)
    except Exception as exc:                       # Pillow 缺失时退回原图
        shutil.copy2(shot, dst)
        if verbose:
            print("   (未裁剪：%s)" % exc)
    ok = os.path.getsize(dst) > 0
    if verbose:
        print("  %-28s -> %-30s %s" % (os.path.basename(src), os.path.basename(dst),
                                       png_size(dst) if ok else "FAIL"))
    return ok, ""


def main(argv):
    ap = argparse.ArgumentParser(description="用 draw.io viewer 渲染 .drawio")
    ap.add_argument("src", nargs="?")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--scale", type=float, default=2.4)
    ap.add_argument("--pad", type=int, default=16)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        print("viewer:", "OK" if os.path.isfile(VIEWER) else "缺失")
        print("chrome:", pick_chrome() or "缺失")
        return 0 if (os.path.isfile(VIEWER) and pick_chrome()) else 1
    if not (a.src and a.dst):
        ap.error("需要 <in.drawio> <out.png>")
    ok, msg = render(a.src, a.dst, a.scale, a.pad)
    if not ok:
        print("FAIL", msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
