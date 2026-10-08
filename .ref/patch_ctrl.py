# -*- coding: utf-8 -*-
"""One-off patch: drop the now-unused i_piece_n port / mv_step signal from
rtl/puzzle_ctrl.vhd and use the derived 'shape_n' instead."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")
orig = s

s = s.replace("        i_piece_n : in  std_logic_vector(2 downto 0);   -- pieces in this level (3 or 4)\n", "")
s = s.replace('if (i_piece_n = "011") then', "if (shape_n = 3) then")
s = s.replace("to_integer(unsigned(i_piece_n))", "shape_n")
s = s.replace("                mv_step <= '0';\n", "")
s = s.replace("                    mv_step <= '1';\n", "")
s = s.replace("    -- move request pipeline: one cycle to latch the request, so the direction\n"
              "    -- inputs and the shape database are stable when the move is validated\n"
              "    signal mv     : std_logic := '0';\n",
              "    -- move request pipeline: one cycle to latch the request, so the direction\n"
              "    -- inputs and the shape database are stable when the move is validated\n"
              "    signal mv     : std_logic := '0';\n")

p.write_text(s, encoding="utf-8")
print("changed" if s != orig else "NO CHANGE")
for i, line in enumerate(s.splitlines(), 1):
    if "i_piece_n" in line or "mv_step" in line:
        print(f"  still present {i}: {line.strip()}")
