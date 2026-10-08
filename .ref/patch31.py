# -*- coding: utf-8 -*-
"""Fix the display tearing/flicker: the engine advanced its row on tick_200 while
the matrix driver scanned rows on t_40, so the row being *displayed* and the row
being *rendered* were unrelated except once every 200 ms.  That mismatch reads as
flicker/tearing.

Both counters now advance on the same tick_200 pulse:
  * the engine builds row r and publishes it into the frame register in that same
    tick, and
  * the matrix lights row r of the (stable) frame in that same tick.
The panel therefore shows row r of frame n while the engine rebuilds row r of
frame n+1 -- no tearing, and the refresh is 25 Hz.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_top.vhd")
s = p.read_text(encoding="utf-8")

# matrix row counter follows the same tick as the renderer
s = s.replace("            elsif (t_40 = '1') then\n                mrow <= mrow + 1;",
              "            elsif (t_200 = '1') then\n                mrow <= mrow + 1;")

s = s.replace("""    -- Matrix row counter.  The engine publishes a whole frame every 8 ticks of
    -- tick_200 (25 Hz); the driver lights one row at a time on the 40 Hz tick,
    -- so one full pass over the frame takes 8 x 25 ms = 0.2 s.  Frame rate and
    -- scan rate are tied only through the frame contents, which is stable.""",
              """    -- Matrix row counter.  It advances on the SAME tick as the engine's frame
    -- renderer: the driver lights row r of the frame that is currently stable
    -- while the engine rebuilds row r for the next frame.  Driving the two from
    -- different ticks (40 Hz scan vs 200 Hz render) made displayed row and
    -- rendered row unrelated, which looked like flicker.""")

# driver scans on tick_200
s = s.replace("            i_clk   => clk,\n            i_rst   => rst,\n            i_en    => sw7,\n            i_row   => std_logic_vector(mrow),",
              "            i_clk   => clk,\n            i_rst   => rst,\n            i_en    => sw7,\n            i_row   => std_logic_vector(mrow),")

p.write_text(s, encoding="utf-8")
print("sync fixed")
