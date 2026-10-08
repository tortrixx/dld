# -*- coding: utf-8 -*-
"""FIX 3 -- game_fsm: level time limit is never loaded; o_go re-fires forever.

DEFECT 3a (confirmed by reading the code): S_PREVIEW exits with `st <= S_PLAYING`
and does NOT load cnt, and T_LEVEL1/T_LEVEL2 are referenced nowhere.  cnt is still
1 from the preview, so the very next 1 Hz tick takes the `cnt <= 1` branch and the
game jumps straight to S_FAIL.  The play state lasted under a second instead of
30 s / 40 s -- i.e. even with a working key the game was unplayable.

DEFECT 3b (confirmed by tracing): the o_go request/ack handshake has no memory of
having completed.  Once the engine returns to SH_IDLE, i_shuf_busy falls and the
handshake immediately requests another scatter, so the engine is re-scattered
essentially continuously.  That clears sel/locked on every request (so 确认 can
never stick) and keeps the engine busy so key input is ignored.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")

# ---- 3a: load the level time limit when play begins ------------------------
old = """                        elsif (i_tick_1hz = '1') then
                            if (cnt <= 1) then
                                -- preview over -> scatter and start playing
                                st <= S_PLAYING;
                            else
                                cnt <= cnt - 1;
                            end if;
                        end if;"""
new = """                        elsif (i_tick_1hz = '1') then
                            if (cnt <= 1) then
                                -- Preview over.  Load the level's TIME LIMIT here
                                -- (requirement B5 = 30 s, B10 = 40 s).  This was
                                -- missing: cnt stayed at 1 from the preview, so
                                -- the first playing tick immediately timed out and
                                -- the game ended after under a second.
                                if (level = '0') then
                                    cnt <= to_unsigned(T_LEVEL1, 6);
                                else
                                    cnt <= to_unsigned(T_LEVEL2, 6);
                                end if;
                                st <= S_PLAYING;
                            else
                                cnt <= cnt - 1;
                            end if;
                        end if;"""
assert old in s, "preview exit block not found"
s = s.replace(old, new)

# ---- 3b: make o_go once per play session -----------------------------------
old2 = """                if (st /= S_PLAYING) then
                    req_go <= '0';
                elsif ((req_go = '0') and (i_shuf_busy = '0')) then
                    req_go <= '1';                 -- one cycle of request...
                elsif (i_shuf_busy = '1') then
                    req_go <= '0';                 -- ...cleared once accepted
                end if;

                -- level-1 -> level-2 transitions also need a fresh scatter
                if ((st = S_PREVIEW) and (level = '1') and (i_tick_1hz = '1')) then
                    req_go <= '1';
                end if;"""
new2 = """                -- Scatter request: ONE request per play session.
                -- Without the go_done memory, the handshake re-fires the moment
                -- the engine returns to idle, so the engine was being re-scattered
                -- continuously -- which clears sel/locked every time and keeps the
                -- engine busy, so no key could ever have an effect.
                if (st /= S_PLAYING) then
                    req_go  <= '0';
                    go_done <= '0';                -- re-arm for the next session
                elsif (req_go = '0') and (go_done = '0') and (i_shuf_busy = '0') then
                    req_go <= '1';                 -- one request...
                elsif (i_shuf_busy = '1') then
                    req_go  <= '0';                -- ...accepted by the engine
                    go_done <= '1';                -- never request again this session
                end if;"""
assert old2 in s, "handshake block not found"
s = s.replace(old2, new2)

s = s.replace("    signal kdec    : std_logic_vector(3 downto 0) := K_NONE;  -- decoded game key",
              "    signal kdec    : std_logic_vector(3 downto 0) := K_NONE;  -- decoded game key\n"
              "    signal go_done : std_logic := '0';   -- scatter already requested this session")

# reset the new flag
s = s.replace("                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');\n            elsif (i_sw = '0') then\n                -- B1: with the switch off the whole system is held at the top of\n                -- the sequence, so switching back on always shows a fresh\n                -- self-test / idle rather than resuming a half-played game.\n                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');",
              "                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');\n                go_done <= '0';\n            elsif (i_sw = '0') then\n                -- B1: with the switch off the whole system is held at the top of\n                -- the sequence, so switching back on always shows a fresh\n                -- self-test / idle rather than resuming a half-played game.\n                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');\n                go_done <= '0';")

p.write_text(s, encoding="utf-8")
print("game_fsm: level time loaded, o_go one-shot")
