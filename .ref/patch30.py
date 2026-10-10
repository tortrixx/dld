# -*- coding: utf-8 -*-
"""puzzle_top：改用引擎的 64 位帧输出，并为点阵驱动
切出对应的行 —— 该驱动按 t_40 扫描各行。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_top.vhd"
s = p.read_text(encoding="utf-8")

# 组件端口位宽
s = s.replace("            o_scanrow : out std_logic_vector(2 downto 0);\n"
              "            o_rowr    : out std_logic_vector(7 downto 0);\n"
              "            o_rowg    : out std_logic_vector(7 downto 0)\n",
              "            o_scanrow : out std_logic_vector(2 downto 0);\n"
              "            o_rowr    : out std_logic_vector(63 downto 0);\n"
              "            o_rowg    : out std_logic_vector(63 downto 0)\n")

# 信号声明：引擎现在输出整帧
s = s.replace("    -- engine output: one rendered row\n"
              "    signal eng_rowr : std_logic_vector(7 downto 0);\n"
              "    signal eng_rowg : std_logic_vector(7 downto 0);\n",
              "    -- engine output: a complete 64-bit frame per colour plane\n"
              "    signal eng_fr   : std_logic_vector(63 downto 0);\n"
              "    signal eng_fg   : std_logic_vector(63 downto 0);\n")

s = s.replace("            o_rowr    => eng_rowr,\n"
              "            o_rowg    => eng_rowg",
              "            o_rowr    => eng_fr,\n"
              "            o_rowg    => eng_fg")

# 为点阵驱动（t_40）加一个扫描行计数器
s = s.replace("    signal disp_data  : std_logic_vector(31 downto 0);",
              "    -- row the matrix driver is currently lighting\n"
              "    signal mrow      : unsigned(2 downto 0) := (others => '0');\n"
              "    signal disp_data  : std_logic_vector(31 downto 0);")

s = s.replace("begin\n\n    -- S1 : clock, ticks, reset",
              "begin\n\n"
              "    ----------------------------------------------------------------------------\n"
              "    -- Matrix row counter.  The engine publishes a whole frame every 8 ticks of\n"
              "    -- tick_200 (25 Hz); the driver lights one row at a time on the 40 Hz tick,\n"
              "    -- so one full pass over the frame takes 8 x 25 ms = 0.2 s.  Frame rate and\n"
              "    -- scan rate are tied only through the frame contents, which is stable.\n"
              "    ----------------------------------------------------------------------------\n"
              "    process (clk)\n"
              "    begin\n"
              "        if rising_edge(clk) then\n"
              "            if (rst = '1') then\n"
              "                mrow <= (others => '0');\n"
              "            elsif (t_40 = '1') then\n"
              "                mrow <= mrow + 1;\n"
              "            end if;\n"
              "        end if;\n"
              "    end process;\n\n"
              "    -- S1 : clock, ticks, reset")

# 点阵内容：切出引擎帧中的行，或替换成整屏画面
s = s.replace("    process (state, gblink, eng_rowr, eng_rowg, scanrow, win_row, fail_row)\n"
              "        variable lv : std_logic;\n"
              "    begin\n"
              "        lv := gblink;\n\n"
              "        if (state = S_SELF_TEST) then\n"
              "            -- full yellow on the bright half of the 2 Hz flash\n"
              "            if (lv = '1') then\n"
              "                mat_r <= (others => '1');\n"
              "                mat_g <= (others => '1');\n"
              "            else\n"
              "                mat_r <= (others => '0');\n"
              "                mat_g <= (others => '0');\n"
              "            end if;\n"
              "        elsif (state = S_WIN) then\n"
              "            mat_r <= win_row and (lv & lv & lv & lv & lv & lv & lv & lv);\n"
              "            mat_g <= (others => '0');\n"
              "        elsif (state = S_FAIL) then\n"
              "            mat_r <= fail_row and (lv & lv & lv & lv & lv & lv & lv & lv);\n"
              "            mat_g <= (others => '0');\n"
              "        else\n"
              "            mat_r <= eng_rowr;\n"
              "            mat_g <= eng_rowg;\n"
              "        end if;\n"
              "    end process;",
              "    process (state, gblink, mrow, eng_fr, eng_fg, win_row, fail_row)\n"
              "        variable lv  : std_logic;\n"
              "        variable rw  : std_logic_vector(7 downto 0);\n"
              "        variable gw  : std_logic_vector(7 downto 0);\n"
              "    begin\n"
              "        lv := gblink;\n\n"
              "        -- slice the row the driver is lighting out of the 64-bit picture.\n"
              "        -- bit index = 8*row + col with row 0 = TOP, so row 0 is the TOP slice.\n"
              "        case to_integer(mrow) is\n"
              "            when 0      => rw := eng_fr(63 downto 56); gw := eng_fg(63 downto 56);\n"
              "            when 1      => rw := eng_fr(55 downto 48); gw := eng_fg(55 downto 48);\n"
              "            when 2      => rw := eng_fr(47 downto 40); gw := eng_fg(47 downto 40);\n"
              "            when 3      => rw := eng_fr(39 downto 32); gw := eng_fg(39 downto 32);\n"
              "            when 4      => rw := eng_fr(31 downto 24); gw := eng_fg(31 downto 24);\n"
              "            when 5      => rw := eng_fr(23 downto 16); gw := eng_fg(23 downto 16);\n"
              "            when 6      => rw := eng_fr(15 downto 8);  gw := eng_fg(15 downto 8);\n"
              "            when others => rw := eng_fr(7 downto 0);   gw := eng_fg(7 downto 0);\n"
              "        end case;\n\n"
              "        if (state = S_SELF_TEST) then\n"
              "            -- whole panel yellow, flashing at 2 Hz (requirement B1)\n"
              "            mat_r <= (others => lv);\n"
              "            mat_g <= (others => lv);\n"
              "        elsif (state = S_WIN) then\n"
              "            mat_r <= win_row and (lv & lv & lv & lv & lv & lv & lv & lv);\n"
              "            mat_g <= (others => '0');\n"
              "        elsif (state = S_FAIL) then\n"
              "            mat_r <= fail_row and (lv & lv & lv & lv & lv & lv & lv & lv);\n"
              "            mat_g <= (others => '0');\n"
              "        else\n"
              "            mat_r <= rw;\n"
              "            mat_g <= gw;\n"
              "        end if;\n"
              "    end process;")

# 胜利/失败图案取行必须跟随 mrow，而不是 scanrow
s = s.replace("    with scanrow select\n        win_row <=", "    with std_logic_vector(mrow) select\n        win_row <=")
s = s.replace("    with scanrow select\n        fail_row <=", "    with std_logic_vector(mrow) select\n        fail_row <=")

# 驱动的行号
s = s.replace("            i_row   => scanrow,", "            i_row   => std_logic_vector(mrow),")

p.write_text(s, encoding="utf-8")
print("puzzle_top updated")
