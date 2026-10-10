# -*- coding: utf-8 -*-
"""在生成器里注册 keypad_raw_top。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "scripts" / "gen_project.py"
s = p.read_text(encoding="utf-8")
old = '''    "keypad_diag_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                        "seg", "cat"],'''
new = '''    "keypad_diag_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                        "seg", "cat"],
    "keypad_raw_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                       "seg", "cat"],'''
assert old in s
s = s.replace(old, new)
s = s.replace('"puzzle_top.vhd", "board_test_top.vhd", "keypad_diag_top.vhd"]:',
              '"puzzle_top.vhd", "board_test_top.vhd", "keypad_diag_top.vhd",\n'
              '              "keypad_raw_top.vhd"]:')
p.write_text(s, encoding="utf-8")
print("registered")
