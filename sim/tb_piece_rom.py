# -*- coding: utf-8 -*-
"""tb_piece_rom.py —— piece_rom 功能仿真激励与断言

【本模块是什么】
    `piece_rom` 是**零片形状查找表**：纯组合，`i_level` 选关，一次输出 4 块零片的
    **相对**掩码（`o_mask`，每块 64 位、位序 bit(8*行+列)、bit0 = 左上角）、
    包围盒高/宽（`o_h`/`o_w`）与实际使用的块数（`o_n`）。
    零片形状错了 → 拼图**永远拼不上，而且不报错**，所以必须当成数据逐点验。

【判据的独立来源（不许自证）】
    ① 第一关三块零片的**形状**来自课程 PDF 图 4-2 的逐像素解码，
       该解码在本仓库里有独立落地：`.ref/solve_l1.py`：
           P1 = 1x3 横条   3 格   {(0,0),(0,1),(0,2)}
           P2 = 6 格阶梯/十字 {(0,0),(0,1),(0,2),(1,0),(1,1),(2,0)}
           P3 = L 形 3 格    {(0,1),(1,0),(1,1)}
       —— 这两边（PDF 解码 vs `rtl/puzzle_pkg.vhd` 的位串）是**两份独立材料**，
          对上了才说明 RTL 常量没抄错。
    ② 第二关四块 2x2 方块是自设计图案：`bbox=2x2 且 4 格` ⇒ 只能是实心 2x2。
    ③ **可解性**（最强的一条）：把实测掩码当形状，程序化穷举
       「每块恰用一次 / 两两不重叠 / 并集 == 目标」：
         · 第一关在 4x3 矩形（第 2~5 行 x 第 2~4 列，12 格）内**恰 2 种**铺法
           （`.ref/solve_l1.py` 的已知结论；其中 (2,2)(3,2)(4,3) 就是 pkg 的
            L1_TGT0/1/2）；
         · 第二关在 4x4 方块（16 格）内锚点集合**唯一** = {(2,2),(2,4),(4,2),(4,4)}
           （= pkg 的 L2_TGT0..3）。
       这条断言只用"形状能不能铺满目标"这一语义，**不引用 RTL 里的任何掩码常量**。
    ④ 面积守恒：三块零片格数之和 == 目标图案格数（第一关 12、第二关 16）。
       pkg 注释里记着参考仓库曾出现"11 格 vs 12 格不守恒"的事故。

【中间信号 / OBSERVE 的诚实说明（重要）】
    `piece_rom` 是**纯常量选择**的组合模块：架构体里没有任何 signal，
    综合后网表里节点数 == 端口数（实测 1 个输入 + 283 个输出位 = 284，
    用 `quartus_sh` 的 `get_names` 转储过 `db/puzzle.map.*`，**comb/reg 节点为 0**）。
    也就是说：这个模块在硬件里**不存在**可观测的内部中间信号 —— 这不是偷懒，
    是它对得上的物理事实。所以本 tb 的波形里放的是**聚合端口的分解通道**：
    `o_mask[0..3]`（4 条 64 位总线，各一块零片）、`o_h[0..3]`、`o_w[0..3]`、`o_n` —— 
    即"这一组零片"的内部构成，而不是一个 256 位的大黑盒。
    （另外三个模块 rng_lfsr / disp_format / buzzer_ctrl 都有真实内部节点，见各自 tb。）

【时间线】（单位 ns；`DURATION` = 400；纯组合、与时钟无关，只采两个点）
    0~200    i_level='0'（第一关，3 块）
    200~400  i_level='1'（第二关，4 块）
"""

import pathlib
import re

DURATION = 400.0
GRID_PERIOD = 10.0

T_L1 = 100.0        # 第一关采样点
T_L2 = 300.0        # 第二关采样点

