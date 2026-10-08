# -*- coding: utf-8 -*-
"""tb_pattern_rom.py —— pattern_rom 功能仿真

【本轮要回答什么】
    `pattern_rom` 是**唯一**存放"完整图案"的地方（`docs/02` §5.4）。第一关的图案
    来自课程 PDF 图 4-1 的**逐像素解码**，本工程最容易出错的也正是这个常量
    （历史上真的错过一次：第二关方块低一行，见 ERR-008）。

    所以本轮不去"看波形好不好看"，而是把图案**当作数据**逐点验证：
      ① i_level='0' → o_mask 必须精确等于"第 2~5 行 × 第 2~4 列"的实心矩形；
      ② 面积（popcount）必须是 12（图 4-1 的格数，也是三块零片面积之和）；
      ③ i_level='1' → 必须是"第 2~5 行 × 第 2~5 列"的实心方块，面积 16；
      ④ 第一关图案必须是第二关图案的**子集**（两关共用同一块板面区域，
         第二关只是把它向右加宽一列）—— 若两个常量各写各的，这条必挂。

【判据与时间无关】只用两个采样点（电平各保持 200 ns），不依赖任何时钟。
"""

DURATION = 400.0
GRID_PERIOD = 10.0

# 期望值：**由坐标生成**，不写 64 位字面量 —— 否则就是把 RTL 里的常量抄一遍，
# 抄错了也看不出来（这正是本工程要防的"自证"）。
def rect_mask(rows, cols):
    m = 0
    for r in rows:
        for c in cols:
            m |= (1 << (8 * r + c))
    return m


L1_EXPECT = rect_mask(range(2, 6), range(2, 5))     # 4 行 x 3 列 = 12 格
L2_EXPECT = rect_mask(range(2, 6), range(2, 6))     # 4 行 x 4 列 = 16 格

OBSERVE = ["i_level", "o_mask"]


def build(b):
    b.input_bit("i_level")
    b.output_bus("o_mask", 64)
    # 前 200 ns 选第一关，后 200 ns 选第二关
    b.segments("i_level", [(200.0, 0), (200.0, 1)])


def _hex(v):
    return "X" if v is None else ("0x%016X" % v)


def _popcount(v):
    return None if v is None else bin(v).count("1")


def check(vf):
    res = []

    m1 = vf.bus_value_at("o_mask", 100.0)
    m2 = vf.bus_value_at("o_mask", 300.0)

    res.append((
        "① i_level='0' 时 o_mask 精确等于图 4-1（第 2~5 行 x 第 2~4 列实心矩形）",
        m1 == L1_EXPECT,
        "实测 %s，期望 %s" % (_hex(m1), _hex(L1_EXPECT)),
    ))

    res.append((
        "② 第一关图案面积 = 12 格（= 三块零片 3+6+3，面积守恒的前提）",
        _popcount(m1) == 12,
        "实测 popcount = %s，期望 12" % _popcount(m1),
    ))

    res.append((
        "③ i_level='1' 时 o_mask 精确等于第二关 4x4 方块（第 2~5 行 x 第 2~5 列）",
        m2 == L2_EXPECT,
        "实测 %s，期望 %s" % (_hex(m2), _hex(L2_EXPECT)),
    ))

    res.append((
        "④ 第二关图案面积 = 16 格（= 四块 2x2 零片 4x4）",
        _popcount(m2) == 16,
        "实测 popcount = %s，期望 16" % _popcount(m2),
    ))

    ok_sub = (m1 is not None) and (m2 is not None) and ((m1 & ~m2) == 0) and (m1 != m2)
    res.append((
        "⑤ 第一关图案是第二关图案的真子集（两关共用同一区域，第二关右扩一列）",
        ok_sub,
        "m1 & ~m2 = %s" % _hex(None if m1 is None or m2 is None else (m1 & ~m2)),
    ))

    return res
