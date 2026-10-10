-- ============================================================================
--  game_fsm  --  主状态机：游戏流程、倒计时、关卡切换
--  子系统：S3（游戏控制）
--
--  本模块掌管「时间」与「决策」，不掌管任何坐标：每一个空间上的
--  问题都由 puzzle_ctrl 回答。
--
--  状态流程（方括号内是需求编号）：
--
--      SW7=0 ──► 全部熄灭（B1）
--      S_SELF_TEST  2 s，2 Hz 闪烁（B1）
--      S_IDLE       DISP7=5，DISP0=level（B2、B3）
--        --"start"-->  S_PREVIEW
--      S_PREVIEW    5 s 预览，倒计时显示在 DISP7 上（B4）
--        --预览结束--> 散落零片，进入 S_PLAYING
--      S_PLAYING     30 s（第一关）/ 40 s（第二关）/ **60 s（第三关，自拟）**
--                    "select" 循环切换选中的零片（B6）
--                    方向键移动它，由 puzzle_ctrl 校验（B7）
--                    "confirm" 锁定它（B8）
--                    全部锁定且都在目标上  -> S_WIN（第一关 -> 第二关，第二关 -> 第三关）
--                    全部锁定但位置错误，或超时 -> S_FAIL（B9、B10）
--      S_WIN / S_FAIL   显示图案；"start" 开始新一局（B11）
--
--  "start" 在**对局进行中**也同样有效，这就是需求 B11。
--
--  ---------------------------------------------------------------------------
--  ⚠️ 2026-10-09（第 12 工作阶段 / D2 设计）：**关数从 2 关变成 3 关**。
--
--    提高要求 2 的原文是"**增加游戏关数，多种拼图图案随机选择**"——两件事写在同一条里。
--    旧实现把"多种图案随机选择"放在**基本要求的第二关**上（每局随机），"增加关数"欠账；
--    现在改成正面的口径：
--       第一关 = 图 4-1（B4 指定，固定）      level='0'
--       第二关 = 自拟图案，**固定为 PAT3**    level='1', lvl3='0'   （B10 字面）
--       第三关 = 图案从四幅库**随机选**       level='1', lvl3='1'   （A2 新增关）
--    所以"关数"用**两位信息**表示：`level` 保持原来的含义（'0'=第一关、'1'=第二关及以后），
--    新增一位 `lvl3` 表示"已经过了第二关"。这样做的原因是**实测**出来的：
--    把 `o_level` 直接加宽成 2 位（最直观的写法）会在 `piece_rom`/`pattern_rom`/
--    `puzzle_ctrl` 前面各插一级比较器，同一个第三关功能让 Fmax 从 48.87 掉到 46 以下
--    （13 个 fitter seed 的最好值）；保持 `level` 那位寄存器**一个字节都不动**、
--    另加一个独立标志，Fmax 几乎不动（48.87，默认 seed）。教训：**在 98% 占用率下，
--    "动了哪根既有网"比"加了多少逻辑"重要得多**。
--  ---------------------------------------------------------------------------
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity game_fsm is
    port (
        i_clk      : in  std_logic;
        i_rst      : in  std_logic;                      -- 高电平有效
        i_sw       : in  std_logic;                      -- SW7 系统开关
        i_tick_1hz : in  std_logic;
        -- ⚠️ 第 16 工作阶段：**删掉了 `i_tick_2hz` 端口**（从未使用；ERR-038 改成用
        --    i_tick_4hz 翻转得到 2 Hz 方波）。留着它只会让顶层多一根死线。
        i_tick_4hz : in  std_logic;                      -- ERR-038：翻转它 → 2 Hz 方波
        i_press    : in  std_logic;                      -- 单拍：有一个按键被接受
        i_key      : in  std_logic_vector(3 downto 0);   -- 被接受的按键码
        o_sel      : out std_logic;                      -- 单拍：循环切换选择
        o_move     : out std_logic;                      -- 单拍：移动请求
        o_conf     : out std_logic;                      -- 单拍：锁定请求
        o_go       : out std_logic;                      -- 散落请求：**电平**（请求/应答握手，
                                                         -- 不是单拍脉冲；见下方注释与
                                                         -- docs/02 §… 的 ERR-006/024 说明）
        o_up       : out std_logic;
        o_down     : out std_logic;
        o_left     : out std_logic;
        o_right    : out std_logic;
        o_rot      : out std_logic;                      -- A4: 90° 旋转请求（1 拍）
        o_level    : out std_logic;                      -- '0' = 第一关，'1' = 第二关/第三关
        o_lvl3     : out std_logic;                      -- '1' = 第三关（A2：增加关数）
        o_state    : out std_logic_vector(2 downto 0);   -- state_t
        o_time     : out std_logic_vector(5 downto 0);   -- 倒计时秒数
        o_blink    : out std_logic;                      -- 2 Hz 闪烁标志
        i_solved   : in  std_logic;                      -- 来自 puzzle_ctrl
        i_all_lock : in  std_logic;                      -- 来自 puzzle_ctrl
        i_shuf_busy: in  std_logic;                      -- 来自 puzzle_ctrl
        o_sound    : out std_logic_vector(3 downto 0)    -- 音效选择码（4 位，A1 v2）
    );
