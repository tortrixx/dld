# -*- coding: utf-8 -*-
"""修正：'others' 是 VHDL 保留字，不能用作变量名。
把该变量改名为 occ_rest，并删掉对已失效的 'work' 的赋值。"""
import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 变量声明
s = s.replace("        variable others: std_logic_vector(63 downto 0);",
              "        variable occ_rest : std_logic_vector(63 downto 0);")
# 该变量的所有使用处（全都是 'others :=' 或 'others or' 形式）
s = s.replace("others := (others => '0');", "occ_rest := (others => '0');")
s = s.replace("others := others or", "occ_rest := occ_rest or")
s = s.replace("occ and others", "occ and occ_rest")
# 对已不存在的信号留下的失效赋值
s = s.replace("                work   <= (others => '0');\n", "")

p.write_text(s, encoding="utf-8")

bad = [(i, l.strip()) for i, l in enumerate(s.splitlines(), 1)
       if re.search(r"\bothers\s*:=", l) or re.search(r"\bothers\s+or\b", l)
       or "occ and others" in l or "work   <=" in l]
print("remaining bad lines:", bad if bad else "none")
