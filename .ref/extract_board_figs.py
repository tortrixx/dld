# -*- coding: utf-8 -*-
"""提取实验板手册里的数码管模块图片（附图9／附图10），以读取板上印制的
实际段命名与排列顺序。"""
import pathlib
from pypdf import PdfReader

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld-lab")
OUT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\.ref") / "board_figs"
OUT.mkdir(parents=True, exist_ok=True)

r = PdfReader(str(ROOT / "MAXII数字实验板（LCM12864液晶版）.pdf"))
for pno in range(len(r.pages)):
    page = r.pages[pno]
    try:
        imgs = list(page.images)
    except Exception as e:
        print(f"page {pno+1}: {e}")
        continue
    if imgs:
        print(f"--- page {pno+1}: {len(imgs)} image(s)")
    for i, im in enumerate(imgs):
        dest = OUT / f"p{pno+1:02d}_{i}_{im.name}"
        dest.write_bytes(im.data)
        print(f"    {dest.name}  {len(im.data)} bytes")
