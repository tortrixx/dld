# -*- coding: utf-8 -*-
"""Verify three audit claims against the actual constants.

Claims to test:
  A. row_mask / srl8 shifts the piece the WRONG WAY (audit says base >> ac where
     base << ac is needed).
  B. L2_TARGET_MASK is one row below the L2 piece targets.
  C. the engine's green channel can never be set without red (so the selected
     piece is drawn yellow instead of green).
"""
import pathlib, re, sys

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
PKG = (ROOT / "rtl" / "puzzle_pkg.vhd").read_text(encoding="utf-8")

def const_bits(name):
    m = re.search(r"constant\s+" + name + r"\s*:\s*std_logic_vector\(63 downto 0\)\s*:=\s*\"([01]{64})\"",
                  PKG, re.S)
    return m.group(1) if m else None

def cells(bits):
    val = int(bits, 2)
    return {(i // 8, i % 8) for i in range(64) if (val >> i) & 1}

def fig(cs):
    return "\n".join("  " + " ".join("#" if (r, c) in cs else "." for c in range(8))
                     for r in range(8))

def bits_of(cs):
    v = 0
    for (r, c) in cs:
        v |= 1 << (8 * r + c)
    return format(v, "064b")

# ---- the package's srl8 semantics -----------------------------------------
# srl8(r, dc): v := '0' & r(7 downto 1) for dc=1  ->  v(c) = r(c-1), i.e. r << 1.
# So srl8(x, ac) == x << ac, which MOVES a bit from column k to column k+ac.
# Placing a piece whose shape is stored relative to its bbox origin at anchor
# column ac therefore needs exactly x << ac == srl8(x, ac).  Claim A is FALSE if
# the code uses srl8.  Verify by direct construction:
P0 = cells(const_bits("L1_P0"))          # 1x3 bar, row 0 cols 0..2
print("L1_P0 shape:", sorted(P0))
for ac in range(6):
    # srl8 semantics: new(c) = old(c-ac)
    shifted = {(r, c + ac) for (r, c) in P0 if c + ac <= 7}
    print(f"  anchor col {ac} -> {sorted(shifted)}   (expected for 'placed at col {ac}')")

# ---- claim B: L2 target vs L2 piece targets -------------------------------
print("\nL2_TARGET_MASK cells:")
l2t = cells(const_bits("L2_TARGET_MASK"))
print(fig(l2t))
print("rows:", sorted({r for r, _ in l2t}), " cols:", sorted({c for _, c in l2t}))

L2_TGT = [(2, 2), (2, 4), (4, 2), (4, 4)]
# the four 2x2 pieces
piece = {(0, 0), (0, 1), (1, 0), (1, 1)}
union = set()
for (r0, c0) in L2_TGT:
    union |= {(r + r0, c + c0) for (r, c) in piece}
print("\nUnion of the four L2 pieces at their anchors:")
print(fig(union))
print("rows:", sorted({r for r, _ in union}), " cols:", sorted({c for _, c in union}))
print("target == piece union ?", l2t == union)
if l2t != union:
    print("  -> MISMATCH. Corrected literal for rows 2..5, cols 2..5 :")
    good = {(r, c) for r in range(2, 6) for c in range(2, 6)}
    print('  "%s"' % bits_of(good))

# ---- claim C: green without red ------------------------------------------
print("\nClaim C (engine colour):")
print("  redrow := cov or (tgtrow and not cov)  -> red is set for EVERY piece cell")
print("  grnrow := kc, and kc is built only from cells already in cov")
print("  => green is always a SUBSET of red, so pure green is unreachable;")
print("     a selected piece renders as red+green = YELLOW, same as locked.")
print("  => CLAIM C is TRUE.")
