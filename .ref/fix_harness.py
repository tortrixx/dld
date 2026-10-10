# -*- coding: utf-8 -*-
"""为 puzzle_ctrl 新增的行扫描端口列表更新 scratch 测试框架。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / ".tmp" / "scratch" / "pc_only" / "scratch_top.vhd"
s = p.read_text(encoding="ascii")
s = s.replace(
    "            o_sel_idx : out std_logic_vector(1 downto 0);\n"
    "            o_pos     : out std_logic_vector(31 downto 0);\n"
    "            o_lock    : out std_logic_vector(3 downto 0);\n"
    "            o_px_red  : out std_logic_vector(63 downto 0);\n"
    "            o_px_grn  : out std_logic_vector(63 downto 0)\n",
    "            o_sel_idx : out std_logic_vector(1 downto 0);\n"
    "            o_pos     : out std_logic_vector(31 downto 0);\n"
    "            o_lock    : out std_logic_vector(3 downto 0);\n"
    "            o_scanrow : out std_logic_vector(2 downto 0);\n"
    "            o_red     : out std_logic_vector(7 downto 0);\n"
    "            o_grn     : out std_logic_vector(7 downto 0)\n")
s = s.replace(
    "            o_solved => so, o_all_lock => so2, o_busy => so3,\n"
    "            o_sel_idx => si, o_pos => po, o_lock => lo,\n"
    "            o_px_red => sink, o_px_grn => gr\n",
    "            o_solved => so, o_all_lock => so2, o_busy => so3,\n"
    "            o_sel_idx => si, o_pos => po, o_lock => lo,\n"
    "            o_scanrow => open, o_red => r8, o_grn => g8\n")
s = s.replace("    signal gr   : std_logic_vector(63 downto 0);\n",
              "    signal gr   : std_logic_vector(63 downto 0);\n"
              "    signal r8   : std_logic_vector(7 downto 0);\n"
              "    signal g8   : std_logic_vector(7 downto 0);\n")
# 使用新的行输出，以免它们被优化掉
s = s.replace("    sink <= tv;", "    sink <= tv xor (r8 & g8 & r8 & g8 & r8 & g8 & r8 & g8);")
p.write_text(s, encoding="ascii")
print("harness updated")
