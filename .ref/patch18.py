# -*- coding: utf-8 -*-
"""Add a pipeline register for the check engine's zero-based row index.

Reported critical path (41.5 MHz): pos -> Mux4 (the sel/= guards) -> LessThan
(row range test) -> Add17 -> chk_pos -> Add19 -> process_2 -> row_mask.
The row index (rr - piece_row) was computed combinationally from the register
outputs and immediately fed into srl8.  Registering it splits the path without
changing the algorithm, because the check already runs over many cycles.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# register for the currently evaluated zero-based row
s = s.replace(
    "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');",
    "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');\n"
    "    signal chk_orow : std_logic_vector(3 downto 0) := (others => '0');")

# in CH_RUN, latch the row index at the start of the state and use it next cycle
old = """                    when CH_RUN =>
                        chk_row <= chk_row + 1;
                        if (chk_row = 8) then
                            chk <= CH_DONE;
                        else"""
new = """                    when CH_RUN =>
                        chk_row <= chk_row + 1;
                        -- Pipeline: the zero-based row for the candidate is
                        -- registered here and consumed by the comparison below on
                        -- the FOLLOWING cycle.  Computing it combinationally and
                        -- feeding it straight into srl8 put a 26 ns path through
                        -- the row subtract, the range test and the shift.
                        chk_orow <= std_logic_vector(
                                        resize(chk_row - unsigned(chk_pos(7 downto 4)), 4));
                        if (chk_row = 8) then
                            chk <= CH_DONE;
                        else"""
assert old in s
s = s.replace(old, new)

# use the registered value instead of recomputing srow for the candidate
old2 = """                            -- candidate's mask for this panel row
                            srow := to_integer(chk_row) -
                                    to_integer(unsigned(chk_pos(7 downto 4)));
                            rw   := row_mask(chk_shp, srow,
                                             to_integer(unsigned(chk_pos(3 downto 0))));"""
new2 = """                            -- candidate's mask for this panel row (index pipelined)
                            rw := row_mask(chk_shp, to_integer(chk_orow),
                                           to_integer(unsigned(chk_pos(3 downto 0))));"""
assert old2 in s
s = s.replace(old2, new2)

p.write_text(s, encoding="utf-8")
print("check engine pipelined")
