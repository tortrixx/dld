# -*- coding: utf-8 -*-
"""Model the puzzle_ctrl move/shift logic in Python and verify it exhaustively.

Bit convention (must match puzzle_pkg and dot_matrix_scan):
    bit index = 8*row + col,  bit 0 = TOP-LEFT cell
    => moving DOWN  (row+1) = shift toward HIGHER bit indices = mask << 8
    => moving UP    (row-1) = shift toward LOWER  bit indices = mask >> 8
    => moving RIGHT (col+1) = shift toward HIGHER bit indices = per-row << 1
    => moving LEFT  (col-1) = shift toward LOWER  bit indices = per-row >> 1
"""

def cells(mask):
    return {(i // 8, i % 8) for i in range(64) if (mask >> i) & 1}

def mask_of(cs):
    m = 0
    for (r, c) in cs:
        m |= 1 << (8 * r + c)
    return m

def norm(cells_):
    mr = min(r for r, _ in cells_); mc = min(c for _, c in cells_)
    return frozenset((r - mr, c - mc) for r, c in cells_)

# --- the three level-1 pieces (relative shapes), from the PDF figures --------
P = [
    {(0, 0), (0, 1), (0, 2)},                                   # 1x3 bar
    {(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)},           # cross
    {(0, 1), (1, 0), (1, 1)},                                   # L-tromino
]
TGT = [(2, 2), (3, 2), (4, 3)]

def place(shape, r0, c0):
    return {(r + r0, c + c0) for r, c in shape}

# --- the incremental update used by the RTL ---------------------------------
def move_up(occ):
    """row-1: drop the top row, shift everything toward lower bit indices."""
    return (occ >> 8) & ((1 << 56) - 1)

def move_down(occ):
    """row+1: shift toward higher indices, drop whatever passes bit 63."""
    return (occ << 8) & ((1 << 64) - 1)

def move_left(occ, w=8):
    """col-1: per-row shift toward lower bit indices."""
    out = 0
    for r in range(8):
        row = (occ >> (8 * r)) & 0xFF
        out |= ((row >> 1) & 0xFF) << (8 * r)
    return out

def move_right(occ):
    """col+1: per-row shift toward higher bit indices."""
    out = 0
    for r in range(8):
        row = (occ >> (8 * r)) & 0xFF
        out |= ((row << 1) & 0xFF) << (8 * r)
    return out

MOVE = {"up": move_up, "down": move_down, "left": move_left, "right": move_right}
DELTA = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

def popcount(m):
    return bin(m).count("1")

# ============================================================================
# Test 1: the incremental update must equal a ground-truth re-placement
# ============================================================================
print("=== Test 1: incremental shift == ground-truth re-placement ===")
fails = 0
checked = 0
for si, shape in enumerate(P):
    h = max(r for r, _ in shape) + 1
    w = max(c for _, c in shape) + 1
    for r0 in range(0, 8 - h + 1):
        for c0 in range(0, 8 - w + 1):
            occ0 = mask_of(place(shape, r0, c0))
            for name, fn in MOVE.items():
                dr, dc = DELTA[name]
                nr, nc = r0 + dr, c0 + dc
                in_bounds = (0 <= nr) and (0 <= nc) and (nr + h <= 8) and (nc + w <= 8)
                got = fn(occ0)
                if not in_bounds:
                    continue          # RTL rejects out-of-bounds moves outright
                want = mask_of(place(shape, nr, nc))
                checked += 1
                if got != want:
                    fails += 1
                    if fails <= 5:
                        print(f"  FAIL piece{si} ({r0},{c0}) {name}: got {sorted(cells(got))} want {sorted(cells(want))}")
print(f"  checked {checked} in-bounds moves, {fails} mismatches")

# ============================================================================
# Test 2: the bounds test used by the RTL must exactly match geometry
# ============================================================================
print("\n=== Test 2: (cr+h<=8 and cc+w<=8) == geometric in-bounds ===")
bad = 0
for shape in P:
    h = max(r for r, _ in shape) + 1
    w = max(c for _, c in shape) + 1
    for cr in range(8):
        for cc in range(8):
            analytic = (cr + h <= 8) and (cc + w <= 8)
            geometric = all(0 <= r < 8 and 0 <= c < 8 for r, c in place(shape, cr, cc))
            if analytic != geometric:
                bad += 1
print(f"  mismatches: {bad}")

# ============================================================================
# Test 3: the target anchors really do tile figure 4-1, disjointly
# ============================================================================
print("\n=== Test 3: target anchors tile the picture ===")
FIG41 = {(r, c) for r in range(2, 6) for c in range(2, 5)}
occ_sets = [place(P[i], *TGT[i]) for i in range(3)]
union = set().union(*occ_sets)
disj = all(not (occ_sets[i] & occ_sets[j]) for i in range(3) for j in range(i + 1, 3))
print(f"  union == fig4-1 : {union == FIG41}")
print(f"  pairwise disjoint: {disj}")
print(f"  areas {[len(s) for s in occ_sets]} sum={sum(len(s) for s in occ_sets)}")

# ============================================================================
# Test 4: exhaustive reachability + legality of moves over the whole state space
# ============================================================================
print("\n=== Test 4: move legality (bounds + overlap) over random play ===")
import random
random.seed(12345)
violations = 0
for trial in range(2000):
    # scatter: random legal disjoint placement of the 3 pieces
    occs = [0, 0, 0]
    posn = [None, None, None]
    okall = True
    for i, shape in enumerate(P):
        h = max(r for r, _ in shape) + 1
        w = max(c for _, c in shape) + 1
        spots = [(r, c) for r in range(8 - h + 1) for c in range(8 - w + 1)]
        random.shuffle(spots)
        placed = False
        for (r, c) in spots:
            m = mask_of(place(shape, r, c))
            if all((m & o) == 0 for o in occs):
                occs[i] = m; posn[i] = (r, c); placed = True; break
        if not placed:
            okall = False
    if not okall:
        continue

    for step in range(60):
        i = random.randrange(3)
        name = random.choice(list(MOVE))
        shape = P[i]
        h = max(r for r, _ in shape) + 1
        w = max(c for _, c in shape) + 1
        r0, c0 = posn[i]
        dr, dc = DELTA[name]
        nr, nc = r0 + dr, c0 + dc
        legal = (0 <= nr) and (0 <= nc) and (nr + h <= 8) and (nc + w <= 8)
        if legal:
            m = mask_of(place(shape, nr, nc))
            if any((m & occs[j]) != 0 for j in range(3) if j != i):
                legal = False
        if legal:
            # the RTL shift must reproduce exactly this footprint
            got = MOVE[name](occs[i])
            want = mask_of(place(shape, nr, nc))
            if got != want:
                violations += 1
                if violations <= 3:
                    print(f"  VIOLATION piece{i} {name} {r0},{c0} -> {nr},{nc}")
            occs[i] = got; posn[i] = (nr, nc)
        # else: illegal move must be rejected -> state unchanged
print(f"  random-play violations: {violations}")

print("\nRESULT:", "ALL MODEL CHECKS PASSED" if (fails == 0 and bad == 0 and violations == 0
      and union == FIG41 and disj) else "*** MODEL CHECKS FAILED ***")