end entity game_fsm;

architecture rtl of game_fsm is

    ----------------------------------------------------------------------------
    -- 按键映射表 —— 把键盘位置变成游戏按键的唯一一处。
    --
    -- 键盘扫描上报的是普通索引 4*row + column，其中 **row 0 是最下面那一物理行**
    -- （板子的丝印把行从最上面的 ROW3 标到最下面的 ROW0 —— 见板子手册，附图26），
    -- 而 column 0 是最左边那一列
    -- （COL0..COL3 从左到右印在板上）。
    --
    -- 板子上的按键印成 KEY1..KEY16，按从左到右、从上到下的顺序读，
    -- 因此物理网格与上报索引的对应关系是：
    --
    --            COL0   COL1   COL2   COL3
    --   ROW3     KEY1   KEY2   KEY3   KEY4        索引 12..15
    --   ROW2     KEY5   KEY6   KEY7   KEY8        索引  8..11
    --   ROW1     KEY9   KEY10  KEY11  KEY12       索引  4.. 7
    --   ROW0     KEY13  KEY14  KEY15  KEY16       索引  0.. 3   <- 最下面
    --
    -- ⚠️ 2026-10-09 第 13 工作阶段（提高要求 A4「零片 90° 旋转」）：新增【旋转】键
    --    KEY8（= 索引 11）。它就在【上】键右边，右手的食指/中指够得到，且不影响
    --    原来的 3x3 控制键区布局：
    --
    --            COL0    COL1    COL2      COL3
    --   ROW2     KEY5    KEY6    KEY7      KEY8
    --                            [UP]      [ROTATE]
    --   ROW1     KEY9    KEY10   KEY11     KEY12
    --            ...     [LEFT]  [CONFIRM] [RIGHT]
    --   ROW0     KEY13   KEY14   KEY15     KEY16
    --            (无)    [START] [DOWN]    [SELECT]
    --
    -- 上板确认（2026-10-08）：KEY14（= 索引 1）开始游戏，
    -- KEY16（= 索引 3）选择零片。两者都保留在玩家已经
    -- 熟悉的位置：控制键区的左下角 / 右下角。
    --
    -- ⚠️ 索引 0 **不可用**：没有按键按下时扫描器上报 K_NONE（"0000"），
    --    所以 KEY13 与"没有按键按下"无法区分。绝不能
    --    给它任何游戏功能（旧表把它映射成 LEFT，那是死代码 ——
    --    仿真时抓到，见 docs/06 / tb_puzzle_top ⑧）。
    --
    -- 七个控制键集中在右下角**同一个**连续的 3x3 区块里，
    -- 方向键按标准的「十字」排列（中心 = 确认，
    -- 与数字小键盘完全一样）：
    --
    --            COL1    COL2      COL3
    --   ROW2     KEY6    KEY7      KEY8
    --                    [UP]
    --   ROW1     KEY10   KEY11     KEY12
    --            [LEFT]  [CONFIRM] [RIGHT]
    --   ROW0     KEY14   KEY15     KEY16
    --            [START] [DOWN]    [SELECT]
    --
    -- 其它一切情况都返回 K_NONE。如果哪天上板测量发现
    -- 物理位置不同，只改这一个函数。
    ----------------------------------------------------------------------------
    function key_of(idx : std_logic_vector(3 downto 0))
        return std_logic_vector is
    begin
        case idx is
            when "0001" => return K_START;    -- KEY14（上板确认）
            when "0011" => return K_SELECT;   -- KEY16（上板确认）
            when "1010" => return K_UP;       -- KEY7   十字的上臂
            when "0010" => return K_DOWN;     -- KEY15  十字的下臂
            when "0101" => return K_LEFT;     -- KEY10  十字的左臂
            when "0111" => return K_RIGHT;    -- KEY12  十字的右臂
            when "0110" => return K_CONFIRM;  -- KEY11  十字的中心
            when "1011" => return K_ROT;      -- KEY8   十字右侧（A4，上板核对）
            when others => return K_NONE;     -- 含 "0000" = 无按键（KEY13）
        end case;
    end function;

    signal st      : state_t := S_SELF_TEST;
    signal level   : std_logic := '0';
    -- ⚠️ 第三关标志（A2"增加游戏关数"）。与 `level` 分开是**实测**的决定，不是风格问题：
    --    见文件头的说明（加宽 o_level 会让 Fmax 掉 2~5 MHz）。
    signal lvl3    : std_logic := '0';
    signal cnt     : unsigned(5 downto 0) := (others => '0');
    -- ⚠️ **ERR-051 的修法（2026-10-10）：自检窗口复用 `cnt`，且刻意"倒计数"。**
    --
    -- 【原来错在哪】自检窗口用一个 2 位 `selfc` 数 tick_1hz（`selfc = 1` 时退出），
    --    于是**入口相位不同、时长就是 (1, 2] s**：
    --      · 复位/上电路径：tick 计数器与 FSM 同时被 i_rst 清零，入口落在 1 s 网格上
    --        ⇒ 恰好 2.000 s；
    --      · **SW7 关→开重新进入**：tick_1hz 自由走，入口可落在网格任意位置
    --        ⇒ 只要 1 s 就数满 2 个脉冲 ⇒ 自检只有 **1 s**（B2 明文要求"2 秒后进入待机"）。
    --    更要命的是它**放大了 ERR-051**：自检音效（buzzer_ctrl 的 MEL_SELF）发声步是
    --    第 0/8 步，而 `step` 是自由走的 —— 窗口只有 4~8 步时，某些相位**一个发声步都
    --    碰不到 ⇒ 整段 2 s 一声不响**（"恰好一声"只在复位路径成立）。
    --
    -- 【现在怎么做】改数 **tick_4hz 满 8 拍**（8 × 250 ms = **恰好 2 s**，两条进入路径
    --    一致），窗口**恒为 8 个旋律步**；8 个连续步**必然恰好包含第 0 或第 8 步中的一个**
    --    （两者相隔 8）⇒ **恒为一声**。
