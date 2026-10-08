# -*- coding: utf-8 -*-
"""FIX 6 -- remove the duplicated fail_row declaration and un-mirror the WIN/FAIL
picture slices.

The package convention is bit = 8*row + col, so row 0 occupies bits 7..0.  The
WIN/FAIL row extraction was reading WIN_MASK(63 downto 56) for row 0, i.e. it
displayed both end pictures VERTICALLY MIRRORED.  FAIL_MASK happens to be
vertically symmetric so it looked fine; WIN_MASK (the tick) did not.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_top.vhd")
s = p.read_text(encoding="utf-8")

# de-duplicate the declaration
s = s.replace("    signal prev_row : std_logic_vector(7 downto 0);  -- target picture row\n"
              "    signal fail_row : std_logic_vector(7 downto 0);\n"
              "    signal fail_row : std_logic_vector(7 downto 0);\n",
              "    signal prev_row : std_logic_vector(7 downto 0);  -- target picture row\n"
              "    signal fail_row : std_logic_vector(7 downto 0);\n")

# un-mirror win_row
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
