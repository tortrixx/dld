# -*- coding: utf-8 -*-
"""修正 keypad_raw_top：seg_scan 需要一个真正的扫描 tick（把 i_tick 接成 '1' 会让
数码管位计数器以 50 MHz 飞快计数）。增加一个 200 Hz tick，并使用行锁存。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "keypad_raw_top.vhd"
s = p.read_text(encoding="utf-8")

s = s.replace("    signal seg_raw : std_logic_vector(7 downto 0);\n",
              "    signal seg_raw : std_logic_vector(7 downto 0);\n"
              "    -- 200 Hz tick for the seven-segment scan (50 MHz / 250000)\n"
              "    signal div     : unsigned(17 downto 0) := (others => '0');\n"
              "    signal t200    : std_logic := '0';\n")

s = s.replace("""    process (clk)
    begin
        if rising_edge(clk) then
            if (sw7 = '0') then
                slow <= (others => '0');
                ph   <= (others => '0');
            elsif (slow = 16_777_215) then
                slow <= (others => '0');
                ph   <= ph + 1;
            else
                slow <= slow + 1;
            end if;
        end if;
    end process;""",
              """    process (clk)
    begin
        if rising_edge(clk) then
            -- 200 Hz tick (divide by 250 000) for the display scan
            if (div = 249_999) then
                div  <= (others => '0');
                t200 <= '1';
            else
                div  <= div + 1;
                t200 <= '0';
            end if;

            -- ~3 column changes per second so the phase is readable by eye
            if (sw7 = '0') then
                slow <= (others => '0');
                ph   <= (others => '0');
            elsif (slow = 16_777_215) then
                slow <= (others => '0');
                ph   <= ph + 1;
            else
                slow <= slow + 1;
            end if;
        end if;
    end process;""")

s = s.replace("            i_tick   => '1',", "            i_tick   => t200,")

p.write_text(s, encoding="utf-8")
print("keypad_raw_top fixed")
