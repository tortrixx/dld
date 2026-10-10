# -*- coding: utf-8 -*-
"""求解第一关的零片几何：为从 PDF 图 4-2 解码出的三块零片
选择一组目标（锚点）摆位，使得

  * 每块零片都落在 8x8 点阵之内，
  * 各零片两两不相交，
  * 它们的并集**恰好**等于图 4-1 的矩形（行 2..5，列 2..4），

然后打印得到的目标锚点和推导出的目标掩码。选定的
目标会成为 rtl/puzzle_pkg.vhd 里的常量，而目标掩码是**推导**出来的 ——
即各零片在其目标位置上的并集（这样画面与零片永远不会
彼此脱节）。
"""
import itertools, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

ROWS, COLS = 8, 8

# 从图 4-2 解码出的各零片，坐标相对其包围盒左上角
P1 = {(0, 0), (0, 1), (0, 2)}                                  # 1x3 横条，3 格
P2 = {(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)}          # 十字形，6 格
P3 = {(0, 1), (1, 0), (1, 1)}                                  # L 形三格，3 格
PIECES = [("P1", P1), ("P2", P2), ("P3", P3)]

FIG41 = {(r, c) for r in range(2, 6) for c in range(2, 5)}     # 12 格

def bbox(cells):
    return (max(r for r, _ in cells) + 1, max(c for _, c in cells) + 1)

def place(cells, r0, c0):
    return {(r + r0, c + c0) for r, c in cells}

# 候选锚点：零片包围盒仍能放进 8x8 的每一个位置
def anchors(cells):
    h, w = bbox(cells)
    return [(r, c) for r in range(ROWS - h + 1) for c in range(COLS - w + 1)]

sols = []
for (n1, s1), (n2, s2), (n3, s3) in [ (PIECES[0], PIECES[1], PIECES[2]) ]:
    for a1 in anchors(s1):
        q1 = place(s1, *a1)
        for a2 in anchors(s2):
            q2 = place(s2, *a2)
            if q1 & q2:
                continue
            for a3 in anchors(s3):
                q3 = place(s3, *a3)
                if (q3 & q1) or (q3 & q2):
                    continue
                if (q1 | q2 | q3) == FIG41:
                    sols.append((a1, a2, a3))

print(f"exact target placements found: {len(sols)}")

def show(cells):
    return "\n".join("   " + " ".join("#" if (r, c) in cells else "." for c in range(8))
                     for r in range(8))

# 偏好「居中/对称」的摆位：十字形（P2）尽量居中
def score(sol):
    a1, a2, a3 = sol
    # 偏好 P2（6 格十字形）靠近中心，横条贴在上/下边缘
    cr, cc = a2
    centre_pen = abs(cr - 3) + abs(cc - 2)
    # 偏好把 L 形三格放在角部区域
    corner_pen = min(abs(a3[0] - 0), abs(a3[0] - 6)) + min(abs(a3[1] - 0), abs(a3[1] - 5))
    return (centre_pen, corner_pen)

sols.sort(key=score)
a1, a2, a3 = sols[0]
print(f"\nchosen target anchors:  P1{ a1 }  P2{ a2 }  P3{ a3 }")
q1, q2, q3 = place(P1, *a1), place(P2, *a2), place(P3, *a3)
print("\ncombined target picture (must equal fig 4-1):")
print(show(q1 | q2 | q3))
print("\nP1 (bar):");   print(show(q1))
print("P2 (cross):"); print(show(q2))
print("P3 (L):");     print(show(q3))

assert (q1 | q2 | q3) == FIG41
assert not (q1 & q2) and not (q1 & q3) and not (q2 & q3)

# --- VHDL 字面量：位号 = 8*行 + 列，bit0 = 左上角，bit63 对应最左边的字符
def vhdl_lit(cells):
    val = 0
    for r in range(8):
        for c in range(8):
            if (r, c) in cells:
                val |= 1 << (8 * r + c)
    return format(val, "064b")

print("\n--- VHDL constants (bit index = 8*row + col) ---")
print(f'L1_TARGET_MASK : "{vhdl_lit(q1 | q2 | q3)}"')
for nm, cells in (("Q1", q1), ("Q2", q2), ("Q3", q3)):
    print(f'{nm} placed mask : "{vhdl_lit(cells)}"')

# ROM 里的相对（归一化）掩码 = 零片形状本身
print("\n--- piece relative masks (as stored in piece_rom) ---")
for nm, cells in PIECES:
    h, w = bbox(cells)
    print(f'{nm}: bbox {h}x{w}  rel mask = "{vhdl_lit(cells)}"')

print("\n--- target anchors for RTL ---")
for nm, a in (("P1", a1), ("P2", a2), ("P3", a3)):
    print(f'{nm}: row={a[0]} col={a[1]}')
    print(f'   as 4-bit row/col: row="{format(a[0],"04b")}" col="{format(a[1],"04b")}"')

json.dump({
    "anchors": {"P1": a1, "P2": a2, "P3": a3},
    "target_mask": vhdl_lit(q1 | q2 | q3),
    "placed": {"Q1": vhdl_lit(q1), "Q2": vhdl_lit(q2), "Q3": vhdl_lit(q3)},
}, open(ROOT / ".ref" / "l1_geometry.json", "w"), indent=2)
print("\nwrote .ref/l1_geometry.json")
