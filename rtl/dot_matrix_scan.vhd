-- ============================================================================
--  dot_matrix_scan  --  8x8 dual-colour dot-matrix driver (row scan)
--  Subsystem : S6 (display)
--
--  Board wiring / polarity (from the manual, absolute truth):
--     rows    ROW0..ROW7 -> PIN_8,7,6,5,4,3,2,1     (row = LOW to select)
--     red     COLR0..COLR7 -> PIN_22,21,16,15,14,13,12,11  (red  = HIGH to light)
--     green   COLG0..COLG7 -> PIN_45,44,43,42,41,40,39,38  (green= HIGH to light)
--
--  A dot lights RED   when its row is LOW, its red column is HIGH and its green
--  column is LOW.  It lights GREEN when its row is LOW, its red column is LOW and
--  its green column is HIGH.
--  BOTH columns HIGH lights BOTH LEDs of that dot -> it looks YELLOW; both LOW
--  means the dot is dark.  (An earlier version of this comment wrongly said
--  "both HIGH = dot off" -- that contradicts the two lines below it and the
--  board test, which draws the self-test as all-yellow.  Corrected 2026-10-08.)
--
--  Three display colours therefore come from only two bit-planes:
--     red only -> RED,  green only -> GREEN,  both -> YELLOW.
--  That is how requirement B8 draws locked pieces and how B1 draws the self-test.
--
--  NOTE: this driver is a pure straight-through 2-bit-plane driver -- it does NOT
--  enforce red/green mutual exclusion.  "Mutual exclusion" is a property of the
--  *content* the caller supplies for single-colour pictures; if a caller drives
--  both planes high, the panel really does show yellow.
--
--  INTERFACE: the driver takes ONE ROW at a time (8 bits per colour) plus the
--  index of that row.  This is deliberate: the puzzle engine renders a single row
--  per scan period, so there is no 64-bit frame buffer anywhere in the design.
--  Keeping the interface row-sized is what made the whole engine fit in the
--  EPM1270 (see the measured notes in puzzle_ctrl.vhd).
--
--  >>> HARDWARE CONSTRAINT -- READ BEFORE USING THE 16 LEDs <<<
--  The board shares PIN_38..45 between COLG0..COLG7 and LD8..LD15, and
--  PIN_137..144 between LD8..LD15 and the VGA port.  Driving the LEDs would cost
--  the matrix its green colour, which requirement B6 depends on.  No requirement
--  of topic 4 asks for the LEDs, so they are deliberately left unused.
--
--  ROW ORDER -- MEASURED ON REAL HARDWARE, DO NOT "SIMPLIFY" THIS AWAY:
--  the manual lists ROW0..ROW7 on PIN_8..PIN_1 but never says which physical edge
--  ROW0 is.  Measured with board_test_top test 2 (hollow frame whose top-left dot
--  is red): the red marker appeared at the BOTTOM-LEFT, so ROW0 is the BOTTOM row
--  and the logical row index must be counted up from the bottom.  The decode
--  below is therefore reversed.  Columns (COLR0 = left-most) and the red/green
--  banks were confirmed correct as-is.  Keeping this in the RTL (rather than
--  reversing the .qsf pin list) means the .qsf still matches the manual
--  pin-for-pin and simulation sees the same mapping as the silicon.
--
--  Ghosting : the sources update the row data and the row index together, so a
--  row is never driven with another row's data.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity dot_matrix_scan is
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                       -- active HIGH
        i_en    : in  std_logic;                       -- '0' = matrix fully dark
        i_row   : in  std_logic_vector(2 downto 0);    -- which logical row (0 = top)
        i_colr  : in  std_logic_vector(7 downto 0);    -- red   bits for that row
        i_colg  : in  std_logic_vector(7 downto 0);    -- green bits for that row
        o_row   : out std_logic_vector(7 downto 0);    -- ROW0..ROW7, active LOW
        o_colr  : out std_logic_vector(7 downto 0);    -- COLR0..COLR7
        o_colg  : out std_logic_vector(7 downto 0)     -- COLG0..COLG7
    );
end entity dot_matrix_scan;

architecture rtl of dot_matrix_scan is

    signal row_sel : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- Row decode, one-hot, ACTIVE LOW, with the logical row counted from the
    -- bottom (see the ROW ORDER note in the header).
    ----------------------------------------------------------------------------
    with i_row select
        row_sel <= "01111111" when "000",   -- logical row 0 = TOP    -> ROW7 (PIN_1)
                   "10111111" when "001",
                   "11011111" when "010",
                   "11101111" when "011",
                   "11110111" when "100",
                   "11111011" when "101",
                   "11111101" when "110",
                   "11111110" when others;  -- logical row 7 = BOTTOM -> ROW0 (PIN_8)

    ----------------------------------------------------------------------------
    -- Registered outputs.  While disabled the whole panel is off.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if ((i_rst = '1') or (i_en = '0')) then
                o_row  <= (others => '1');
                o_colr <= (others => '0');
                o_colg <= (others => '0');
            else
                o_row  <= row_sel;
                o_colr <= i_colr;
                o_colg <= i_colg;
            end if;
        end if;
    end process;

end architecture rtl;
