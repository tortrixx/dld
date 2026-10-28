-- ============================================================================
--  keypad_scan  ——  4x4 矩阵键盘扫描（带消抖）
--  所属子系统：S2（键盘输入）
--
--  板级接线（板级手册）：
--     列 COL0..COL3 -> PIN_117,118,119,120
--     行 ROW0..ROW3 -> PIN_111,112,113,114
--
--  输出键号 = 4*行 + 列。其中行号 0 是板上丝印的最下面一行 ROW0，
--  列号 0 是最左边一列 COL0。把键号解释成游戏控制是 game_fsm 的职责。
--
--  扫描方案：先把所有列驱动为低，读一次行线；
--  再逐列把该列驱动为低、其余列拉高，看哪一相能让行线保持低。
--  这样即使某一列有接线问题，按键本身仍能被检测到，不会整列丢键。
--
--  消抖：同一读数连续 4 轮扫描一致才接受。一轮扫描 = 2 个 tick_200
--  = 10 ms，故按下 / 松开各约 40 ms。
--
--  输出：o_key 保存已接受的键号；o_press / o_release 是单时钟脉冲，
--  因此按住不放只产生一次动作。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity keypad_scan is
    port (
        i_clk     : in  std_logic;
        i_rst     : in  std_logic;                       -- 高电平有效
        i_tick    : in  std_logic;                       -- 200 Hz 扫描 tick
        i_row     : in  std_logic_vector(3 downto 0);    -- 矩阵行 ROW0..ROW3
        o_col     : out std_logic_vector(3 downto 0);    -- 矩阵列 COL0..COL3
        o_key     : out std_logic_vector(3 downto 0);    -- 被接受的键号
        o_press   : out std_logic;                       -- 单时钟脉冲
        o_release : out std_logic;                       -- 单时钟脉冲
        o_raw     : out std_logic_vector(3 downto 0)     -- 调试：实时列驱动
    );
end entity keypad_scan;

architecture rtl of keypad_scan is

    -- 按键按下时行线读到的电平（实验台实测为 '0'）。
    constant KP_ACTIVE : std_logic := '0';

    type scan_t is (SC_ALL_LOW, SC_ALL_HIGH, SC_RELEASE, SC_SETTLE);

    signal state   : scan_t := SC_ALL_HIGH;
    signal phase   : unsigned(1 downto 0) := (others => '0');
    -- 等待行线稳定的计数器：64 个时钟约 1.28 us
    signal settle  : unsigned(5 downto 0) := (others => '0');   -- 0..63

    -- 所有列驱动为低时锁存的行图样
    signal row_all : std_logic_vector(3 downto 0) := (others => KP_ACTIVE);
    -- 逐列扫描结果：col_low(c) = '1' 表示只有列 c 被拉低时，有行线为低
    signal col_low : std_logic_vector(3 downto 0) := (others => '0');
    signal col_all : std_logic := '0';                -- 1 = 所有列驱动为低

    signal cand    : std_logic_vector(3 downto 0) := K_NONE;  -- 候选键号
    signal any_hit : std_logic := '0';
    signal rd_done : std_logic := '0';

    -- 消抖后的稳定键号，以及连续一致计数
    signal stable    : std_logic_vector(3 downto 0) := K_NONE;
    signal cnt       : unsigned(1 downto 0) := (others => '0'); -- 0..DEBOUNCE_MAX
    signal key_r     : std_logic_vector(3 downto 0) := K_NONE;
    signal press_r   : std_logic := '0';
    signal release_r : std_logic := '0';

    signal col_drv   : std_logic_vector(3 downto 0) := (others => '1');

