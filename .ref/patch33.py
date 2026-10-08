# -*- coding: utf-8 -*-
"""Register the keypad diagnostic top level in the project generator."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\scripts\gen_project.py")
s = p.read_text(encoding="utf-8")
old = '''    "disp_test_top":  ["clk", "sw7", "dot_row", "dot_colr", "dot_colg", "seg", "cat"],'''
new = '''    "disp_test_top":  ["clk", "sw7", "dot_row", "dot_colr", "dot_colg", "seg", "cat"],
    "keypad_diag_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                        "seg", "cat"],'''
assert old in s
s = s.replace(old, new)
# add the new source file to the compile list
s = s.replace('"puzzle_top.vhd", "board_test_top.vhd"]:',
              '"puzzle_top.vhd", "board_test_top.vhd", "keypad_diag_top.vhd"]:')
p.write_text(s, encoding="utf-8")
print("registered")
