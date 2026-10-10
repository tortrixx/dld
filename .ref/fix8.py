# -*- coding: utf-8 -*-
"""修复键盘诊断：加上 unsigned -> std_logic_vector 的类型转换，并把 buzz
加入生成器的端口列表（新的守护检查抓到了这处遗漏，而这正是
它被写出来的目的）。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "keypad_diag_top.vhd"
s = p.read_text(encoding="utf-8")
s = s.replace("    disp(23 downto 20) <= npress;                       -- press counter\n"
              "    disp(19 downto 16) <= nseen;                        -- distinct keys seen",
              "    disp(23 downto 20) <= std_logic_vector(npress);      -- press counter\n"
              "    disp(19 downto 16) <= std_logic_vector(nseen);       -- distinct keys seen")
p.write_text(s, encoding="utf-8")

q = ROOT / "scripts" / "gen_project.py"
t = q.read_text(encoding="utf-8")
t = t.replace('''    "keypad_diag_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                        "dot_row", "dot_colr", "dot_colg", "seg", "cat"],''',
              '''    "keypad_diag_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                        "dot_row", "dot_colr", "dot_colg", "seg", "cat", "buzz"],''')
q.write_text(t, encoding="utf-8")
print("fixed")
