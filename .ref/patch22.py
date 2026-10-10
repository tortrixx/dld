# -*- coding: utf-8 -*-
"""把 2 Hz 闪烁做成真正的方波。

clk_gen 的 tick_2hz 是**一个时钟宽**的脉冲（每 500 ms 只有 10 ms 为高）。
直接把它当作闪烁电平，会让显示在每个半周期里只亮一个时钟，
也就是肉眼根本看不到亮 —— 这正是自检那 2 秒里板上**什么都不显示**的原因，
尽管状态机一直在跑。每个 tick 翻转一次即可得到占空比 50 % 的 2 Hz 方波，
这正是要求 B1 所要求的。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")

s = s.replace('    signal sound_p : std_logic_vector(2 downto 0) := "000";',
              '    signal sound_p : std_logic_vector(2 downto 0) := "000";\n'
              '    -- 2 Hz SQUARE WAVE for the blinks.\n'
              '    -- The tick from clk_gen is a ONE-CLOCK pulse (10 ms wide), so using\n'
              '    -- it directly as a blink LEVEL leaves the display lit for a single\n'
              '    -- clock per 500 ms -- effectively invisible.  This toggle turns it into\n'
              '    -- a 50 % duty square wave, which is what B1 ("flashing at 2 Hz") means.\n'
              '    signal blink_r : std_logic := \'0\';')

# 翻转进程
s = s.replace("""    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sound_p <= "000";""",
              """    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                blink_r <= '0';
            elsif (i_tick_2hz = '1') then
                blink_r <= not blink_r;      -- 2 Hz square wave, 50 % duty
            end if;
        end if;
    end process;

    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sound_p <= "000";""")

s = s.replace("    o_blink    <= i_tick_2hz;", "    o_blink    <= blink_r;")

p.write_text(s, encoding="utf-8")
print("blink is now a square wave; o_blink assignments:", s.count("o_blink    <="))
