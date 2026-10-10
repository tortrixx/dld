# -*- coding: utf-8 -*-
"""让 scratch 测试框架改用 puzzle_ctrl 的行扫描端口列表。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / ".ref" / "scratch_pc.py"
s = p.read_text(encoding="utf-8")
s = s.replace("""            o_sel_idx : out std_logic_vector(1 downto 0);
            o_pos     : out std_logic_vector(31 downto 0);
            o_lock    : out std_logic_vector(3 downto 0);
            o_px_red  : out std_logic_vector(63 downto 0);
            o_px_grn  : out std_logic_vector(63 downto 0)
""", """            o_sel_idx : out std_logic_vector(1 downto 0);
            o_pos     : out std_logic_vector(31 downto 0);
            o_lock    : out std_logic_vector(3 downto 0);
            o_scanrow : out std_logic_vector(2 downto 0);
            o_red     : out std_logic_vector(7 downto 0);
            o_grn     : out std_logic_vector(7 downto 0)
""")
s = s.replace("""            o_solved => so, o_all_lock => so2, o_busy => so3,
            o_sel_idx => si, o_pos => po, o_lock => lo,
            o_px_red => sink, o_px_grn => gr
""", """            o_solved => so, o_all_lock => so2, o_busy => so3,
            o_sel_idx => si, o_pos => po, o_lock => lo,
            o_scanrow => open, o_red => r8, o_grn => g8
""")
s = s.replace("    signal gr   : std_logic_vector(63 downto 0);",
              "    signal r8   : std_logic_vector(7 downto 0);\n    signal g8   : std_logic_vector(7 downto 0);")
s = s.replace("end architecture;",
              "    sink <= tv xor (r8 & g8 & r8 & g8 & r8 & g8 & r8 & g8);\nend architecture;")
p.write_text(s, encoding="utf-8")
print("scratch_pc.py updated")
