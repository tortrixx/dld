# -*- coding: utf-8 -*-
"""Verify decoded figure data: area conservation + exact tiling of the L1 pattern."""
from itertools import product

# --- Decoded from PDF figures (top-left origin, row 0 = top) ---
FIG_4_1 = {  # 4 rows x 3 cols solid rectangle at rows 2-5, cols 2-4  (12 cells)
    (r, c) for r in range(2, 6) for c in range(2, 5)
}
FIG_4_2 = {  # scattered pieces, 12 cells total
    (0, 4), (0, 5), (0, 6),
    (2, 4), (2, 5), (2, 6),
    (3, 4), (3, 5),
    (4, 4),
    (4, 1),
    (5, 0), (5, 1),
}
FIG_4_3 = {  # selected piece shown GREEN
    (2, 4), (2, 5), (2, 6),
    (3, 4), (3, 5),
    (4, 4),
}

def ascii_of(cells):
    return "\n".join(
        "  " + " ".join("X" if (r, c) in cells else "." for c in range(8))
        for r in range(8)
    )

print("FIG 4-1 (12 cells):"); print(ascii_of(FIG_4_1))
print(f"area = {len(FIG_4_1)}\n")
print("FIG 4-2 (scattered):"); print(ascii_of(FIG_4_2))
print(f"area = {len(FIG_4_2)}\n")
print("FIG 4-3 (green selected):"); print(ascii_of(FIG_4_3))

# --- Area conservation: pieces must exactly cover the complete pattern ---
assert len(FIG_4_1) == 12, len(FIG_4_1)
assert len(FIG_4_2) == 12, len(FIG_4_2)
print("\n[OK] area conservation: complete pattern 12 == scattered cells 12")

# --- The three pieces as they appear in FIG 4-2 ---
P1 = {(0, 4), (0, 5), (0, 6)}                       # domino row, 3 cells
P2 = {(2, 4), (2, 5), (2, 6), (3, 4), (3, 5), (4, 4)}  # cross, 6 cells
P3 = {(4, 1), (5, 0), (5, 1)}                        # L-tromino, 3 cells
assert P1 | P2 | P3 == FIG_4_2, "piece partition must reproduce FIG 4-2"
assert len(P1) + len(P2) + len(P3) == 12
print("[OK] pieces 3+6+3 = 12, partition == FIG 4-2")
print(f"  P1 (3): {sorted(P1)}")
print(f"  P2 (6): {sorted(P2)}")
print(f"  P3 (3): {sorted(P3)}")

# --- FIG 4-3 green region must equal exactly one piece (P2) ---
assert FIG_4_3 == P2, "FIG 4-3 green region should be the selected piece"
print("[OK] FIG 4-3 green region == piece P2 (6 cells) -> confirms 'selected = green'")

# --- Exhaustive tiling search: can the 3 pieces tile the 4x3 rectangle? ---
def norm(cells):
    mr = min(r for r, _ in cells); mc = min(c for _, c in cells)
    return frozenset((r - mr, c - mc) for r, c in cells)

def transforms(cells):
    """All 8 dihedral transforms of a polyomino, normalized."""
    out = set()
    cur = set(cells)
    for _ in range(4):
        cur = {(c, -r) for r, c in cur}       # rotate 90
        out.add(norm(cur))
        out.add(norm({(r, -c) for r, c in cur}))  # + mirror
    return out

RECT = norm(FIG_4_1)
print(f"\nL1 complete pattern normalized {len(RECT)} cells: {sorted(RECT)}")

pieces = [("P1", P1), ("P2", P2), ("P3", P3)]
tilesets = [(nm, sorted(transforms(pc))) for nm, pc in pieces]

solutions = []
for t0 in tilesets[0][1]:
    for t1 in tilesets[1][1]:
        for t2 in tilesets[2][1]:
            for perm in [(t0, t1, t2), (t0, t2, t1), (t1, t0, t2),
                         (t1, t2, t0), (t2, t0, t1), (t2, t1, t0)]:
                for r0, c0 in product(range(-3, 4), repeat=2):
                    occ = {(r + r0, c + c0) for r, c in perm[0]}
                    if not occ <= RECT or len(occ) != 3:
                        continue
                    for r1, c1 in product(range(-3, 4), repeat=2):
                        occ1 = occ | {(r + r1, c + c1) for r, c in perm[1]}
                        if len(occ1) != 9 or not occ1 <= RECT:
                            continue
                        for r2, c2 in product(range(-3, 4), repeat=2):
                            occ2 = occ1 | {(r + r2, c + c2) for r, c in perm[2]}
                            if occ2 == RECT:
                                solutions.append((perm, (r0, c0), (r1, c1), (r2, c2)))
print(f"tilings found = {len(solutions)}")
assert solutions, "pieces must be able to exactly cover the complete pattern"