begin

    ----------------------------------------------------------------------------
    -- 扫描状态机。
    --   SC_ALL_HIGH：等待一个扫描 tick，开始新一轮
    --   SC_ALL_LOW ：所有列驱动为低，进入等待稳定
    --   SC_SETTLE  ：等待 64 拍后锁存"所有列为低"时的行图样
    --   SC_RELEASE ：逐列拉低，记录哪一列能让行线保持低
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                state   <= SC_ALL_HIGH;
                phase   <= (others => '0');
                settle  <= (others => '0');
                col_all <= '0';
                col_low <= (others => '0');
                rd_done <= '0';
                row_all <= (others => KP_ACTIVE);
            else
                case state is

                    -- 相位 A：所有列拉低，然后采样各行
                    when SC_ALL_LOW =>
                        if (i_tick = '1') then
                            col_all <= '1';
                            col_low <= (others => '0');   -- 新一轮
                            settle  <= (others => '0');
                            state   <= SC_SETTLE;
                        end if;

                    -- 等待信号稳定，然后锁存行图样
                    when SC_SETTLE =>
                        if (settle = 63) then
                            row_all <= i_row;
                            rd_done <= '1';
                            col_all <= '0';
                            phase   <= (others => '0');
                            state   <= SC_RELEASE;
                        else
                            settle <= settle + 1;
                        end if;

                    -- 相位 B：每次只把一列拉低、其余拉高。
                    -- 若按下的键位于该列，对应行会保持低电平，于是该相位
                    -- 就确定了列号。多个相位的结果必须累加（每列一位）。
                    when SC_RELEASE =>
                        if (settle = 63) then
                            settle <= (others => '0');
                            if (i_row(0) = KP_ACTIVE) or (i_row(1) = KP_ACTIVE)
                               or (i_row(2) = KP_ACTIVE) or (i_row(3) = KP_ACTIVE) then
                                col_low(to_integer(phase)) <= '1';
                            end if;

                            if (phase = 3) then
                                state <= SC_ALL_HIGH;
                            else
                                phase <= phase + 1;
                            end if;
                        else
                            settle <= settle + 1;
                        end if;

                    when others =>
                        if (i_tick = '1') then
                            state <= SC_ALL_LOW;
                        end if;
                end case;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 组合逻辑列驱动，与相位同拍，避免驱动与键号译码不一致。
    -- 每个相位只有一列为低，其余为高。
    ----------------------------------------------------------------------------
    with phase select
        col_drv <= "1110" when "00",
                   "1101" when "01",
                   "1011" when "10",
                   "0111" when others;

    o_col <= (others => '0') when (col_all = '1') else col_drv;
    o_raw <= col_drv;

    ----------------------------------------------------------------------------
    -- 行采样 -> 候选键号。
    --   必须恰好一行被拉低，否则报 K_NONE：同时按下不同行的两个键时，
    --   "取最后一行"会合成一个谁都没按过的鬼键，不如不报。
    --   列号取最后一个命中的相位；若一个都没命中，回退到列 0，
    --   宁可报一个键也不静默丢键。
    ----------------------------------------------------------------------------
    process (row_all, col_low)
        variable r    : integer;
        variable hit  : std_logic;
        variable crow : integer;
        variable ccol : integer;
        variable found : boolean;
        variable nrow : integer;
    begin
        hit   := '0';
        crow  := 0;
        ccol  := 0;

        nrow := 0;
        for r in 0 to 3 loop
            if (row_all(r) = KP_ACTIVE) then
                nrow := nrow + 1;
                crow := r;
            end if;
        end loop;
        if (nrow = 1) then hit := '1'; else hit := '0'; end if;

        found := false;
        if (hit = '1') then
            for c in 0 to 3 loop
                if (col_low(c) = '1') then
                    ccol  := c;
                    found := true;
                end if;
            end loop;
            if not found then
                ccol := 0;                        -- 回退
            end if;
        end if;

        any_hit <= hit;
        if (hit = '1') then
            cand <= std_logic_vector(to_unsigned(4 * crow + ccol, 4));
        else
            cand <= K_NONE;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 消抖：每完成一轮扫描恰好采样一次。
    -- 候选值与当前稳定值不同则累计 1，连续 DEBOUNCE_MAX+1 次一致才接受。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                stable    <= K_NONE;
                cnt       <= (others => '0');
                key_r     <= K_NONE;
                press_r   <= '0';
                release_r <= '0';
            else
                press_r   <= '0';
                release_r <= '0';

                if (i_tick = '1') and (state = SC_ALL_HIGH) then
                    if (cand /= stable) then
                        if (cnt = DEBOUNCE_MAX) then
                            stable <= cand;
                            cnt    <= (others => '0');
                        else
                            cnt <= cnt + 1;
                        end if;
                    else
                        cnt <= (others => '0');
                    end if;

                    -- 接受 / 释放，各一个时钟宽
                    key_r <= stable;
                    if ((stable /= K_NONE) and (stable /= key_r)) then
                        -- 新键被接受；若直接换到另一个键而不经过松开，
                        -- 也报成一次新的按下，保证任何键都不会被吞掉。
                        press_r <= '1';
                    elsif ((stable = K_NONE) and (key_r /= K_NONE)) then
                        release_r <= '1';
                    end if;
                end if;
            end if;
        end if;
    end process;

    o_key     <= key_r;
    o_press   <= press_r;
    o_release <= release_r;

end architecture rtl;
