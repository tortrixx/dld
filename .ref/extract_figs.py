# -*- coding: utf-8 -*-
"""从题目 PDF 中提取内嵌图片（图就是视觉规格）。"""
import pathlib
from pypdf import PdfReader

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld-lab")
OUT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref") / "topics_figs"
OUT.mkdir(parents=True, exist_ok=True)

r = PdfReader(str(ROOT / "2026秋季学期数字电路与逻辑设计实验（下）实验题目.pdf"))
for pno in (0, 8, 9):          # 从 0 起算：第 1 页（键盘）、第 9 页、第 10 页
    page = r.pages[pno]
    imgs = list(page.images)
    print(f"--- page {pno+1}: {len(imgs)} image(s)")
    for i, im in enumerate(imgs):
        dest = OUT / f"p{pno+1:02d}_{i}_{im.name}"
        dest.write_bytes(im.data)
        print(f"    {dest.name}  {len(im.data)} bytes")
