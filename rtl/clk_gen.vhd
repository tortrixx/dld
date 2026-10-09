-- ============================================================================
--  clk_gen  --  clock divider chain, system reset and tick generation
--  Subsystem : S1 (clock and time base)
--
--  Responsibilities
--    * filter the raw reset push-button (BTN0, active HIGH on this board)
--    * produce the power-on reset
--    * produce a CASCADED divider chain.  Only the very first stage ever sees
--      the 50 MHz board clock; every following stage counts pulses produced by
--      the previous one.  This keeps the whole design cheap in logic cells,
--      which matters because the EPM1270 has only 1270 LEs.
--
--  Time base produced
--    tick_1k   : 1   kHz  (1 ms)      -> 秒计数/复位；**点阵行推进与数码管位选**
--    tick_200  : 200 Hz  (5 ms)       -> keypad scan round + 引擎行渲染（内容 25 Hz）
--    tick_100  : 100 Hz  (10 ms)      -> generic 10 ms grid
--    tick_2hz  : 2   Hz (500 ms)      -> 音效节奏（**不再当"闪烁"用**，见 tick_4hz）
--    tick_4hz  : 4   Hz (250 ms)      -> 翻转它得到 **2 Hz 方波**（B1 自检闪烁、结算闪示）
--    tick_1hz  : 1   Hz (1 s)         -> one-second game counter
--    tick_40   : 40  Hz (25 ms)       -> **仅 board_test_top 自检用**（点阵逐行轮播）
--
--  ⚠️ 2026-10-09 第 11 工作阶段（全项目审计发现）：
--    · tick_1k 的用途表原来只写 "game seconds, reset timing"，漏了它在 puzzle_top 里
--      真正驱动的两条线（点阵行计数器 mrow、seg_scan 位选）—— 这正是 ERR-031 那类
--      "注释少写一句 → 后人把时序算错"的温床，已补全；
--    · tick_2hz 原来被写成 "self-test flash, blink flag"，但"每个 2 Hz 脉冲翻转一次"
--      得到的是 **1 Hz** 方波（B1 要 2 Hz）→ 新增 tick_4hz 专供翻转，语义写清楚；
--    · tick_40 原来写 "这一路已不再使用"，**是错的**：board_test_top 的 9 阶段自检
--      用它逐行推进点阵（`elsif (t_40 = '1') then row_idx <= row_idx + 1`）。
--      tick_100 才是真的悬空（全工程只声明、无读者）。
--
--  Reset polarity : o_rst is ACTIVE HIGH.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity clk_gen is
    port (
        i_clk    : in  std_logic;                      -- board global clock (PIN_18)
        i_btn    : in  std_logic;                      -- reset key BTN0, active HIGH
        o_rst    : out std_logic;                      -- system reset, active HIGH
        o_tick_1k  : out std_logic;                    -- 1 ms pulse
        o_tick_200 : out std_logic;                    -- 5 ms pulse
        o_tick_100 : out std_logic;                    -- 10 ms pulse（当前无人使用）
        o_tick_2hz : out std_logic;                    -- 500 ms pulse（音效节奏）
        o_tick_4hz : out std_logic;                    -- 250 ms pulse（翻转 → 2 Hz 方波）
        o_tick_1hz : out std_logic;                    -- 1 s pulse
        -- 200 Hz / 5 = 40 Hz。
        -- ⚠️ 这一路**仍在使用**：board_test_top 的 9 阶段硬件自检靠它逐行推进点阵
        --    （见 board_test_top.vhd 的 `elsif (t_40 = '1')`）。游戏的显示扫描走
        --    tick_1k（125 Hz，ERR-027），与此无关。**不要按误解删这个端口**。
        o_tick_40  : out std_logic
    );
end entity clk_gen;

architecture rtl of clk_gen is

    -- stage 1 : 50 MHz -> 1 kHz
    signal c1      : unsigned(15 downto 0) := (others => '0');  -- needs 50000 -> 16 bit
    signal t1      : std_logic := '0';
    -- stage 2 : 1 kHz -> 200 Hz
    signal c2      : unsigned(2 downto 0)  := (others => '0');  -- 5 -> needs 3 bit
    signal t2      : std_logic := '0';
    -- stage 3 : 200 Hz -> 100 Hz
    signal c3      : std_logic := '0';
    signal t3      : std_logic := '0';
    -- stage 4 : 100 Hz -> 2 Hz
    signal c4      : unsigned(5 downto 0)  := (others => '0');  -- 50 -> needs 6 bit
    signal t4      : std_logic := '0';
    -- stage 5 : 100 Hz -> 1 Hz
    signal c5      : unsigned(6 downto 0)  := (others => '0');  -- 100 -> needs 7 bit
    signal t5      : std_logic := '0';
    -- stage 6 : 100 Hz -> 4 Hz  (divide by 25)  -> 2 Hz 方波的翻转节拍（ERR-038）
    signal c7      : unsigned(4 downto 0)  := (others => '0');  -- 25 -> needs 5 bit
    signal t7      : std_logic := '0';
    -- stage 7 : 200 Hz -> 40 Hz  (divide by 5), for the board self-test scan
    signal c6      : unsigned(2 downto 0)  := (others => '0');
    signal t6      : std_logic := '0';

    -- reset path
    signal d_press : std_logic_vector(CNT_BTN downto 0) := (others => '1');
    signal s_por   : std_logic := '1';
    signal s_btn   : std_logic := '0';

    -- Power-on counter: saturating, never wraps -> cannot produce a phantom
    -- reset later on.  Counts 0..T_POR_MS-1.
    -- ⚠️ 审计（2026-10-09 第 11 工作阶段）：4 位只在 **T_POR_MS ≤ 16** 时够用 ——
    --    比较用的是 `to_unsigned(CNT_POR, por_cnt'length)`，一旦 T_POR_MS ≥ 17，
    --    CNT_POR 会被**截断成 0**、比较恒假、上电复位直接失效（而且不报错）。
    --    改 T_POR_MS 时请同时加宽 por_cnt（或改用 8 位）。
    signal por_cnt : unsigned(3 downto 0) := (others => '0');

