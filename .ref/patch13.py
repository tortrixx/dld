# -*- coding: utf-8 -*-
"""删掉现在已重复的 scanrow 计数器（scanrow 由渲染器驱动）。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

old = """    ----------------------------------------------------------------------------
    -- Scan row counter: one row per 200 Hz tick, in step with the matrix driver
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                scanrow <= (others => '0');
            elsif (i_tick = '1') then
                scanrow <= scanrow + 1;
            end if;
        end if;
    end process;

"""
assert old in s, "old scanrow process not found"
s = s.replace(old, "")
p.write_text(s, encoding="utf-8")
print("removed duplicate scanrow driver; remaining scanrow <=", s.count("scanrow <="))
