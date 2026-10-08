# -*- coding: utf-8 -*-
"""Verify every mask constant in rtl/puzzle_pkg.vhd against the PDF-decoded figures.

Parses the VHDL, decodes each constant to a cell set, and checks:
  * L1_TARGET == FIG 4-1 exactly
  * L1_P0/P1/P2 partition FIG 4-2 exactly (3+6+3 = 12)
  * L1_P1 == FIG 4-3 green region
  * L1 pieces tile L1_TARGET exactly
  * L2 pieces (16 cells, 4 pieces) tile L2_TARGET exactly
  * every piece fits in PIECE_MAX_DIM
"""
import re, pathlib
from itertools import product

PKG = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_pkg.vhd")
src = PKG.read_text(encoding="utf-8")

def const_bits(name):
    m = re.search(r"constant\s+" + name + r"\s*:\s*std_logic_vector\(63 downto 0\)\s*:=\s*\"([01]{64})\"",
                  src, re.S)
    if not m:
        raise SystemExit(f"constant {name} not found")
    return m.group(1)

def cells_xy(bits):
    """bits is the VHDL literal: leftmost char = bit63. Return {(row,col)} with bit0 = top-left."""
    val = int(bits, 2)          # bit i of val == index i in the literal from the right
    return {(i // 8, i % 8) for i in range(64) if (val >> i) & 1}

def norm(cells):
    """Translate a cell set so its bbox top-left is (0,0) -- shape comparison."""
    mr = min(r for r, _ in cells); mc = min(c for _, c in cells)
    return frozenset((r - mr, c - mc) for r, c in cells)

def fig(mask):
    return "\n".join("  " + " ".join("#" if (r, c) in mask else "." for c in range(8))
                     for r in range(8))

FIG41 = {(r, c) for r in range(2, 6) for c in range(2, 5)}
FIG42 = {(0,4),(0,5),(0,6),(2,4),(2,5),(2,6),(3,4),(3,5),(4,4),(4,1),(5,0),(5,1)}
FIG43 = {(2,4),(2,5),(2,6),(3,4),(3,5),(4,4)}

names = ["L1_TARGET_MASK","L1_P0","L1_P1","L1_P2","L2_TARGET_MASK",
         "L2_P0","L2_P1","L2_P2","L2_P3","WIN_MASK","FAIL_MASK"]
C = {n: cells_xy(const_bits(n)) for n in names}
for n in names:
    print(f"{n:16s} cells={len(C[n]):2d}  rows={sorted({r for r,_ in C[n]})} cols={sorted({c for _,c in C[n]})}")

ok = True
def chk(cond, msg):
    global ok
    print(("  [OK] " if cond else "  [FAIL] ") + msg)
    if not cond: ok = False

print("\n-- FIG 4-1 vs L1_TARGET_MASK")
# target picture is stored in ABSOLUTE matrix coordinates -> must match the figure exactly
chk(C["L1_TARGET_MASK"] == FIG41, "L1_TARGET_MASK == FIG 4-1 (4x3 rect @ rows2-5, cols2-4)")

print("\n-- FIG 4-2 partition (pieces are stored RELATIVE to their bbox top-left,")
print("   so compare shape after normalising both sides)")
P = [C["L1_P0"], C["L1_P1"], C["L1_P2"]]
chk(len(P[0]) == 3 and len(P[1]) == 6 and len(P[2]) == 3, "piece areas are 3 / 6 / 3")
# reconstruct FIG 4-2 by placing each piece at its position in the figure
FIG42_PIECES = [{(0,4),(0,5),(0,6)}, {(2,4),(2,5),(2,6),(3,4),(3,5),(4,4)}, {(4,1),(5,0),(5,1)}]
for i, fp in enumerate(FIG42_PIECES):
    chk(norm(P[i]) == norm(fp), f"L1_P{i} shape == figure piece {i+1} shape {sorted(norm(fp))}")
chk(sum(len(p) for p in P) == len(FIG42), "areas conserve (12 == 12)")
# disjointness must be checked on the PLACED pieces (the relative masks all
# share the origin (0,0) by construction, so comparing them directly is wrong)
fp_sets = [frozenset(x) for x in FIG42_PIECES]
chk(not (fp_sets[0] & fp_sets[1]) and not (fp_sets[0] & fp_sets[2])
    and not (fp_sets[1] & fp_sets[2]), "figure pieces are pairwise disjoint")
chk(set().union(*fp_sets) == FIG42, "figure pieces exactly partition FIG 4-2")

print("\n-- FIG 4-3 green region")
chk(norm(C["L1_P1"]) == norm(FIG43), "L1_P1 shape == FIG 4-3 green region (the selected piece)")

print("\n-- piece bounding boxes <= PIECE_MAX_DIM")
for n in ["L1_P0","L1_P1","L1_P2","L2_P0","L2_P1","L2_P2","L2_P3"]:
    h = max(r for r,_ in C[n]) + 1
    w = max(c for _,c in C[n]) + 1
    chk(h <= 3 and w <= 3, f"{n} bbox {h}x{w} <= 3x3")

def norm(cells):
    mr = min(r for r,_ in cells); mc = min(c for _,c in cells)
    return frozenset((r-mr, c-mc) for r,c in cells)

def transforms(cells):
    out, cur = set(), set(cells)
    for _ in range(4):
        cur = {(c, -r) for r, c in cur}
        out.add(norm(cur)); out.add(norm({(r,-c) for r,c in cur}))
    return sorted(out)

def count_tilings(target, pieces):
    T = norm(target)
    ts = [transforms(p) for p in pieces]
    n = len(pieces)
    # recursive exact cover over tile placements anchored anywhere in target bbox
    def rec(idx, occ):
        if idx == n:
            return 1 if occ == T else 0
        total = 0
        for t in ts[idx]:
            for r0, c0 in product(range(0, 9), repeat=2):
                place = {(r+r0, c+c0) for r,c in t}
                if place <= T and not (place & occ):
                    total += rec(idx + 1, occ | place)
        return total
    return rec(0, frozenset())

print("\n-- exact tilings (pieces cover the complete picture)")
n1 = count_tilings(C["L1_TARGET_MASK"], [C["L1_P0"], C["L1_P1"], C["L1_P2"]])
chk(n1 > 0, f"level-1 pieces can tile L1 target ({n1} tilings found)")
n2 = count_tilings(C["L2_TARGET_MASK"], [C["L2_P0"], C["L2_P1"], C["L2_P2"], C["L2_P3"]])
chk(n2 > 0, f"level-2 pieces can tile L2 target ({n2} tilings found)")

print("\n-- L2 area conservation")
chk(sum(len(C[f'L2_P{i}']) for i in range(4)) == len(C["L2_TARGET_MASK"]),
    f"L2 pieces {sum(len(C[f'L2_P{i}']) for i in range(4))} == target {len(C['L2_TARGET_MASK'])}")

# --- the target picture must equal the pieces at their TARGET ANCHORS --------
# This is the check that would have caught L2_TARGET_MASK being one row below the
# L2 piece targets: the ghost is drawn from the target mask, so if the two
# disagree the player is shown a picture that cannot be assembled.
print("\n-- target picture == union of pieces at their target anchors")
TGT = {
    "L1": ([C["L1_P0"], C["L1_P1"], C["L1_P2"]], [(2, 2), (3, 2), (4, 3)],
           C["L1_TARGET_MASK"]),
}
TGT2_TARGETS = [(2, 2), (2, 4), (4, 2), (4, 4)]
TGT["L2"] = ([C["L2_P0"], C["L2_P1"], C["L2_P2"], C["L2_P3"]], TGT2_TARGETS,
             C["L2_TARGET_MASK"])
for name, (pieces, anchors, target) in TGT.items():
    u = set()
    for pc, (ar, ac) in zip(pieces, anchors):
        u |= {(r + ar, c + ac) for (r, c) in norm(pc)}
    chk(u == target, f"{name}: target picture == union of pieces at target anchors")

print("\n" + ("ALL CHECKS PASSED" if ok else "*** SOME CHECKS FAILED ***"))
raise SystemExit(0 if ok else 1)