begin

    ----------------------------------------------------------------------------
    -- Divider chain.  Every stage uses the same two-statement idiom:
    --   count to N-1, emit a one-clock-wide pulse, wrap.
    -- Note: stage 1 counts CLK_HZ/1000 = 50000 pulses, so the counter needs
    -- 16 bits -- declaring it too narrow silently truncates and the whole time
    -- base becomes wrong.  Keep the widths in sync with puzzle_pkg.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            -- stage 1
            if (c1 = CNT_1K) then
                c1 <= (others => '0'); t1 <= '1';
            else
                c1 <= c1 + 1;          t1 <= '0';
            end if;

            -- stage 2 : counts tick_1k pulses
            if (t1 = '1') then
                if (c2 = CNT_200) then
                    c2 <= (others => '0'); t2 <= '1';
                else
                    c2 <= c2 + 1;          t2 <= '0';
                end if;
            else
                t2 <= '0';
            end if;

            -- stage 3 : 200 Hz -> 100 Hz (divide by 2)
            if (t2 = '1') then
                c3 <= not c3;
                t3 <= c3;                  -- emit when c3 toggles 1 -> 0
            else
                t3 <= '0';
            end if;

            -- stage 4 : 100 Hz -> 2 Hz
            if (t3 = '1') then
                if (c4 = CNT_2HZ) then
                    c4 <= (others => '0'); t4 <= '1';
                else
                    c4 <= c4 + 1;          t4 <= '0';
                end if;
            else
                t4 <= '0';
            end if;

            -- stage 5 : 100 Hz -> 1 Hz
            if (t3 = '1') then
                if (c5 = CNT_1HZ) then
                    c5 <= (others => '0'); t5 <= '1';
                else
                    c5 <= c5 + 1;          t5 <= '0';
                end if;
            else
                t5 <= '0';
            end if;

            -- stage 6 : 100 Hz -> 4 Hz (divide by 25) = 250 ms.  ERR-038：game_fsm
            -- 在它上面翻转 → **2 Hz 方波**（B1 要求的"2 Hz 闪烁"）。tick_2hz 那一路
            -- 直接当闪烁用只能得到 1 Hz，全项目审计时才发现。
            if (t3 = '1') then
                if (c7 = CNT_4HZ) then
                    c7 <= (others => '0'); t7 <= '1';
                else
                    c7 <= c7 + 1;          t7 <= '0';
                end if;
            else
                t7 <= '0';
            end if;

            -- stage 7 : 200 Hz -> 40 Hz (divide by 5).  **只有 board_test_top
            -- 的硬件自检用**：它每 40 Hz 脉冲推进一行，8 行轮一遍 = 200 ms。
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
    -- Push-button filter.
    -- The board states: "keys output LOW when idle and HIGH while pressed, and
    -- a debounce circuit must be designed by the user".  So a press is a HIGH.
    -- A shift register of 20 bits, all HIGH, means "pressed and stable for
    -- 20 ms".  Because the register starts all-HIGH at power-up, no reset is
    -- needed for it and no phantom press can be generated (the shift register
    -- only fills with '1' if the key really is held down).
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (t1 = '1') then                                  -- 1 ms steps
                d_press <= d_press(d_press'high - 1 downto 0) & i_btn;
            end if;
        end if;
    end process;

    s_btn <= '1' when (d_press = (d_press'range => '1')) else '0';

    ----------------------------------------------------------------------------
    -- Power-on reset : hold the system in reset for T_POR_MS milliseconds
    -- after configuration.  Implemented as a saturating counter (it stops at
    -- its maximum) so it can never wrap around and re-assert later.
    --
    -- ⚠️ MEASURED (tb_clk_gen, 2026-10-08): s_por actually releases when por_cnt
    --    reaches CNT_POR = T_POR_MS-1, i.e. after **9** tick_1k periods (~9 ms),
    --    not 10 -- an off-by-one between the constant name and the count.
    --    It is functionally harmless (a POR of 9 ms vs 10 ms changes nothing for
    --    a design whose real time base is milliseconds), so the RTL is left as
    --    measured on the board; only this comment was corrected.  If you ever
    --    need exactly T_POR_MS, compare against T_POR_MS instead of CNT_POR.
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
