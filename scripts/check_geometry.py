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
    if m:
        return m.group(1)
    # 别名常量（L2_TARGET_MASK := L2_PAT0）：递归解析，否则"抄一份字面量"就成了自证
    a = re.search(r"constant\s+" + name + r"\s*:\s*std_logic_vector\(63 downto 0\)\s*:=\s*([A-Za-z_][A-Za-z_0-9]*)\s*;",
                  src, re.S)
    if a:
        return const_bits(a.group(1))
    raise SystemExit(f"constant {name} not found")

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
         "L2_PAT0","L2_PAT1","L2_PAT2","L2_PAT3",
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

def const_anchor(name):
    """Parse a packed 8-bit anchor constant: "row(4 bits)" & "col(4 bits)"."""
    m = re.search(r"constant\s+" + name +
                  r"\s*:\s*std_logic_vector\(7 downto 0\)\s*:=\s*\"([01]{4})\"\s*&\s*\"([01]{4})\"",
                  src, re.S)
    if not m:
        raise SystemExit(f"anchor constant {name} not found")
    return int(m.group(1), 2), int(m.group(2), 2)


def tilings_no_rotation(target, pieces):
    """Every EXACT tiling of `target` by `pieces`, TRANSLATION ONLY.

    Level 2 has no rotation key (improvement requirement A4 is explicitly out of
    scope), so allowing the mirror/rotation transforms used for the level-1 figure
    would be an over-permissive proof of "solvable": a pattern that only tiles with
    a rotated piece would be a DEAD END on the real board.
    Returns a list of slot-ordered anchor tuples.
    """
    T = frozenset(target)
    shapes = [norm(p) for p in pieces]
    sizes = [(max(r for r, _ in s) + 1, max(c for _, c in s) + 1) for s in shapes]
    out = []

    def rec(i, used, acc):
        if i == len(shapes):
            if used == T:
                out.append(tuple(acc))
            return
        h, w = sizes[i]
        for r0 in range(0, 9 - h):
            for c0 in range(0, 9 - w):
                p = frozenset((r + r0, c + c0) for r, c in shapes[i])
                if p <= T and not (p & used):
                    acc.append((r0, c0))
                    rec(i + 1, used | p, acc)
                    acc.pop()

    rec(0, frozenset(), [])
    return out


print("\n-- exact tilings (pieces cover the complete picture)")
n1 = count_tilings(C["L1_TARGET_MASK"], [C["L1_P0"], C["L1_P1"], C["L1_P2"]])
chk(n1 > 0, f"level-1 pieces can tile L1 target ({n1} tilings found; rotations allowed, "
            f"as documented -- the engine's verdict is the assembled picture anyway)")
n2 = tilings_no_rotation(C["L2_TARGET_MASK"], [C["L2_P0"], C["L2_P1"], C["L2_P2"], C["L2_P3"]])
chk(len(n2) > 0, f"level-2 pieces can tile L2 (PAT0) by TRANSLATION ONLY "
                 f"({len(n2)} tiling(s) found)")

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
L2_WITNESS = [const_anchor(f"L2_TGT{i}") for i in range(4)]
TGT["L2"] = ([C["L2_P0"], C["L2_P1"], C["L2_P2"], C["L2_P3"]], L2_WITNESS,
             C["L2_TARGET_MASK"])
for name, (pieces, anchors, target) in TGT.items():
    u = set()
    for pc, (ar, ac) in zip(pieces, anchors):
        u |= {(r + ar, c + ac) for (r, c) in norm(pc)}
    chk(u == target, f"{name}: target picture == union of pieces at target anchors")

# --- 第二关**图案库**（提高要求 A2 / 自拟 S1「多种拼图图案随机选择」，2026-10-09）---
# 硬约束：**每幅候选图案都必须能被现成的四块零片（形状自拟，2026-10-09 由 2x2 方块
# 改成 3/2/5/6 格的四种异形）恰好铺满** —— 铺不满就是死局。
# 零片只能**平移**（无旋转键，A4 不实现），所以这里用 tilings_no_rotation 独立穷举，
# 不允许镜像/旋转变换（用 count_tilings 会放松成"旋转后能铺"，那是过度宽松的证明）。
print("\n-- 第二关图案库（A2/S1）：逐图案**只许平移**的穷举可铺性")
PAT_N = 4
PATS = [C[f"L2_PAT{i}"] for i in range(PAT_N)]
L2P = [C[f"L2_P{i}"] for i in range(4)]
chk(C["L2_TARGET_MASK"] == C["L2_PAT0"],
    "L2_TARGET_MASK 仍等于 L2_PAT0（图案 0 = 原第二关图案，一字未改 → 旧证据继续有效）")
