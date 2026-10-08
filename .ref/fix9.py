# -*- coding: utf-8 -*-
"""Fix the nibble widths: row lines are single bits, so the nibble needs three
padding zeros (not one)."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_diag_top.vhd")
s = p.read_text(encoding="utf-8")
s = s.replace('disp(11 downto 8)  <= "0" & kp_row(1);', 'disp(11 downto 8)  <= "000" & kp_row(1);')
s = s.replace('disp(7 downto 4)   <= "0" & kp_row(2);', 'disp(7 downto 4)   <= "000" & kp_row(2);')
s = s.replace('disp(3 downto 0)   <= "0" & kp_row(3);', 'disp(3 downto 0)   <= "000" & kp_row(3);')
p.write_text(s, encoding="utf-8")
print("widths fixed")
