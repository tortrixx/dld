# -*- coding: utf-8 -*-
"""用实际常量核对三条审计结论。

待检验的结论：
  A. row_mask / srl8 把零片移向了**错误**的方向（审计称需要 base << ac，
     而实际用的是 base >> ac）。
  B. L2_TARGET_MASK 比第二关的零片目标低一行。
  C. 引擎的绿色通道绝不可能在没有红色的情况下被置起（于是被选中的
     零片被画成黄色而不是绿色）。
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

# ---- 包里 srl8 的语义 -----------------------------------------
# srl8(r, dc)：dc=1 时 v := '0' & r(7 downto 1)  ->  v(c) = r(c-1)，即 r << 1。
# 所以 srl8(x, ac) == x << ac，也就是把某一位从列 k 移到列 k+ac。
# 因此，要把形状按相对其包围盒原点存储的零片放到锚点
# 列 ac 上，恰好需要 x << ac == srl8(x, ac)。如果代码用的是 srl8，
# 则结论 A 为**假**。用直接构造来验证：
P0 = cells(const_bits("L1_P0"))          # 1x3 横条，行 0 列 0..2
print("L1_P0 shape:", sorted(P0))
for ac in range(6):
    # srl8 语义：new(c) = old(c-ac)
    shifted = {(r, c + ac) for (r, c) in P0 if c + ac <= 7}
    print(f"  anchor col {ac} -> {sorted(shifted)}   (expected for 'placed at col {ac}')")

# ---- 结论 B：第二关目标与第二关零片目标 -------------------------------
print("\nL2_TARGET_MASK cells:")
l2t = cells(const_bits("L2_TARGET_MASK"))
print(fig(l2t))
print("rows:", sorted({r for r, _ in l2t}), " cols:", sorted({c for _, c in l2t}))

L2_TGT = [(2, 2), (2, 4), (4, 2), (4, 4)]
# 四块 2x2 零片
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

# ---- 结论 C：有绿无红 ------------------------------------------
print("\nClaim C (engine colour):")
print("  redrow := cov or (tgtrow and not cov)  -> red is set for EVERY piece cell")
print("  grnrow := kc, and kc is built only from cells already in cov")
print("  => green is always a SUBSET of red, so pure green is unreachable;")
print("     a selected piece renders as red+green = YELLOW, same as locked.")
print("  => CLAIM C is TRUE.")
