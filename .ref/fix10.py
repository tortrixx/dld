# -*- coding: utf-8 -*-
"""修复新扫描器中的列识别逻辑。

BUG：row_rel 在每个释放相位都被覆盖，所以只有最后一个相位的
读数得以保留——这意味着只有第 3 列的按键能被识别出来。各释放
相位必须累加：每个相位记录在它自己那一列被释放期间有哪些行
被拉低，被按下的列就是看到行被拉低的那个相位。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

# ---- 累加每个相位的列信息 --------------------------------
s = s.replace(
    "    signal row_all : std_logic_vector(3 downto 0);    -- rows with ALL columns LOW\n"
    "    signal row_rel : std_logic_vector(3 downto 0);    -- rows with all but one HIGH\n",
    "    signal row_all : std_logic_vector(3 downto 0);    -- rows with ALL columns LOW\n"
    "    -- per-phase record: col_low(c) = '1' means that while column c was the\n"
    "    -- only one released, a row line fell -> the pressed key is in column c.\n"
    "    signal col_low : std_logic_vector(3 downto 0) := (others => '0');\n")

s = s.replace("""                    -- Phase B: drive all HIGH, release one column per step, and
                    -- find which column lets a row fall.
                    when SC_RELEASE =>
                        if (settle = 63) then
                            row_rel <= i_row;
                            settle  <= (others => '0');
                            if (phase = 3) then
                                state <= SC_ALL_HIGH;
                            else
                                phase <= phase + 1;
                            end if;
                        else
                            settle <= settle + 1;
                        end if;""",
              """                    -- Phase B: drive all HIGH and release ONE column per step.
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
                        end if;""")

# 新一轮开始时清空累加器
s = s.replace("                        if (i_tick = '1') then\n"
              "                            col_all <= '1';\n"
              "                            settle  <= (others => '0');\n"
              "                            state   <= SC_SETTLE;\n"
              "                        end if;",
              "                        if (i_tick = '1') then\n"
              "                            col_all <= '1';\n"
              "                            col_low <= (others => '0');   -- new round\n"
              "                            settle  <= (others => '0');\n"
              "                            state   <= SC_SETTLE;\n"
              "                        end if;")

s = s.replace("                state   <= SC_ALL_HIGH;\n"
              "                phase   <= (others => '0');\n"
              "                settle  <= (others => '0');\n"
              "                col_all <= '0';\n"
              "                rd_done <= '0';",
              "                state   <= SC_ALL_HIGH;\n"
              "                phase   <= (others => '0');\n"
              "                settle  <= (others => '0');\n"
              "                col_all <= '0';\n"
              "                col_low <= (others => '0');\n"
              "                rd_done <= '0';")

# ---- 用累加器解码 ------------------------------------------
s = s.replace("    process (rd_done, row_all, row_rel, state)",
              "    process (row_all, col_low)")
s = s.replace("""        -- (2) which column?  With all columns driven HIGH, releasing the column
        --     of the pressed key is the only way to make that row fall.
        found := false;
        if (hit = '1') then
            for c in 0 to 3 loop
                if (row_rel(c) = KP_ACTIVE) then
                    ccol  := c;
                    found := true;
                end if;
            end loop;
            if not found then
                ccol := 0;      -- identity unknown, keep the key anyway
            end if;
        end if;""",
              """        -- (2) which column?  col_low(c) was set if a row fell while column c was
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
        end if;""")

p.write_text(s, encoding="utf-8")
print("column accumulator installed")
