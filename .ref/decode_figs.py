# -*- coding: utf-8 -*-
"""把题目 PDF 里的 8x8 点阵图解码成精确的坐标掩码。"""
import pathlib
from PIL import Image

FIG = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref\topics_figs")

def analyse(name, rows=8, cols=8):
    im = Image.open(FIG / name).convert("RGB")
    W, H = im.size
    px = im.load()
    # 板内区域：图有黑色边框；在其内部按网格取样
    print(f"\n=== {name}  {W}x{H} ===")
    # 求非白色内容的包围盒
    xs, ys = [], []
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if not (r > 230 and g > 230 and b > 230):
                xs.append(x); ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    print(f"content bbox x[{x0},{x1}] y[{y0},{y1}]  size {x1-x0+1}x{y1-y0+1}")
    # 由包围盒推算间距
    pitchx = (x1 - x0 + 1) / cols
    pitchy = (y1 - y0 + 1) / rows
    grid = []
    for r in range(rows):
        line = []
        for c in range(cols):
            cx = int(x0 + (c + 0.5) * pitchx)
            cy = int(y0 + (r + 0.5) * pitchy)
            # 取小片区域采样，判定主导颜色
            cntR = cntG = cntW = 0
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    xx, yy = cx + dx, cy + dy
                    if 0 <= xx < W and 0 <= yy < H:
                        rr, gg, bb = px[xx, yy]
                        if rr > 150 and gg < 120 and bb < 120:
                            cntR += 1
                        elif gg > 110 and rr < 160 and bb < 160:
                            cntG += 1
                        elif rr > 200 and gg > 200 and bb > 200:
                            cntW += 1
            line.append("R" if cntR > 12 else ("G" if cntG > 12 else "."))
        grid.append(line)
    for line in grid:
        print("   " + " ".join(line))
    return grid

for n in ["p09_0_IM76.jpg", "p09_4_IM80.jpg", "p09_5_IM81.jpg"]:
    analyse(n)
