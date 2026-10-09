# -*- coding: utf-8 -*-
"""tb_pattern_rom.py —— pattern_rom 功能仿真（含 A2/S1 第二关图案库）

【本轮要回答什么】
    `pattern_rom` 是**唯一**存放"完整图案"的地方（`docs/02` §5.4）。第一关的图案
    来自课程 PDF 图 4-1 的**逐像素解码**，本工程最容易出错的也正是这个常量
    （历史上真的错过一次：第二关方块低一行，见 ERR-008）。

    2026-10-09 起（提高要求 A2 / 自拟 S1「多种拼图图案随机选择」）：
      · **第一关只有一幅**（图 4-1，B4 明文指定）→ i_pat 必须被**忽略**；
      · **第二关是 4 幅图案的库**，按 i_pat 选一幅 → 逐幅验证。
    第 11 工作阶段（2026-10-09）把第二关零片由"四块 2x2 方块"换成**四种异形**
    （3/2/5/6 格），图案库随之换成四幅**用这四块恰好铺满**的轮廓 —— 本 tb 只负责
    "ROM 输出 == 图案"，可铺性由 scripts/check_geometry.py 独立穷举。

    所以本轮把图案**当作数据**逐点验证，期望值**由 8x8 的 ASCII 图独立描述**、
    不抄 RTL 字面量（抄一遍就是把 RTL 的常量复述一遍，抄错了也看不出来）：
      ① i_level='0', i_pat=0 → 图 4-1（第 2~5 行 x 第 2~4 列），面积 12；
      ② i_level='0', i_pat=3 → **仍是图 4-1**（第一关忽略图案库，B4）；
      ③ i_level='1', i_pat=0..3 → 4 幅图案逐幅精确匹配（期望值由 ASCII 图生成）；
      ④ 第二关 4 幅面积都 = 16（= 四块异形零片 3+2+5+6）；
      ⑤ 图 4-1 是图案 0 的真子集（两关共用同一块板面区域，第二关只是右扩一列）；
      ⑥ **每幅图案都连通且无洞**（轮廓要能一眼读出，也才可能被零片铺满）；
      ⑦ 4 幅图案互不相同（图案库不能有重复项，否则"随机"有概率白换）。

【判据与时间无关】只用 6 个时间槽（每槽 200 ns），不依赖任何时钟。
"""

DURATION = 1200.0
GRID_PERIOD = 10.0


# 期望值：**由坐标/ASCII 生成**，不写 64 位字面量
def rect_mask(rows, cols):
    m = 0
    for r in rows:
        for c in cols:
            m |= (1 << (8 * r + c))
    return m


L1_EXPECT = rect_mask(range(2, 6), range(2, 5))     # 4 行 x 3 列 = 12 格

# 第二关图案库：**8x8 的 ASCII 描述**（与 rtl/puzzle_pkg.vhd 的位串是两份材料）
L2_ASCII = {
    0: ["........", "........", "..####..", "..####..",
        "..####..", "..####..", "........", "........"],   # 田 4x4 实心方块
    1: ["........", "........", "..###...", ".#####..",
        ".#####..", "..###...", "........", "........"],   # 十 胖十字
    2: ["........", "........", ".####...", "...####.",
        "...####.", ".####...", "........", "........"],   # S/Z 锯齿
    3: ["........", "........", ".####...", ".#####..",
        "..####..", "...###..", "........", "........"],   # 阶梯
}


def ascii_mask(rows):
    m = 0
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch == "#":
                m |= 1 << (8 * r + c)
    return m


L2_EXPECT = {k: ascii_mask(v) for k, v in L2_ASCII.items()}

# 时间槽：(i_level, i_pat)；槽 i 的中心 = 100 + 200*i
SLOTS = [(0, 0), (0, 3), (1, 0), (1, 1), (1, 2), (1, 3)]

OBSERVE = ["i_level", "i_pat", "o_mask"]


def build(b):
    b.input_bit("i_level")
    b.input_bus("i_pat", 2)
    b.output_bus("o_mask", 64)
    b.segments("i_level", [(200.0, lv) for (lv, _p) in SLOTS])
    b.bus_segments("i_pat", [(200.0, p) for (_lv, p) in SLOTS])


def _hex(v):
    return "X" if v is None else ("0x%016X" % v)


def _popcount(v):
    return None if v is None else bin(v).count("1")


def _cells(m):
    return {(r, c) for r in range(8) for c in range(8) if (m >> (8 * r + c)) & 1}


