-- ============================================================================
--  disp_format  --  turns the game state into seven-segment content
--  Subsystem : S6 (display)
--
--  Requirements that pin the display down:
--    B1  self-test : ALL EIGHT digits show "8", flashing at 2 Hz
--    B2  idle      : DISP7 shows "5", DISP0 shows "1" (level 1), rest blank
--    B3  level number is shown by DISP0
--    B4  preview   : DISP7 counts down the 5 s preview
--    B5  playing   : DISP4:DISP3 show the two-digit remaining time
--    B9  level 2   : DISP2 additionally shows "2"
--
--  Digit numbering (matches the board: DISP7 is the left-most digit):
--    bits 31..28 = DISP7, bits 27..24 = DISP6, ... bits 3..0 = DISP0
--
--  This module is purely combinational.  It owns no state -- deciding WHAT the
--  numbers are is the state machine's job, deciding HOW they are laid out is
--  this module's job.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity disp_format is
    port (
        i_state : in  std_logic_vector(2 downto 0);   -- state_t
        i_level : in  std_logic;                      -- '0' = level 1, '1' = level 2
        i_time  : in  std_logic_vector(5 downto 0);   -- countdown value in seconds
        i_blink : in  std_logic;                      -- 2 Hz blink flag (self-test)
        o_data  : out std_logic_vector(31 downto 0);  -- 8 x BCD
        o_blank : out std_logic_vector(7 downto 0)    -- '1' = blank that digit
    );
end entity disp_format;

architecture rtl of disp_format is

    -- helper: make one BCD digit, and one blank flag
    function bcd(v : integer) return std_logic_vector is
        variable r : std_logic_vector(3 downto 0);
    begin
        if (v < 0) or (v > 9) then
            r := "1111";          -- out of range -> the decoder blanks it
        else
            r := std_logic_vector(to_unsigned(v, 4));
        end if;
        return r;
    end function;

