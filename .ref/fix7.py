# -*- coding: utf-8 -*-
"""go_done 只能由一个进程驱动。它既在状态寄存器进程（第 133/142 行）
里被赋值，又在命令进程里被赋值。命令进程已经在状态不是 S_PLAYING 时
重新置位它，所以状态进程
完全不需要碰它。"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")

# 删掉状态寄存器进程里的那两处赋值（都以 "go_done <= '0';\n" 结尾）
s = s.replace("                selfc <= (others => '0');\n                go_done <= '0';\n",
              "                selfc <= (others => '0');\n")
s = s.replace("                selfc <= (others => '0');\n                go_done <= '0';\n",
              "                selfc <= (others => '0');\n")

p.write_text(s, encoding="utf-8")
print("go_done assignments now:", [i + 1 for i, l in enumerate(s.splitlines()) if "go_done <=" in l])
