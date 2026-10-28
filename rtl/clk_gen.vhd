-- ============================================================================
--  clk_gen  ——  时钟分频、tick 产生与系统复位
--  所属子系统：S1（时钟与时间基准）
--
--  功能：
--    · 对 BTN0（高电平有效）做 20 ms 消抖
--    · 产生上电复位（计数到 CNT_POR，实际约 9 ms）
--    · 产生一条级联分频链：只有第一级面对 50 MHz 板钟，其后各级
--      只数上一级的脉冲，逻辑开销小（EPM1270 只有 1270 个 LE）
--
--  输出的时间基准：
--    tick_1k   1 kHz  (1 ms)    点阵行扫描、数码管位选、引擎行渲染
--    tick_200  200 Hz (5 ms)    键盘扫描轮次
--    tick_100  100 Hz (10 ms)   当前未使用
--    tick_2hz  2 Hz   (500 ms)  仅供 board_test_top 的自检计数
--    tick_4hz  4 Hz   (250 ms)  翻转得到 2 Hz 方波（自检闪烁、结算闪示）；
--                               同时是蜂鸣器的换步节拍
--    tick_1hz  1 Hz   (1 s)     游戏倒计时与预览计时
--    tick_40   40 Hz  (25 ms)   仅供 board_test_top 逐行推进点阵
--
--  o_rst 为高电平有效。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity clk_gen is
    port (
        i_clk    : in  std_logic;                      -- 板级全局时钟（PIN_18）
        i_btn    : in  std_logic;                      -- 复位按键 BTN0，高电平有效
        o_rst    : out std_logic;                      -- 系统复位，高电平有效
        o_tick_1k  : out std_logic;                    -- 1 ms 脉冲
        o_tick_200 : out std_logic;                    -- 5 ms 脉冲
        o_tick_100 : out std_logic;                    -- 10 ms 脉冲（当前未使用）
        o_tick_2hz : out std_logic;                    -- 500 ms 脉冲（供板级自检计数）
        o_tick_4hz : out std_logic;                    -- 250 ms 脉冲（用于翻转出 2 Hz）
        o_tick_1hz : out std_logic;                    -- 1 s 脉冲
        o_tick_40  : out std_logic                     -- 25 ms 脉冲（供板级自检扫描）
    );
end entity clk_gen;

architecture rtl of clk_gen is

    -- 第 1 级：50 MHz -> 1 kHz，需数到 50000，故 16 位
    signal c1      : unsigned(15 downto 0) := (others => '0');
    signal t1      : std_logic := '0';
    -- 第 2 级：1 kHz -> 200 Hz，需数到 5，故 3 位
    signal c2      : unsigned(2 downto 0)  := (others => '0');
    signal t2      : std_logic := '0';
    -- 第 3 级：200 Hz -> 100 Hz（2 分频）
    signal c3      : std_logic := '0';
    signal t3      : std_logic := '0';
    -- 第 4/5/6 级：100 Hz -> 4 Hz -> 2 Hz -> 1 Hz
    -- 三个节拍共用一条 25 分频链，避免各数一遍造成重复触发器
    signal c25     : unsigned(4 downto 0)  := (others => '0');  -- 0..24 -> 4 Hz
    signal c4x     : unsigned(1 downto 0)  := (others => '0');  -- 第几个 4 Hz 脉冲
    signal t7      : std_logic := '0';                          -- 4 Hz
    signal t4      : std_logic := '0';                          -- 2 Hz（t7 二分频）
    signal t5      : std_logic := '0';                          -- 1 Hz（t7 四分频）
    -- 第 7 级：200 Hz -> 40 Hz（5 分频），供板级自检扫描使用
    signal c6      : unsigned(2 downto 0)  := (others => '0');
    signal t6      : std_logic := '0';

    -- 复位路径
    -- 按键消抖：饱和计数器，每 1 ms 采一个样。
    -- 宽度必须满足 T_BTN_MS <= 31，改常量时需同步加宽。
    signal bcnt    : unsigned(4 downto 0) := (others => '0');
    signal s_por   : std_logic := '1';
    signal s_btn   : std_logic := '0';

    -- 上电计数器：饱和计数、绝不回绕，因此不会产生幽灵复位。
    -- 宽度必须满足 T_POR_MS <= 16，否则 CNT_POR 会被截断、复位失效。
    signal por_cnt : unsigned(3 downto 0) := (others => '0');

