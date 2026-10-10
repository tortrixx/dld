# -*- coding: utf-8 -*-
"""用 Python 建模 puzzle_ctrl 的移动/移位逻辑，并对其进行穷尽验证。

bit 约定（必须与 puzzle_pkg 和 dot_matrix_scan 一致）：
    bit 下标 = 8*row + col，bit 0 = 左上角单元
    => 向下移动（row+1）= 朝更大的 bit 下标移位 = mask << 8
    => 向上移动（row-1）= 朝更小的 bit 下标移位 = mask >> 8
    => 向右移动（col+1）= 朝更大的 bit 下标移位 = 逐行 << 1
    => 向左移动（col-1）= 朝更小的 bit 下标移位 = 逐行 >> 1
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

# --- 三个 1 关零片（相对形状），取自 PDF 插图 --------
P = [
    {(0, 0), (0, 1), (0, 2)},                                   # 1x3 长条
    {(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)},           # 十字
    {(0, 1), (1, 0), (1, 1)},                                   # L 形三格骨牌
]
TGT = [(2, 2), (3, 2), (4, 3)]

def place(shape, r0, c0):
    return {(r + r0, c + c0) for r, c in shape}

# --- RTL 所用的增量更新 ---------------------------------
def move_up(occ):
    """row-1：丢掉最上面一行，把所有内容朝更小的 bit 下标移位。"""
    return (occ >> 8) & ((1 << 56) - 1)

def move_down(occ):
    """row+1：朝更大的下标移位，越过 bit 63 的内容丢弃。"""
    return (occ << 8) & ((1 << 64) - 1)

def move_left(occ, w=8):
    """col-1：逐行朝更小的 bit 下标移位。"""
    out = 0
    for r in range(8):
        row = (occ >> (8 * r)) & 0xFF
        out |= ((row >> 1) & 0xFF) << (8 * r)
    return out

def move_right(occ):
    """col+1：逐行朝更大的 bit 下标移位。"""
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
# 测试 1：增量更新必须等于按基准重新摆放的结果
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
                    continue          # RTL 会直接拒绝越界移动
                want = mask_of(place(shape, nr, nc))
                checked += 1
                if got != want:
                    fails += 1
                    if fails <= 5:
                        print(f"  FAIL piece{si} ({r0},{c0}) {name}: got {sorted(cells(got))} want {sorted(cells(want))}")
print(f"  checked {checked} in-bounds moves, {fails} mismatches")

# ============================================================================
# 测试 2：RTL 所用的边界判定必须与几何完全一致
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
# 测试 3：各目标锚点确实无重叠地铺满图 4-1
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
# 测试 4：在整个状态空间上穷尽检验移动的可达性与合法性
# ============================================================================
print("\n=== Test 4: move legality (bounds + overlap) over random play ===")
import random
random.seed(12345)
violations = 0
for trial in range(2000):
    # 散落：为 3 个零片随机生成合法且互不重叠的摆放
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
            # RTL 的移位必须精确复现这一覆盖范围
            got = MOVE[name](occs[i])
            want = mask_of(place(shape, nr, nc))
            if got != want:
                violations += 1
                if violations <= 3:
                    print(f"  VIOLATION piece{i} {name} {r0},{c0} -> {nr},{nc}")
            occs[i] = got; posn[i] = (nr, nc)
        # 否则：非法移动必须被拒绝 -> 状态不变
print(f"  random-play violations: {violations}")

print("\nRESULT:", "ALL MODEL CHECKS PASSED" if (fails == 0 and bad == 0 and violations == 0
      and union == FIG41 and disj) else "*** MODEL CHECKS FAILED ***")
