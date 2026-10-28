-- ============================================================================
--  seg_scan  ——  8 位数码管驱动（动态扫描 + 7 段译码）
--  所属子系统：S6（显示）
--
--  板级连线与极性（板级手册）：
--     段线 AA,AB,AC,AD,AE,AF,AG,AP
--       -> PIN_62,59,58,57,55,53,52,51   段 = 高电平点亮
--     位选 CAT0..CAT7
--       -> PIN_63,66,67,68,69,70,30,31   共阴 = 低电平选通
--
--  某位的段线为高、且该位 CATn 为低时，该位点亮。
--  小数点 AP 不使用（引脚与板上其它外设共用），译码结果中恒为 '0'。
--
--  段位序（与手册一致）：
--     bit0 = AA -> PIN_62      bit4 = AE -> PIN_55
--     bit1 = AB -> PIN_59      bit5 = AF -> PIN_53
--     bit2 = AC -> PIN_58      bit6 = AG -> PIN_52
--     bit3 = AD -> PIN_57      bit7 = AP -> PIN_51（小数点）
--
--  扫描节拍 i_tick = 1 kHz，8 位轮一遍为 8 ms，即每位 125 Hz。
--  位序：idx=0 -> CAT0，idx=7 -> CAT7。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity seg_scan is
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                        -- 高电平有效
        i_tick  : in  std_logic;                        -- 位选推进节拍（1 kHz）
        i_en    : in  std_logic;                        -- '0' = 所有位熄灭
        i_data  : in  std_logic_vector(31 downto 0);    -- 8 x 4 位 BCD，digit7..digit0
        i_blank : in  std_logic_vector(7 downto 0);     -- '1' = 该位被消隐
        -- 诊断模式：i_raw_en='1' 时旁路 BCD 译码，i_raw 直接驱动段线。
        -- 板级自检用它逐根点亮段线，确认物理段序。
        i_raw_en : in  std_logic;
        i_raw    : in  std_logic_vector(7 downto 0);    -- bit0=AA ... bit6=AG, bit7=AP
        o_seg   : out std_logic_vector(7 downto 0);     -- AA..AP
        o_cat   : out std_logic_vector(7 downto 0)      -- CAT0..CAT7，低电平有效
    );
end entity seg_scan;

architecture rtl of seg_scan is

    signal idx     : unsigned(2 downto 0) := (others => '0');
    signal seg_r   : std_logic_vector(7 downto 0) := (others => '0');
    signal cat_r   : std_logic_vector(7 downto 0) := (others => '1');

    -- 当前选中位的 BCD 值
    signal nib     : std_logic_vector(3 downto 0);
    -- 译码后的段，bit0=AA, bit1=AB ... bit6=AG, bit7=AP
    signal decoded : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- 位选计数器：1 kHz / 8 = 每位 125 Hz，高于闪烁融合频率。
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
    -- 选出当前活动位的 BCD 半字节：digit7 在最高半字节，digit0 在最低。
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
    -- 7 段译码器（共阴，段 = 高电平点亮）。
    --   bit0=AA(a) bit1=AB(b) bit2=AC(c) bit3=AD(d)
    --   bit4=AE(e) bit5=AF(f) bit6=AG(g) bit7=AP(dp，恒 0)
    --
    -- 每个码都写成完整的 8 位字面量，而不是靠移位拼出来：
    -- 段到引脚的顺序是硬件上最易错的一环，逐位写出便于核对。
    --
    -- 0x0..0x9 = 数字，0xF = 灭，0xA..0xE = 结算画面字母 A/P/S/F/L。
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
            when "1000" => decoded <= "0" & "1111111";   -- 8: 全部段
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
    -- 输出寄存器。
    --   o_seg：译码后的段；AP 恒为 '0'。
    --   o_cat：当前活动位恰好一个 '0'；关闭时全为 '1'。
    --   消隐掩码把该位的所有段一起拉黑，实现"DISPx 熄灭"而不影响其它位。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                seg_r <= (others => '0');
                cat_r <= (others => '1');
            else
                -- 段线
                if (i_en = '1') and (i_blank(to_integer(idx)) = '0') then
                    if (i_raw_en = '1') then
                        seg_r <= i_raw;              -- 诊断：直通
                    else
                        seg_r <= decoded;            -- decoded 中 AP 已经是 '0'
                    end if;
                else
                    seg_r <= (others => '0');
                end if;

                -- 阴极：独热，低电平有效
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
