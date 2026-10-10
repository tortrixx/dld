# -*- coding: utf-8 -*-
"""按精确的 8x8 点阵网格解码图片（原点 x=14.5、y=17，间距 16）。"""
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG = ROOT / ".ref" / "topics_figs"
GRID = {  # 每张图各自标定的原点，由色块质心推得
    "p09_0_IM76.jpg": (15.5, 17.0),
    "p09_4_IM80.jpg": (14.5, 17.0),
    "p09_5_IM81.jpg": (14.5, 17.0),
}
PITCH = 16.0

def decode(name):
    im = Image.open(FIG / name).convert("RGB")
    W, H = im.size
    px = im.load()
    x0, y0 = GRID[name]
    rows = []
    for r in range(8):
        line = []
        for c in range(8):
            cx = int(round(x0 + c * PITCH))
            cy = int(round(y0 + r * PITCH))
            cr = cg = cw = 0
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < W and 0 <= y < H:
                        rr, gg, bb = px[x, y]
                        if rr > 110 and (rr - gg) > 40 and (rr - bb) > 40:
                            cr += 1
                        elif gg > 100 and (gg - rr) > 30 and (gg - bb) > 30:
                            cg += 1
                        elif rr > 200 and gg > 200 and bb > 200:
                            cw += 1
            line.append("R" if cr >= 8 else ("G" if cg >= 8 else "."))
        rows.append(line)
    print(f"\n=== {name} ===")
    for r, line in enumerate(rows):
        print(f"  r{r}: " + " ".join(line))
    # 便于 VHDL 使用：逐行 8 位掩码，bit c = 第 c 列（MSB = col7 .. LSB = col0）
    print("  row masks (bit c = column c):")
    for r, line in enumerate(rows):
        bits = "".join("1" if ch != "." else "0" for ch in line)
        val = int(bits[::-1], 2)   # bit 下标 == 列下标 -> 为二进制字面量而反转
        lit = [c for c, ch in enumerate(line) if ch != "."]
        col = [ch for ch in line if ch != "."]
        print(f"    row{r}: \"{bits}\"  (0x{val:02X})  lit cols={lit} {set(col) if col else ''}")
    return rows

for n in ["p09_0_IM76.jpg", "p09_4_IM80.jpg", "p09_5_IM81.jpg"]:
    decode(n)
