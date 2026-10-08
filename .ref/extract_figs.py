# -*- coding: utf-8 -*-
"""Extract embedded images from the topics PDF (figures are visual specs)."""
import pathlib
from pypdf import PdfReader

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld-lab")
OUT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref") / "topics_figs"
OUT.mkdir(parents=True, exist_ok=True)

r = PdfReader(str(ROOT / "2026秋季学期数字电路与逻辑设计实验（下）实验题目.pdf"))
for pno in (0, 8, 9):          # 0-based: page 1 (keypad), page 9, page 10
    page = r.pages[pno]
    imgs = list(page.images)
    print(f"--- page {pno+1}: {len(imgs)} image(s)")
    for i, im in enumerate(imgs):
        dest = OUT / f"p{pno+1:02d}_{i}_{im.name}"
        dest.write_bytes(im.data)
        print(f"    {dest.name}  {len(im.data)} bytes")
