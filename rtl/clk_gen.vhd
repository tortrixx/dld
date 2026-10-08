-- ============================================================================
--  clk_gen  --  clock divider chain, system reset and tick generation
--  Subsystem : S1 (clock and time base)
--
--  Responsibilities
--    * filter the raw reset push-button (BTN0, active HIGH on this board)
--    * produce the power-on reset
--    * produce a CASCADED divider chain.  Only the very first stage ever sees
--      the 50 MHz board clock; every following stage counts pulses produced by
--      the previous one.  This keeps the whole design cheap in logic cells,
--      which matters because the EPM1270 has only 1270 LEs.
--
--  Time base produced
--    tick_1k   : 1   kHz  (1 ms)      -> game seconds, reset timing
--    tick_200  : 200 Hz  (5 ms)       -> dot-matrix / keypad scan round
--    tick_100  : 100 Hz  (10 ms)      -> generic 10 ms grid
--    tick_2hz  : 2   Hz (500 ms)      -> self-test flash, "blink" flag
--    tick_1hz  : 1   Hz (1 s)         -> one-second game counter
--
--  Reset polarity : o_rst is ACTIVE HIGH.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity clk_gen is
    port (
        i_clk    : in  std_logic;                      -- board global clock (PIN_18)
        i_btn    : in  std_logic;                      -- reset key BTN0, active HIGH
        o_rst    : out std_logic;                      -- system reset, active HIGH
        o_tick_1k  : out std_logic;                    -- 1 ms pulse
        o_tick_200 : out std_logic;                    -- 5 ms pulse
        o_tick_100 : out std_logic;                    -- 10 ms pulse
        o_tick_2hz : out std_logic;                    -- 500 ms pulse
        o_tick_1hz : out std_logic;                    -- 1 s pulse
        -- 200 Hz / 5 = 40 Hz.  The puzzle engine builds a display row in 5 ticks
        -- of the 200 Hz tick, so the dot-matrix driver must advance one row per
        -- 40 Hz pulse to stay exactly in step with the row the engine publishes.
        o_tick_40  : out std_logic
    );
end entity clk_gen;

architecture rtl of clk_gen is

    -- stage 1 : 50 MHz -> 1 kHz
    signal c1      : unsigned(15 downto 0) := (others => '0');  -- needs 50000 -> 16 bit
    signal t1      : std_logic := '0';
    -- stage 2 : 1 kHz -> 200 Hz
    signal c2      : unsigned(2 downto 0)  := (others => '0');  -- 5 -> needs 3 bit
    signal t2      : std_logic := '0';
    -- stage 3 : 200 Hz -> 100 Hz
    signal c3      : std_logic := '0';
    signal t3      : std_logic := '0';
    -- stage 4 : 100 Hz -> 2 Hz
    signal c4      : unsigned(5 downto 0)  := (others => '0');  -- 50 -> needs 6 bit
    signal t4      : std_logic := '0';
    -- stage 5 : 100 Hz -> 1 Hz
    signal c5      : unsigned(6 downto 0)  := (others => '0');  -- 100 -> needs 7 bit
    signal t5      : std_logic := '0';
    -- stage 6 : 200 Hz -> 40 Hz  (divide by 5), for the row-scan lockstep
    signal c6      : unsigned(2 downto 0)  := (others => '0');
    signal t6      : std_logic := '0';

    -- reset path
    signal d_press : std_logic_vector(CNT_BTN downto 0) := (others => '1');
    signal s_por   : std_logic := '1';
    signal s_btn   : std_logic := '0';

    -- Power-on counter: saturating, never wraps -> cannot produce a phantom
    -- reset later on.  Counts 0..T_POR_MS-1, so 4 bits are enough.
    signal por_cnt : unsigned(3 downto 0) := (others => '0');

