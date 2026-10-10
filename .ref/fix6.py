# -*- coding: utf-8 -*-
"""修复 6 —— 去掉重复的 fail_row 声明，并纠正 WIN/FAIL
图案切片的镜像。

包约定是 bit = 8*row + col，所以第 0 行占 bit 7..0。WIN/FAIL
的行提取却为第 0 行读了 WIN_MASK(63 downto 56)，也就是说它把
两幅结束图案都显示成上下镜像了。FAIL_MASK 恰好是上下
对称的，所以看起来没问题；WIN_MASK（对勾）则不然。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_top.vhd")
s = p.read_text(encoding="utf-8")

# 去重该声明
s = s.replace("    signal prev_row : std_logic_vector(7 downto 0);  -- target picture row\n"
              "    signal fail_row : std_logic_vector(7 downto 0);\n"
              "    signal fail_row : std_logic_vector(7 downto 0);\n",
              "    signal prev_row : std_logic_vector(7 downto 0);  -- target picture row\n"
              "    signal fail_row : std_logic_vector(7 downto 0);\n")

# 纠正 win_row 的镜像
old_win = """    with std_logic_vector(mrow) select
        win_row <= WIN_MASK(63 downto 56) when "000",
                   WIN_MASK(55 downto 48) when "001",
                   WIN_MASK(47 downto 40) when "010",
                   WIN_MASK(39 downto 32) when "011",
                   WIN_MASK(31 downto 24) when "100",
                   WIN_MASK(23 downto 16) when "101",
                   WIN_MASK(15 downto  8) when "110",
                   WIN_MASK( 7 downto  0) when others;"""
new_win = """    -- NOTE the slice order: in this project's convention bit = 8*row + col, so
    -- logical row 0 is bits 7..0 (NOT the top slice).  Reading 63..56 for row 0
    -- displayed both end pictures vertically mirrored.
    with std_logic_vector(mrow) select
        win_row <= WIN_MASK( 7 downto  0) when "000",
                   WIN_MASK(15 downto  8) when "001",
                   WIN_MASK(23 downto 16) when "010",
                   WIN_MASK(31 downto 24) when "011",
                   WIN_MASK(39 downto 32) when "100",
                   WIN_MASK(47 downto 40) when "101",
                   WIN_MASK(55 downto 48) when "110",
                   WIN_MASK(63 downto 56) when others;"""
assert old_win in s, "win_row block not found"
s = s.replace(old_win, new_win)

old_fail = """    with std_logic_vector(mrow) select
        fail_row <= FAIL_MASK(63 downto 56) when "000",
                    FAIL_MASK(55 downto 48) when "001",
                    FAIL_MASK(47 downto 40) when "010",
                    FAIL_MASK(39 downto 32) when "011",
                    FAIL_MASK(31 downto 24) when "100",
                    FAIL_MASK(23 downto 16) when "101",
                    FAIL_MASK(15 downto  8) when "110",
                    FAIL_MASK( 7 downto  0) when others;"""
new_fail = """    with std_logic_vector(mrow) select
        fail_row <= FAIL_MASK( 7 downto  0) when "000",
                    FAIL_MASK(15 downto  8) when "001",
                    FAIL_MASK(23 downto 16) when "010",
                    FAIL_MASK(31 downto 24) when "011",
                    FAIL_MASK(39 downto 32) when "100",
                    FAIL_MASK(47 downto 40) when "101",
                    FAIL_MASK(55 downto 48) when "110",
                    FAIL_MASK(63 downto 56) when others;"""
assert old_fail in s, "fail_row block not found"
s = s.replace(old_fail, new_fail)

p.write_text(s, encoding="utf-8")
print("win/fail slices un-mirrored; declaration de-duplicated")
