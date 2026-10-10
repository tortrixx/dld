# -*- coding: utf-8 -*-
"""修复 3 —— game_fsm：关卡时限从未被加载；o_go 反复重发。

缺陷 3a（经阅读代码确认）：S_PREVIEW 以 `st <= S_PLAYING` 退出，
且没有加载 cnt，而 T_LEVEL1/T_LEVEL2 在别处从未被引用。cnt 从预览
出来时仍是 1，所以紧接着的下一个 1 Hz tick 就走进 `cnt <= 1` 分支，
游戏直接跳到 S_FAIL。对局状态持续不到一秒，而不是 30 s / 40 s——
也就是说，即使按键工作正常，游戏也无法进行。

缺陷 3b（经跟踪确认）：o_go 的请求/应答握手不记得自己
已经完成过。一旦引擎回到 SH_IDLE，i_shuf_busy 拉低，握手就
立刻再请求一次散落，于是引擎几乎在不停地被重新散落。
这会在每次请求时清掉 sel/locked（所以 确认 永远无法生效），
并让引擎一直忙碌，从而忽略按键输入。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")

# ---- 3a：开始对局时加载关卡时限 ------------------------
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

# ---- 3b：让 o_go 每次对局只发一次 -----------------------------------
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

# 复位这个新标志
s = s.replace("                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');\n            elsif (i_sw = '0') then\n                -- B1: with the switch off the whole system is held at the top of\n                -- the sequence, so switching back on always shows a fresh\n                -- self-test / idle rather than resuming a half-played game.\n                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');",
              "                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');\n                go_done <= '0';\n            elsif (i_sw = '0') then\n                -- B1: with the switch off the whole system is held at the top of\n                -- the sequence, so switching back on always shows a fresh\n                -- self-test / idle rather than resuming a half-played game.\n                st    <= S_SELF_TEST;\n                level <= '0';\n                cnt   <= (others => '0');\n                selfc <= (others => '0');\n                go_done <= '0';")

p.write_text(s, encoding="utf-8")
print("game_fsm: level time loaded, o_go one-shot")
