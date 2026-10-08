# -*- coding: utf-8 -*-
"""Fix a real off-by-one in the keypad scan.

col_drv was REGISTERED while phase was updated in the same clock.  On the first
cycle after a tick, phase still held 3 (from the previous round) while col_drv had
just become "1110" (phase 0's column).  The sampler therefore associated every
reading with the WRONG column -- keys decoded to the wrong code, and with the
one-cycle offset the first column was effectively never read.  On the board this
showed up as "pressing any key changes nothing".

Fix: derive the column drive COMBINATIONALLY from phase, so the driven column and
the index used to build the key code can never disagree.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

# --- sequencer: no longer drives columns -------------------------------------
s = s.replace("""                    when ST_IDLE =>
                        -- kick off a round on the scan tick
                        if (i_tick = '1') then
                            phase   <= (others => '0');
                            col_drv <= "1110";          -- phase 0 : column 0 low
                            settle  <= (others => '0');
                            state   <= ST_SETTLE;
                        end if;""",
              """                    when ST_IDLE =>
                        -- kick off a round on the scan tick
                        if (i_tick = '1') then
                            phase   <= (others => '0');
                            settle  <= (others => '0');
                            state   <= ST_SETTLE;
                        end if;""")

s = s.replace("""                    when ST_SCAN =>
                        -- phase advanced AFTER the read is captured, so the
                        -- capture in the other process uses the settled driver
                        if (phase = 3) then
                            state <= ST_IDLE;
                        else
                            phase   <= phase + 1;
                            -- exactly one '0' at position phase+1
                            case phase is
                                when "00" => col_drv <= "1101";
                                when "01" => col_drv <= "1011";
                                when others => col_drv <= "0111";
                            end case;
                            settle <= (others => '0');
                            state  <= ST_SETTLE;
                        end if;""",
              """                    when ST_SCAN =>
                        -- advance the phase; the column drive follows it
                        -- COMBINATIONALLY (see the decode below), so the driven
                        -- column and the index used to build the key code can
                        -- never disagree.
                        if (phase = 3) then
                            state <= ST_IDLE;
                        else
                            phase  <= phase + 1;
                            settle <= (others => '0');
                            state  <= ST_SETTLE;
                        end if;""")

# --- combinational column decode ---------------------------------------------
s = s.replace("    o_col <= col_drv;\n    o_raw <= col_drv;",
              """    ----------------------------------------------------------------------------
    -- Column drive: exactly one '0', at the position given by 'phase'.
    -- COMBINATIONAL on purpose -- see the note in ST_SCAN above.
    ----------------------------------------------------------------------------
    with phase select
        col_drv <= "1110" when "00",
                   "1101" when "01",
                   "1011" when "10",
                   "0111" when others;

    o_col <= col_drv;
    o_raw <= col_drv;""")

# reset no longer needs to set col_drv (it is combinational now)
s = s.replace("                phase   <= (others => '0');\n"
              "                settle  <= (others => '0');\n"
              "                col_drv <= \"1110\";",
              "                phase   <= (others => '0');\n"
              "                settle  <= (others => '0');")

p.write_text(s, encoding="utf-8")
print("keypad off-by-one fixed")
