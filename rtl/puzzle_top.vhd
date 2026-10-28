library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

-- ============================================================================
--  puzzle_top  ——  整机顶层
--  题目 4：简易拼图游戏（数字电路与逻辑设计实验）
--  器件：Altera MAX II EPM1270T144C5   工具：Quartus II 9.1   语言：VHDL
--
--  本文件是唯一绑定引脚的文件（与 quartus/puzzle.qsf 一起）。
--  所有子模块都用显式 component 声明与具名端口关联例化：
--  具名映射里漏写或写错端口是编译错误，可避免悬空信号。
--
--  按功能划分为 7 个模块（与 docs/report/fig_overview.png 一致）：
--
--     模块 1  时钟与节拍       clk_gen
--     模块 2  键盘输入         keypad_scan
--     模块 3  游戏控制         game_fsm
--     模块 4  拼图核心         puzzle_ctrl
--     模块 5  显示系统         disp_format / seg_scan / dot_matrix_scan
--     模块 6  图案与随机数据   piece_rom / pattern_rom / rng_lfsr
--     模块 7  音效输出         buzzer_ctrl
--
--  共 11 个子模块 + 本顶层。
--
--  点阵如何驱动：
--  引擎（puzzle_ctrl）内部有整帧的 64 位帧寄存器 frame_r / frame_g
--  （每色 64 位、共 128 个触发器），经 o_rowr / o_rowg 送到本文件的
--  eng_fr / eng_fg。本文件按行计数器 mrow 从帧里切出当前行（8 红 + 8 绿），
--  再按游戏状态选择显示内容，最后由 dot_matrix_scan 驱动物理行。
--  每拍的组合计算路径只有 8 位宽，这是引擎能装进 EPM1270 的关键。
--
--  硬件说明：PIN_38..45 由点阵绿色列与 LD8..LD15 共用，
--  而 PIN_137..144 由 LD8..LD15 与 VGA 端口共用。驱动这些 LED
--  会让点阵失去绿色，而 B6"选中零片变绿"正依赖绿色，
--  因此本设计刻意不使用这 16 个 LED。
-- ============================================================================

entity puzzle_top is
    port (
        clk      : in  std_logic;                       -- PIN_18 板载 50 MHz 主时钟
        sw7      : in  std_logic;                       -- PIN_125 系统总使能（上拨 = '1'）
        btn      : in  std_logic;                       -- PIN_61 BTN0 复位（按下 = '1'）
        kp_row   : in  std_logic_vector(3 downto 0);    -- PIN_111..114 键盘行输入
        kp_col   : out std_logic_vector(3 downto 0);    -- PIN_117..120 键盘列驱动
        dot_row  : out std_logic_vector(7 downto 0);    -- PIN_8,7,6,5,4,3,2,1 行选通（低有效）
        dot_colr : out std_logic_vector(7 downto 0);    -- PIN_22,21,16,15,14,13,12,11 红列
        dot_colg : out std_logic_vector(7 downto 0);    -- PIN_45,44,43,42,41,40,39,38 绿列
        seg      : out std_logic_vector(7 downto 0);    -- PIN_62,59,58,57,55,53,52,51 段选（高）
        cat      : out std_logic_vector(7 downto 0);    -- PIN_63,66,67,68,69,70,30,31 位选（低）
        buzz     : out std_logic                        -- PIN_60 蜂鸣器
    );
end entity puzzle_top;

