# -*- coding: utf-8 -*-
"""对拍版 SVG（fig2/fig3 是手工维护的）改了文字后，重渲染它们的 PNG。

fig2: viewBox 890x428，输出 2.2x → 1958x942
fig3: viewBox 910x314，输出 2.2x → 2002x691
其它图都由各自的生成脚本负责 PNG，不要在这里加。
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPT = os.path.join(ROOT, "docs", "report")
SCALE = 2.2
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
          r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
TARGETS = ["fig2_game_fsm", "fig3_puzzle_core"]


def pick(exe_list):
    for e in exe_list:
        if os.path.isfile(e):
            return e
    return None


def main():
    exe = pick(CHROME)
    if not exe:
        print("找不到 chrome/edge，无法渲染")
        return 1
    for name in TARGETS:
        svg = os.path.join(RPT, name + ".svg")
        png = os.path.join(RPT, name + ".png")
        src = open(svg, encoding="utf-8").read()
        vb = re.search(r'viewBox="([\d.\- ]+)"', src)
        w, h = float(vb.group(1).split()[2]), float(vb.group(1).split()[3])
        url = "file:///" + svg.replace("\\", "/")
        subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=%s" % SCALE,
                        "--window-size=%d,%d" % (int(w), int(h)),
                        "--screenshot=" + png, url], capture_output=True)
        site = os.path.join(ROOT, "docs", "assets", "images", name + ".png")
        shutil.copy2(png, site)
        print("  %-16s %dx%d → %s（%d B，站点副本已同步）"
              % (name, w, h, os.path.basename(png), os.path.getsize(png)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
