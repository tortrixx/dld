-- ============================================================================
--  pattern_rom  --  complete-picture lookup table
--  Subsystem : S5 (pictures and random data)
--
--  Pure combinational.  Only the two level pictures are stored; the win/fail
--  pictures are separate constants because they are not pictures the player ever
--  has to assemble.
--
--  The level-1 picture is the figure-4-1 rectangle, DECODED FROM THE COURSE PDF
--  and verified bit-exact against the three pieces at their target anchors
--  (see .ref/solve_l1.py).  The level-2 picture is self-designed.
--
--  ⚠️ 2026-10-09（提高要求 A2 / 自拟 S1「多种拼图图案随机选择」）：
--    · **第一关只有一幅**（图 4-1，B4 明文指定）—— i_level='0' 时 i_pat 被忽略；
--    · **第二关是一个图案库**（puzzle_pkg.L2_PATS 的 4 幅），按 i_pat (= pat_sel，
--      开局预览起点锁存的 rng_lfsr 低 2 位) 选一幅 → 重开一局图案会变。
--    图案库的硬约束（每幅必须能被四块 2x2 零片恰好铺满）与逐图案穷举复核
--    见 rtl/puzzle_pkg.vhd 与 scripts/check_geometry.py。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity pattern_rom is
    port (
        i_level : in  std_logic;                      -- '0' = level 1, '1' = level 2
        i_pat   : in  std_logic_vector(1 downto 0);   -- 图案库下标（只对第二关有效）
        o_mask  : out std_logic_vector(63 downto 0)   -- target picture mask
    );
end entity pattern_rom;

architecture rtl of pattern_rom is
begin

    -- Level 1 : the ONE figure-4-1 picture (requirement B4 fixes it).
    -- Level 2 : the pattern LIBRARY, indexed by pat_sel (A2 / S1).
    o_mask <= L1_TARGET_MASK when (i_level = '0')
              else L2_PATS(to_integer(unsigned(i_pat)));

end architecture rtl;
