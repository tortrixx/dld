-- ============================================================================
--  game_fsm  ——  主状态机：游戏流程、倒计时、关卡切换
--  所属子系统：S3（游戏控制）
--
--  本模块只掌管"时间"与"决策"，不掌管任何坐标；所有空间问题由
--  puzzle_ctrl 回答。
--
--  状态流程：
--      SW7=0               全系统熄灭
--      S_SELF_TEST         自检约 2 s，2 Hz 闪烁（B1）
--      S_IDLE              DISP7=5，DISP0=关卡号（B2、B3）
--        --start-->        S_PREVIEW
--      S_PREVIEW           显示完整图案，倒计时在 DISP7（B4）
--        --倒计时结束-->   散落零片，进入 S_PLAYING
--      S_PLAYING           第一关 30 s / 第二关 40 s / 第三关 60 s
--                          select 循环选择，方向键移动，confirm 锁定
--                          全部锁定且画面正确 -> 下一关或 S_WIN
--                          全部锁定但位置错误，或超时 -> S_FAIL
--      S_WIN / S_FAIL      显示结算画面；start 开始新一局（B11）
--
--  start 在对局进行中同样有效，这就是 B11"随时重新开始"。
--
--  三关用两位信息表示：
--      level='0'             第一关
--      level='1', lvl3='0'   第二关（图案固定）
--      level='1', lvl3='1'   第三关（图案随机）
--  不把 level 直接加宽成 2 位，是因为那会在 piece_rom / pattern_rom /
--  puzzle_ctrl 前各插一级比较器，在接近满占用的器件上明显压缩时序余量。
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
        i_tick_4hz : in  std_logic;                      -- 翻转它得到 2 Hz 方波
        i_press    : in  std_logic;                      -- 单拍：有一个按键被接受
        i_key      : in  std_logic_vector(3 downto 0);   -- 被接受的按键码
        o_sel      : out std_logic;                      -- 单拍：循环切换选择
        o_move     : out std_logic;                      -- 单拍：移动请求
        o_conf     : out std_logic;                      -- 单拍：锁定请求
        o_go       : out std_logic;                      -- 散落请求：电平握手
        o_up       : out std_logic;
        o_down     : out std_logic;
        o_left     : out std_logic;
        o_right    : out std_logic;
        o_rot      : out std_logic;                      -- 90° 旋转请求（1 拍）
        o_level    : out std_logic;                      -- '0' = 第一关，'1' = 第二/三关
        o_lvl3     : out std_logic;                      -- '1' = 第三关
        o_state    : out std_logic_vector(2 downto 0);   -- state_t
        o_time     : out std_logic_vector(5 downto 0);   -- 倒计时秒数
        o_blink    : out std_logic;                      -- 2 Hz 闪烁标志
        i_solved   : in  std_logic;                      -- 来自 puzzle_ctrl
        i_all_lock : in  std_logic;                      -- 来自 puzzle_ctrl
        i_shuf_busy: in  std_logic;                      -- 来自 puzzle_ctrl
        o_sound    : out std_logic_vector(3 downto 0)    -- 音效选择码
    );
end entity game_fsm;

