-- ============================================================================
--  dot_matrix_scan  ——  8x8 双色点阵驱动（行扫描）
--  所属子系统：S6（显示）
--
--  板级连线与极性（板级手册）：
--     行   ROW0..ROW7  -> PIN_8,7,6,5,4,3,2,1         低电平选通
--     红   COLR0..COLR7-> PIN_22,21,16,15,14,13,12,11 高电平点亮
--     绿   COLG0..COLG7-> PIN_45,44,43,42,41,40,39,38 高电平点亮
--
--  某一行被拉低时，该行上红列为高的点显示红色、绿列为高的点显示绿色；
--  红绿同时为高则显示黄色（两个 LED 同时亮），同时为低则熄灭。
--  因此三种颜色只需两个位平面：仅红 -> 红，仅绿 -> 绿，两者都有 -> 黄。
--  本模块是直通的 2 位平面驱动，不强制红绿互斥。
--
--  接口每次只接收一行（每种颜色 8 位）和该行的逻辑行号。
--  逻辑行 0 = 面板顶部 = ROW7，行号自上而下递增。
--  （板子的物理 ROW0 在最下面，因此逻辑行号与 ROW 编号相反；
--    该顺序由板级自检的"左上角红点"图案在实机上确认。）
--
--  注意：PIN_38..45 与 LD8..LD15、VGA 端口共用。驱动这些 LED 会让点阵
--  失去绿色，而 B6"选中零片变绿"正依赖绿色，因此本设计刻意不使用这些 LED。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity dot_matrix_scan is
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                       -- 高电平有效
        i_en    : in  std_logic;                       -- '0' = 点阵全灭
        i_row   : in  std_logic_vector(2 downto 0);    -- 哪一逻辑行（0 = 顶部）
        i_colr  : in  std_logic_vector(7 downto 0);    -- 该行的红色位
        i_colg  : in  std_logic_vector(7 downto 0);    -- 该行的绿色位
        o_row   : out std_logic_vector(7 downto 0);    -- ROW0..ROW7，低电平有效
        o_colr  : out std_logic_vector(7 downto 0);    -- COLR0..COLR7
        o_colg  : out std_logic_vector(7 downto 0)     -- COLG0..COLG7
    );
end entity dot_matrix_scan;

architecture rtl of dot_matrix_scan is

    signal row_sel : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- 行译码：独热、低电平有效。
    -- 逻辑行 0 = 顶部 -> ROW7（PIN_1）；逻辑行 7 = 底部 -> ROW0（PIN_8）。
    ----------------------------------------------------------------------------
    with i_row select
        row_sel <= "01111111" when "000",
                   "10111111" when "001",
                   "11011111" when "010",
                   "11101111" when "011",
                   "11110111" when "100",
                   "11111011" when "101",
                   "11111101" when "110",
                   "11111110" when others;

    ----------------------------------------------------------------------------
    -- 寄存器输出：行选通与两个颜色平面同拍更新，不会出现"这一行的数据
    -- 配上一行的选通"的鬼影。复位或禁用时整屏熄灭。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if ((i_rst = '1') or (i_en = '0')) then
                o_row  <= (others => '1');
                o_colr <= (others => '0');
                o_colg <= (others => '0');
            else
                o_row  <= row_sel;
                o_colr <= i_colr;
                o_colg <= i_colg;
            end if;
        end if;
    end process;

end architecture rtl;