begin

    process (i_state, i_level, i_time, i_blink)
        variable d    : std_logic_vector(31 downto 0);
        variable bl   : std_logic_vector(7 downto 0);
        variable t    : integer range 0 to 99;
        variable tens : integer range 0 to 9;
        variable ones : integer range 0 to 9;
        variable lvlv : integer range 1 to 2;
    begin
        d  := (others => '0');
        bl := (others => '1');            -- blank everything by default
        t  := to_integer(unsigned(i_time));

        if (i_level = '0') then
            lvlv := 1;
        else
            lvlv := 2;
        end if;

        case i_state is

            ------------------------------------------------------------------
            -- B1 self-test : all eight digits "8", flashing at 2 Hz.
            -- i_blink is '1' for half a 2 Hz period, so blanking on i_blink=0
            -- gives exactly a 2 Hz on/off flash.
            ------------------------------------------------------------------
            when S_SELF_TEST =>
                for k in 0 to 7 loop
                    d(4 * k + 3 downto 4 * k) := bcd(8);
                    if (i_blink = '1') then
                        bl(k) := '0';
                    else
                        bl(k) := '1';
                    end if;
                end loop;

            ------------------------------------------------------------------
            -- B2 idle : DISP7 = "5", DISP0 = level, everything else dark.
            -- "5" on DISP7 is the requirement's literal idle picture; the level
            -- digit on DISP0 satisfies B3 at the same time.
            ------------------------------------------------------------------
            when S_IDLE =>
                d(31 downto 28) := bcd(5);
                bl(7) := '0';
                d(3 downto 0) := bcd(lvlv);
                bl(0) := '0';

            ------------------------------------------------------------------
            -- B4 preview : DISP7 counts down, DISP0 shows the level.
            ------------------------------------------------------------------
            when S_PREVIEW =>
                d(31 downto 28) := bcd(t);
                bl(7) := '0';
                d(3 downto 0) := bcd(lvlv);
                bl(0) := '0';

            ------------------------------------------------------------------
            -- B5 playing : DISP4:DISP3 = remaining seconds (two digits),
            -- DISP0 = level, and on level 2 DISP2 = "2" (requirement B9).
            --
            -- The tens/ones split uses a LOOKUP TABLE, not "/ 10" and "mod 10".
            -- Quartus inferred an lpm_divide for the division, and the reported
            -- critical path (26 ns, i.e. only 39 MHz) ran straight through its
            -- carry chain.  A 64-entry table is a small ROM and removes the
            -- divider from the design entirely.
            ------------------------------------------------------------------
            when S_PLAYING =>
                case t is
                    when 0  => tens := 0; ones := 0;
                    when 1  => tens := 0; ones := 1;
                    when 2  => tens := 0; ones := 2;
                    when 3  => tens := 0; ones := 3;
                    when 4  => tens := 0; ones := 4;
                    when 5  => tens := 0; ones := 5;
                    when 6  => tens := 0; ones := 6;
                    when 7  => tens := 0; ones := 7;
                    when 8  => tens := 0; ones := 8;
                    when 9  => tens := 0; ones := 9;
                    when 10 => tens := 1; ones := 0;
                    when 11 => tens := 1; ones := 1;
                    when 12 => tens := 1; ones := 2;
                    when 13 => tens := 1; ones := 3;
                    when 14 => tens := 1; ones := 4;
                    when 15 => tens := 1; ones := 5;
                    when 16 => tens := 1; ones := 6;
                    when 17 => tens := 1; ones := 7;
                    when 18 => tens := 1; ones := 8;
                    when 19 => tens := 1; ones := 9;
                    when 20 => tens := 2; ones := 0;
                    when 21 => tens := 2; ones := 1;
                    when 22 => tens := 2; ones := 2;
                    when 23 => tens := 2; ones := 3;
                    when 24 => tens := 2; ones := 4;
                    when 25 => tens := 2; ones := 5;
                    when 26 => tens := 2; ones := 6;
                    when 27 => tens := 2; ones := 7;
                    when 28 => tens := 2; ones := 8;
                    when 29 => tens := 2; ones := 9;
                    when 30 => tens := 3; ones := 0;
                    when 31 => tens := 3; ones := 1;
                    when 32 => tens := 3; ones := 2;
                    when 33 => tens := 3; ones := 3;
                    when 34 => tens := 3; ones := 4;
                    when 35 => tens := 3; ones := 5;
                    when 36 => tens := 3; ones := 6;
                    when 37 => tens := 3; ones := 7;
                    when 38 => tens := 3; ones := 8;
                    when 39 => tens := 3; ones := 9;
                    when others =>                 -- 40..63 (level-2 limit is 40)
                        if (t >= 40) and (t < 50) then
                            tens := 4; ones := t - 40;
                        elsif (t >= 50) and (t < 60) then
                            tens := 5; ones := t - 50;
                        else
                            tens := 6; ones := t - 60;
                        end if;
                end case;

                d(19 downto 16) := bcd(tens);    -- DISP4
                bl(4) := '0';
                d(15 downto 12) := bcd(ones);    -- DISP3
                bl(3) := '0';

                d(3 downto 0) := bcd(lvlv);      -- DISP0
                bl(0) := '0';

                if (i_level = '1') then
                    d(11 downto 8) := bcd(2);    -- DISP2
                    bl(2) := '0';
                end if;

            ------------------------------------------------------------------
            -- win / fail : show a distinctive static pattern.
            --   0.0.7.5 on the level-2 win, 0.0.0.0 on fail -- both are easy to
            --   tell apart from anything else on the panel.
            ------------------------------------------------------------------
            when S_WIN =>
                d(31 downto 28) := bcd(7);
                bl(7) := '0';
                d(27 downto 24) := bcd(5);
                bl(6) := '0';

            when S_FAIL =>
                d(31 downto 28) := bcd(0);
                bl(7) := '0';
                d(27 downto 24) := bcd(0);
                bl(6) := '0';

            when others =>
                null;

        end case;

        o_data  <= d;
        o_blank <= bl;
    end process;

end architecture rtl;
