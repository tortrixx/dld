-- ============================================================================
--  buzzer_ctrl  --  sound effects for the different game situations
--  Subsystem : S7 (sound output)
--  Improvement requirement A1 ("different sounds in different situations").
--
--  The board's buzzer is driven on PIN_60: writing a square wave in the audio
--  band makes it sound.  There is therefore no "note" to select -- a note is just
--  a divider ratio, and the only real work is deciding HOW LONG each sound runs.
--
--  Sound codes (from game_fsm):
--     000  silent
--     001  self-test jingle      (rising two-note)
--     010  preview beep          (short single beep, repeated)
--     011  correct / solved      (rising two-note)
--     100  wrong                 (falling two-note)
--     101  key click             (very short tick)
--     110  victory jingle        (long high note, pulsed)
--     111  failure jingle        (low note, pulsed)
--
--  Duration is counted with the 2 Hz tick (500 ms per step) because it is
--  already available and needs no extra divider; that keeps the module small.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity buzzer_ctrl is
    port (
        i_clk  : in  std_logic;
        i_rst  : in  std_logic;                      -- active HIGH
        i_en   : in  std_logic;                      -- '0' = force silence (SW7)
        i_sel  : in  std_logic_vector(2 downto 0);   -- sound code
        i_t2   : in  std_logic;                      -- 2 Hz tick (500 ms)
        o_buzz : out std_logic
    );
end entity buzzer_ctrl;

architecture rtl of buzzer_ctrl is

    -- tone period selectors: physical toggle count-1 for roughly
    --   2 kHz -> 12 500    (0x30D4)
    --   1 kHz -> 25 000    (0x61A8)
    --    500  -> 50 000    (0xC350)
    --    250  -> 100 000   (0x186A0)
    signal tone_sel : std_logic_vector(1 downto 0) := "00";

    signal cnt      : unsigned(16 downto 0) := (others => '0');
    signal half     : unsigned(16 downto 0) := to_unsigned(25000, 17);
    signal wave     : std_logic := '0';

    signal phase    : unsigned(2 downto 0) := (others => '0');
    signal on_now   : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- Tone and on/off pattern per sound code.
    -- "phase" advances every 500 ms while a sound is selected, which gives each
    -- effect a small rhythm instead of one flat tone.
    ----------------------------------------------------------------------------
    process (i_sel, phase)
        variable tone : std_logic_vector(1 downto 0);
        variable onv  : std_logic;
    begin
        tone := "00";
        onv  := '0';

        case i_sel is
            when "001" =>                     -- self-test : rising two-note
                if (phase(1) = '1') then
                    tone := "00";
                else
                    tone := "01";
                end if;
                onv := '1';

            when "010" =>                     -- preview : short beep, repeated
                tone := "10";
                onv  := phase(0);

            when "011" =>                     -- correct : high pip
                tone := "00";
                if (phase(2) = '0') then
                    onv := '1';
                end if;

            when "100" =>                     -- wrong : low pip
                tone := "11";
                if (phase(2) = '0') then
                    onv := '1';
                end if;

            when "101" =>                     -- key click : very short
                tone := "01";
                if (phase = 0) then
                    onv := '1';
                end if;

            when "110" =>                     -- victory : long high, pulsed
                tone := "00";
                onv  := phase(2);

            when "111" =>                     -- failure : low, pulsed
                tone := "11";
                if (phase(2) = '0') then
                    onv := '1';
                end if;

            when others =>                    -- "000" = silent
                tone := "00";
                onv  := '0';
        end case;

        tone_sel <= tone;
        on_now   <= onv;
    end process;

    -- half-period count for the selected tone
    with tone_sel select
        half <= to_unsigned(12500, 17) when "00",
                to_unsigned(25000, 17) when "01",
                to_unsigned(50000, 17) when "10",
                to_unsigned(100000, 17) when others;

    ----------------------------------------------------------------------------
    -- Square-wave generator
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                cnt  <= (others => '0');
                wave <= '0';
            elsif (cnt >= half) then
                cnt  <= (others => '0');
                wave <= not wave;
            else
                cnt <= cnt + 1;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Rhythm counter (500 ms per step) and final gating.
    -- A sound restarts from phase 0 whenever the code changes, so repeated
    -- events (successive key clicks) always restart cleanly.
    ----------------------------------------------------------------------------
    process (i_clk)
        variable prev : std_logic_vector(2 downto 0) := "000";
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                phase <= (others => '0');
                prev  := "000";
            elsif (i_sel /= prev) then
                phase <= (others => '0');      -- new sound -> restart the rhythm
                prev  := i_sel;
            elsif (i_t2 = '1') then
                phase <= phase + 1;
            end if;
        end if;
    end process;

    o_buzz <= wave when ((i_en = '1') and (on_now = '1')) else '0';

end architecture rtl;
