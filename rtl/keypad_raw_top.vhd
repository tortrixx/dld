-- ============================================================================
--  keypad_raw_top  --  键盘电气测试（引脚已正确约束）
--
--  重要历史 —— 为什么此前每一个键盘结果都毫无意义
--  --------------------------------------------------------------------
--  这个诊断设计最早的几个版本被加进项目生成器的端口表时，
--  并没有带上它们的 kp_row / kp_col 端口。生成器只会为你列出的端口
--  生成引脚约束，于是键盘引脚就处于未约束状态；
--  随后 fitter 把它们放到了任意空闲引脚上
--  （49、102、130、88……）。设计能编译、能运行，只是驱动和读取了
--  **错误的引脚** —— 在实验台上，这与硬件坏掉无法区分。
--  这是通过把 fitter 的 .pin 报告与手册交叉核对发现的。
--  见 docs/05 ERR-002 与 scripts/check_keypad_pins.py。
--
--  它做什么
--  ------------
--  把全部四列都驱动为低，并显示四条行线的电平。
--  在所有列都为低时，按下任何一个键都会把它所在的行连到低电平线上，
--  所以无论这个键位于哪一行/哪一列，该行必然读为低。这是
--  最简单的、不会被行/列顺序骗过的测试。
--
--  显示
--      DISP7      = 子步计数器 0..3（证明固件正在运行）
--      DISP6      = '-'
--      DISP5      = 0
--      DISP4      = 0
--      DISP3..DISP0 = 四条行线：ROW1 ROW2 ROW3 ROW0
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity keypad_raw_top is
    port (
        clk      : in  std_logic;
        sw7      : in  std_logic;
        btn      : in  std_logic;
        kp_row   : in  std_logic_vector(3 downto 0);
        kp_col   : out std_logic_vector(3 downto 0);
        dot_row  : out std_logic_vector(7 downto 0);
        dot_colr : out std_logic_vector(7 downto 0);
        dot_colg : out std_logic_vector(7 downto 0);
        seg      : out std_logic_vector(7 downto 0);
        cat      : out std_logic_vector(7 downto 0);
        buzz     : out std_logic
    );
end entity keypad_raw_top;

architecture rtl of keypad_raw_top is

    signal div     : unsigned(17 downto 0) := (others => '0');
    signal t200    : std_logic := '0';
    signal div2    : unsigned(26 downto 0) := (others => '0');
    signal t_step  : std_logic := '0';
    signal step    : unsigned(1 downto 0) := (others => '0');

    -- 行线是实时显示的（不锁存）：显示每秒刷新 25 次，
    -- 所以按住的键完全可读，瞬态的按键也不会被漏掉
    signal disp    : std_logic_vector(31 downto 0);

begin

    process (clk)
    begin
        if rising_edge(clk) then
            if (div = 249_999) then
                div  <= (others => '0');
                t200 <= '1';
            else
                div  <= div + 1;
                t200 <= '0';
            end if;

            -- 50 MHz 下每步约 0.75 s，作为存活指示
            if (div2 = 33_554_431) then
                div2   <= (others => '0');
                t_step <= '1';
            else
                div2   <= div2 + 1;
                t_step <= '0';
            end if;
        end if;
    end process;

    process (clk)
    begin
        if rising_edge(clk) then
            if (sw7 = '0') then
                step <= (others => '0');
            elsif (t_step = '1') then
                step <= step + 1;               -- 自由运行计数器，会回绕
            end if;
        end if;
    end process;

    -- 所有列都驱动为低：决定性条件
    kp_col <= "0000";

    disp(31 downto 28) <= "00" & std_logic_vector(step);
    disp(27 downto 24) <= "1010";                 -- '-'
    disp(23 downto 20) <= "0000";
    disp(19 downto 16) <= "0000";
    disp(15 downto 12) <= "000" & kp_row(1);
    disp(11 downto 8)  <= "000" & kp_row(2);
    disp(7 downto 4)   <= "000" & kp_row(3);
    disp(3 downto 0)   <= "000" & kp_row(0);

    u_seg : entity work.seg_scan
        port map (
            i_clk    => clk,
            i_rst    => '0',
            i_tick   => t200,
            i_en     => sw7,
            i_data   => disp,
            i_blank  => (others => '0'),
            i_raw_en => '0',
            i_raw    => (others => '0'),
            o_seg    => seg,
            o_cat    => cat
        );

    u_dot : entity work.dot_matrix_scan
        port map (
            i_clk   => clk,
            i_rst   => '0',
            i_en    => '0',
            i_row   => "000",
            i_colr  => (others => '0'),
            i_colg  => (others => '0'),
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );

    buzz <= '0';

end architecture rtl;
