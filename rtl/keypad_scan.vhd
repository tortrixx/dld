-- ============================================================================
--  keypad_scan  --  4x4 matrix keypad scanner, debounced
--  Subsystem : S2 (keyboard input)
--
--  BOARD WIRING (board manual, absolute truth)
--     columns COL0..COL3 -> PIN_117,118,119,120
--     rows    ROW0..ROW3 -> PIN_111,112,113,114
--
--  KEY CODE reported
--     o_key = 4*row + column,  i.e. the plain key index in READING ORDER
--     (row 0 = the top physical row, column 0 = the left-most column).
--     Interpreting that index as a game control is game_fsm's job (key_of).
--
--  ---------------------------------------------------------------------------
--  SCAN SCHEME AND WHY
--  ---------------------------------------------------------------------------
--  Two schemes were tried on the bench:
--
--   (a) column-major, one column driven LOW per phase, read the rows.
--       Worked, but only TWO keys were ever detected.  A row line is only read
--       while its own column is the driven one, so a single wiring/pull-up
--       problem on one column line removes a whole column silently.
--
--   (b) ALL columns driven LOW, then read the rows (used here).
--       Now a pressed key pulls its row LOW no matter which column it sits in,
--       so nothing can be lost to a single bad column.  The column is then found
--       by driving all columns HIGH and releasing ONE at a time; only the column
--       carrying the pressed key lets that row fall.
--
--  Scheme (b) is a superset of (a) in robustness: it converts "one bad column
--  loses four keys" into "one bad column loses at most a column identity, and
--  even then the key is still detected".
--
--  Debounce : a reading must be identical for DEBOUNCE_MAX+1 scan rounds
--             (now 4 rounds = 40 ms -- see the ERR-031 note in puzzle_pkg.vhd:
--              one round is TWO tick_200 periods = 10 ms, because SC_ALL_HIGH and
--              SC_ALL_LOW each wait for a tick; the old "16 x 5 ms = 80 ms" text
--              under-counted by 2x and the real value was 160 ms).
--  Outputs  : o_key holds the accepted index; o_press is a ONE-CLOCK pulse when a
--             newly accepted key appears, so a hold produces exactly one action.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity keypad_scan is
    port (
        i_clk     : in  std_logic;
        i_rst     : in  std_logic;                       -- active HIGH
        i_tick    : in  std_logic;                       -- 200 Hz scan tick
        i_row     : in  std_logic_vector(3 downto 0);    -- matrix rows ROW0..ROW3
        o_col     : out std_logic_vector(3 downto 0);    -- matrix columns COL0..COL3
        o_key     : out std_logic_vector(3 downto 0);    -- accepted key index
        o_press   : out std_logic;                       -- one-clock pulse
        o_release : out std_logic;                       -- one-clock pulse
        o_raw     : out std_logic_vector(3 downto 0)     -- debug: live column drive
    );
end entity keypad_scan;

architecture rtl of keypad_scan is

    -- THE polarity constant of this project: the level a row line reads while
    -- its key is pressed.  Measured on the bench: '0'.
    constant KP_ACTIVE : std_logic := '0';

    type scan_t is (SC_ALL_LOW, SC_ALL_HIGH, SC_RELEASE, SC_SETTLE);

    signal state   : scan_t := SC_ALL_HIGH;
    signal phase   : unsigned(1 downto 0) := (others => '0');
    signal settle  : unsigned(7 downto 0) := (others => '0');

    signal row_all : std_logic_vector(3 downto 0);    -- rows with ALL columns LOW
    -- per-phase record: col_low(c) = '1' means that while column c was the
    -- only one released, a row line fell -> the pressed key is in column c.
    signal col_low : std_logic_vector(3 downto 0) := (others => '0');
    signal col_all : std_logic := '0';                -- 1 = all columns LOW

    signal cand    : std_logic_vector(3 downto 0) := K_NONE;  -- candidate index
    signal any_hit : std_logic := '0';
    signal rd_done : std_logic := '0';

    signal stable    : std_logic_vector(3 downto 0) := K_NONE;
    signal cnt       : unsigned(7 downto 0) := (others => '0');
    signal key_r     : std_logic_vector(3 downto 0) := K_NONE;
    signal press_r   : std_logic := '0';
    signal release_r : std_logic := '0';

    signal col_drv   : std_logic_vector(3 downto 0) := (others => '1');

