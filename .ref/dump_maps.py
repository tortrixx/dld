# -*- coding: utf-8 -*-
"""Dump every coloured pixel-run per page as a coarse ASCII map, to locate/identify each figure."""
import pathlib
from PIL import Image

FIG = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref\topics_figs")
for name in ["p09_0_IM76.jpg", "p09_4_IM80.jpg", "p09_5_IM81.jpg"]:
    im = Image.open(FIG / name).convert("RGB")
    W, H = im.size
    px = im.load()
    print(f"\n=== {name} {W}x{H} ===")
    # coarse 48x49 map: '.' empty, 'B' black ring, 'R' red, 'G' green
    step = 3
    for y in range(0, H, step):
        line = []
        for x in range(0, W, step):
            r, g, b = px[x, y]
            if r > 110 and (r - g) > 40 and (r - b) > 40:
                line.append("R")
            elif g > 100 and (g - r) > 30 and (g - b) > 30:
                line.append("G")
            elif r < 120 and g < 120 and b < 120:
                line.append("#")
            else:
                line.append(".")
        print("".join(line))
