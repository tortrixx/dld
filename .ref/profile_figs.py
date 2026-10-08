# -*- coding: utf-8 -*-
"""Locate actual dot centres in the figures and build exact 8x8 masks."""
import pathlib
from PIL import Image

FIG = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref\topics_figs")

def prof(name):
    im = Image.open(FIG / name).convert("RGB")
    W, H = im.size
    px = im.load()
    print(f"\n=== {name} {W}x{H} ===")

    # column-wise and row-wise count of "colourful" pixels (red or green)
    colred = [0] * W
    rowred = [0] * H
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            red = r > 110 and (r - g) > 40 and (r - b) > 40
            grn = g > 100 and (g - r) > 30 and (g - b) > 30
            if red or grn:
                colred[x] += 1
                rowred[y] += 1
    def runs(arr):
        out, s = [], None
        for i, v in enumerate(arr):
            if v > 0 and s is None:
                s = i
            elif v == 0 and s is not None:
                out.append((s, i - 1, (s + i - 1) / 2.0))
                s = None
        if s is not None:
            out.append((s, len(arr) - 1, (s + len(arr) - 1) / 2.0))
        return out
    cr, rr = runs(colred), runs(rowred)
    print(f"colour-blob column runs ({len(cr)}): " + ", ".join(f"{a}-{b}" for a, b, _ in cr))
    print(f"colour-blob row    runs ({len(rr)}): " + ", ".join(f"{a}-{b}" for a, b, _ in rr))
    return im, cr, rr

for n in ["p09_0_IM76.jpg", "p09_4_IM80.jpg", "p09_5_IM81.jpg"]:
    prof(n)
