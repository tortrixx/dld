-- ============================================================================
--  pattern_rom  --  完整图案查找表
--  子系统：S5（图案与随机数据）
--
--  纯组合逻辑。只存两幅关卡图案；胜利/失败
--  画面是单独的常量，因为玩家从来不需要
--  把它们拼装出来。
--
--  第一关图案是图 4-1 矩形，从课程 PDF 中解码得到，
--  并针对三块零片在其目标锚点处做过逐位精确核对
--  （见 .ref/solve_l1.py）。第二关图案为自行设计。
--
--  ⚠️ 2026-10-09（D2：第二关固定 + 第三关随机；提高要求 A2 / 自拟 S1）：
--    · **第一关只有一幅**（图 4-1，B4 明文指定）—— i_level='0' 时 i_pat 被忽略；
--    · **第二关与第三关共用这个图案库**（puzzle_pkg.L2_PATS 的 4 幅），按 i_pat (= pat_sel)
--      选一幅。**哪一幅由顶层决定**（rtl/puzzle_top.vhd 的 pat_sel 锁存进程）：
--        第二关 → 恒 lock 到 `L2_FIXED_PAT`（PAT3 阶梯，B10"自拟"但不随机）；
--        第三关 → 取 `rng_lfsr` 低 2 位（A2「多种拼图图案随机选择」）→ 重开一局会变。
--      所以本模块**故意保持"按 i_pat 选"这一条通路不变**（接口与语义都没动，
--      只是调用方给的 i_pat 变了），旧证据（tb_pattern_rom）继续有效。
--    图案库的硬约束（每幅必须能被四块异形零片**只许平移**恰好铺满）与逐图案穷举复核
--    见 rtl/puzzle_pkg.vhd 与 scripts/check_geometry.py。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity pattern_rom is
    port (
        i_level : in  std_logic;                      -- '0' = 第一关，'1' = 第二/三关
        i_pat   : in  std_logic_vector(1 downto 0);   -- 图案库下标（只对第二/三关有效）
        o_mask  : out std_logic_vector(63 downto 0)   -- 目标图案掩码
    );
end entity pattern_rom;

architecture rtl of pattern_rom is
begin

    -- 第一关：唯一一幅图 4-1 图案（要求 B4 指定）。
    -- 第二/三关：图案库，由 pat_sel 索引（B10 固定 / A2 随机）。
    o_mask <= L1_TARGET_MASK when (i_level = '0')
              else L2_PATS(to_integer(unsigned(i_pat)));

end architecture rtl;
