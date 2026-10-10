-- ============================================================================
--  seg_scan  ——  8 位数码管驱动（动态扫描 + 译码）
--  子系统：S6（显示）
--
--  板级连线 / 极性（来自手册，绝对真值）：
--     8 个位的段线并联在一起，命名为 AA,AB,AC,AD,AE,AF,AG,AP
--       -> PIN_62,59,58,57,55,53,52,51   （段 = 高电平点亮）
--     8 个共阴极相互独立，命名为 CAT0..CAT7
--       -> PIN_63,66,67,68,69,70,30,31   （共阴极 = 低电平选通）
--
--  因此：某位的段线为高电平、且它自己的 CATn 为低电平时，该位才点亮。
--  小数点 AP（PIN_51）刻意从不驱动 —— 本项目
--  不使用它，且该引脚在板上与其它外设共用。
--
--  段的位序（来自板级手册）：
--      o_seg(0) = AA -> PIN_62      o_seg(4) = AE -> PIN_55
--      o_seg(1) = AB -> PIN_59      o_seg(5) = AF -> PIN_53
--      o_seg(2) = AC -> PIN_58      o_seg(6) = AG -> PIN_52
--      o_seg(3) = AD -> PIN_57      o_seg(7) = AP -> PIN_51  （小数点）
--  下面的译码器正是按这个顺序驱动的。
--
--  !! 历史缺陷 —— 本注释必须保留 !!
--  本文件的第一版用了相反的位序：把 AA 放在
--  第 7 位、把 AP 放在第 0 位。结合引脚映射，这就意味着逻辑上的
--  段 'a' 在物理上接到了 PIN_51，也就是接到了小数点上。
--  实测现象："2" 显示时顶横缺一截，而
--  点亮的却是小数点。该缺陷在波形上看不出来（RTL
--  本身是自洽的），只在真实硬件上才暴露，这正是
--  这里要用一张显式表格把位序钉死的原因。
--
--  CAT 位序：cat(0)=CAT0 -> PIN_63 ... cat(7)=CAT7 -> PIN_31，低电平选通。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity seg_scan is
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                        -- 高电平有效
        i_tick  : in  std_logic;                        -- 位选推进节拍：设计用 1 kHz
                                                        -- -> 每位 125 Hz 刷新（200 Hz 只有
                                                        -- 25 Hz/位，肉眼可见闪）
        i_en    : in  std_logic;                        -- '0' = 所有位熄灭
        i_data  : in  std_logic_vector(31 downto 0);    -- 8 x 4 位 BCD，digit7..digit0
        i_blank : in  std_logic_vector(7 downto 0);     -- '1' = 该位被消隐
        -- 仅诊断模式使用（由 board_test_top 调用）。当 i_raw_en = '1' 时，
        -- BCD 译码器被旁路，i_raw 直接驱动到段线上。
        -- 这是唯一能只点亮一个物理段的方法，
        -- 也正是靠它实测确定段映射关系。
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
    -- 译码后的段，按手册顺序排列：bit0=AA, bit1=AB ... bit6=AG, bit7=AP
    signal decoded : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- 位选计数器：**1 kHz** 节拍 / 8 位 = **125 Hz/位**（舒适地高于临界闪烁融合）。
    -- ⚠️ 原注释写"200 Hz / 8 = 25 Hz，舒适地高于闪烁融合频率"是**错的**：
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
    -- 选出当前活动位的 BCD 半字节。
    -- digit 7 占最高半字节，digit 0 占最低半字节。
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
    -- 7 段译码器，共阴极，段 = 高电平点亮。
    --
    -- 'decoded' 的第 7 位是 AP，恒为 '0' —— 本设计不使用
    -- 小数点。
    --   bit0=AA(a) bit1=AB(b) bit2=AC(c) bit3=AD(d)
    --   bit4=AE(e) bit5=AF(f) bit6=AG(g) bit7=AP(dp=0)
    --
    -- 刻意写成完整的 8 位字面量：段到引脚的顺序是
    -- 本项目最容易出错的一环，所以每个位的每一段都
    -- 直接写出，而不是靠移位挪到位。
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
    --   o_seg : 译码后的段，AP 恒为 '0'。
    --   o_cat : 当前活动位恰好一个 '0'；关闭时全为 '1'。
    --   消隐掩码把该位的所有段一起拉黑，
    --   这样就能满足"DISP7~DISP4 全灭"这类要求，
    --   同时绝不会把共用的阴极线驱动错。
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
