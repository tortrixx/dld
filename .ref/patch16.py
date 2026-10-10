# -*- coding: utf-8 -*-
"""把 puzzle_ctrl 的行输出改名为 o_rowr / o_rowg（行扫描命名）。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")
s = s.replace("        o_red     : out std_logic_vector(7 downto 0);   -- row o_scanrow, red\n"
              "        o_grn     : out std_logic_vector(7 downto 0)    -- row o_scanrow, green\n",
              "        o_rowr    : out std_logic_vector(7 downto 0);   -- red   bits for o_scanrow\n"
              "        o_rowg    : out std_logic_vector(7 downto 0)    -- green bits for o_scanrow\n")
s = s.replace("o_red ", "o_rowr ")
s = s.replace("o_grn ", "o_rowg ")
p.write_text(s, encoding="utf-8")
print("o_rowr refs:", s.count("o_rowr"), " o_rowg refs:", s.count("o_rowg"))
