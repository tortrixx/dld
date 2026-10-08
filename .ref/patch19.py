# -*- coding: utf-8 -*-
"""Fix the pipelined row index: make chk_orow unsigned (so to_integer applies)
and derive it from the PREVIOUS row counter, which is the row being evaluated."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

s = s.replace("    signal chk_orow : std_logic_vector(3 downto 0) := (others => '0');",
              "    signal chk_orow : unsigned(3 downto 0) := (others => '0');  -- pipelined row index")

s = s.replace("""                        chk_orow <= std_logic_vector(
                                        resize(chk_row -
                                               unsigned(chk_pos(7 downto 4)), 4));""",
              """                        -- index of the row evaluated on the NEXT cycle
                        chk_orow <= resize(chk_row -
                                           unsigned(chk_pos(7 downto 4)), 4);""")

s = s.replace("                            rw := row_mask(chk_shp, to_integer(chk_orow),",
              "                            rw := row_mask(chk_shp, to_integer(chk_orow),")

p.write_text(s, encoding="utf-8")
print("ok")