def _connected(m):
    """4 连通（轮廓必须是一整块，不能是散点）。"""
    if m is None:
        return False
    cs = _cells(m)
    if not cs:
        return False
    seen, stack = {next(iter(cs))}, [next(iter(cs))]
    while stack:
        r, c = stack.pop()
        for n in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if n in cs and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(cs)


def _no_hole(m):
    """没有"被亮格完全围住的空腔"：从边框洪水填充，能到所有空格的才是无洞。"""
    if m is None:
        return False
    cs = _cells(m)
    rs = [r for r, _ in cs]
    cs_ = [c for _, c in cs]
    r0, r1, c0, c1 = min(rs) - 1, max(rs) + 1, min(cs_) - 1, max(cs_) + 1
    outside, stack = set(), []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            if (r, c) not in cs and (r in (r0, r1) or c in (c0, c1)):
                outside.add((r, c))
                stack.append((r, c))
    while stack:
        r, c = stack.pop()
        for n in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if (r0 <= n[0] <= r1 and c0 <= n[1] <= c1 and n not in cs
                    and n not in outside):
                outside.add(n)
                stack.append(n)
    return all((r, c) in cs or (r, c) in outside
               for r in range(r0, r1 + 1) for c in range(c0, c1 + 1))


def _at(vf, i):
    return vf.bus_value_at("o_mask", 100.0 + 200.0 * i)


def check(vf):
    res = []
    m_l1_a, m_l1_b = _at(vf, 0), _at(vf, 1)
    m2 = {k: _at(vf, i) for i, k in enumerate((0, 1, 2, 3), start=2)}

    res.append((
        "① i_level='0', i_pat=0 时 o_mask 精确等于图 4-1（第 2~5 行 x 第 2~4 列实心矩形）",
        m_l1_a == L1_EXPECT,
        "实测 %s，期望 %s" % (_hex(m_l1_a), _hex(L1_EXPECT)),
    ))

    res.append((
        "② i_level='0', i_pat=3 时 **仍是图 4-1**（第一关忽略图案库 —— B4 明文指定图 4-1，"
        "A2 的图案库只加在自拟的第二关）",
        m_l1_b == L1_EXPECT and m_l1_b == m_l1_a,
        "实测 %s，期望与 i_pat=0 完全相同 %s" % (_hex(m_l1_b), _hex(L1_EXPECT)),
    ))

    res.append((
        "③ 第一关图案面积 = 12 格（= 三块零片 3+6+3，面积守恒的前提）",
        _popcount(m_l1_a) == 12,
        "实测 popcount = %s，期望 12" % _popcount(m_l1_a),
    ))

    ok_pats = all(m2[k] == L2_EXPECT[k] for k in range(4))
    res.append((
        "④ ★ i_level='1' 时 o_mask = 图案库第 i_pat 幅（**4 幅逐幅精确匹配**；"
        "期望值由 tb 里的 8x8 ASCII 图独立生成，不是抄 64 位字面量）",
        ok_pats,
        "；".join("pat%d 实测 %s 期望 %s%s" % (k, _hex(m2[k]), _hex(L2_EXPECT[k]),
                                             "" if m2[k] == L2_EXPECT[k] else "  <<< 不符")
                 for k in range(4)),
    ))

    res.append((
        "⑤ 第二关 4 幅图案面积都 = 16 格（= 四块异形零片 3+2+5+6 = 16）",
        all(_popcount(v) == 16 for v in m2.values()),
        "实测 popcount = %s" % {k: _popcount(v) for k, v in m2.items()},
    ))

    ok_sub = ((m_l1_a is not None) and (m2[0] is not None)
              and ((m_l1_a & ~m2[0]) == 0) and (m_l1_a != m2[0]))
    res.append((
        "⑥ 图 4-1 是图案 0 的真子集（两关共用同一区域，第二关右扩一列）",
        ok_sub,
        "m1 & ~m2 = %s" % _hex(None if m_l1_a is None or m2[0] is None
                              else (m_l1_a & ~m2[0])),
    ))

    res.append((
        "⑦ 第二关 4 幅图案都**连通且无洞**（轮廓一眼可读；有洞或散点就拼不出来）",
        all(_connected(v) and _no_hole(v) for v in m2.values()),
        "逐幅 连通=%s 无洞=%s"
        % ({k: _connected(v) for k, v in m2.items()},
           {k: _no_hole(v) for k, v in m2.items()}),
    ))

    res.append((
        "⑧ 4 幅图案互不相同（重复项会让\"随机\"有概率白换一幅）",
        len(set(m2.values())) == 4,
        "去重后 %d 幅" % len(set(m2.values())),
    ))

    return res