begin

    ----------------------------------------------------------------------------
    -- 分频链。每一级都是同样的写法：数到 N-1、发出一个时钟宽的脉冲、回绕。
    -- 第 1 级的计数器必须足够宽：声明过窄会静默截断，整个时间基准就错了。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            -- 第 1 级
            if (c1 = CNT_1K) then
                c1 <= (others => '0'); t1 <= '1';
            else
                c1 <= c1 + 1;          t1 <= '0';
            end if;

            -- 第 2 级：数 tick_1k 脉冲
            if (t1 = '1') then
                if (c2 = CNT_200) then
                    c2 <= (others => '0'); t2 <= '1';
                else
                    c2 <= c2 + 1;          t2 <= '0';
                end if;
            else
                t2 <= '0';
            end if;

            -- 第 3 级：200 Hz -> 100 Hz（2 分频）
            if (t2 = '1') then
                c3 <= not c3;
                t3 <= c3;                  -- 在 c3 由 1 变 0 时发出
            else
                t3 <= '0';
            end if;

            -- 第 4/5/6 级：100 Hz -> 4 Hz（25 分频）-> 2 Hz -> 1 Hz
            if (t3 = '1') then
                if (c25 = CNT_4HZ) then
                    c25 <= (others => '0');
                    t7  <= '1';
                    c4x <= c4x + 1;
                    t4  <= not c4x(0);          -- 每隔一个 4 Hz 脉冲 -> 2 Hz
                    if (c4x = "11") then        -- 每四个 -> 1 Hz
                        t5 <= '1';
                    else
                        t5 <= '0';
                    end if;
                else
                    c25 <= c25 + 1;
                    t7  <= '0';
                    t4  <= '0';
                    t5  <= '0';
                end if;
            else
                t7 <= '0';
                t4 <= '0';
                t5 <= '0';
            end if;

            -- 第 7 级：200 Hz -> 40 Hz（5 分频），仅供板级自检逐行推进
            if (t2 = '1') then
                if (c6 = 4) then
                    c6 <= (others => '0'); t6 <= '1';
                else
                    c6 <= c6 + 1;          t6 <= '0';
                end if;
            else
                t6 <= '0';
            end if;
        end if;
    end process;

    o_tick_1k  <= t1;
    o_tick_200 <= t2;
    o_tick_100 <= t3;
    o_tick_2hz <= t4;
    o_tick_4hz <= t7;
    o_tick_1hz <= t5;
    o_tick_40  <= t6;

    ----------------------------------------------------------------------------
    -- 按键消抖。
    -- 板卡手册说明：按键空闲时为低、按下时为高，消抖电路由用户自行设计。
    -- bcnt 统计连续高电平的毫秒数，在 T_BTN_MS 处饱和；达到该值即认为
    -- "按下并稳定 20 ms"。任一低电平样本都会立刻清零，因此松开立即生效。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (t1 = '1') then                                  -- 1 ms 步进
                if (i_btn = '0') then
                    bcnt <= (others => '0');                    -- 任一个低电平样本即清零
                elsif (bcnt /= to_unsigned(T_BTN_MS, bcnt'length)) then
                    bcnt <= bcnt + 1;                           -- 饱和计数
                end if;
            end if;
        end if;
    end process;

    s_btn <= '1' when (bcnt = to_unsigned(T_BTN_MS, bcnt'length)) else '0';

    ----------------------------------------------------------------------------
    -- 上电复位：配置完成后把系统保持在复位状态约 T_POR_MS 毫秒。
    -- 饱和计数器计到最大值就停，绝不回绕，因此不会在之后再次置位。
    -- 由于从 0 起计，实际释放点约为 9 个 tick_1k 周期。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (t1 = '1') then
                if (por_cnt /= to_unsigned(CNT_POR, por_cnt'length)) then
                    por_cnt <= por_cnt + 1;
                end if;
            end if;
        end if;
    end process;

    s_por <= '1' when (por_cnt /= to_unsigned(CNT_POR, por_cnt'length)) else '0';

    o_rst <= s_por or s_btn;

end architecture rtl;
