# -*- coding: utf-8 -*-
"""FIX 1 (clean) -- keypad_scan round capture.

CONFIRMED DEFECTS
  D1  round_code was cleared on EVERY clock while the sequencer sat in ST_IDLE
      (about 250 000 clocks), yet the debounce stage only samples it on the
      200 Hz tick.  The captured value survived one clock, so the sampler always
      read K_NONE and o_key stayed 0 for ever -- exactly the bench symptom
      "pressing any key does nothing".
  D2  only phase 3 (column 3) was ever captured, so keys in columns 0..2 could
      never be seen at all.

FIX
  * take the FIRST hit of ANY settled phase of the round;
  * hold it until the next round starts, so the debounce stage (sampled on the
    tick, ~5 ms later) can actually see it, and so "stable for N rounds" finally
    means something.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

# --- locate the whole row-sampling process body -----------------------------
start = s.index("            if (i_rst = '1') then\n                raw_hit    <= '0';")
end = s.index("    end process;", start)
body = '''            if (i_rst = '1') then
                raw_hit    <= '0';
                raw_code   <= K_NONE;
                round_code <= K_NONE;
                round_seen <= '0';
            else
                -- Combinational view of the currently settled phase.
                -- NOTE: a for loop with last-assignment-wins means the HIGHEST
                -- matching row index is reported when more than one row reads
                -- active (which should not happen for a sane keypad, but is
                -- deterministic if it does).
                raw_hit  <= '0';
                raw_code <= K_NONE;
                for r in 0 to 3 loop
                    if (i_row(r) = KP_ACTIVE) then
                        raw_hit  <= '1';
                        raw_code <= std_logic_vector(
                                        to_unsigned(4 * to_integer(phase) + r, 4));
                    end if;
                end loop;

                -- (1) publish the finished round: the tick is precisely the edge
                --     at which the sequencer leaves ST_IDLE and starts the next
                --     round, so at this moment round_code still holds what the
                --     round that just ended captured.
                if (i_tick = '1') and (state = ST_IDLE) then
                    round_code <= round_hold;     -- hand the result to debounce
                    round_seen <= '0';            -- re-arm for the new round
                end if;

                -- (2) capture the FIRST hit of any settled scan phase.
                --     Previously only (state = ST_SCAN and phase = 3) was taken,
                --     which hid columns 0..2 entirely.
                if (state = ST_SCAN) and (raw_hit = '1') and (round_seen = '0') then
                    round_hold <= raw_code;
                    round_seen <= '1';
                end if;
            end if;
'''
s = s[:start] + body + s[end:]

# --- new signals -------------------------------------------------------------
s = s.replace("    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- key seen in this round",
              "    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- result of the LAST round\n"
              "    signal round_hold : std_logic_vector(3 downto 0) := K_NONE;  -- captured this round\n"
              "    signal round_seen : std_logic := '0';   -- a hit was already taken this round")

p.write_text(s, encoding="utf-8")
print("keypad_scan capture fixed")
