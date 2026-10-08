# -*- coding: utf-8 -*-
"""Decode the 4x4 keypad layout from the course PDF figure 1-1.

Figure 1-1 is the authoritative key map for topic 4 as well ("键位如图1-1所示"
is stated for topic 1, and topic 4 says "所有控制键使用4x4矩阵键盘").  The text
layer of the PDF does not contain the labels, so the figure has to be read.

This prints a coarse ASCII view plus the detected text-free grid, so the key
labels can be transcribed by eye from the rendered image.
"""
import pathlib
from PIL import Image

FIG = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref\topics_figs")
im = Image.open(FIG / "p01_0_IM29.jpg").convert("RGB")
W, H = im.size
print("size", W, H)

# upscale and threshold to make the labels easier to read in the dump
SCALE = 2
big = im.resize((W * SCALE, H * SCALE), Image.LANCZOS)
big.save(FIG / "p01_keypad_big.png")
print("wrote", FIG / "p01_keypad_big.png", big.size)

# coarse ink map so the table structure is visible without an image viewer
px = big.load()
BW, BH = big.size
step = max(1, BW // 78)
for y in range(0, BH, step * 2):
    row = []
    for x in range(0, BW, step):
        r, g, b = px[x, y]
        row.append("#" if (r + g + b) < 480 else ".")
    print("".join(row))