begin

    ----------------------------------------------------------------------------
    -- Divider chain.  Every stage uses the same two-statement idiom:
    --   count to N-1, emit a one-clock-wide pulse, wrap.
    -- Note: stage 1 counts CLK_HZ/1000 = 50000 pulses, so the counter needs
    -- 16 bits -- declaring it too narrow silently truncates and the whole time
    -- base becomes wrong.  Keep the widths in sync with puzzle_pkg.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            -- stage 1
            if (c1 = CNT_1K) then
                c1 <= (others => '0'); t1 <= '1';
            else
                c1 <= c1 + 1;          t1 <= '0';
            end if;

            -- stage 2 : counts tick_1k pulses
            if (t1 = '1') then
                if (c2 = CNT_200) then
                    c2 <= (others => '0'); t2 <= '1';
                else
                    c2 <= c2 + 1;          t2 <= '0';
                end if;
            else
                t2 <= '0';
            end if;

            -- stage 3 : 200 Hz -> 100 Hz (divide by 2)
            if (t2 = '1') then
                c3 <= not c3;
                t3 <= c3;                  -- emit when c3 toggles 1 -> 0
            else
                t3 <= '0';
            end if;

            -- stage 4 : 100 Hz -> 2 Hz
            if (t3 = '1') then
                if (c4 = CNT_2HZ) then
                    c4 <= (others => '0'); t4 <= '1';
                else
                    c4 <= c4 + 1;          t4 <= '0';
                end if;
            else
                t4 <= '0';
            end if;

            -- stage 5 : 100 Hz -> 1 Hz
            if (t3 = '1') then
                if (c5 = CNT_1HZ) then
                    c5 <= (others => '0'); t5 <= '1';
                else
                    c5 <= c5 + 1;          t5 <= '0';
                end if;
            else
                t5 <= '0';
            end if;

            -- stage 6 : 200 Hz -> 40 Hz (divide by 5).  The engine renders one
            -- display row per 5 ticks of tick_200, so the matrix driver advances
            -- one row per 40 Hz pulse and the two stay in lockstep.
            if (t2 = '1') then
                if (c6 = 4) then
                    c6 <= (others => '0'); t6 <= '1';
                else
                    c6 <= c6 + 1;          t6 <= '0';
                end if;
            else
                t6 <= '0';
            end if;
        end if;
    end process;

    o_tick_1k  <= t1;
    o_tick_200 <= t2;
    o_tick_100 <= t3;
    o_tick_2hz <= t4;
    o_tick_1hz <= t5;
    o_tick_40  <= t6;

    ----------------------------------------------------------------------------
    -- Push-button filter.
    -- The board states: "keys output LOW when idle and HIGH while pressed, and
    -- a debounce circuit must be designed by the user".  So a press is a HIGH.
    -- A shift register of 20 bits, all HIGH, means "pressed and stable for
    -- 20 ms".  Because the register starts all-HIGH at power-up, no reset is
    -- needed for it and no phantom press can be generated (the shift register
    -- only fills with '1' if the key really is held down).
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (t1 = '1') then                                  -- 1 ms steps
                d_press <= d_press(d_press'high - 1 downto 0) & i_btn;
            end if;
        end if;
    end process;

    s_btn <= '1' when (d_press = (d_press'range => '1')) else '0';

    ----------------------------------------------------------------------------
    -- Power-on reset : hold the system in reset for T_POR_MS milliseconds
    -- after configuration.  Implemented as a saturating counter (it stops at
    -- its maximum) so it can never wrap around and re-assert later.
    --
    -- ⚠️ MEASURED (tb_clk_gen, 2026-10-08): s_por actually releases when por_cnt
    --    reaches CNT_POR = T_POR_MS-1, i.e. after **9** tick_1k periods (~9 ms),
    --    not 10 -- an off-by-one between the constant name and the count.
    --    It is functionally harmless (a POR of 9 ms vs 10 ms changes nothing for
    --    a design whose real time base is milliseconds), so the RTL is left as
    --    measured on the board; only this comment was corrected.  If you ever
    --    need exactly T_POR_MS, compare against T_POR_MS instead of CNT_POR.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (t1 = '1') then
                if (por_cnt /= to_unsigned(CNT_POR, por_cnt'length)) then
                    por_cnt <= por_cnt + 1;
                end if;
            end if;
        end if;
    end process;

    s_por <= '1' when (por_cnt /= to_unsigned(CNT_POR, por_cnt'length)) else '0';

    o_rst <= s_por or s_btn;

end architecture rtl;
