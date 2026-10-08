# -*- coding: utf-8 -*-
"""Fix name collision: the anchor ROM drove sh_row/sh_col while the scatter
sequencer also assigned sh_row.  Rename the ROM outputs to rom_row/rom_col."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 1. add the ROM output signals next to the other declarations
s = s.replace(
    "    signal rnd_p  : std_logic_vector(7 downto 0);\n"
    "    signal rnd_p2 : std_logic_vector(7 downto 0);\n"
    "    signal rnd_p3 : std_logic_vector(7 downto 0);\n"
    "    signal rnd_m  : std_logic_vector(63 downto 0);\n",
    "    signal rom_row : unsigned(3 downto 0);   -- anchor row from the LFSR\n"
    "    signal rom_col : unsigned(3 downto 0);   -- anchor col from the LFSR\n")

# 2. rename the ROM process targets
s = s.replace("    with rnd_val(6 downto 4) select\n        sh_col <=",
              "    with rnd_val(6 downto 4) select\n        rom_col <=")
s = s.replace("    with rnd_val(2 downto 0) select\n        sh_row <=",
              "    with rnd_val(2 downto 0) select\n        rom_row <=")

# 3. use the ROM outputs when building the candidate anchor
s = s.replace("                        npos := std_logic_vector(sh_row(3 downto 0)) &\n"
              "                                std_logic_vector(sh_col(3 downto 0));",
              "                        npos := std_logic_vector(rom_row) &\n"
              "                                std_logic_vector(rom_col);")

p.write_text(s, encoding="utf-8")

# report
for i, l in enumerate(s.splitlines(), 1):
    if "sh_row" in l or "sh_col" in l or "rom_row" in l or "rom_col" in l:
        print(f"{i}: {l.strip()}")