architecture rtl of puzzle_top is

    -- 模块 1：时钟与节拍（clk_gen）
    component clk_gen
        port (
            i_clk      : in  std_logic;
            i_btn      : in  std_logic;
            o_rst      : out std_logic;
            o_tick_1k  : out std_logic;
            o_tick_200 : out std_logic;
            o_tick_100 : out std_logic;
            o_tick_2hz : out std_logic;
            o_tick_4hz : out std_logic;
            o_tick_1hz : out std_logic;
            o_tick_40  : out std_logic
        );
    end component;

    -- 模块 2：键盘输入（keypad_scan）
    component keypad_scan
        port (
            i_clk     : in  std_logic;
            i_rst     : in  std_logic;
            i_tick    : in  std_logic;
            i_row     : in  std_logic_vector(3 downto 0);
            o_col     : out std_logic_vector(3 downto 0);
            o_key     : out std_logic_vector(3 downto 0);
            o_press   : out std_logic;
            o_release : out std_logic;
            o_raw     : out std_logic_vector(3 downto 0)
        );
    end component;

    -- 模块 3：游戏控制（game_fsm）
    component game_fsm
        port (
            i_clk       : in  std_logic;
            i_rst       : in  std_logic;
            i_sw        : in  std_logic;
            i_tick_1hz  : in  std_logic;
            i_tick_4hz  : in  std_logic;
            i_press     : in  std_logic;
            i_key       : in  std_logic_vector(3 downto 0);
            o_sel       : out std_logic;
            o_move      : out std_logic;
            o_conf      : out std_logic;
            o_go        : out std_logic;
            o_up        : out std_logic;
            o_down      : out std_logic;
            o_left      : out std_logic;
            o_right     : out std_logic;
            o_rot       : out std_logic;
            o_level     : out std_logic;
            o_lvl3      : out std_logic;
            o_state     : out std_logic_vector(2 downto 0);
            o_time      : out std_logic_vector(5 downto 0);
            o_blink     : out std_logic;
            i_solved    : in  std_logic;
            i_all_lock  : in  std_logic;
            i_shuf_busy : in  std_logic;
            o_sound     : out std_logic_vector(3 downto 0)
        );
    end component;

    -- 模块 4：拼图核心（puzzle_ctrl）
    component puzzle_ctrl
        port (
            i_clk     : in  std_logic;
            i_rst     : in  std_logic;
            i_tick    : in  std_logic;
            rnd_step  : out std_logic;
            rnd_val   : in  std_logic_vector(7 downto 0);
            i_level   : in  std_logic;
            i_pat     : in  std_logic_vector(1 downto 0);
            i_sh0     : in  std_logic_vector(63 downto 0);
            i_sh1     : in  std_logic_vector(63 downto 0);
            i_sh2     : in  std_logic_vector(63 downto 0);
            i_sh3     : in  std_logic_vector(63 downto 0);
            i_h0      : in  std_logic_vector(2 downto 0);
            i_h1      : in  std_logic_vector(2 downto 0);
            i_h2      : in  std_logic_vector(2 downto 0);
            i_h3      : in  std_logic_vector(2 downto 0);
            i_w0      : in  std_logic_vector(2 downto 0);
            i_w1      : in  std_logic_vector(2 downto 0);
            i_w2      : in  std_logic_vector(2 downto 0);
            i_w3      : in  std_logic_vector(2 downto 0);
            i_target  : in  std_logic_vector(63 downto 0);
            i_go      : in  std_logic;
            i_select  : in  std_logic;
            i_move    : in  std_logic;
            i_confirm : in  std_logic;
            i_rot     : in  std_logic;
            i_up      : in  std_logic;
            i_down    : in  std_logic;
            i_left    : in  std_logic;
            i_right   : in  std_logic;
            o_ori     : out std_logic_vector(7 downto 0);
            o_solved  : out std_logic;
            o_all_lock: out std_logic;
            o_busy    : out std_logic;
            o_sel_idx : out std_logic_vector(1 downto 0);
            o_pos     : out std_logic_vector(31 downto 0);
            o_lock    : out std_logic_vector(3 downto 0);
            o_scanrow : out std_logic_vector(2 downto 0);
            o_rowr    : out std_logic_vector(63 downto 0);
            o_rowg    : out std_logic_vector(63 downto 0)
        );
    end component;

    -- 模块 5：显示系统（disp_format / seg_scan / dot_matrix_scan）
    component disp_format
        port (
            i_state : in  std_logic_vector(2 downto 0);
            i_level : in  std_logic;
            i_lvl3  : in  std_logic;
            i_time  : in  std_logic_vector(5 downto 0);
            i_blink : in  std_logic;
            o_data  : out std_logic_vector(31 downto 0);
            o_blank : out std_logic_vector(7 downto 0)
        );
    end component;

    component seg_scan
        port (
            i_clk    : in  std_logic;
            i_rst    : in  std_logic;
            i_tick   : in  std_logic;
            i_en     : in  std_logic;
            i_data   : in  std_logic_vector(31 downto 0);
            i_blank  : in  std_logic_vector(7 downto 0);
            i_raw_en : in  std_logic;
            i_raw    : in  std_logic_vector(7 downto 0);
            o_seg    : out std_logic_vector(7 downto 0);
            o_cat    : out std_logic_vector(7 downto 0)
        );
    end component;

    component dot_matrix_scan
        port (
            i_clk   : in  std_logic;
            i_rst   : in  std_logic;
            i_en    : in  std_logic;
            i_row   : in  std_logic_vector(2 downto 0);
            i_colr  : in  std_logic_vector(7 downto 0);
            i_colg  : in  std_logic_vector(7 downto 0);
            o_row   : out std_logic_vector(7 downto 0);
            o_colr  : out std_logic_vector(7 downto 0);
            o_colg  : out std_logic_vector(7 downto 0)
        );
    end component;

    -- 模块 6：图案与随机数据（piece_rom / pattern_rom / rng_lfsr）
    component piece_rom
        port (
            i_level : in  std_logic;
            o_mask  : out mask_arr_t;
            o_h     : out dim_arr_t;
            o_w     : out dim_arr_t;
            o_n     : out std_logic_vector(2 downto 0)
        );
    end component;

    component pattern_rom
        port (
            i_level : in  std_logic;
            i_pat   : in  std_logic_vector(1 downto 0);
            o_mask  : out std_logic_vector(63 downto 0)
        );
    end component;

    component rng_lfsr
        port (
            i_clk  : in  std_logic;
            i_rst  : in  std_logic;
            i_step : in  std_logic;
            o_val  : out std_logic_vector(7 downto 0)
        );
    end component;

    -- 模块 7：音效输出（buzzer_ctrl）
    component buzzer_ctrl
        port (
            i_clk  : in  std_logic;
            i_rst  : in  std_logic;
            i_en   : in  std_logic;
            i_sel  : in  std_logic_vector(3 downto 0);
            i_t4   : in  std_logic;
            o_buzz : out std_logic
        );
    end component;

    ----------------------------------------------------------------------------
    -- 内部连线
    ----------------------------------------------------------------------------
    signal rst      : std_logic;
    signal t_1k     : std_logic;
    signal t_200    : std_logic;
    signal t_100    : std_logic;
    signal t_4hz    : std_logic;
    signal t_1hz    : std_logic;
    signal t_40     : std_logic;

    signal key      : std_logic_vector(3 downto 0);
    signal press    : std_logic;
    signal release  : std_logic;
    signal kp_raw   : std_logic_vector(3 downto 0);

    signal sel, move, conf, go : std_logic;
    signal mv_up, mv_dn, mv_lf, mv_rt : std_logic;
    signal mv_rot   : std_logic;
    signal level    : std_logic;
    signal lvl3     : std_logic;
    signal state    : std_logic_vector(2 downto 0);
    signal gtime    : std_logic_vector(5 downto 0);
    signal gblink   : std_logic;
    signal sound    : std_logic_vector(3 downto 0);

    signal solved   : std_logic;
    signal all_lock : std_logic;
    signal shuf_busy: std_logic;
    signal sel_idx  : std_logic_vector(1 downto 0);
    signal pos_dbg  : std_logic_vector(31 downto 0);
    signal lock_dbg : std_logic_vector(3 downto 0);
    signal scanrow  : std_logic_vector(2 downto 0);

    signal rnd_val  : std_logic_vector(7 downto 0);
    signal rnd_step : std_logic;

    signal shapes   : mask_arr_t;
    signal shape_h  : dim_arr_t;
    signal shape_w  : dim_arr_t;
    signal piece_n  : std_logic_vector(2 downto 0);
    signal tgt_mask : std_logic_vector(63 downto 0);

    -- 图案库选择：进入预览时锁存（第二关固定 PAT3，第三关随机）
    signal pat_sel  : std_logic_vector(1 downto 0) := L2_FIXED_PAT;
    signal state_q  : std_logic_vector(2 downto 0) := S_SELF_TEST;  -- 上一拍的状态

    -- 引擎输出：每个颜色平面一帧完整的 64 位数据
    signal eng_fr   : std_logic_vector(63 downto 0);
    signal eng_fg   : std_logic_vector(63 downto 0);

    -- 最终送给点阵驱动的行
    signal mat_r    : std_logic_vector(7 downto 0);
    signal mat_g    : std_logic_vector(7 downto 0);

    -- 结算画面闪示：数 2 Hz 半周期，数满后常亮
    signal endflash_cnt : unsigned(2 downto 0) := (others => '0');
    signal endflash_on  : std_logic := '0';

    -- 倒计时告急时的目标提示（"幽灵"）
    signal hint_on    : std_logic := '0';
    signal hint_blink : std_logic := '0';
    signal hint_mask  : std_logic_vector(7 downto 0) := (others => '0');

    -- 点阵驱动当前点亮的行
    signal mrow      : unsigned(2 downto 0) := (others => '0');
    signal disp_data  : std_logic_vector(31 downto 0);
    signal disp_blank : std_logic_vector(7 downto 0);

    -- 特殊状态的行数据源
    signal win_row  : std_logic_vector(7 downto 0);
    signal prev_row : std_logic_vector(7 downto 0);  -- 目标图案的行
    signal fail_row : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- 点阵行计数器：1 kHz 推进，8 行一轮 = 8 ms，即 125 Hz 刷新率。
    -- 引擎的行渲染也接同一个 tick，避免"扫描的行"与"渲染的行"不同源
    -- 造成错行。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                mrow <= (others => '0');
            elsif (t_1k = '1') then
                mrow <= mrow + 1;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 图案选择点：每次进入 S_PREVIEW 的那一拍锁存一次，图案必须在
    -- 预览开始前定下来。
    --   第三关（lvl3='1'）-> 取 rnd_val 低 2 位，四幅库随机
    --   第二关（lvl3='0'）-> 固定 L2_FIXED_PAT（PAT3）
    --   第一关            -> pattern_rom 忽略 i_pat，恒为图 4-1
    -- 重开一局第三关时，上一局的散落已推进 LFSR，图案通常会变化。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                state_q <= S_SELF_TEST;
                pat_sel <= L2_FIXED_PAT;
            else
                state_q <= state;
                if (state = S_PREVIEW) and (state_q /= S_PREVIEW) then
                    if (lvl3 = '1') then
                        pat_sel <= rnd_val(1 downto 0);   -- 第三关：随机
                    else
                        pat_sel <= L2_FIXED_PAT;          -- 第二关：固定
                    end if;
                end if;
            end if;
        end if;
    end process;

    -- 子模块例化（按信号流顺序；模块编号见上面的组件声明）

    -- 时钟、tick、复位
    u_clk : clk_gen
        port map (
            i_clk      => clk,
            i_btn      => btn,
            o_rst      => rst,
            o_tick_1k  => t_1k,
            o_tick_200 => t_200,
            o_tick_100 => t_100,
            o_tick_2hz => open,          -- 游戏不使用 2 Hz 脉冲
            o_tick_4hz => t_4hz,
            o_tick_1hz => t_1hz,
            o_tick_40  => t_40
        );

    -- 键盘
    u_keypad : keypad_scan
        port map (
            i_clk     => clk,
            i_rst     => rst,
            i_tick    => t_200,
            i_row     => kp_row,
            o_col     => kp_col,
            o_key     => key,
            o_press   => press,
            o_release => release,
            o_raw     => kp_raw
        );

    -- 主状态机
    u_fsm : game_fsm
        port map (
            i_clk       => clk,
            i_rst       => rst,
            i_sw        => sw7,
            i_tick_1hz  => t_1hz,
            i_tick_4hz  => t_4hz,
            i_press     => press,
            i_key       => key,
            o_sel       => sel,
            o_move      => move,
            o_conf      => conf,
            o_go        => go,
            o_up        => mv_up,
            o_down      => mv_dn,
            o_left      => mv_lf,
            o_right     => mv_rt,
            o_rot       => mv_rot,
            o_level     => level,
            o_state     => state,
            o_time      => gtime,
            o_blink     => gblink,
            i_solved    => solved,
            i_all_lock  => all_lock,
            i_shuf_busy => shuf_busy,
            o_sound     => sound,
            o_lvl3      => lvl3
        );

    -- 零片形状库与完整图案
    u_pieces : piece_rom
        port map (
            i_level => level,
            o_mask  => shapes,
            o_h     => shape_h,
            o_w     => shape_w,
            o_n     => piece_n
        );

    u_pattern : pattern_rom
        port map (
            i_level => level,
            i_pat   => pat_sel,
            o_mask  => tgt_mask
        );

    -- 随机数源
    u_rng : rng_lfsr
        port map (
            i_clk  => clk,
            i_rst  => rst,
            i_step => rnd_step,
            o_val  => rnd_val
        );

    -- 拼图核心
    --
    -- 引擎始终拿到真实的目标图案：成功判据是"拼好的画面 == 目标图案"，
    -- 对局中把 i_target 置零会让判据无法满足。引擎内部不画目标虚影，
    -- 因此零片不会被红色轮廓遮住；预览态由本文件直接切目标掩码显示。
    u_puzzle : puzzle_ctrl
        port map (
            i_clk     => clk,
            i_rst     => rst,
            i_tick    => t_1k,          -- 行渲染节拍 1 kHz；
                                        -- 一行 npc+2 拍、8 行一帧 ->
                                        -- 内容更新率约 25 / 21 Hz，
                                        -- 点阵扫描率则是 125 Hz
            rnd_step  => rnd_step,
            rnd_val   => rnd_val,
            i_level   => level,
            i_pat     => pat_sel,
            i_sh0     => shapes(0),
            i_sh1     => shapes(1),
            i_sh2     => shapes(2),
            i_sh3     => shapes(3),
            i_h0      => shape_h(0),
            i_h1      => shape_h(1),
            i_h2      => shape_h(2),
            i_h3      => shape_h(3),
            i_w0      => shape_w(0),
            i_w1      => shape_w(1),
            i_w2      => shape_w(2),
            i_w3      => shape_w(3),
            i_target  => tgt_mask,
            i_go      => go,
            i_select  => sel,
            i_move    => move,
            i_confirm => conf,
            i_rot     => mv_rot,
            i_up      => mv_up,
            i_down    => mv_dn,
            i_left    => mv_lf,
            i_right   => mv_rt,
            o_ori     => open,          -- 仅供模块级仿真观察
            o_solved  => solved,
            o_all_lock=> all_lock,
            o_busy    => shuf_busy,
            o_sel_idx => sel_idx,
            o_pos     => pos_dbg,
            o_lock    => lock_dbg,
            o_scanrow => scanrow,
            o_rowr    => eng_fr,
            o_rowg    => eng_fg
        );

    -- 数码管内容 + 扫描
    u_disp : disp_format
        port map (
            i_state => state,
            i_level => level,
            i_lvl3  => lvl3,
            i_time  => gtime,
            i_blink => gblink,
            o_data  => disp_data,
            o_blank => disp_blank
        );

    u_seg : seg_scan
        port map (
            i_clk    => clk,
            i_rst    => rst,
            i_tick   => t_1k,           -- 1 kHz：8 位轮一遍 = 8 ms，125 Hz/位
            i_en     => sw7,
            i_data   => disp_data,
            i_blank  => disp_blank,
            i_raw_en => '0',
            i_raw    => (others => '0'),
            o_seg    => seg,
            o_cat    => cat
        );

    ----------------------------------------------------------------------------
    -- 从 64 位图案中取出某一行。
    -- 位下标 = 8*row + col，第 0 行在最上方，因此逻辑第 0 行是位 7..0。
    -- 结算画面与预览图案都是整幅常量，不需要由引擎拼装。
    ----------------------------------------------------------------------------
    with std_logic_vector(mrow) select
        win_row <= WIN_MASK( 7 downto  0) when "000",
                   WIN_MASK(15 downto  8) when "001",
                   WIN_MASK(23 downto 16) when "010",
                   WIN_MASK(31 downto 24) when "011",
                   WIN_MASK(39 downto 32) when "100",
                   WIN_MASK(47 downto 40) when "101",
                   WIN_MASK(55 downto 48) when "110",
                   WIN_MASK(63 downto 56) when others;

    with std_logic_vector(mrow) select
        prev_row <= tgt_mask(7 downto 0)   when "000",
                    tgt_mask(15 downto 8)  when "001",
                    tgt_mask(23 downto 16) when "010",
                    tgt_mask(31 downto 24) when "011",
                    tgt_mask(39 downto 32) when "100",
                    tgt_mask(47 downto 40) when "101",
                    tgt_mask(55 downto 48) when "110",
                    tgt_mask(63 downto 56) when others;

    with std_logic_vector(mrow) select
        fail_row <= FAIL_MASK( 7 downto  0) when "000",
                    FAIL_MASK(15 downto  8) when "001",
                    FAIL_MASK(23 downto 16) when "010",
                    FAIL_MASK(31 downto 24) when "011",
                    FAIL_MASK(39 downto 32) when "100",
                    FAIL_MASK(47 downto 40) when "101",
                    FAIL_MASK(55 downto 48) when "110",
                    FAIL_MASK(63 downto 56) when others;

    ----------------------------------------------------------------------------
    -- 倒计时告急提示（"幽灵"）。
    --
    -- 倒计时 <= 10 秒时，把目标图案里尚未被零片覆盖的格子显示出来，
    -- 并以 2 Hz 闪烁。拼对的格子被零片覆盖，幽灵自然消失，
    -- 因此它同时是"还差哪几格"的进度提示。
    --
    -- 用绿色闪烁而不是换一种静态颜色：双色点阵每个点只有
    -- 灭 / 红 / 绿 / 黄四种状态，而对局中红（普通零片）、绿（选中零片）、
    -- 黄（锁定零片）已经全部被占用，只能再加一个时间维度来区分。
    ----------------------------------------------------------------------------
    hint_on    <= '1' when (unsigned(gtime) <= 10) else '0';
    hint_blink <= hint_on and gblink;
    hint_mask  <= (others => hint_blink);

    ----------------------------------------------------------------------------
    -- 结算画面闪示：先闪 1 s（4 个 250 ms 半周期），然后常亮，
    -- 兼顾"抓注意力"和"远距离读图"。离开 WIN/FAIL 立刻复位。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                endflash_cnt <= (others => '0');
                endflash_on  <= '0';
            elsif (state /= S_WIN) and (state /= S_FAIL) then
                endflash_cnt <= (others => '0');
                endflash_on  <= '0';
            elsif (t_4hz = '1') then
                if (endflash_cnt = 3) then
                    endflash_on <= '1';          -- 4 个 250 ms 半周期后：常亮
                else
                    endflash_cnt <= endflash_cnt + 1;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 各状态下的点阵内容：
    --   SELF_TEST  整屏黄色，2 Hz 闪烁（B1）
    --   IDLE       全暗（B2）
    --   PREVIEW    完整目标图案（B4）
    --   PLAYING    引擎画面 + 告急提示
    --   WIN        绿色粗对勾，先闪后常亮
    --   FAIL       红色叉，先闪后常亮
    --
    -- 敏感表必须包含 hint_mask：本进程在 S_PLAYING 分支读它。
    ----------------------------------------------------------------------------
    process (state, gblink, endflash_on, mrow, eng_fr, eng_fg, win_row, fail_row, prev_row,
             hint_mask)
        variable lv  : std_logic;
        variable ev  : std_logic;        -- 结算画面的亮度：闪烁相位或常亮
        variable rw  : std_logic_vector(7 downto 0);
        variable gw  : std_logic_vector(7 downto 0);
    begin
        lv := gblink;
        ev := gblink or endflash_on;

        -- 从 64 位帧中切出当前行（帧内第 0 行在最高 8 位）
        case to_integer(mrow) is
            when 0      => rw := eng_fr(63 downto 56); gw := eng_fg(63 downto 56);
            when 1      => rw := eng_fr(55 downto 48); gw := eng_fg(55 downto 48);
            when 2      => rw := eng_fr(47 downto 40); gw := eng_fg(47 downto 40);
            when 3      => rw := eng_fr(39 downto 32); gw := eng_fg(39 downto 32);
            when 4      => rw := eng_fr(31 downto 24); gw := eng_fg(31 downto 24);
            when 5      => rw := eng_fr(23 downto 16); gw := eng_fg(23 downto 16);
            when 6      => rw := eng_fr(15 downto 8);  gw := eng_fg(15 downto 8);
            when others => rw := eng_fr(7 downto 0);   gw := eng_fg(7 downto 0);
        end case;

        if (state = S_SELF_TEST) then
            -- 整屏黄色，2 Hz 闪烁（B1）
            mat_r <= (others => lv);
            mat_g <= (others => lv);
        elsif (state = S_IDLE) then
            -- 待机全暗。这里不能显示引擎帧：零片尚未散落，
            -- 否则它们会全部堆在锚点 (0,0)。
            mat_r <= (others => '0');
            mat_g <= (others => '0');
        elsif (state = S_PREVIEW) then
            -- 显示完整目标图案；引擎不参与。
            mat_r <= prev_row;
            mat_g <= (others => '0');
        elsif (state = S_WIN) then
            -- 绿色粗对勾：只点绿列，红列清零
            mat_r <= (others => '0');
            mat_g <= win_row and (ev & ev & ev & ev & ev & ev & ev & ev);
        elsif (state = S_FAIL) then
            -- 红色叉：只点红列，绿列清零
            mat_r <= fail_row and (ev & ev & ev & ev & ev & ev & ev & ev);
            mat_g <= (others => '0');
        else
            -- S_PLAYING：引擎画面。
            -- 绿 = 选中/锁定零片，再叠加"目标中尚未覆盖且告急"的提示；
            -- 红 = 不属于选中零片的格子。
            -- 提示项减掉 rw：已被零片盖住的格子不再画幽灵，
            -- 否则红 + 绿会变成黄色闪烁，形成假提示。
            mat_r <= rw;
            mat_g <= gw or (prev_row and (not rw) and hint_mask);
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 点阵驱动。i_row 来自本文件的行计数器 mrow，1 kHz 推进，
    -- 8 行一轮 = 125 Hz。
    ----------------------------------------------------------------------------
    u_dot : dot_matrix_scan
        port map (
            i_clk   => clk,
            i_rst   => rst,
            i_en    => sw7,
            i_row   => std_logic_vector(mrow),
            i_colr  => mat_r,
            i_colg  => mat_g,
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );

    -- 音效输出
    u_buzz : buzzer_ctrl
        port map (
            i_clk  => clk,
            i_rst  => rst,
            i_en   => sw7,
            i_sel  => sound,
            i_t4   => t_4hz,
            o_buzz => buzz
        );

end architecture rtl;
