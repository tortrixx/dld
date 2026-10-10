# -*- coding: utf-8 -*-
"""在工程生成器里注册键盘自检顶层。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "scripts" / "gen_project.py"
s = p.read_text(encoding="utf-8")
old = '''    "disp_test_top":  ["clk", "sw7", "dot_row", "dot_colr", "dot_colg", "seg", "cat"],'''
new = '''    "disp_test_top":  ["clk", "sw7", "dot_row", "dot_colr", "dot_colg", "seg", "cat"],
    "keypad_diag_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                        "seg", "cat"],'''
assert old in s
s = s.replace(old, new)
# 把新增的源文件加入编译列表
s = s.replace('"puzzle_top.vhd", "board_test_top.vhd"]:',
              '"puzzle_top.vhd", "board_test_top.vhd", "keypad_diag_top.vhd"]:')
p.write_text(s, encoding="utf-8")
print("registered")
