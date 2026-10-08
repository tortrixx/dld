# -*- coding: utf-8 -*-
"""Solve level-1 piece geometry: choose a target (anchor) placement for the three
pieces decoded from PDF figure 4-2 so that

  * every piece sits inside the 8x8 matrix,
  * the pieces are pairwise disjoint,
  * their union is EXACTLY the figure-4-1 rectangle (rows 2..5, cols 2..4),

then print the resulting target anchors and the derived target mask.  The chosen
targets become constants in rtl/puzzle_pkg.vhd, and the target mask is DERIVED as
the union of the pieces at their targets (so picture and pieces can never drift
apart).
"""
import itertools, json

ROWS, COLS = 8, 8

# pieces as decoded from figure 4-2, coordinates relative to their bbox top-left
P1 = {(0, 0), (0, 1), (0, 2)}                                  # 1x3 bar,  3 cells
P2 = {(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)}          # cross,    6 cells
P3 = {(0, 1), (1, 0), (1, 1)}                                  # L-tromino,3 cells
PIECES = [("P1", P1), ("P2", P2), ("P3", P3)]

FIG41 = {(r, c) for r in range(2, 6) for c in range(2, 5)}     # 12 cells

def bbox(cells):
    return (max(r for r, _ in cells) + 1, max(c for _, c in cells) + 1)

def place(cells, r0, c0):
    return {(r + r0, c + c0) for r, c in cells}

# candidate anchors: every position where the piece's bbox still fits in 8x8
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

# prefer a "centred / symmetric" placement: the cross (P2) as centred as possible
def score(sol):
    a1, a2, a3 = sol
    # prefer P2 (the 6-cell cross) near the centre, and the bar on top/bottom edge
    cr, cc = a2
    centre_pen = abs(cr - 3) + abs(cc - 2)
    # prefer the L-tromino in a corner region
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

# --- VHDL literals: bit index = 8*row + col, bit0 = top-left, bit63 leftmost char
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

# relative (normalised) mask for the ROM = the piece shape itself
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
}, open(r"C:\Users\sznnn\Desktop\dld\.ref\l1_geometry.json", "w"), indent=2)
print("\nwrote .ref/l1_geometry.json")
