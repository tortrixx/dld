-- ============================================================================
--  keypad_raw_top  --  KEYPAD ELECTRICAL TEST (correctly constrained pins)
--
--  IMPORTANT HISTORY -- WHY EVERY EARLIER KEYPAD RESULT WAS MEANINGLESS
--  --------------------------------------------------------------------
--  The first versions of this diagnostic were added to the project generator's
--  port table WITHOUT their kp_row / kp_col ports.  The generator only emits pin
--  constraints for the ports you list, so the keypad pins were left
--  unconstrained; the fitter then placed them on arbitrary free pins
--  (49, 102, 130, 88, ...).  The design compiled, ran, and simply drove and read
--  the WRONG PINS -- which is indistinguishable from broken hardware on the
--  bench.  Found by cross-checking the fitter's .pin report against the manual.
--  See docs/05 ERR-002 and scripts/check_keypad_pins.py.
--
--  WHAT IT DOES
--  ------------
--  Drives ALL FOUR COLUMNS LOW and displays the four row-line levels.
--  With every column low, pressing ANY key connects its row to a LOW line, so
--  that row MUST read LOW no matter which row/column the key occupies.  This is
--  the simplest test that cannot be fooled by row/column order.
--
--  DISPLAY
--      DISP7      = sub-step counter 0..3 (proves the firmware is running)
--      DISP6      = '-'
--      DISP5      = 0
--      DISP4      = 0
--      DISP3..DISP0 = the four row lines: ROW1 ROW2 ROW3 ROW0
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity keypad_raw_top is
    port (
        clk      : in  std_logic;
        sw7      : in  std_logic;
        btn      : in  std_logic;
        kp_row   : in  std_logic_vector(3 downto 0);
        kp_col   : out std_logic_vector(3 downto 0);
        dot_row  : out std_logic_vector(7 downto 0);
        dot_colr : out std_logic_vector(7 downto 0);
        dot_colg : out std_logic_vector(7 downto 0);
        seg      : out std_logic_vector(7 downto 0);
        cat      : out std_logic_vector(7 downto 0);
        buzz     : out std_logic
    );
end entity keypad_raw_top;

architecture rtl of keypad_raw_top is

    signal div     : unsigned(17 downto 0) := (others => '0');
    signal t200    : std_logic := '0';
    signal div2    : unsigned(26 downto 0) := (others => '0');
    signal t_step  : std_logic := '0';
    signal step    : unsigned(1 downto 0) := (others => '0');

    -- rows are shown live (no latch): the display refreshes 25 times a second, so
    -- a held key is perfectly readable and a transient one cannot be missed
    signal disp    : std_logic_vector(31 downto 0);

begin

    process (clk)
    begin
        if rising_edge(clk) then
            if (div = 249_999) then
                div  <= (others => '0');
                t200 <= '1';
            else
                div  <= div + 1;
                t200 <= '0';
            end if;

            -- ~0.75 s per step at 50 MHz, as a liveness indicator
            if (div2 = 33_554_431) then
                div2   <= (others => '0');
                t_step <= '1';
            else
                div2   <= div2 + 1;
                t_step <= '0';
            end if;
        end if;
    end process;

    process (clk)
    begin
        if rising_edge(clk) then
            if (sw7 = '0') then
                step <= (others => '0');
            elsif (t_step = '1') then
                step <= step + 1;               -- free-running counter, wraps
            end if;
        end if;
    end process;

    -- ALL columns driven LOW: the decisive condition
    kp_col <= "0000";

    disp(31 downto 28) <= "00" & std_logic_vector(step);
    disp(27 downto 24) <= "1010";                 -- '-'
    disp(23 downto 20) <= "0000";
    disp(19 downto 16) <= "0000";
    disp(15 downto 12) <= "000" & kp_row(1);
    disp(11 downto 8)  <= "000" & kp_row(2);
    disp(7 downto 4)   <= "000" & kp_row(3);
    disp(3 downto 0)   <= "000" & kp_row(0);

    u_seg : entity work.seg_scan
        port map (
            i_clk    => clk,
            i_rst    => '0',
            i_tick   => t200,
            i_en     => sw7,
            i_data   => disp,
            i_blank  => (others => '0'),
            i_raw_en => '0',
            i_raw    => (others => '0'),
            o_seg    => seg,
            o_cat    => cat
        );

    u_dot : entity work.dot_matrix_scan
        port map (
            i_clk   => clk,
            i_rst   => '0',
            i_en    => '0',
            i_row   => "000",
            i_colr  => (others => '0'),
            i_colg  => (others => '0'),
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );

    buzz <= '0';

end architecture rtl;
