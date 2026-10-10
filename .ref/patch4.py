# -*- coding: utf-8 -*-
"""修正命名冲突：锚点 ROM 驱动 sh_row/sh_col，而散落序列器也在给 sh_row
赋值。把 ROM 的输出改名为 rom_row/rom_col。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

# 1. 在其它声明旁边加上 ROM 的输出信号
s = s.replace(
    "    signal rnd_p  : std_logic_vector(7 downto 0);\n"
    "    signal rnd_p2 : std_logic_vector(7 downto 0);\n"
    "    signal rnd_p3 : std_logic_vector(7 downto 0);\n"
    "    signal rnd_m  : std_logic_vector(63 downto 0);\n",
    "    signal rom_row : unsigned(3 downto 0);   -- anchor row from the LFSR\n"
    "    signal rom_col : unsigned(3 downto 0);   -- anchor col from the LFSR\n")

# 2. 重命名 ROM 进程的赋值目标
s = s.replace("    with rnd_val(6 downto 4) select\n        sh_col <=",
              "    with rnd_val(6 downto 4) select\n        rom_col <=")
s = s.replace("    with rnd_val(2 downto 0) select\n        sh_row <=",
              "    with rnd_val(2 downto 0) select\n        rom_row <=")

# 3. 在构造候选锚点时改用 ROM 的输出
s = s.replace("                        npos := std_logic_vector(sh_row(3 downto 0)) &\n"
              "                                std_logic_vector(sh_col(3 downto 0));",
              "                        npos := std_logic_vector(rom_row) &\n"
              "                                std_logic_vector(rom_col);")

p.write_text(s, encoding="utf-8")

# 报告
for i, l in enumerate(s.splitlines(), 1):
    if "sh_row" in l or "sh_col" in l or "rom_row" in l or "rom_col" in l:
        print(f"{i}: {l.strip()}")
