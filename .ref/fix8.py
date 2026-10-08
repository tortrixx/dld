# -*- coding: utf-8 -*-
"""Fix the keypad diagnostic: unsigned -> std_logic_vector cast, and add buzz to
the generator's port list (the new guard caught this omission, which is exactly
what it was written for)."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_diag_top.vhd")
s = p.read_text(encoding="utf-8")
s = s.replace("    disp(23 downto 20) <= npress;                       -- press counter\n"
              "    disp(19 downto 16) <= nseen;                        -- distinct keys seen",
              "    disp(23 downto 20) <= std_logic_vector(npress);      -- press counter\n"
              "    disp(19 downto 16) <= std_logic_vector(nseen);       -- distinct keys seen")
p.write_text(s, encoding="utf-8")

q = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\scripts\gen_project.py")
t = q.read_text(encoding="utf-8")
t = t.replace('''    "keypad_diag_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                        "dot_row", "dot_colr", "dot_colg", "seg", "cat"],''',
              '''    "keypad_diag_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                        "dot_row", "dot_colr", "dot_colg", "seg", "cat", "buzz"],''')
q.write_text(t, encoding="utf-8")
print("fixed")
