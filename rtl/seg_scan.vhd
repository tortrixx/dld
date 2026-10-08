-- ============================================================================
--  seg_scan  --  8-digit seven-segment display driver (dynamic scan + decode)
--  Subsystem : S6 (display)
--
--  Board wiring / polarity (from the manual, absolute truth):
--     8 digit segments are wired in PARALLEL and named AA,AB,AC,AD,AE,AF,AG,AP
--       -> PIN_62,59,58,57,55,53,52,51   (segment = HIGH to light)
--     the 8 cathodes are INDEPENDENT and named CAT0..CAT7
--       -> PIN_63,66,67,68,69,70,30,31   (common cathode = LOW to select)
--
--  So: a digit lights when its segment lines are HIGH AND its own CATn is LOW.
--  The decimal point AP (PIN_51) is deliberately NEVER driven -- this project
--  does not use it and the pin is shared with other peripherals on the board.
--
--  Segment bit order (from the board manual):
--      o_seg(0) = AA -> PIN_62      o_seg(4) = AE -> PIN_55
--      o_seg(1) = AB -> PIN_59      o_seg(5) = AF -> PIN_53
--      o_seg(2) = AC -> PIN_58      o_seg(6) = AG -> PIN_52
--      o_seg(3) = AD -> PIN_57      o_seg(7) = AP -> PIN_51  (decimal point)
--  and the decoder below drives exactly that order.
--
--  !! HISTORICAL BUG -- KEEP THIS COMMENT !!
--  The first version of this file used the opposite bit order: it put AA in
--  bit 7 and AP in bit 0.  Combined with the pin map that meant the logical
--  segment 'a' was physically wired to PIN_51, i.e. to the DECIMAL POINT.
--  Symptom on the bench: "2" was displayed with its top bar missing and the
--  decimal point lit instead.  The fault is invisible on a waveform (the RTL
--  was self-consistent) and only appears on real hardware, which is exactly why
--  the bit order is pinned down by an explicit table here.
--
--  CAT bit order :  cat(0)=CAT0 -> PIN_63 ... cat(7)=CAT7 -> PIN_31, LOW selects.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity seg_scan is
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                        -- active HIGH
        i_tick  : in  std_logic;                        -- 位选推进节拍：设计用 1 kHz
                                                        -- -> 每位 125 Hz 刷新（200 Hz 只有
                                                        -- 25 Hz/位，肉眼可见闪）
        i_en    : in  std_logic;                        -- '0' = all digits dark
        i_data  : in  std_logic_vector(31 downto 0);    -- 8 x 4-bit BCD, digit7..digit0
        i_blank : in  std_logic_vector(7 downto 0);     -- '1' = this digit is blanked
        -- Diagnostic mode ONLY (used by board_test_top).  When i_raw_en = '1' the
        -- BCD decoder is bypassed and i_raw is driven straight onto the segment
        -- lines.  This is the only way to light exactly ONE physical segment,
        -- which is what identifies the segment mapping empirically.
        i_raw_en : in  std_logic;
        i_raw    : in  std_logic_vector(7 downto 0);    -- bit0=AA ... bit6=AG, bit7=AP
        o_seg   : out std_logic_vector(7 downto 0);     -- AA..AP
        o_cat   : out std_logic_vector(7 downto 0)      -- CAT0..CAT7, active LOW
    );
end entity seg_scan;

