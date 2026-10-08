# -*- coding: utf-8 -*-
"""Make the 2 Hz blink a proper square wave.

clk_gen's tick_2hz is a ONE-CLOCK pulse (10 ms of every 500 ms).  Using it
directly as the blink level leaves the display lit for a single clock per half
period, i.e. visually never on -- which is why the board showed NOTHING during
the 2-second self-test even though the state machine was running.  Toggling on
each tick gives a 50 % duty 2 Hz square wave, as requirement B1 asks.
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

# toggle process
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
