# -*- coding: utf-8 -*-
"""把 rtl/puzzle_pkg.vhd 里的每个掩码常量与 PDF 解码出的图逐一对账。

解析 VHDL，把每个常量解码成格子集合，然后检查：
  * L1_TARGET == FIG 4-1（逐格一致）
  * L1_P0/P1/P2 恰好划分 FIG 4-2（3+6+3 = 12）
  * L1_P1 == FIG 4-3 的绿色区域
  * 第一关零片恰好铺满 L1_TARGET
  * 第二关零片（16 格、4 块）恰好铺满 L2_TARGET
  * 每块零片都塞得进 PIECE_MAX_DIM
"""
import re, pathlib, sys
from itertools import product

# ⚠️ Windows 控制台默认 GBK：本文件里用到了 ⭐ 之类的符号，必须先切到 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 仓库根 = 本脚本所在目录的上一级（**不写死绝对路径**，见 gen_project.py 的同款说明）
ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "rtl" / "puzzle_pkg.vhd"
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
    """bits 是 VHDL 字面量：最左的字符 = bit63。返回 {(行,列)}，其中 bit0 = 左上角。"""
    val = int(bits, 2)          # val 的 bit i == 字面量里从右数第 i 个字符
    return {(i // 8, i % 8) for i in range(64) if (val >> i) & 1}

def norm(cells):
    """把格子集合平移，使其紧包围盒左上角为 (0,0) —— 用于形状比较。"""
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
# 目标图案存的是**点阵绝对坐标** → 必须与图逐格一致
chk(C["L1_TARGET_MASK"] == FIG41, "L1_TARGET_MASK == FIG 4-1 (4x3 rect @ rows2-5, cols2-4)")

print("\n-- FIG 4-2 partition (pieces are stored RELATIVE to their bbox top-left,")
print("   so compare shape after normalising both sides)")
P = [C["L1_P0"], C["L1_P1"], C["L1_P2"]]
chk(len(P[0]) == 3 and len(P[1]) == 6 and len(P[2]) == 3, "piece areas are 3 / 6 / 3")
# 把每块零片放到它在图里的位置，重建 FIG 4-2
FIG42_PIECES = [{(0,4),(0,5),(0,6)}, {(2,4),(2,5),(2,6),(3,4),(3,5),(4,4)}, {(4,1),(5,0),(5,1)}]
for i, fp in enumerate(FIG42_PIECES):
    chk(norm(P[i]) == norm(fp), f"L1_P{i} shape == figure piece {i+1} shape {sorted(norm(fp))}")
chk(sum(len(p) for p in P) == len(FIG42), "areas conserve (12 == 12)")
# 互不重叠必须在**摆好位置后**的零片上检查（相对掩码按定义
# 都以原点 (0,0) 为锚，直接比较它们是错的）
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
    # 在目标包围盒内任意锚点递归做精确覆盖
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
    """解析打包成 8 位的锚点常量："行(4 位)" & "列(4 位)"。"""
    m = re.search(r"constant\s+" + name +
                  r"\s*:\s*std_logic_vector\(7 downto 0\)\s*:=\s*\"([01]{4})\"\s*&\s*\"([01]{4})\"",
                  src, re.S)
    if not m:
        raise SystemExit(f"anchor constant {name} not found")
    return int(m.group(1), 2), int(m.group(2), 2)


def tilings_no_rotation(target, pieces):
    """`pieces` 对 `target` 的**所有**精确铺法，**只许平移**。

    第二关没有旋转键（提高要求 A4 明确不在范围内），所以
    若允许第一关图用过的镜像/旋转变换，就会给出过度宽松的
    「可解」证明：只能靠旋转后的零片才铺得满的图案，
    在真实板子上是**死局**。
    返回按槽序排列的锚点元组列表。
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

# --- 目标图案必须等于各零片放在**目标锚点**上的并集
# 正是这条检查本可以抓出 L2_TARGET_MASK 比第二关零片目标低一行的问题：
# 幽灵图案是用目标掩码画的，所以两者一旦不一致，
# 玩家看到的就会是一幅拼不出来的图案。
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

# --- D2（2026-10-09 第 12 工作阶段）：**哪一幅是第二关的固定图案** ----------------
# 口径（用户拍板）：第一关 = 图 4-1（B4 指定，固定）；第二关 = **自拟但固定**的一幅
# （B10 只要求"自拟"，随机选择属提高要求 A2）；第三关 = 从库里**随机选**（A2）。
# 这里把"固定的是哪一幅"钉死，并核对它确实来自这个库、且它的见证铺法能被穷举出来。
print("\n-- D2：第二关固定图案（B10 自拟但固定）与第三关随机库（A2）")
mf = re.search(r"constant\s+L2_FIXED_PAT\s*:\s*std_logic_vector\(1 downto 0\)\s*:=\s*\"([01]{2})\"",
               src, re.S)
chk(mf is not None, "puzzle_pkg 里有 L2_FIXED_PAT（第二关固定图案的下标）")
if mf:
    FIXED = int(mf.group(1), 2)
    chk(0 <= FIXED < PAT_N, f"L2_FIXED_PAT = {FIXED} 落在图案库 0..{PAT_N-1} 内")
    chk(FIXED == 3,
        "第二关固定图案 = PAT3（阶梯）—— 用户 2026-10-09 明确要求**不要**用原来的 4x4 田；"
        "且 PAT3 是四幅里唯一有 2 种等价铺法的图案 → ERR-021 的'画面判据'回归落在正常流程里")
    sols3 = tilings_no_rotation(PATS[3], L2P)
    W3 = [const_anchor(f"L2_PAT3_TGT{i}") for i in range(4)]
    chk(tuple(W3) in sols3,
        f"L2_PAT3_TGT0..3 写的见证铺法 {W3} 确实是 PAT3 的 {len(sols3)} 种铺法之一"
        "（文档里的锚点不是手抄的，而是穷举出来的）")
    chk(len(sols3) == 2, f"PAT3 恰好 2 种铺法（实测 {len(sols3)} 种）—— ERR-021 回归用例")
    if len(sols3) == 2:
        print(f"   PAT3 的两种铺法: {sols3[0]} / {sols3[1]}")
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

# --- A4 旋转（2026-10-09 第 13 工作阶段）：**朝向几何**的离线证明 -------------------
# A4 原文："零片不仅能上下左右移动，还可以 90° 旋转"。RTL 的实现做法是：
#   · 在**固定的 3x3 盒**里转（每个调用点只有 3 个 4:1 mux，便宜）；
#   · 但 3x3 盒里转出来的**紧包围盒不在 (0,0)**（1x3 横条转 90° 会落到盒子第 2 列），
#     所以在"算行掩码"的唯一一处把偏移补回来：
#        盒内行号 = 紧包围盒行号 + dr,   列移位 = 锚点列 - dc
#        dr/dc: "00" (0,0)  "01" (0,3-h)  "10" (3-h,3-w)  "11" (3-w,0)
# 这里用一个**独立定义**（在紧包围盒里直接转）当参考模型，逐个零片、逐个朝向、
# 逐行比对上面那套"盒内转 + 偏移补偿"，确保两条路给出**同一幅画面**。
# 同时断言旋转的几条硬前提：
#   ① 每个零片的原始紧包围盒本来就锚在 (0,0)（否则偏移公式不成立）；
#   ② 任意朝向的紧包围盒仍锚在 (0,0)，高宽 = (w,h)（奇朝向）或 (h,w)（偶朝向）；
#   ③ 任意朝向都仍塞得进 3x3（引擎只取 3 行、srl8 只处理 8 位，这条是硬前提）；
#   ④ 转 4 次回到原样（朝向是 4 循环群）。
print("\n-- A4 旋转：朝向几何（盒内转 + 锚点偏移  ==  紧包围盒里转）")
PIECES = [("L1_P0", C["L1_P0"]), ("L1_P1", C["L1_P1"]), ("L1_P2", C["L1_P2"]),
          ("L2_P0", C["L2_P0"]), ("L2_P1", C["L2_P1"]), ("L2_P2", C["L2_P2"]),
          ("L2_P3", C["L2_P3"])]
ORIS = ["00", "01", "10", "11"]


def bbox(cs):
    return (max(r for r, _ in cs) + 1, max(c for _, c in cs) + 1)


def rot_ref(cs, ori):
    """参考模型：在零片**自己的紧包围盒 h x w** 里转，结果仍锚在 (0,0)。
    "01" 顺时针 90° -> new(r',c') = old(h-1-c', r')，尺寸 w x h
    "10" 180°       -> new(r',c') = old(h-1-r', w-1-c')
    "11" 顺时针 270°-> new(r',c') = old(c', w-1-r')
    """
    h, w = bbox(cs)
    if ori == "00":
        return frozenset(cs)
    if ori == "01":
        return frozenset((c, h - 1 - r) for (r, c) in cs)
    if ori == "10":
        return frozenset((h - 1 - r, w - 1 - c) for (r, c) in cs)
    return frozenset((w - 1 - c, r) for (r, c) in cs)


def box_cell(cs3, ori, r, c):
    """RTL 的 rot_row：在固定 3x3 盒里取朝向 ori、行 r、列 c 的格子。"""
    if ori == "00":
        rr, cc = r, c
    elif ori == "01":
        rr, cc = 2 - c, r
    elif ori == "10":
        rr, cc = 2 - r, 2 - c
    else:
        rr, cc = c, 2 - r
    return (rr, cc) in cs3


def rot_off(h, w, ori):
    """RTL 的 rot_off_r / rot_off_c。"""
    dr = (3 - h) if ori == "10" else ((3 - w) if ori == "11" else 0)
    dc = (3 - h) if ori == "01" else ((3 - w) if ori == "10" else 0)
    return dr, dc


rot_bad = []
for name, cs in PIECES:
    h, w = bbox(cs)
    if (min(r for r, _ in cs), min(c for _, c in cs)) != (0, 0):
        rot_bad.append(f"{name} 原始紧包围盒不锚在 (0,0) —— 偏移公式不成立")
    for ori in ORIS:
        ref = rot_ref(cs, ori)
        rh, rw = bbox(ref)
        if (min(r for r, _ in ref), min(c for _, c in ref)) != (0, 0):
            rot_bad.append(f"{name} ori={ori} 紧包围盒不锚在 (0,0)")
        exp = (w, h) if ori in ("01", "11") else (h, w)
        if (rh, rw) != exp:
            rot_bad.append(f"{name} ori={ori} 高宽 {rh}x{rw} != 期望 {exp[0]}x{exp[1]}")
        if rh > 3 or rw > 3:
            rot_bad.append(f"{name} ori={ori} 超出 3x3（{rh}x{rw}）")
        # 3x3 盒 + 偏移补偿 必须与参考模型逐格一致
        dr, dc = rot_off(h, w, ori)
        got = {(r, c) for r in range(rh) for c in range(rw)
               if box_cell(cs, ori, r + dr, c + dc)}
        if got != set(ref):
            rot_bad.append(f"{name} ori={ori} 盒内转+偏移 != 紧包围盒参考模型")
        if ori == "00" and ref != frozenset(cs):
            rot_bad.append(f"{name} ori=00 不是恒等")

chk(not rot_bad, "7 块零片 x 4 朝向：盒内转 + 锚点偏移 == 紧包围盒参考模型，"
                 "且每块都锚在 (0,0)、高宽按 90°/270° 互换、全部塞得进 3x3"
                 + ("" if not rot_bad else "；失败：" + "; ".join(rot_bad[:4])))

# 转 4 次回原样（4 循环群）
cyc_bad = [n for n, cs in PIECES
           if rot_ref(rot_ref(rot_ref(rot_ref(cs, "01"), "01"), "01"), "01") != frozenset(cs)]
chk(not cyc_bad, "每个零片连转 4 次 90° 回到原样（朝向是 4 循环群）"
                 + ("" if not cyc_bad else "；失败：" + str(cyc_bad)))

# 面积守恒（旋转不改格数）
area_bad = [n for n, cs in PIECES if any(len(rot_ref(cs, o)) != len(cs) for o in ORIS)]
chk(not area_bad, "旋转不改零片面积（4 个朝向格数都相同）"
                 + ("" if not area_bad else "；失败：" + str(area_bad)))

# ============================================================================
#  ⭐ 第 14 工作阶段（2026-10-09）：**旋转必需性**离线证明
#
#  用户上板反馈："旋转 90 度效果倒是有，但是旋转好像对游戏并没有什么影响，
#  不旋转也能成功通关。" —— 根因是四块零片都从 ori="00" 开始散落，而四幅图案
#  本来就用 `tilings_no_rotation`（只许平移）解出来的，所以**存在"一次都不转"
#  的通关走法**。
#
#  修法：puzzle_pkg.PIECE_ORI_INIT 给了每块零片一个**非零初始朝向**
#  （块 k 占 ori(2k+1 downto 2k)）。这里独立证明三件事：
#    ① 初始朝向常量与 RTL 里写的那一串逐位一致（防止手抄错）；
#    ② **保持初始朝向、只许平移**时，四幅图案 PAT0..PAT3 与第一关的 4x3 矩形
#       **都没有恰好覆盖**（⇒ 不按【旋转】键不可能通关，"旋转不影响游戏"不成立）；
#    ③ 允许旋转之后每幅都仍然可解（否则就是死局）。
#  这三条都不信任 RTL：用的是本文件里的 rot_ref（已在上面被证明与 RTL 的
#  rot_row + rot_off_r/c 逐格等价）。
# ============================================================================
print("\n-- ⭐ A4 旋转必需性（第 14 工作阶段）：初始朝向 = puzzle_pkg.PIECE_ORI_INIT")
_ini_m = re.search(r"constant\s+PIECE_ORI_INIT\s*:\s*std_logic_vector\(7 downto 0\)\s*:=\s*"
                   r"\"([01]{2})\"\s*&\s*\"([01]{2})\"\s*&\s*\"([01]{2})\"\s*&\s*\"([01]{2})\"", src, re.S)
chk(_ini_m is not None, "puzzle_pkg 里有 PIECE_ORI_INIT（4 块零片各 2 位的初始朝向）")
if _ini_m:
    INIT_L2 = "".join(_ini_m.groups())          # 块3 块2 块1 块0（MSB 在前，与 VHDL 拼接一致）
    INIT = [INIT_L2[6:8], INIT_L2[4:6], INIT_L2[2:4], INIT_L2[0:2]]
    print(f"   PIECE_ORI_INIT = \"{INIT_L2}\"  ->  块 0..3 朝向 = {INIT}")
    ORIS_L = ["00", "01", "10", "11"]

    def _rot_pieces(pieces, oris):
        return [rot_ref(p, o) for p, o in zip(pieces, oris)]

    def tilings_given_orientation(target, pieces, oris):
        """恰好覆盖：每块零片**固定在自己给定的朝向上**，只许平移。"""
        T = frozenset(norm(target))
        shapes = [norm(cs) for cs in _rot_pieces(pieces, oris)]
        sizes = [bbox(s) for s in shapes]
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

    # ① 旋转必需性：第一关（3 块）+ 四幅图案（4 块）都不能"保持初始朝向"铺满
    need_bad = []
    l1_ori = INIT[:3]
    n_l1 = tilings_given_orientation(C["L1_TARGET_MASK"], [C["L1_P0"], C["L1_P1"], C["L1_P2"]], l1_ori)
    if n_l1:
        need_bad.append(f"第一关：保持初始朝向 {l1_ori} 仍能铺满（{len(n_l1)} 种）→ 旋转不是必需的")
    for i in range(PAT_N):
        s = tilings_given_orientation(PATS[i], L2P, INIT)
        if s:
            need_bad.append(f"L2_PAT{i}：保持初始朝向 {INIT} 仍能铺满（{len(s)} 种）→ 旋转不是必需的")
    chk(not need_bad,
        "第一关 + 四幅图案：**保持 PIECE_ORI_INIT、只许平移时都恰好覆盖不了** "
        "（⇒ 玩家必须按【旋转】，A4 真的是通关必需的一步）"
        + ("" if not need_bad else "；失败：" + "; ".join(need_bad[:4])))

    # ② 每块零片在初始朝向下形状都真的变了（不是"只转了一块"）
    changed = [k for k in range(4)
               if norm(rot_ref(L2P[k], INIT[k])) != norm(L2P[k])]
    chk(len(changed) == 4, f"四块零片在初始朝向下**形状都变了**（实测变了 {len(changed)} 块：{changed}）—— "
                           f"每块都必须被转一次")

    # ③ 允许旋转后仍然可解（不是死局）：用 count_tilings 的多朝向版本
    def solvable_any_orientation(target, pieces):
        T = frozenset(norm(target))
        alts = [sorted({norm(rot_ref(p, o)) for o in ORIS_L}) for p in pieces]

        def rec(i, used):
            if i == len(alts):
                return used == T
            for s in alts[i]:
                h, w = bbox(s)
                for r0 in range(0, 9 - h):
                    for c0 in range(0, 9 - w):
                        p = frozenset((r + r0, c + c0) for r, c in s)
                        if p <= T and not (p & used):
                            if rec(i + 1, used | p):
                                return True
            return False

        return rec(0, frozenset())

    dead = []
    if not solvable_any_orientation(C["L1_TARGET_MASK"], [C["L1_P0"], C["L1_P1"], C["L1_P2"]]):
        dead.append("第一关")
    for i in range(PAT_N):
        if not solvable_any_orientation(PATS[i], L2P):
            dead.append(f"L2_PAT{i}")
    chk(not dead, "允许旋转后第一关与四幅图案**都仍然可解**（旋转是必需的一步，但不是死局）"
                  + ("" if not dead else "；失败：" + str(dead)))

print("\n" + ("ALL CHECKS PASSED" if ok else "*** SOME CHECKS FAILED ***"))
raise SystemExit(0 if ok else 1)