--    ⚠️ **时长的准确说法**：窗口是"数满 8 个 `tick_4hz`"，而 `tick_4hz` 是自由走的
--       （clk_gen 只被 i_rst 复位、与 FSM 入口无关）⇒ 从入口到第 8 个脉冲 = **7~8 个
--       250 ms 周期**，即复位路径 ≈2.000 s、SW7 重入路径落在 **(1.75, 2.0] s**。
--       所以只能说"窗口恒为 8 个旋律步、恰好一声"，**不要说"时长恒为 2 s"**
--       （这正是 ERR-051 自己总结的"绝对说法要逐路径验"）。
    --
    -- 【为什么是"复用 cnt + 倒计数"】本器件 **LAB 已满 127/127**，每一步都要量：
    --      · 加宽 `selfc` 2→3 位（数 tick_4hz）：实测 SEED 5 下 fitter 要 **128 LABs，
    --        直接装不下**；
    --      · 复用 `cnt` 但**正计数**（`cnt <= cnt + 1` 比到 7）：`cnt` 在别处只有
    --        `cnt - 1` 与常量装载，正计数要**新造一个 6 位加法器** —— 实测同样装不下；
    --      · ✅ **复用 `cnt` + 倒计数**（入口装 7、数到 0 退出）：直接复用已有的
    --        减法器与比较器，`selfc` 整个删掉（−2 FF）。**这是三种里唯一装得下的**。
    --    这就是"99% 占用率下先找'已经在手边的资源'"那条经验（docs/05 §1.5）的又一次应用。
    --    ⚠️ `cnt` 复用是安全的：自检期间它本来就空闲；S_IDLE 不用它；
    --       进预览时会被重新装载为 T_PREVIEW（见下面 S_PREVIEW 分支）。
    --    ⚠️ 复位 / SW7=0 / `when others` 三处入口都装载 `T_SELFTEST_T4`，
    --       保证**任何一条进入路径**的窗口长度都一样（ERR-051 的教训：绝对说法要逐路径验）。

    -- 交给 puzzle_ctrl 的单拍命令脉冲，在下面的输出
    -- 段里生成
    signal req_go  : std_logic := '0';
    signal move_r  : std_logic := '0';

    signal up_r, down_r, left_r, right_r : std_logic := '0';
    signal rot_r : std_logic := '0';                    -- A4: 旋转请求（1 拍）
    signal sel_r, conf_r : std_logic := '0';
    signal sound_p : std_logic_vector(3 downto 0) := SND_NONE;
    -- ⚠️ 第 14 工作阶段（A1 v2）：瞬时音效的**保持**计数器。
    --    见下面音效进程的说明：单拍脉冲必须被保持 ≥1 个旋律步才听得见。
    --    ⚠️ 刻意**没有**单独的"锁存码"寄存器：保持期内直接不给 `sound_p` 赋值即可
    --    （寄存器保持语义），省掉 4 个 FF + 一个 4 位多路器。
    signal snd_hold : unsigned(1 downto 0) := (others => '0');
    -- 用于闪烁的 2 Hz 方波。
    -- ⚠️ ERR-038（2026-10-09 第 11 工作阶段，全项目审计发现）：B1 要求"以 **2 Hz** 闪烁"。
    --    原来拿 tick_2hz（500 ms 一个脉冲）直接翻转，得到的是 **1 s 周期 = 1 Hz** 方波
    --    —— 只有要求的一半，而注释/文档却按 2 Hz 记账（与 ERR-031 同类的 2 倍算错）。
    --    现在改为在 **tick_4hz（250 ms）** 上翻转：高 250 ms / 低 250 ms → 整周期
    --    500 ms = **真正的 2 Hz、50% 占空**。
    --    为什么必须翻转而不是直接当电平用：tick 是**一个时钟宽的脉冲**（20 ns），
    --    直接当电平只会每 250 ms 亮一个时钟，肉眼根本看不见。
    signal blink_r : std_logic := '0';
    signal kdec    : std_logic_vector(3 downto 0) := K_NONE;  -- 译码后的游戏按键
    signal go_done : std_logic := '0';   -- 本局已经请求过散落

    ----------------------------------------------------------------------------
    -- ⚠️ ERR-024 : 判决必须等**本局的散落**跑过之后才生效。
    --
    -- puzzle_ctrl 的 locked/pos 只在 i_go（散落）时才清零，所以刚进 S_PLAYING
    -- 的那一两拍，引擎里还是**上一局**的残留状态（全锁定 + 上一局的拼法）。
    -- 旧实现无条件采信 i_solved/i_all_lock，于是：
    --   · 上一局拼对了 → 新一局刚开局就"过关"，直接跳进第二关；
    --   · 上一局拼错了但已全锁 → 新一局刚开局就判负（还没散落就出叉）。
    -- 上板现象（2026-10-08）："第一关拼好按确认出叉，退出重进又直接跳第二关"。
    -- 仿真证据：tb_game_fsm 断言 ⑯⑰（修复前 r07 = 15/17，对局开始后 3 拍就已
    -- 经跳到失败/第二关）。
    -- 修法：本局至少要**看见过一次**散落的忙态，判决才被允许。
    ----------------------------------------------------------------------------
    signal shuf_seen : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- 倒计时 / 状态寄存器。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                st    <= S_SELF_TEST;
                level <= '0';
                lvl3  <= '0';
                cnt   <= to_unsigned(T_SELFTEST_T4, 6);   -- 自检倒计数初值（8 拍 = 2 s）
            elsif (i_sw = '0') then
                -- B1：开关关闭时整个系统被保持在序列的起点，
                -- 这样重新打开时总是从头显示一次自检 / 待机，
                -- 而不是接着一局没玩完的游戏继续。
                st    <= S_SELF_TEST;
                level <= '0';
                lvl3  <= '0';
                cnt   <= to_unsigned(T_SELFTEST_T4, 6);   -- 自检窗口恒 8 拍 = 2 s
            else
                case st is

                    when S_SELF_TEST =>
                        -- ⚠️ ERR-051 修法（见 `cnt` 的声明注释）：数 **tick_4hz** 满 8 拍
                        --    = 恰好 **2 s**（B2），且**两条进入路径都成立**。
                        --    旧写法数 tick_1hz（2 拍）在 SW7 重新进入时只有 1 s，
                        --    并让自检音效在某些相位整段不响。
                        --    ⚠️ 这里**倒计数**（入口装载 7，数到 0 退出）而不是正计数：
                        --       `cnt` 在预览/对局里本来就是**递减**的（`cnt <= cnt - 1`），
                        --       倒计数直接复用**已有的减法器与比较器**；
                        --       正计数则要新造一个 6 位加法器（实测会多要一个 LAB）。
                        if (i_tick_4hz = '1') then
                            if (cnt = 0) then            -- 8 拍 x 250 ms = 2 s
                                st <= S_IDLE;
                            else
                                cnt <= cnt - 1;
                            end if;
                        end if;

                    when S_IDLE =>
                        if (i_press = '1') and (kdec = K_START) then
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';                  -- 新一局从第一关开始
                            lvl3  <= '0';
                            st    <= S_PREVIEW;
                        end if;

                    when S_PREVIEW =>
                        if (i_press = '1') and (kdec = K_START) then
                            -- B11：任何时候都可以重新开始
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';
                            lvl3  <= '0';
                            st    <= S_PREVIEW;
                        elsif (i_tick_1hz = '1') then
                            if (cnt <= 1) then
                                -- 预览结束。在这里装载本关的**时限**
                                -- （需求 B5 = 30 s、B10 = 40 s、第三关 = 60 s（第 18 工作阶段之前是 40 s）；
                                -- 见 puzzle_pkg.T_LEVEL3）。这里原来是漏掉的：cnt 从预览
                                -- 一直停在 1，于是进入对局后的第一个
                                -- tick 就立刻超时，游戏在不到一秒内
                                -- 就结束了。
                                if (level = '0') then
                                    cnt <= to_unsigned(T_LEVEL1, 6);
                                elsif (lvl3 = '1') then
                                    cnt <= to_unsigned(T_LEVEL3, 6);
                                else
                                    cnt <= to_unsigned(T_LEVEL2, 6);
                                end if;
                                st <= S_PLAYING;
                            else
                                cnt <= cnt - 1;
                            end if;
                        end if;

                    when S_PLAYING =>
                        -- 背景音乐轨迹位在预览期就已经锁存好（见信号声明处），这里只消费
                        if (i_press = '1') and (kdec = K_START) then
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';
                            lvl3  <= '0';
                            st    <= S_PREVIEW;
                        elsif (i_solved = '1') and (shuf_seen = '1')
                              and (i_shuf_busy = '0') then
                            if (level = '0') then
                                level <= '1';              -- B9：进入第二关
                                cnt   <= to_unsigned(T_PREVIEW, 6);
                                st    <= S_PREVIEW;
                            elsif (lvl3 = '0') then
                                lvl3  <= '1';              -- A2：新增第三关
                                cnt   <= to_unsigned(T_PREVIEW, 6);
                                st    <= S_PREVIEW;
                            else
                                st <= S_WIN;               -- 胜利（最后一关已完成）
                            end if;
                        elsif (i_all_lock = '1') and (shuf_seen = '1')
                              and (i_shuf_busy = '0') then
                            st <= S_FAIL;                  -- B9：拼装错误
                        elsif (i_tick_1hz = '1') then
                            if (cnt <= 1) then
                                st <= S_FAIL;              -- B9/B10：超时
                            else
                                cnt <= cnt - 1;
                            end if;
                        end if;

                    when S_WIN | S_FAIL =>
                        if (i_press = '1') and (kdec = K_START) then
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';
                            lvl3  <= '0';
                            st    <= S_PREVIEW;            -- B11
                        end if;

                    when others =>
                        -- 不可达（6 个状态全部枚举）；保留兜底并同样装载自检倒计数初值，
                        -- 免得万一进入时 `cnt` 停在别的值、自检窗口长度不定（ERR-051 的教训）。
                        st  <= S_SELF_TEST;
                        cnt <= to_unsigned(T_SELFTEST_T4, 6);
                end case;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 命令译码：给 puzzle_ctrl 的按键单拍脉冲。
    --   start   -> 由上面的状态寄存器处理
    --   select  -> 循环切换选中的零片            (B6)
    --   confirm -> 锁定选中的零片                (B8)
    --   arrows  -> 移动选中的零片                (B7)
    -- 只有在真正对局过程中才接受移动与锁定。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sel_r   <= '0';
                conf_r  <= '0';
                up_r    <= '0'; down_r  <= '0';
                left_r  <= '0'; right_r <= '0';
                rot_r   <= '0';
                move_r  <= '0';
                req_go  <= '0';
                shuf_seen <= '0';
            else
                -- 默认值：每条命令都是单拍脉冲
                sel_r  <= '0';
                conf_r <= '0';
                move_r <= '0';
                rot_r  <= '0';
                up_r   <= '0'; down_r  <= '0';
                left_r <= '0'; right_r <= '0';

                if (i_press = '1') and (st = S_PLAYING) then
                    case kdec is
                        when K_SELECT => sel_r  <= '1';
                        when K_CONFIRM => conf_r <= '1';
                        when K_UP      => up_r   <= '1'; move_r <= '1';
                        when K_DOWN    => down_r <= '1'; move_r <= '1';
                        when K_LEFT    => left_r <= '1'; move_r <= '1';
                        when K_RIGHT   => right_r <= '1'; move_r <= '1';
                        when K_ROT     => rot_r   <= '1';   -- A4（引擎同一条校验流水）
                        when others    => null;
                    end case;
                end if;

                -- 散落请求：进入对局时置起，一直保持到
                -- 引擎报告自己不再忙为止。用请求/应答
                -- 握手（而不是单拍脉冲）意味着散落永远不会
                -- 被漏掉，无论它要花多久。
                -- 散落请求：每局只请求一次。
                -- 没有 go_done 这个记忆位时，握手会在
                -- 引擎一回到空闲时立刻重新触发，于是引擎被
                -- 不停地反复散落 —— 每次都清掉 sel/locked 并让
                -- 引擎一直忙，任何按键都不可能起作用。
                if (st /= S_PLAYING) then
                    req_go  <= '0';
                    go_done <= '0';                -- 为下一局重新武装
                elsif (req_go = '0') and (go_done = '0') and (i_shuf_busy = '0') then
                    req_go <= '1';                 -- 发出一次请求……
                elsif (i_shuf_busy = '1') then
                    req_go  <= '0';                -- ……被引擎接受
                    go_done <= '1';                -- 本局不再请求
                end if;

                -- ⚠️ ERR-024 : 判决的前置条件 —— 本局已经看到过散落的忙态。
                -- 引擎的 locked/pos 只由散落清零，所以在这之前 i_solved/i_all_lock
                -- 反映的是**上一局**的状态，绝不能用来判决。
                if (st /= S_PLAYING) then
                    shuf_seen <= '0';
                elsif (i_shuf_busy = '1') then
                    shuf_seen <= '1';
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- B1 自检 / 结果画面的 2 Hz 闪烁标志。
    -- ⚠️ ERR-038：在 4 Hz 节拍上翻转 -> 真正的 2 Hz 方波（500 ms
    --    的节拍只能得到 1 Hz）。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                blink_r <= '0';
            elsif (i_tick_4hz = '1') then
                blink_r <= not blink_r;      -- 4 Hz 节拍翻转 → 2 Hz 方波（ERR-038）
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 音效选择（提高要求 A1）。
    --
    -- ⚠️ 2026-10-09 第 14 工作阶段重做（用户上板反馈"游戏过程中没有任何音效"）。
    --    v1 的三个缺口，逐条对应这里的三个改动：
    --      ① **对局中默认码是 "000"（静音）** → 现在对局默认码 = `SND_BGM`
    --         （背景音乐），玩家一进对局就有声音 —— A1 的原文是"提示音效**或音乐**"；
    --      ② 按键/旋转/确认/过关/拼错在 v1 是**单拍脉冲**（~20 ns）→ 蜂鸣器来不及
    --         发声，等于听不见；现在用 `snd_hold`（2 位）把它们**保持 2 个旋律步
    --         （250~500 ms）**，足够把第一拍完整放出来；
    --      ③ 场景只有 7 个（3 位码）→ 现在 **16 个**（4 位码，见 puzzle_pkg 的 SND_*），
    --         移动 / 旋转 / 选择 / 确认 / 被拒绝 / 最后 5 秒各有各的声音。
    --
    --    ⚠️ 判决音效仍然只门控 `shuf_seen`（与 v1 一致，ERR-039c 已记录未修）。
    --    ⚠️ "移动/旋转被拒绝"的专用音效（SND_NAK 1101）**本轮做了又撤了**：
    --       它需要 puzzle_ctrl 多一个 o_nak 输出 + 这里多一级优先分支，实测整机 +5 LE
    --       且把最差路径拖垮（1268 → 1273 LE / 128 LABs，装不进 EPM1270）。
    --       SND_NAK 的码与乐句保留在 puzzle_pkg / buzzer_ctrl 里（16 个码的接口不变），
    --       将来腾出面积可以直接接上（负结果见 docs/05 §1）。
    --    ⚠️ 这里只做**寄存器**赋值（不写成组合多路器）：v1 的实测教训是
    --       `i_solved → 音效多路器 → buzz` 曾是最差路径之一，所以码必须是寄存的。
    ----------------------------------------------------------------------------
    process (i_clk)
        variable evc : std_logic_vector(3 downto 0);
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sound_p  <= SND_NONE;
                snd_hold <= (others => '0');
            else
                -- ---- (1) 本拍的"瞬时事件"码 ----
                -- ⚠️ 面积（第 14 工作阶段实测）：**按键类事件用一次 `case kdec` 译码**，
                --    而不是"conf? rot? sel? move? press?"四个 elsif 级联 —— 后者每一级都要
                --    一个 4 位 2:1 mux，实测更贵；按键到什么音效本来就是一张表。
                if (st /= S_PLAYING) then
                    evc := SND_NONE;
                elsif (i_solved = '1') and (shuf_seen = '1') then
                    evc := SND_CLEAR;                    -- 过关（上行）
                elsif (i_all_lock = '1') and (shuf_seen = '1') then
                    evc := SND_WRONG;                    -- 锁满了但画面不对（下行）
                else
                    evc := SND_NONE;
                end if;
                -- ⚠️⚠️ 2026-10-10 第 18 工作阶段（**用户第二次反馈按键音效**）：
                --    "确认、旋转按键我认为没必要有特殊音效来打扰背景游戏音效"。
                --    ⇒ **【确认】与【旋转】也不再发声**，于是**对局中任何按键都不发声**：
                --      原来的 `elsif (i_press = '1') then case kdec ...` 整段被删除 ——
                --      它只剩"全部给 SND_NONE"这一个结果，等于白算一次 4 位译码。
                --      **净效果是省逻辑**（少一级 4 位译码 + 两个查表臂），
                --      而且 `kdec` 仍然被 o_sel/o_conf/o_move/o_rot 那些输出用着，不受影响。
                --    演进（三次用户反馈，别把中间态当成最终态）：
                --      第 16 工作阶段第一轮："上下左右不需要额外音效" → 移动/选择/开始静音，
                --                             保留确认 `1100` 与旋转 `1010`；
                --      第 16 工作阶段第二轮：内容换成马里奥系曲子（音效码不变）；
                --      **第 18 工作阶段（本轮）**："确认、旋转没必要有特殊音效来打扰背景音乐"
                --                             → **对局中彻底没有按键音**，只有背景音乐。
                --    ⚠️ `SND_CONF`(1100) / `SND_ROT`(1010) 两个**常量与乐句仍然保留**
                --      （`buzzer_ctrl` 里只是删掉了它们的查表臂，见该文件注释），
                --      接口仍是 4 位 / 16 个码，将来想加回来不用改结构。
                -- ⚠️ 第 15 工作阶段（面积）：这里**删掉了**"最后 5 秒每秒催一下"的
                --    `elsif (i_tick_1hz='1') and (cnt<=5)` 分支。原因是**实测的装箱**：
                --    加完"每关一首背景音乐"之后，整机 1267 LE 却要 **128~129 个 LAB**
                --    （器件的瓶颈是 127 个 LAB，不是 1270 个 LE），试过 SEED 2~16，
                --    只有 seed 5 能装进 127 LAB 但 Fmax 掉到 47.14 MHz；把这一支拿掉
                --    → **1261 LE / 127 LAB / Fmax 51.77 MHz**，装回去了。
                --    功能上没有损失（题目没要求这个提示音），取舍记在 docs/05 §1.4；
                --    将来腾出面积可以照这行加回来（`SND_TIME` 常量仍留在 puzzle_pkg）。

                -- ---- (2) 保持 + 输出：事件码直接**写进输出寄存器**并保持 2 个旋律步 ----
                -- ⚠️ 面积：这里**没有**单独的 `snd_lat` 寄存器 —— 输出 `sound_p` 本身
                --    就是寄存器，保持期内不赋值即自动保持（少 4 个 FF + 一个 4 位 2:1 mux，
                --    实测见 docs/05 §1）。
                --    ⚠️ 对局默认码 = **按关卡选的背景音乐**（第 15 工作阶段）：
                --       码 = `"10" & lvl3 & level`（见下面 S_PLAYING 那一行）→
                --       第一关 1000 / 第二关 1001 / 第三关 **1011**。
                --       两个位直接来自既有寄存器，**纯拼线、0 逻辑单元**。
                --       为了让这三位正好等于 `"10" & lvl3 & level`，码表把第三关的曲子
                --       放在 1011、旋转音挪到 1010（`puzzle_pkg` 里有详细说明）。
                --       ⚠️ 本条注释曾经错误地描述成一个**被放弃的中间方案**
                --       （`"10" & lvl3 & (level and not lvl3)`，多一级 AND-NOT）：
                --       那个版本**能装下但 Fmax 掉到 48.41 MHz**（不符 50 MHz），
                --       另一个"把轨迹位拍进 2 位寄存器"的版本要 1272 LE，都否决了；
                --       最终采用"改码表 + 纯拼线"。**收尾审查时按实现改正了这条注释。**
                if (evc /= SND_NONE) then
                    sound_p  <= evc;
                    snd_hold <= "10";
                elsif (snd_hold /= 0) then
                    if (i_tick_4hz = '1') then
                        snd_hold <= snd_hold - 1;
                    end if;
                    -- sound_p 保持：这是寄存器的"不赋值即保持"语义，不是遗漏
                else
                    case st is
                        when S_SELF_TEST => sound_p <= SND_SELF;     -- POST 单声短鸣
                        when S_PREVIEW   => sound_p <= SND_PREVIEW;  -- "准备"提示
                        -- ⭐ 第 15 工作阶段（每关一首背景音乐）：**纯拼线**，
                        --    码 = "10" & lvl3 & level → 第一关 1000 / 第二关 1001 /
                        --    第三关 1011。两个位直接来自既有寄存器，**0 逻辑单元**。
                        when S_PLAYING   => sound_p <= "10" & lvl3 & level;
                        when S_WIN       => sound_p <= SND_WIN;      -- 胜利号角
                        when S_FAIL      => sound_p <= SND_FAIL;     -- 游戏结束
                        when others      => sound_p <= SND_NONE;     -- 待机静音
                    end case;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 输出
    ----------------------------------------------------------------------------
    -- 键盘扫描的原始键索引在唯一一处被译码成游戏按键
    kdec <= key_of(i_key);

    o_state    <= st;
    o_level    <= level;
    o_lvl3     <= lvl3;
    o_time     <= std_logic_vector(cnt);
    o_blink    <= blink_r;
    o_go       <= req_go;
    o_sel      <= sel_r;
    o_conf     <= conf_r;
    o_move     <= move_r;
    o_up       <= up_r;
    o_down     <= down_r;
    o_left     <= left_r;
    o_right    <= right_r;
    o_rot      <= rot_r;
    o_sound    <= sound_p;

end architecture rtl;
