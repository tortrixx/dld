# -*- coding: utf-8 -*-
"""Fix: 'others' is a VHDL reserved word and cannot be used as a variable name.
Rename the variable to occ_rest, and drop the stale 'work' assignment."""
import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# variable declaration
s = s.replace("        variable others: std_logic_vector(63 downto 0);",
              "        variable occ_rest : std_logic_vector(63 downto 0);")
# all uses of the variable (they are all 'others :=' or 'others or' forms)
s = s.replace("others := (others => '0');", "occ_rest := (others => '0');")
s = s.replace("others := others or", "occ_rest := occ_rest or")
s = s.replace("occ and others", "occ and occ_rest")
# stale assignment to a signal that no longer exists
s = s.replace("                work   <= (others => '0');\n", "")

p.write_text(s, encoding="utf-8")

bad = [(i, l.strip()) for i, l in enumerate(s.splitlines(), 1)
       if re.search(r"\bothers\s*:=", l) or re.search(r"\bothers\s+or\b", l)
       or "occ and others" in l or "work   <=" in l]
print("remaining bad lines:", bad if bad else "none")
