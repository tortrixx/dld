# -*- coding: utf-8 -*-
"""Measure puzzle_ctrl in isolation with LIVE inputs (so nothing is optimised
away).  Reports logic elements / registers so we can attribute area instead of
guessing which construct is expensive."""
import pathlib, shutil, subprocess

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
QUARTUS = pathlib.Path(r"C:\QuartusII91\QuartusII91\quartus\bin")

TOP = """
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity scratch_top is
    port (
        clk  : in  std_logic;
        rv   : in  std_logic_vector(7 downto 0);
        sin  : in  std_logic_vector(7 downto 0);
        sink : out std_logic_vector(63 downto 0)
    );
end entity;

architecture rtl of scratch_top is
    component puzzle_ctrl
        port (
            i_clk     : in  std_logic;
            i_rst     : in  std_logic;
            i_tick    : in  std_logic;
            rnd_step  : out std_logic;
            rnd_val   : in  std_logic_vector(7 downto 0);
            i_level   : in  std_logic;
            i_sh0     : in  std_logic_vector(63 downto 0);
            i_sh1     : in  std_logic_vector(63 downto 0);
            i_sh2     : in  std_logic_vector(63 downto 0);
            i_sh3     : in  std_logic_vector(63 downto 0);
            i_h0      : in  std_logic_vector(2 downto 0);
            i_h1      : in  std_logic_vector(2 downto 0);
            i_h2      : in  std_logic_vector(2 downto 0);
            i_h3      : in  std_logic_vector(2 downto 0);
            i_w0      : in  std_logic_vector(2 downto 0);
            i_w1      : in  std_logic_vector(2 downto 0);
            i_w2      : in  std_logic_vector(2 downto 0);
            i_w3      : in  std_logic_vector(2 downto 0);
            i_target  : in  std_logic_vector(63 downto 0);
            i_go      : in  std_logic;
            i_select  : in  std_logic;
            i_move    : in  std_logic;
            i_confirm : in  std_logic;
            i_up      : in  std_logic;
            i_down    : in  std_logic;
            i_left    : in  std_logic;
            i_right   : in  std_logic;
            o_solved  : out std_logic;
            o_all_lock: out std_logic;
            o_busy    : out std_logic;
            o_sel_idx : out std_logic_vector(1 downto 0);
            o_pos     : out std_logic_vector(31 downto 0);
            o_lock    : out std_logic_vector(3 downto 0);
            o_scanrow : out std_logic_vector(2 downto 0);
            o_red     : out std_logic_vector(7 downto 0);
            o_grn     : out std_logic_vector(7 downto 0)
        );
    end component;

    signal tv   : std_logic_vector(63 downto 0);
    signal ts   : std_logic_vector(63 downto 0);
    signal so   : std_logic;
    signal so2  : std_logic;
    signal so3  : std_logic;
    signal si   : std_logic_vector(1 downto 0);
    signal po   : std_logic_vector(31 downto 0);
    signal lo   : std_logic_vector(3 downto 0);
    signal r8   : std_logic_vector(7 downto 0);
    signal g8   : std_logic_vector(7 downto 0);
    signal rs   : std_logic;
begin
    -- a live rotating stimulus so no input is constant
    process (clk) begin
        if rising_edge(clk) then
            tv <= tv(62 downto 0) & (sin(0) xor rv(0));
        end if;
    end process;
    ts <= tv xor (rv & rv & rv & rv & rv & rv & rv & rv);

    u : puzzle_ctrl
        port map (
            i_clk => clk, i_rst => sin(1), i_tick => sin(2),
            rnd_step => rs, rnd_val => rv, i_level => sin(3),
            i_sh0 => tv, i_sh1 => ts, i_sh2 => tv, i_sh3 => ts,
            i_h0 => sin(5 downto 3), i_h1 => sin(5 downto 3),
            i_h2 => sin(5 downto 3), i_h3 => sin(5 downto 3),
            i_w0 => sin(7 downto 5), i_w1 => sin(7 downto 5),
            i_w2 => sin(7 downto 5), i_w3 => sin(7 downto 5),
            i_target => ts, i_go => sin(4), i_select => sin(0),
            i_move => sin(6), i_confirm => sin(7),
            i_up => rv(1), i_down => rv(2), i_left => rv(3), i_right => rv(4),
            o_solved => so, o_all_lock => so2, o_busy => so3,
            o_sel_idx => si, o_pos => po, o_lock => lo,
            o_scanrow => open, o_red => r8, o_grn => g8
        );
    sink <= tv xor (r8 & g8 & r8 & g8 & r8 & g8 & r8 & g8);
end architecture;
"""

d = ROOT / ".tmp" / "scratch" / "pc_only"
if d.exists():
    shutil.rmtree(d)
d.mkdir(parents=True)
(d / "scratch_top.vhd").write_text(TOP, encoding="ascii")
for f in ["puzzle_pkg.vhd", "puzzle_ctrl.vhd"]:
    shutil.copy(ROOT / "rtl" / f, d / f)

qsf = ['set_global_assignment -name FAMILY "MAX II"',
       'set_global_assignment -name DEVICE EPM1270T144C5',
       'set_global_assignment -name TOP_LEVEL_ENTITY scratch_top',
       'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
       'set_global_assignment -name VHDL_FILE puzzle_pkg.vhd',
       'set_global_assignment -name VHDL_FILE puzzle_ctrl.vhd',
       'set_global_assignment -name VHDL_FILE scratch_top.vhd']
(d / "scratch.qsf").write_text("\n".join(qsf) + "\n", encoding="ascii")
(d / "scratch.qpf").write_text(
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    '<!DOCTYPE project SYSTEM "..\\bin\\project.dtd">\n<project>\n'
    '<header><fileVersion version="1"/></header>\n'
    '<project><name>scratch</name><revision name="scratch"/></project>\n'
    '</project>\n', encoding="ascii")

r = subprocess.run([str(QUARTUS / "quartus_map.exe"), "scratch"],
                   cwd=d, capture_output=True, text=True, errors="replace")
print("exit", r.returncode)
for l in (r.stdout + r.stderr).splitlines():
    if "Error" in l:
        print("  ", l.strip())
rpt = d / "output_files" / "scratch.map.rpt"
if rpt.exists():
    for line in rpt.read_text(errors="replace").splitlines():
        if any(k in line for k in ("Total logic elements", "Total registers",
                                   "Total logic cells in carry")):
            print(line.strip())
