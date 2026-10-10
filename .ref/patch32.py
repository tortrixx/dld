# -*- coding: utf-8 -*-
"""修正键盘扫描里一个真实的差一错误。

col_drv 是**寄存**的，而 phase 在同一时钟里更新。于是 tick 之后的第一个
周期里，phase 还保持着 3（上一轮的残留），而 col_drv 刚刚
变成 "1110"（相位 0 的列）。采样器因此把每一次
读数都关联到了**错误**的列 —— 键被解码成错误的键码，而且由于
这一个周期的偏移，第一列实际上从未被读到。在板上这表现为
「按任何键都没有变化」。

修法：列驱动改为**组合**地从 phase 推导，这样被驱动的列与
用于构造键码的下标就绝不可能不一致。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

# --- 序列器：不再驱动列 -------------------------------------
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

# --- 组合逻辑列译码 ---------------------------------------------
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

# 复位不再需要设置 col_drv（它现在是组合的）
s = s.replace("                phase   <= (others => '0');\n"
              "                settle  <= (others => '0');\n"
              "                col_drv <= \"1110\";",
              "                phase   <= (others => '0');\n"
              "                settle  <= (others => '0');")

p.write_text(s, encoding="utf-8")
print("keypad off-by-one fixed")
