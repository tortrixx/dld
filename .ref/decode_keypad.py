# -*- coding: utf-8 -*-
"""从课程 PDF 的图 1-1 解码 4x4 键盘布局。

图 1-1 同时也是题目 4 的权威键位图（题目 1 写明"键位如图1-1所示"，
题目 4 则说"所有控制键使用4x4矩阵键盘"）。PDF 的文字
层不含键位标签，所以必须读图。

这里打印一幅粗略的 ASCII 视图，以及检测出的无文字网格，以便对着
渲染出的图像用肉眼抄录键位标签。
"""
import pathlib
from PIL import Image

FIG = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref\topics_figs")
im = Image.open(FIG / "p01_0_IM29.jpg").convert("RGB")
W, H = im.size
print("size", W, H)

# 放大并二值化，让标签在转储里更容易辨认
SCALE = 2
big = im.resize((W * SCALE, H * SCALE), Image.LANCZOS)
big.save(FIG / "p01_keypad_big.png")
print("wrote", FIG / "p01_keypad_big.png", big.size)

# 粗略墨迹图，不用看图工具也能看出表格结构
px = big.load()
BW, BH = big.size
step = max(1, BW // 78)
for y in range(0, BH, step * 2):
    row = []
    for x in range(0, BW, step):
        r, g, b = px[x, y]
        row.append("#" if (r + g + b) < 480 else ".")
    print("".join(row))
