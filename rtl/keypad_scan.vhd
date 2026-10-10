-- ============================================================================
--  keypad_scan  --  4x4 矩阵键盘扫描（带消抖）
--  子系统：S2（键盘输入）
--
--  板上接线（板级手册，绝对真值）
--     列 COL0..COL3 -> PIN_117,118,119,120
--     行 ROW0..ROW3 -> PIN_111,112,113,114
--
--  报出的键码
--     o_key = 4*行 + 列，即按阅读顺序的朴素键号
--     ⚠️ 修正（2026-10-09 审计）：这里的 "row 0" 是**板上丝印的最下一行 ROW0**
--     （PIN_111），不是"最上一行"—— 手册附图 26 里 ROW3 在最上、ROW0 在最下，
--     而 `i_row(0)` 接的就是 `kp_row[0] = PIN_111`。键位图以 `game_fsm.key_of()`
--     为准（该处已按实测的 KEY14=index1=开始 / KEY16=index3=选择 校核过）；
--     本模块只负责"报出 4*行+列"这个原始编号。
--     把这个键号解释成游戏控制是 game_fsm（key_of）的职责。
--
--  ---------------------------------------------------------------------------
--  扫描方案及其理由
--  ---------------------------------------------------------------------------
--  在实验台上试过两种方案：
--
--   (a) 列优先：每个相位只把一列驱动为低，然后读行。
--       可行，但始终只能检测到两个键。一条行线只在它自己所在的列被驱动
--       时才被读取，所以只要某条列线上有一个接线/上拉问题，就会静默地
--       丢掉整列键。
--
--   (b) 所有列都驱动为低，然后读行（本模块采用）。
--       这样，按下的键无论坐在哪一列，都会把它所在的行拉低，因此不会因为
--       某一列有问题就丢掉任何一个键。随后，列号是通过"把所有列驱动为
--       高，再每次只释放一列"来确定的：只有承载被按键的那一列，才会让
--       对应的行落下。
--
--  在健壮性上，方案 (b) 是 (a) 的超集：它把"一列坏掉会丢四个键"
--  变成"一列坏掉最多只丢一个列号，而且即便在这种情况下，这个键仍然
--  能被检测到"。
--
--  消抖：一次读数必须在连续 DEBOUNCE_MAX+1 轮扫描中保持一致
--        （现在是 4 轮 = 40 ms —— 见 puzzle_pkg.vhd 里 ERR-031 的说明：
--        一轮是两个 tick_200 周期 = 10 ms，因为 SC_ALL_HIGH 和
--        SC_ALL_LOW 各自都要等一个 tick；旧的"16 x 5 ms = 80 ms"说法
--        少算了一倍，真实值是 160 ms）。
--  输出：o_key 保存被接受的键号；当一个新接受的键出现时，o_press 是一个
--        单时钟脉冲，所以按住不放只会产生恰好一次动作。
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

    -- 本项目的极性常量：按键被按下时行线读到的电平。
    -- 实验台实测为 '0'。
    constant KP_ACTIVE : std_logic := '0';

    type scan_t is (SC_ALL_LOW, SC_ALL_HIGH, SC_RELEASE, SC_SETTLE);

    signal state   : scan_t := SC_ALL_HIGH;
    signal phase   : unsigned(1 downto 0) := (others => '0');
    -- ⚠️ 2026-10-09 第 15 工作阶段（面积优化，实测）：settle 只数 0..63，原来声明成
    --    8 位 —— 高 2 位**永远为 0**，但 Quartus **不做值域分析**：实测
    --    `.tmp/opt/.../db/scratch.hier_info` 里 settle[0..7].CLK 八个触发器**真的都在**，
    --    那 2 个触发器是真花的钱。收到 6 位后 keypad_scan 少 12 个 LC（整机 -7 LE，
    --    见 .tmp/opt/p_kp_width 与 area_base 的对比）。
    --    ⚠️ 改这里必须确认判据值仍 ≤ 63（本模块的判据是 `settle = 63`）。
    signal settle  : unsigned(5 downto 0) := (others => '0');   -- 0..63 -> 6 位（原为 8 位）

    signal row_all : std_logic_vector(3 downto 0) := (others => KP_ACTIVE);
    -- ⚠️ ERR-036（2026-10-09 第 11 工作阶段，全项目审计发现）：原来 row_all **没有初值**，
    --    复位分支也不给它赋值 → 上电后到第一轮锁存之前它是确定的 0（MAX IV/MAX II 上电为低），
    --    而 0 的每一位都 = KP_ACTIVE ⇒ 配合**旧判据**（取"最后一个有效行"）会先造出一个
    --    "第 3 行被按下"的幻影候选，把消抖计数预置成 1：**上电后第一个键只要 3 轮
    --    （30 ms）就被接受**，比设计值少 1 轮（tb 断言 ⑨ 把 9T 当成了期望值）。
    --    现在：① 初值与复位分支都**显式**写出该值；② 判据改成"必须**恰好一行**被拉低"
    --    （见下面的组合进程）—— 全 0（4 行都"有效"）与全 1（0 行有效）**都判为"没有键"**，
    --    所以这个初值只影响上电头几拍，**不改变任何按键行为**（这也是本轮不为它重跑
    --    整机仿真的理由：行为等价、只是把默认值写明）。
    -- 逐相位记录：col_low(c) = '1' 表示当只有列 c 被释放时，有一条行线落下
    -- -> 被按下的键位于列 c。
    signal col_low : std_logic_vector(3 downto 0) := (others => '0');
    signal col_all : std_logic := '0';                -- 1 = 所有列驱动为低

    signal cand    : std_logic_vector(3 downto 0) := K_NONE;  -- 候选键号
    signal any_hit : std_logic := '0';
    signal rd_done : std_logic := '0';

    signal stable    : std_logic_vector(3 downto 0) := K_NONE;
    -- ⚠️ 2026-10-09 第 15 工作阶段（面积优化，实测）：同上 —— cnt 只数
    --    0..DEBOUNCE_MAX(=3)，8 位里高 6 位恒为 0，但六个触发器真的被综合出来。
    --    收到 2 位（0..3）。**若 DEBOUNCE_MAX 改成 > 3，必须同步加宽 cnt**
    --    （位宽 = ceil(log2(DEBOUNCE_MAX+1))），否则 `cnt = DEBOUNCE_MAX` 恒不成立、
    --    消抖会永远接受不了按键（与 clk_gen 里 T_BTN_MS/por_cnt 的位宽陷阱同类）。
    signal cnt       : unsigned(1 downto 0) := (others => '0'); -- 0..DEBOUNCE_MAX -> 2 位（原为 8 位）
    signal key_r     : std_logic_vector(3 downto 0) := K_NONE;
    signal press_r   : std_logic := '0';
    signal release_r : std_logic := '0';

    signal col_drv   : std_logic_vector(3 downto 0) := (others => '1');

