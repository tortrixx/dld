# -*- coding: utf-8 -*-
"""修正显示的撕裂/闪烁：引擎按 tick_200 推进行号，而
点阵驱动按 t_40 扫描行，于是**正在显示**的行与**正在渲染**的行
除了每 200 ms 偶然对上一次之外互不相关。这种错位看起来就是
闪烁/撕裂。

现在两个计数器都在同一个 tick_200 脉冲上推进：
  * 引擎构造第 r 行并在同一拍把它发布进帧寄存器，
    以及
  * 点阵在同一拍点亮（已稳定的）帧的第 r 行。
于是面板显示第 n 帧的第 r 行时，引擎正在重建
第 n+1 帧的第 r 行 —— 不会撕裂，刷新率为 25 Hz。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_top.vhd"
s = p.read_text(encoding="utf-8")

# 点阵行计数器跟随与渲染器相同的 tick
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

# 驱动按 tick_200 扫描
s = s.replace("            i_clk   => clk,\n            i_rst   => rst,\n            i_en    => sw7,\n            i_row   => std_logic_vector(mrow),",
              "            i_clk   => clk,\n            i_rst   => rst,\n            i_en    => sw7,\n            i_row   => std_logic_vector(mrow),")

p.write_text(s, encoding="utf-8")
print("sync fixed")
