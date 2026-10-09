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
        i_level : in  std_logic;                      -- '0' = level 1, '1' = level 2/3
        i_pat   : in  std_logic_vector(1 downto 0);   -- 图案库下标（只对第二/三关有效）
        o_mask  : out std_logic_vector(63 downto 0)   -- target picture mask
    );
end entity pattern_rom;

architecture rtl of pattern_rom is
begin

    -- Level 1 : the ONE figure-4-1 picture (requirement B4 fixes it).
    -- Level 2/3 : the pattern LIBRARY, indexed by pat_sel (B10 fixed / A2 random).
    o_mask <= L1_TARGET_MASK when (i_level = '0')
              else L2_PATS(to_integer(unsigned(i_pat)));

end architecture rtl;