architecture rtl of game_fsm is

    ----------------------------------------------------------------------------
    -- 按键映射表 —— 把键盘索引变成游戏按键的唯一一处。
    --
    -- 键盘扫描上报 4*row + col，其中 row 0 是最下面一行，col 0 是最左列。
    -- 板上的按键按从左到右、从上到下印成 KEY1..KEY16：
    --
    --            COL0    COL1     COL2       COL3
    --   ROW3     KEY1    KEY2     KEY3       KEY4
    --   ROW2     KEY5    KEY6     KEY7[UP]   KEY8[ROT]
    --   ROW1     KEY9    KEY10    KEY11      KEY12
    --            ...    [LEFT]   [CONFIRM]  [RIGHT]
    --   ROW0     KEY13   KEY14    KEY15      KEY16
    --            (无)   [START]  [DOWN]     [SELECT]
    --
    -- 七个控制键集中在右下角的 3x3 区块，方向键按标准十字排列
    -- （中心 = 确认），与数字小键盘一致；【旋转】在【上】的右边。
    --
    -- 索引 0 不可用：没有按键时扫描器上报 K_NONE（"0000"），无法与
    -- KEY13 区分，因此绝不能给它分配功能。
    ----------------------------------------------------------------------------
    function key_of(idx : std_logic_vector(3 downto 0))
        return std_logic_vector is
    begin
        case idx is
            when "0001" => return K_START;    -- KEY14
            when "0011" => return K_SELECT;   -- KEY16
            when "1010" => return K_UP;       -- KEY7
            when "0010" => return K_DOWN;     -- KEY15
            when "0101" => return K_LEFT;     -- KEY10
            when "0111" => return K_RIGHT;    -- KEY12
            when "0110" => return K_CONFIRM;  -- KEY11
            when "1011" => return K_ROT;      -- KEY8
            when others => return K_NONE;     -- 含 "0000" = 无按键（KEY13）
        end case;
    end function;

    signal st      : state_t := S_SELF_TEST;
    signal level   : std_logic := '0';
    signal lvl3    : std_logic := '0';
    signal cnt     : unsigned(5 downto 0) := (others => '0');

    -- 交给 puzzle_ctrl 的命令脉冲
    signal req_go  : std_logic := '0';
    signal move_r  : std_logic := '0';

    signal up_r, down_r, left_r, right_r : std_logic := '0';
    signal rot_r : std_logic := '0';
    signal sel_r, conf_r : std_logic := '0';
    signal sound_p : std_logic_vector(3 downto 0) := SND_NONE;
    -- 瞬时音效的保持计数器：单拍脉冲必须保持至少一个旋律步才听得见
    signal snd_hold : unsigned(1 downto 0) := (others => '0');
    -- 2 Hz 方波：在 4 Hz 节拍上翻转
    signal blink_r : std_logic := '0';
    signal kdec    : std_logic_vector(3 downto 0) := K_NONE;  -- 译码后的游戏按键
    signal go_done : std_logic := '0';   -- 本局已经请求过散落

    -- 判决必须等本局的散落跑过之后才生效。
    -- 引擎的 locked/pos 只由散落清零，否则刚进对局的一两拍里看到的
    -- 还是上一局的残留状态，会出现"一开局就过关/判负"。
    signal shuf_seen : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- 倒计时 / 状态寄存器
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                st    <= S_SELF_TEST;
                level <= '0';
                lvl3  <= '0';
                cnt   <= to_unsigned(T_SELFTEST_T4, 6);
            elsif (i_sw = '0') then
                -- B1：开关关闭时系统停在序列起点，重新打开时总是从头
                -- 显示一次自检 / 待机，而不是接着上一局继续。
                st    <= S_SELF_TEST;
                level <= '0';
                lvl3  <= '0';
                cnt   <= to_unsigned(T_SELFTEST_T4, 6);
            else
                case st is

                    -- 自检：数 8 个 250 ms 节拍（约 2 s）。
                    -- 倒计数可直接复用对局阶段的减法器与比较器。
                    when S_SELF_TEST =>
                        if (i_tick_4hz = '1') then
                            if (cnt = 0) then
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
                                -- 预览结束，装载本关时限。
                                -- 倒计时按自由走的 1 Hz 节拍递减，而预览入口
                                -- 由按键触发，因此预览窗口为 (T_PREVIEW-1, T_PREVIEW] s；
                                -- 对局限时是在预览结束的节拍上装载的，与节拍对齐，
                                -- 窗口恰为 T_LEVEL* 秒。
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
                                st <= S_WIN;               -- 最后一关完成
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
                        -- 6 个状态已全部枚举；兜底同样装载自检初值，
                        -- 避免 cnt 停在别的值导致自检窗口长度不定。
                        st  <= S_SELF_TEST;
                        cnt <= to_unsigned(T_SELFTEST_T4, 6);
                end case;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 命令译码：给 puzzle_ctrl 的按键单拍脉冲。
    --   select  -> 循环切换选中的零片（B6）
    --   confirm -> 锁定选中的零片（B8）
    --   方向键  -> 移动选中的零片（B7）
    --   旋转    -> 顺时针 90°（A4）
    -- 只有在真正对局过程中才接受这些命令。
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
                        when K_ROT     => rot_r   <= '1';
                        when others    => null;
                    end case;
                end if;

                -- 散落请求：进入对局时置起，保持到引擎开始忙为止。
                -- 用请求 / 应答握手而不是单拍脉冲，散落就不会被漏掉。
                -- go_done 保证每局只请求一次；否则引擎一回到空闲就会
                -- 被反复重新散落，按键永远无法生效。
                if (st /= S_PLAYING) then
                    req_go  <= '0';
                    go_done <= '0';                -- 为下一局重新武装
                elsif (req_go = '0') and (go_done = '0') and (i_shuf_busy = '0') then
                    req_go <= '1';                 -- 发出一次请求
                elsif (i_shuf_busy = '1') then
                    req_go  <= '0';                -- 被引擎接受
                    go_done <= '1';                -- 本局不再请求
                end if;

                -- 判决的前置条件：本局已经看到过散落的忙态
                if (st /= S_PLAYING) then
                    shuf_seen <= '0';
                elsif (i_shuf_busy = '1') then
                    shuf_seen <= '1';
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 2 Hz 闪烁标志：在 4 Hz 节拍上翻转（500 ms 一周期，50% 占空）。
    -- tick 是一个时钟宽的脉冲，必须翻转成方波才能驱动显示。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                blink_r <= '0';
            elsif (i_tick_4hz = '1') then
                blink_r <= not blink_r;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 音效选择（提高要求 A1）。
    --
    -- 两类声音：
    --   · 状态音：按状态直接选码（自检 / 预览 / 背景音乐 / 胜利 / 失败）；
    --   · 瞬时事件：过关、拼错。蜂鸣器一拍只有一个音，单拍脉冲只发出
    --     二十纳秒的毛刺，听不见，因此用 snd_hold 保持 2 个旋律步。
    --
    -- 背景音乐码由 "10" & lvl3 & level 直接拼出，不增加逻辑单元：
    --   第一关 1000 / 第二关 1001 / 第三关 1011。
    --
    -- 对局中不发出按键音（移动、选择、旋转、确认均静音），
    -- 只保留背景音乐与胜负音效，避免打断音乐。
    ----------------------------------------------------------------------------
    process (i_clk)
        variable evc : std_logic_vector(3 downto 0);
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sound_p  <= SND_NONE;
                snd_hold <= (others => '0');
            else
                -- (1) 本拍的瞬时事件码
                if (st /= S_PLAYING) then
                    evc := SND_NONE;
                elsif (i_solved = '1') and (shuf_seen = '1') then
                    evc := SND_CLEAR;                    -- 过关（上行）
                elsif (i_all_lock = '1') and (shuf_seen = '1') then
                    evc := SND_WRONG;                    -- 锁满了但画面不对（下行）
                else
                    evc := SND_NONE;
                end if;

                -- (2) 保持 + 输出：事件码直接写进输出寄存器并保持 2 个旋律步
                if (evc /= SND_NONE) then
                    sound_p  <= evc;
                    snd_hold <= "10";
                elsif (snd_hold /= 0) then
                    if (i_tick_4hz = '1') then
                        snd_hold <= snd_hold - 1;
                    end if;
                    -- sound_p 保持：寄存器的"不赋值即保持"语义
                else
                    case st is
                        when S_SELF_TEST => sound_p <= SND_SELF;     -- POST 单声短鸣
                        when S_PREVIEW   => sound_p <= SND_PREVIEW;  -- "准备"提示
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
