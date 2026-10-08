# -*- coding: utf-8 -*-
"""FIX 1 -- keypad_scan: the round result was destroyed before it was sampled.

Defects (both confirmed by reading the code):
  D1  round_code is cleared on EVERY clock while the scan sequencer sits in
      ST_IDLE (~250 000 clocks), but the debounce stage only samples it on the
      200 Hz tick.  The phase-3 capture therefore survives exactly one clock and
      the sampler always reads K_NONE  ->  o_key is permanently 0, which is
      exactly the bench symptom "pressing any key does nothing".
  D2  only phase 3 is ever captured, so keys in columns 0..2 can never be seen.

Fix: capture on ANY settled phase of the round (first hit wins) and hold the
result until the NEXT round begins.  Holding it for a whole scan period also
makes the debounce stage's "stable for N rounds" comparison meaningful, which it
could never be before.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

old = """                if (state = ST_IDLE) then
                    round_code <= K_NONE;          -- new round is starting
                elsif ((state = ST_SCAN) and (phase = 3)) then
                    round_code <= raw_code;        -- last phase of the round
                end if;"""

new = """                -- Capture policy:
                --   * take the FIRST hit of ANY settled phase (not just phase 3),
                --     so keys in every column are visible;
                --   * HOLD the result until the next round is kicked off, because
                --     the debounce stage samples it on the 200 Hz tick -- roughly
                --     250 000 clocks after the round finished.  Clearing it on
                --     every ST_IDLE clock (the previous behaviour) meant the
                --     sampler read K_NONE forever and no key was ever accepted.
                if ((state = ST_IDLE) and (i_tick = '1')) then
                    round_code <= raw_code;        -- publish the finished round
                elsif ((state = ST_SCAN) or (state = ST_SETTLE)) then
                    if (raw_hit = '1') and (round_code /= raw_code) then
                        -- do not overwrite an accepted hit within the same round
                        null;
                    end if;
                end if;
                -- first hit of the round wins; earlier phases take priority
                if (state = ST_SCAN) and (raw_hit = '1') then
                    if (round_code = K_NONE) or (round_seen = '0') then
                        round_code <= raw_code;
                        round_seen <= '1';
                    end if;
                elsif ((state = ST_IDLE) and (i_tick = '1')) then
                    round_seen <= '0';             -- re-arm for the next round
                end if;"""

assert old in s, "capture block not found"
s = s.replace(old, new)

# new arming flag
s = s.replace("    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- key seen in this round",
              "    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- key seen in this round\n"
              "    signal round_seen : std_logic := '0';   -- a hit was already taken this round")

# reset the new flag
s = s.replace("                raw_hit    <= '0';\n                raw_code   <= K_NONE;\n                round_code <= K_NONE;",
              "                raw_hit    <= '0';\n                raw_code   <= K_NONE;\n"
              "                round_code <= K_NONE;\n                round_seen <= '0';")

p.write_text(s, encoding="utf-8")
print("keypad_scan patched")