architecture rtl of seg_scan is

    signal idx     : unsigned(2 downto 0) := (others => '0');
    signal seg_r   : std_logic_vector(7 downto 0) := (others => '0');
    signal cat_r   : std_logic_vector(7 downto 0) := (others => '1');

    -- BCD value of the digit currently selected
    signal nib     : std_logic_vector(3 downto 0);
    -- decoded segments in MANUAL order: bit0=AA, bit1=AB ... bit6=AG, bit7=AP
    signal decoded : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- 位选计数器：**1 kHz** 节拍 / 8 位 = **125 Hz/位**（舒适地高于临界闪烁融合）。
    -- ⚠️ 原注释写"200 Hz / 8 = 25 Hz，comfortably above flicker fusion"是**错的**：
    --    25 Hz 对 LED 明显可见闪（2026-10-08 用户实测反馈"数码管闪得比较明显"）。
    --    顶层因此把 i_tick 从 tick_200 改成 tick_1k；本模块本身与节拍无关，
    --    只是把"该给多少"的注释改正过来。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                idx <= (others => '0');
            elsif (i_tick = '1') then
                idx <= idx + 1;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Select the BCD nibble of the active digit.
    -- digit 7 occupies the top nibble, digit 0 the bottom one.
    ----------------------------------------------------------------------------
    with to_integer(idx) select
        nib <= i_data(31 downto 28) when 7,
               i_data(27 downto 24) when 6,
               i_data(23 downto 20) when 5,
               i_data(19 downto 16) when 4,
               i_data(15 downto 12) when 3,
               i_data(11 downto  8) when 2,
               i_data( 7 downto  4) when 1,
               i_data( 3 downto  0) when others;

    ----------------------------------------------------------------------------
    -- 7-segment decoder, common cathode, segment = HIGH to light.
    --
    -- Bit 7 of 'decoded' is AP and is ALWAYS '0' -- this design does not use the
    -- decimal point.
    --   bit0=AA(a) bit1=AB(b) bit2=AC(c) bit3=AD(d)
    --   bit4=AE(e) bit5=AF(f) bit6=AG(g) bit7=AP(dp=0)
    --
    -- Written as full 8-bit literals on purpose: the segment-to-pin order is the
    -- single most error-prone part of this project, so every segment of every
    -- digit is spelled out instead of being shifted into place.
    --
    -- 0x0..0x9 = 数字，0xF = 灭，**0xA..0xE = 结算画面的字母 A/P/S/F/L**
    -- （码值定义在 puzzle_pkg 的 DIG_*，见那里的说明：'S' 与 '5' 同形、'I' 用 '1'）。
    ----------------------------------------------------------------------------
    process (nib)
    begin
        case nib is
            --        AP g f e d c b a
            when "0000" => decoded <= "0" & "0111111";   -- 0: a b c d e f
            when "0001" => decoded <= "0" & "0000110";   -- 1: b c（也当字母 'I' 用）
            when "0010" => decoded <= "0" & "1011011";   -- 2: a b d e g
            when "0011" => decoded <= "0" & "1001111";   -- 3: a b c d g
            when "0100" => decoded <= "0" & "1100110";   -- 4: b c f g
            when "0101" => decoded <= "0" & "1101101";   -- 5: a c d f g（= 字母 'S'）
            when "0110" => decoded <= "0" & "1111101";   -- 6: a c d e f g
            when "0111" => decoded <= "0" & "0000111";   -- 7: a b c
            when "1000" => decoded <= "0" & "1111111";   -- 8: all
            when "1001" => decoded <= "0" & "1101111";   -- 9: a b c d f g
            when "1010" => decoded <= "0" & "1110111";   -- A: a b c e f g
            when "1011" => decoded <= "0" & "1110011";   -- P: a b e f g
            when "1100" => decoded <= "0" & "1101101";   -- S: a c d f g（同 '5'）
            when "1101" => decoded <= "0" & "1110001";   -- F: a e f g
            when "1110" => decoded <= "0" & "0111000";   -- L: d e f
            when others => decoded <= "00000000";        -- 1111 = 灭
        end case;
    end process;

    ----------------------------------------------------------------------------
    -- Output registers.
    --   o_seg : decoded segments, AP always '0'.
    --   o_cat : exactly one '0' at the active digit; ALL '1' when switched off.
    --   The blank mask forces the whole set of segments dark for that digit,
    --   which is how "DISP7~DISP4 all dark" type requirements are met without
    --   ever driving the shared cathode lines incorrectly.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                seg_r <= (others => '0');
                cat_r <= (others => '1');
            else
                -- segments
                if (i_en = '1') and (i_blank(to_integer(idx)) = '0') then
                    if (i_raw_en = '1') then
                        seg_r <= i_raw;              -- diagnostic: straight through
                    else
                        seg_r <= decoded;            -- AP is already '0' in decoded
                    end if;
                else
                    seg_r <= (others => '0');
                end if;

                -- cathodes : one-hot, active LOW
                case to_integer(idx) is
                    when 0 => cat_r <= "11111110";
                    when 1 => cat_r <= "11111101";
                    when 2 => cat_r <= "11111011";
                    when 3 => cat_r <= "11110111";
                    when 4 => cat_r <= "11101111";
                    when 5 => cat_r <= "11011111";
                    when 6 => cat_r <= "10111111";
                    when others => cat_r <= "01111111";
                end case;
            end if;
        end if;
    end process;

    o_seg <= seg_r;
    o_cat <= cat_r;

end architecture rtl;