chk(sum(len(p) for p in L2P) == 16, "第二关四块零片面积 = 3+2+5+6 = 16 格")
chk(len({frozenset(norm(p)) for p in L2P}) == 4, "第二关四块零片**形状互不相同**（不再是四块 2x2）")
for i, p in enumerate(PATS):
    chk(len(p) == 16, f"L2_PAT{i}: 面积 = {len(p)} 格（必须 16 = 四块零片之和）")
    chk(len(p) == 16 and min(r for r, _ in p) >= 0 and max(r for r, _ in p) <= 7
        and min(c for _, c in p) >= 0 and max(c for _, c in p) <= 7,
        f"L2_PAT{i}: 全部格子落在 8x8 点阵内")
    sols = tilings_no_rotation(p, L2P)
    chk(len(sols) > 0,
        f"L2_PAT{i}: 四块异形零片能**恰好铺满**（只许平移：{len(sols)} 种铺法）")
    if i == 0 and sols:
        chk(len(sols) == 1 and sols[0] == tuple(L2_WITNESS),
            f"L2_PAT0（田）的解**唯一**，且 == pkg.L2_TGT0..3 写的见证锚点 {L2_WITNESS}")
    if sols:
        print(f"   L2_PAT{i} 见证铺法（槽 0..3 的锚点）: {sols[0]}")
chk(len(set(frozenset(p) for p in PATS)) == PAT_N,
    f"{PAT_N} 幅图案互不相同（去重后 {len(set(frozenset(p) for p in PATS))} 幅）")
for i, p in enumerate(PATS):
    print(f"   L2_PAT{i}:")
    print("\n".join("     " + l for l in fig(p).split("\n")))

# --- 结算画面（2026-10-09：胜利 = 粗红对勾，失败 = 红叉）------------------------
# 检查目的：
#   1) 胜利图案必须是一张**够粗、方向正确**的对勾（细线在 8x8 上读不出形状——那是
#      2026-10-08 第一次上板反馈的问题）；
#   2) 它是 ERR-015（取行时把画面上下颠倒 / 左右镜像）的天然回归判据：对勾是斜的，
#      一旦翻转，"最高行在右半边、最低行在左半边"立刻不成立。
print("\n-- 结算画面：胜利粗对勾 / 失败叉")
W, F = C["WIN_MASK"], C["FAIL_MASK"]
chk(W != F, "胜利图案 != 失败图案")
top_r = min(r for r, _ in W)
bot_r = max(r for r, _ in W)
chk(all(c >= 4 for _r, c in W if _r == top_r),
    f"对勾最高行(row {top_r})只出现在**右半边**（列 {sorted(c for _r, c in W if _r == top_r)}）")
chk(all(c <= 3 for _r, c in W if _r == bot_r),
    f"对勾最低行(row {bot_r})只出现在**左半边**（列 {sorted(c for _r, c in W if _r == bot_r)}）"
    "　=> 上下颠倒或左右镜像都会失败（ERR-015 回归）")
chk(16 <= len(W) <= 40, f"对勾够粗（亮格数 {len(W)} ∈ [16,40]），8x8 上远距离可读")
chk(len({r for r, _ in W}) >= 6 and len({c for _, c in W}) >= 6,
    "对勾铺满 ≥6 行 × ≥6 列（不是缩在角落里的小勾）")
chk(all(((7 - r, c) in F) == ((r, c) in F) for r in range(8) for c in range(8)),
    "失败十字上下对称")

print("\n" + ("ALL CHECKS PASSED" if ok else "*** SOME CHECKS FAILED ***"))
raise SystemExit(0 if ok else 1)
