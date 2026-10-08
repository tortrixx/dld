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
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use work.puzzle_pkg.ALL;

entity pattern_rom is
    port (
        i_level : in  std_logic;                      -- '0' = level 1, '1' = level 2
        o_mask  : out std_logic_vector(63 downto 0)   -- target picture mask
    );
end entity pattern_rom;

architecture rtl of pattern_rom is
begin

    o_mask <= L1_TARGET_MASK when (i_level = '0') else L2_TARGET_MASK;

end architecture rtl;
