-- ============================================================================
--  pattern_rom  ——  完整图案查找表
--  所属子系统：S5（图案与随机数据）
--
--  纯组合逻辑。共 5 幅图案：
--    · 第一关 1 幅：图 4-1 矩形（B4 指定），i_level='0' 时 i_pat 被忽略；
--    · 第二 / 三关共用图案库 4 幅（puzzle_pkg.L2_PATS），由 i_pat 选择。
--
--  选择哪一幅由顶层决定（puzzle_top 的 pat_sel 锁存）：
--    第二关 -> 固定 L2_FIXED_PAT（PAT3 阶梯）
--    第三关 -> rng_lfsr 低 2 位，每局随机
--  本模块只负责"按 i_pat 取表"，不关心关卡语义。
--
--  结算画面（对勾 / 叉）是单独的常量，不在这里，因为玩家不需要把它们拼出来。
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

    -- 第一关：图 4-1 图案（B4 指定）。
    -- 第二 / 三关：图案库，由 pat_sel 索引。
    o_mask <= L1_TARGET_MASK when (i_level = '0')
              else L2_PATS(to_integer(unsigned(i_pat)));

end architecture rtl;
