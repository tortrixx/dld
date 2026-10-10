# -*- coding: utf-8 -*-
"""为检查引擎的零基行号加一个流水寄存器。

上报的关键路径（41.5 MHz）：pos -> Mux4（sel/= 的守卫）-> LessThan
（行范围判定）-> Add17 -> chk_pos -> Add19 -> process_2 -> row_mask。
行号（rr - piece_row）原先是从寄存器输出组合算出来的，并立刻
送进 srl8。把它寄存起来就切断了这条路径，而算法不变，
因为检查本来就要跑很多个周期。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 当前正在求值的零基行号所用的寄存器
s = s.replace(
    "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');",
    "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');\n"
    "    signal chk_orow : std_logic_vector(3 downto 0) := (others => '0');")

# 在 CH_RUN 中，于状态起始处锁存行号，并在下一个周期使用
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

# 候选行改用已寄存的值，不再重算 srow
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
