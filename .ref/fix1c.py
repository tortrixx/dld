# -*- coding: utf-8 -*-
"""修复 1c —— 去掉多余的 round_code 寄存器。

tick 边沿既发布本轮结果，又正是消抖级采样的时刻。
若用非阻塞赋值，消抖级会读到旧的 round_code（滞后一轮）。
让消抖级直接从 round_hold 取值，就去掉了这个多余的
寄存器以及一轮的滞后：tick 到来时 round_hold 已经
是最终值，因为本轮最后一次扫描相位大约在 1 ms 之前就结束了。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "keypad_scan.vhd"
s = p.read_text(encoding="utf-8")

s = s.replace("    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- result of the LAST round\n"
              "    signal round_hold : std_logic_vector(3 downto 0) := K_NONE;  -- captured this round\n",
              "    -- Result of the round that has just finished.  It is held from the\n"
              "    -- moment of capture until the next round starts, which is precisely\n"
              "    -- what the debounce stage needs: it samples once per round.\n"
              "    signal round_hold : std_logic_vector(3 downto 0) := K_NONE;\n")

s = s.replace("                round_code <= K_NONE;\n                round_seen <= '0';",
              "                round_hold <= K_NONE;\n                round_seen <= '0';")

s = s.replace("""                if (i_tick = '1') and (state = ST_IDLE) then
                    round_code <= round_hold;     -- hand the result to debounce
                    round_seen <= '0';            -- re-arm for the new round
                end if;""",
              """                if (i_tick = '1') and (state = ST_IDLE) then
                    -- The debounce stage samples round_hold on this very edge, so
                    -- the value must ALREADY be final here -- which it is, because
                    -- the round's scan phases finished about a millisecond ago.
                    -- (An extra register assigned here would be read stale by the
                    -- debounce in the same edge, delaying every key by one round.)
                    round_seen <= '0';            -- re-arm for the new round
                end if;""")

s = s.replace("                    if (round_code /= stable) then",
              "                    if (round_hold /= stable) then")
s = s.replace("                            stable <= round_code;", "                            stable <= round_hold;")

p.write_text(s, encoding="utf-8")
print("round_code register removed; debounce now reads round_hold directly")
print("round_code refs left:", s.count("round_code"))