begin

    ----------------------------------------------------------------------------
    -- Column drive.
    --   SC_ALL_LOW / SC_SETTLE while col_all='1' : every column LOW
    --   SC_RELEASE                                : all HIGH except the one
    --                                               selected by 'phase'
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                state   <= SC_ALL_HIGH;
                phase   <= (others => '0');
                settle  <= (others => '0');
                col_all <= '0';
                col_low <= (others => '0');
                rd_done <= '0';
            else
                case state is

                    -- Phase A: pull ALL columns low, then sample the rows.
                    when SC_ALL_LOW =>
                        if (i_tick = '1') then
                            col_all <= '1';
                            col_low <= (others => '0');   -- new round
                            settle  <= (others => '0');
                            state   <= SC_SETTLE;
                        end if;

                    -- Settle, then latch the "all columns low" row pattern.
                    when SC_SETTLE =>
                        if (settle = 63) then
                            row_all <= i_row;
                            rd_done <= '1';
                            col_all <= '0';
                            phase   <= (others => '0');
                            state   <= SC_RELEASE;
                        else
                            settle <= settle + 1;
                        end if;

                    -- Phase B: drive all HIGH and release ONE column per step.
                    -- While column c is released, the only way a row can fall is
                    -- if the pressed key sits in column c -- so each phase that
                    -- sees a fall identifies one column.  The results must be
                    -- ACCUMULATED (an earlier version overwrote a single register
                    -- each phase, so only the last column was ever identified).
                    when SC_RELEASE =>
                        if (settle = 63) then
                            settle <= (others => '0');
                            -- any row low while this column is released?
                            if (i_row(0) = KP_ACTIVE) or (i_row(1) = KP_ACTIVE)
                               or (i_row(2) = KP_ACTIVE) or (i_row(3) = KP_ACTIVE) then
                                col_low(to_integer(phase)) <= '1';
                            end if;

                            if (phase = 3) then
                                state <= SC_ALL_HIGH;
                            else
                                phase <= phase + 1;
                            end if;
                        else
                            settle <= settle + 1;
                        end if;

                    when others =>
                        if (i_tick = '1') then
                            state <= SC_ALL_LOW;
                        end if;
                end case;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Combinational column drive (never registered, so the drive and the phase
    -- used to build the key code cannot disagree).
    ----------------------------------------------------------------------------
    with phase select
        col_drv <= "1110" when "00",
                   "1101" when "01",
                   "1011" when "10",
                   "0111" when others;

    o_col <= (others => '0') when (col_all = '1') else col_drv;
    o_raw <= col_drv;

    ----------------------------------------------------------------------------
    -- Row sampling -> candidate key index.
    --   any pressed row?
    --     yes -> the index is 4*row + column, and the column is the phase whose
    --            RELEASE let that row fall (i.e. the row was low in row_rel).
    --            If no release pinpoints it, fall back to column 0 so the key is
    --            still reported rather than lost.
    ----------------------------------------------------------------------------
    process (row_all, col_low)
        variable r    : integer;
        variable hit  : std_logic;
        variable crow : integer;
        variable ccol : integer;
        variable found : boolean;
    begin
        hit   := '0';
        crow  := 0;
        ccol  := 0;

        -- (1) is any row active with all columns low?
        for r in 0 to 3 loop
            if (row_all(r) = KP_ACTIVE) then
                hit  := '1';
                crow := r;
            end if;
        end loop;

        -- (2) which column?  col_low(c) was set if a row fell while column c was
        --     the only released one.  Normally exactly one bit is set.  If none is
        --     (inconsistent wiring), keep the key but fall back to column 0 so it
        --     is still reported rather than silently lost.
        found := false;
        if (hit = '1') then
            for c in 0 to 3 loop
                if (col_low(c) = '1') then
                    ccol  := c;
                    found := true;
                end if;
            end loop;
            if not found then
                ccol := 0;
            end if;
        end if;

        any_hit <= hit;
        if (hit = '1') then
            cand <= std_logic_vector(to_unsigned(4 * crow + ccol, 4));
        else
            cand <= K_NONE;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Debounce: exactly one sample per completed scan round.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                stable    <= K_NONE;
                cnt       <= (others => '0');
                key_r     <= K_NONE;
                press_r   <= '0';
                release_r <= '0';
            else
                press_r   <= '0';
                release_r <= '0';

                if (i_tick = '1') and (state = SC_ALL_HIGH) then
                    if (cand /= stable) then
                        if (cnt = DEBOUNCE_MAX) then
                            stable <= cand;
                            cnt    <= (others => '0');
                        else
                            cnt <= cnt + 1;
                        end if;
                    else
                        cnt <= (others => '0');
                    end if;

                    -- accept / release, one clock wide each
                    if ((stable /= K_NONE) and (key_r = K_NONE)) then
                        key_r   <= stable;
                        press_r <= '1';
                    elsif ((stable = K_NONE) and (key_r /= K_NONE)) then
                        key_r     <= K_NONE;
                        release_r <= '1';
                    elsif ((stable /= K_NONE) and (stable /= key_r)) then
                        -- a DIFFERENT key was accepted without an intervening
                        -- release: report it as a new press so no key is swallowed
                        key_r   <= stable;
                        press_r <= '1';
                    end if;
                end if;
            end if;
        end if;
    end process;

    o_key     <= key_r;
    o_press   <= press_r;
    o_release <= release_r;

end architecture rtl;