# ============================================================
# 独立参考 ①：图 4-2 的三块零片（PDF 逐像素解码，见 .ref/solve_l1.py）
#   坐标是"相对包围盒左上角"的 (行, 列)
# ============================================================
L1_SHAPES_PDF = [
    frozenset({(0, 0), (0, 1), (0, 2)}),                                # P1 1x3 横条 3 格
    frozenset({(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (2, 0)}),        # P2 6 格
    frozenset({(0, 1), (1, 0), (1, 1)}),                                # P3 L 形 3 格
]
# 独立参考 ②：第二关四块 2x2 实心方块（自设计图案的语义描述）
L2_SHAPE = frozenset({(0, 0), (0, 1), (1, 0), (1, 1)})

# 目标图案的几何（课程 PDF 图 4-1 / docs/02：两关共用同一区域，第二关右扩一列）
T1_CELLS = frozenset((r, c) for r in range(2, 6) for c in range(2, 5))    # 4x3 = 12
T2_CELLS = frozenset((r, c) for r in range(2, 6) for c in range(2, 6))    # 4x4 = 16


# ============================================================
# 从 rtl/puzzle_pkg.vhd 读"唯一真值源"里的常量（不做 VHDL 解析器，只取需要的几条）
# ============================================================
def _pkg_text():
    p = pathlib.Path(__file__).resolve().parent.parent / "rtl" / "puzzle_pkg.vhd"
    return p.read_text(encoding="utf-8", errors="replace")


def _pkg_int(name, default=None):
    m = re.search(r"constant\s+%s\s*:\s*integer\s*:=\s*([0-9_]+)" % name, _pkg_text())
    if not m:
        if default is None:
            raise RuntimeError("puzzle_pkg 里找不到常量 %s" % name)
        return default
    return int(m.group(1).replace("_", ""))


def _pkg_anchor(name):
    """读 (row & col) 打包的 8 位锚点常量，返回 (row, col)。"""
    m = re.search(r'constant\s+%s\s*:\s*std_logic_vector\(7\s+downto\s+0\)\s*:=\s*'
                  r'"([01]{4})"\s*&\s*"([01]{4})"' % name, _pkg_text())
    if not m:
        raise RuntimeError("puzzle_pkg 里找不到锚点常量 %s" % name)
    return int(m.group(1), 2), int(m.group(2), 2)


PIECE_MAX_DIM = _pkg_int("PIECE_MAX_DIM")
L1_TGT = [_pkg_anchor("L1_TGT%d" % i) for i in range(3)]
L2_TGT = [_pkg_anchor("L2_TGT%d" % i) for i in range(4)]


# ============================================================
# 掩码 <-> 格集合（位序约定：bit(8*行 + 列)、bit0 = 左上角）
# ============================================================
def mask_to_cells(m):
    return frozenset((r, c) for r in range(8) for c in range(8)
                     if (m >> (8 * r + c)) & 1)


def cells_to_mask(cells):
    v = 0
    for (r, c) in cells:
        v |= 1 << (8 * r + c)
    return v


def popcount(m):
    return bin(m).count("1")


def bbox(cells):
    if not cells:
        return (0, 0)
    return (max(r for r, _ in cells) + 1, max(c for _, c in cells) + 1)


def place(cells, anchor):
    return frozenset((r + anchor[0], c + anchor[1]) for (r, c) in cells)


def enumerate_tilings(target, pieces):
    """穷举铺法：每块恰用一次、两两不重叠、并集 == target。返回锚点元组列表。"""
    tables = []
    for shp in pieces:
        tbl = {}
        for ar in range(8):
            for ac in range(8):
                cs = place(shp, (ar, ac))
                if cs <= target:
                    tbl[(ar, ac)] = cs
        tables.append(tbl)
    sols = []

    def rec(i, used, chosen):
        if i == len(pieces):
            if used == target:
                sols.append(tuple(chosen))
            return
        for anc, cs in tables[i].items():
            if cs & used:
                continue
            chosen.append(anc)
            rec(i + 1, used | cs, chosen)
            chosen.pop()

    rec(0, frozenset(), [])
    return sols


# ============================================================
# 节点声明
# ============================================================
# ⚠️ 本模块**没有**内部节点可观测（见文件头"中间信号说明"）。
#    这里列的是聚合端口的分解通道：4 块零片各自的掩码 / 高 / 宽 + 块数。
OBSERVE = (
    ["i_level"]
    + ["o_mask[%d]" % i for i in range(4)]
    + ["o_h[%d]" % i for i in range(4)]
    + ["o_w[%d]" % i for i in range(4)]
    + ["o_n"]
)


def build(b):
    b.input_bit("i_level")
    for i in range(4):
        b.output_bus("o_mask[%d]" % i, 64)      # 数组型端口按元素声明
        b.output_bus("o_h[%d]" % i, 3)
        b.output_bus("o_w[%d]" % i, 3)
    b.output_bus("o_n", 3)
    b.segments("i_level", [(200.0, 0), (200.0, 1)])


# ============================================================
# 断言
# ============================================================
def _hex(v):
    return "X" if v is None else "0x%016X" % v


def _render(cells):
    return "\n".join("      " + "".join("#" if (r, c) in cells else "." for c in range(8))
                     for r in range(8))


def check(vf):
    res = []

    def rd(t):
        masks = [vf.bus_value_at("o_mask[%d]" % i, t) for i in range(4)]
        hs = [vf.bus_value_at("o_h[%d]" % i, t) for i in range(4)]
        ws = [vf.bus_value_at("o_w[%d]" % i, t) for i in range(4)]
        return masks, hs, ws, vf.bus_value_at("o_n", t)

    m1, h1, w1, n1 = rd(T_L1)
    m2, h2, w2, n2 = rd(T_L2)

    l1_cells = [None if m is None else mask_to_cells(m) for m in m1]
    l2_cells = [None if m is None else mask_to_cells(m) for m in m2]
    l1_pc = [None if c is None else len(c) for c in l1_cells]
    l2_pc = [None if c is None else len(c) for c in l2_cells]

    # ---- ① 第一关：块数 3、占位槽全 0、格数 3+6+3 = 12 = 目标格数（面积守恒）----
    ok = (n1 == 3 and m1[3] == 0 and l1_pc[:3] == [3, 6, 3]
          and sum(x for x in l1_pc[:3]) == len(T1_CELLS))
    res.append((
        "① 第一关 o_n=3；未用槽 o_mask[3]=0；三块格数 3+6+3 = %d = 目标图案格数 %d（面积守恒）"
        % (sum(x for x in l1_pc[:3] if x is not None), len(T1_CELLS)),
        ok,
        "o_n=%s  槽3掩码=%s  各块格数=%s" % (n1, _hex(m1[3]), l1_pc),
    ))

    # ---- ② 第一关三块掩码 == PDF 图 4-2 的逐像素解码（独立参考）----
    bad = []
    for i in range(3):
        if l1_cells[i] != L1_SHAPES_PDF[i]:
            bad.append("槽%d 实测:\n%s\n      期望:\n%s"
                       % (i, _render(l1_cells[i] or set()), _render(L1_SHAPES_PDF[i])))
    res.append((
        "② 第一关三块形状与课程 PDF 图 4-2 的逐像素解码（.ref/solve_l1.py）逐格相同",
        not bad,
        "\n".join(bad) if bad else "P1=1x3 横条(3) P2=6 格阶梯 P3=L 形(3)：全部一致",
    ))

    # ---- ③ 第二关：块数 4、四块都是实心 2x2、格数和 16 = 目标格数 ----
    ok = (n2 == 4 and l2_pc == [4, 4, 4, 4] and sum(l2_pc) == len(T2_CELLS)
          and all(c == L2_SHAPE for c in l2_cells))
    res.append((
        "③ 第二关 o_n=4；四块均为实心 2x2；格数 4x4 = %d = 目标图案格数 %d"
        % (sum(l2_pc), len(T2_CELLS)),
        ok,
        "o_n=%s  各块格数=%s  四块形状均 == 2x2 实心：%s"
        % (n2, l2_pc, all(c == L2_SHAPE for c in l2_cells)),
    ))

    # ---- ④ 包围盒自洽：实测掩码的实际包围盒 == 声明的 o_h/o_w，且 <= PIECE_MAX_DIM ----
    bad = []
    for tag, cells, hs, ws in (("L1", l1_cells, h1, w1), ("L2", l2_cells, h2, w2)):
        for i in range(4):
            if cells[i] is None:
                bad.append("%s 槽%d 掩码含 X" % (tag, i))
                continue
            bh, bw = bbox(cells[i])
            if (bh, bw) != (hs[i], ws[i]):
                bad.append("%s 槽%d 掩码实际包围盒 %dx%d ≠ 声明 o_h/o_w = %sx%s"
                           % (tag, i, bh, bw, hs[i], ws[i]))
            if bh > PIECE_MAX_DIM or bw > PIECE_MAX_DIM:
                bad.append("%s 槽%d 包围盒 %dx%d 超出 PIECE_MAX_DIM=%d"
                           % (tag, i, bh, bw, PIECE_MAX_DIM))
    res.append((
        "④ 每块零片的 o_h/o_w 都等于其掩码的**实际**包围盒，且均 <= PIECE_MAX_DIM=%d"
        % PIECE_MAX_DIM,
        not bad,
        "\n".join(bad) if bad else
        "两关 8 块全部自洽（L1 高=%s 宽=%s；L2 高=%s 宽=%s）" % (h1, w1, h2, w2),
    ))

    # ---- ⑤ 相对形状归一化：每块都贴住包围盒左上角（min 行 = min 列 = 0）----
    bad = []
    for tag, cells in (("L1", l1_cells), ("L2", l2_cells)):
        for i, cs in enumerate(cells):
            if not cs:
                continue
            if min(r for r, _ in cs) != 0 or min(c for _, c in cs) != 0:
                bad.append("%s 槽%d 未归一化（min 行=%d min 列=%d）"
                           % (tag, i, min(r for r, _ in cs), min(c for _, c in cs)))
    res.append((
        "⑤ 每块零片都是**相对**形状：掩码里 min 行 = min 列 = 0（左上角对齐）",
        not bad,
        "\n".join(bad) if bad else "两关 7 块（L1 槽3 空）全部左上角对齐",
    ))

    # ---- ⑥ ⭐ 可解性（第一关）：实测掩码在 4x3 目标内恰 2 种铺法 ----
    sols1 = enumerate_tilings(T1_CELLS, [c for c in l1_cells[:3]])
    res.append((
        "⑥ ⭐ 可解性：第一关三块实测掩码在 4x3 目标（第 2~5 行 x 第 2~4 列）内"
        "恰好 2 种合法铺法（参考仓库 .ref/solve_l1.py 的独立结论也是 2）",
        len(sols1) == 2,
        "铺法数 = %d；%s" % (len(sols1),
                            "；".join("锚点=%s" % (list(s),) for s in sols1)),
    ))

    # ---- ⑦ ⭐ pkg 声明的目标锚点确实能拼出目标图案（解的一致性）----
    placed = [place(l1_cells[i], L1_TGT[i]) for i in range(3)]
    ok = (all(p <= T1_CELLS for p in placed)
          and not (placed[0] & placed[1]) and not (placed[0] & placed[2])
          and not (placed[1] & placed[2])
          and (placed[0] | placed[1] | placed[2]) == T1_CELLS)
    res.append((
        "⑦ ⭐ 按 puzzle_pkg 的 L1_TGT0/1/2 摆这三块实测零片 → 不重叠且并集 == 4x3 目标图案"
        "（「pkg 给的答案」必须是真实解之一）",
        ok,
        "锚点 %s；并集格数 = %d（目标 %d）"
        % (L1_TGT, len(placed[0] | placed[1] | placed[2]), len(T1_CELLS)),
    ))

    # ---- ⑧ ⭐ 可解性（第二关）：锚点集合唯一，且 == pkg 的 L2_TGT0..3 ----
    sols2 = enumerate_tilings(T2_CELLS, l2_cells)
    sets2 = {frozenset(s) for s in sols2}
    res.append((
        "⑧ ⭐ 可解性：第二关四块实测掩码在 4x4 目标内合法铺法 > 0，"
        "且**去重后的锚点集合唯一** = {(2,2),(2,4),(4,2),(4,4)}（== pkg 的 L2_TGT0..3）",
        len(sets2) == 1 and frozenset(L2_TGT) in sets2,
        "有序铺法数 = %d，去重锚点集合数 = %d，唯一集合 = %s（pkg L2_TGT = %s）"
        % (len(sols2), len(sets2),
           sorted(min(sets2)) if sets2 else None, L2_TGT),
    ))

    # ---- ⑨ i_level 真的在换一套零片（不是常量输出）----
    diff = [i for i in range(4) if m1[i] != m2[i]]
    res.append((
        "⑨ i_level='0' 与 '1' 的零片确实不同（i_level 真的参与选择，不是常量输出）",
        len(diff) >= 3,
        "两关掩码不同的槽 = %s；L1 槽0=%s  L2 槽0=%s" % (diff, _hex(m1[0]), _hex(m2[0])),
    ))

    # ---- ⑩ 目标图案之间的几何关系（参考模型自检 + 语义：第二关右扩一列）----
    ok = (len(T1_CELLS) == 12 and len(T2_CELLS) == 16
          and T1_CELLS < T2_CELLS and (T2_CELLS - T1_CELLS)
          == frozenset((r, 5) for r in range(2, 6)))
    res.append((
        "⑩ （参考模型自检）两张目标图案的几何关系：第二关 = 第一关**右扩一列**"
        "（第 5 列 4 格），面积 12 -> 16 —— 这一条校验的是 tb 自己的参考模型，"
        "不依赖 RTL（RTL 侧由 ⑥⑦⑧ 的可解性断言覆盖）",
        ok,
        "|T1|=%d |T2|=%d 差集=%s（应为第 5 列 4 格）"
        % (len(T1_CELLS), len(T2_CELLS), sorted(T2_CELLS - T1_CELLS)),
    ))

    return res