begin

    ----------------------------------------------------------------------------
    -- 列驱动。
    --   SC_ALL_LOW / SC_SETTLE 且 col_all='1' 时：所有列驱动为低
    --   SC_RELEASE                              ：除由 'phase' 选中的那一列
    --                                             外，其余全为高
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
                row_all <= (others => KP_ACTIVE);     -- ERR-036：把上电默认值写明（判据见下）
            else
                case state is

                    -- 相位 A：把所有列驱动为低，然后采样各行。
                    when SC_ALL_LOW =>
                        if (i_tick = '1') then
                            col_all <= '1';
                            col_low <= (others => '0');   -- 新一轮
                            settle  <= (others => '0');
                            state   <= SC_SETTLE;
                        end if;

                    -- 等待稳定，然后锁存"所有列驱动为低"时的行图样。
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

                    -- 相位 B：全部驱动为高，每步只释放一列。
                    -- 当列 c 被释放时，行能落下的唯一可能，
                    -- 就是被按下的键正位于列 c —— 所以每个看到行落下的相位
                    -- 都确定了一列。这些结果必须被**累加**
                    -- （早先的版本每个相位都覆盖同一个寄存器，
                    -- 因此只有最后一列会被识别出来）。
                    when SC_RELEASE =>
                        if (settle = 63) then
                            settle <= (others => '0');
                            -- 这一列被释放时有行线为低吗？
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
    -- 组合逻辑列驱动（不打拍，所以驱动与用于生成键号的相位
    -- 不会不一致）。
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
    --   有行被按下吗？
    --     有 -> 键号 = 4*行 + 列，而列就是"其 RELEASE 让该行落下"的那个相位
    --            （即该行在 row_rel 期间为低）。
    --            如果没有任何释放能定位它，就回退到列 0，这样键仍然会被报出
    --            而不是被丢掉。
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

        -- (1) 必须**恰好一行**被拉低。
        --     ⚠️ ERR-036（2026-10-09 第 11 工作阶段审计）：原来取"最后一行为低"，
        --     手里同时按下两个不同行的键时会合成一个**谁都没按过的"鬼键"**
        --     （例：(行1,列2)+(行2,列0) → 报 4*2+2=10 = K_UP）。课程需求没有规定多键
        --     行为，所以最不坏的语义是"看不清就不报"：行数 ≠ 1 → K_NONE。
        nrow := 0;
        for r in 0 to 3 loop
            if (row_all(r) = KP_ACTIVE) then
                nrow := nrow + 1;
                crow := r;
            end if;
        end loop;
        if (nrow = 1) then hit := '1'; else hit := '0'; end if;

        -- (2) 哪一列？col_low(c) 表示"只有列 c 被释放时有一行落下"。
        --     正常恰好一位置 1；若一列都没命中（接线/极端情况），保持原来的回退语义
        --     （列 0），"宁可报一个键也不要静默丢键"。
        --     ⚠️ **这里故意不做"恰好一列"的强校验**（ERR-036b 的一次尝试，已在整机上
        --     证实有害）：由于 ERR-039b（SC_RELEASE 的相 0 只有 1 拍、采样恰好落在
        --     相切换那一拍），整机测试台的行激励窗口（SETTLE 段一直拉到 +1400 ns）
        --     会让**相 0 也采到一次"行低"**，于是 col_low 同时命中两列。取"最后一个命中"
        --     （原语义）得到的是**真实按下的那一列**；改成"必须恰好一列"会把按键
        --     全部丢成 K_NONE（实测整机 ①③④…全部失败）。要收严这一条，必须先修
        --     ERR-039b 并把两个测试台的按键窗口整体重新标定。
        found := false;
        if (hit = '1') then
            for c in 0 to 3 loop
                if (col_low(c) = '1') then
                    ccol  := c;
                    found := true;
                end if;
            end loop;
            if not found then
                ccol := 0;                        -- 回退（保持原有行为）
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
                    -- ⚠️ 2026-10-09 第 15 工作阶段（面积优化；**穷举证明等价**）：
                    --    原来的三分支 if/elsif 逐条列了三种"改 key_r"的情形。对
                    --    (stable, key_r) 的全部 256 种取值逐一比对可以证明：
                    --      ① 三条分支里 key_r **总是**被赋成 stable（第一条与第三条
                    --         都是 key_r <= stable，第二条是 key_r <= K_NONE = stable）；
                    --         故 `key_r <= stable` 可以无条件写；
                    --      ② press 的充要条件 = (stable /= K_NONE) and (stable /= key_r)
                    --         （它同时覆盖原来第一条与第三条分支）；
                    --      ③ release 的充要条件 = (stable = K_NONE) and (key_r /= K_NONE)。
                    --    证明脚本 .tmp/mine/proof_cand.py：256 组逐一比对，0 处不一致。
                    --    行为（含"按住只发一次 / 换键当新按下"）逐拍不变。
                    key_r <= stable;
                    if ((stable /= K_NONE) and (stable /= key_r)) then
                        -- 一个键被接受，或者在没有中间释放的情况下接受了另一个不同的键：
                        -- 两者都报成一次新的按下，
                        -- 这样任何键都不会被吞掉。
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
