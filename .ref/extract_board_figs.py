# -*- coding: utf-8 -*-
"""Extract the board manual's 7-segment module images (附图9/附图10) to read the
physical segment naming/ordering printed on the board."""
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
