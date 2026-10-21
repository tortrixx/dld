library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

-- ============================================================================
-- 实体名称: puzzle_top (简易拼图游戏整机顶层)
-- 适用器件: Altera MAX II EPM1270T144C5  EDA环境: Quartus II 9.1
-- 硬件引脚绑定: PIN_18(时钟), PIN_125(使能SW7), PIN_61(复位BTN0), 
--               PIN_111..114/117..120(键盘), PIN_8..1/22..11/45..38(点阵),
--               PIN_62..51/63..31(数码管), PIN_60(蜂鸣器)
-- ============================================================================
entity puzzle_top is
    port (
        clk      : in  std_logic;                       -- PIN_18 板载 50 MHz 主时钟
        sw7      : in  std_logic;                       -- PIN_125 系统总使能 (上拨='1')
        btn      : in  std_logic;                       -- PIN_61 板载 BTN0 异步复位 (低有效)
        kp_row   : in  std_logic_vector(3 downto 0);    -- PIN_114..111 矩阵键盘行输入
        kp_col   : out std_logic_vector(3 downto 0);    -- PIN_120..117 矩阵键盘列驱动
        dot_row  : out std_logic_vector(7 downto 0);    -- PIN_1..8 点阵行阳极 (高有效)
        dot_colr : out std_logic_vector(7 downto 0);    -- PIN_11..22 点阵红阴极 (低有效)
        dot_colg : out std_logic_vector(7 downto 0);    -- PIN_38..45 点阵绿阴极 (低有效)
        seg      : out std_logic_vector(7 downto 0);    -- PIN_62..51 数码管共阴段选
        cat      : out std_logic_vector(7 downto 0);    -- PIN_31..65 数码管共阴位选
        buzz     : out std_logic                        -- PIN_60 蜂鸣器驱动
    );
end entity puzzle_top;

architecture rtl of puzzle_top is

    -- 11 个子实体 Component 显式声明 (与框图完全一致)
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

    -- 内部信号
    signal rst       : std_logic;
    signal t_1k      : std_logic;
    signal t_200     : std_logic;
    signal t_100     : std_logic;
    signal t_4hz     : std_logic;
    signal t_1hz     : std_logic;
    signal t_40      : std_logic;

    signal key       : std_logic_vector(3 downto 0);
    signal press     : std_logic;
    signal release   : std_logic;
    signal kp_raw    : std_logic_vector(3 downto 0);

    signal sel, move, conf, go : std_logic;
    signal mv_up, mv_dn, mv_lf, mv_rt : std_logic;
    signal mv_rot    : std_logic;
    signal level     : std_logic;
    signal lvl3      : std_logic;
    signal state     : std_logic_vector(2 downto 0);
    signal gtime     : std_logic_vector(5 downto 0);
    signal gblink    : std_logic;
    signal sound     : std_logic_vector(3 downto 0);

    signal solved    : std_logic;
    signal all_lock  : std_logic;
    signal shuf_busy : std_logic;
    signal sel_idx   : std_logic_vector(1 downto 0);
    signal pos_dbg   : std_logic_vector(31 downto 0);
    signal lock_dbg  : std_logic_vector(3 downto 0);
    signal scanrow   : std_logic_vector(2 downto 0);

    signal rnd_val   : std_logic_vector(7 downto 0);
    signal rnd_step  : std_logic;

    signal shapes    : mask_arr_t;
    signal shape_h   : dim_arr_t;
    signal shape_w   : dim_arr_t;
    signal piece_n   : std_logic_vector(2 downto 0);
    signal tgt_mask  : std_logic_vector(63 downto 0);

    signal pat_sel   : std_logic_vector(1 downto 0) := L2_FIXED_PAT;
    signal state_q   : std_logic_vector(2 downto 0) := S_SELF_TEST;

    signal eng_fr    : std_logic_vector(63 downto 0);
    signal eng_fg    : std_logic_vector(63 downto 0);
    signal mat_r     : std_logic_vector(7 downto 0);
    signal mat_g     : std_logic_vector(7 downto 0);

    signal endflash_cnt : unsigned(2 downto 0) := (others => '0');
    signal endflash_on  : std_logic := '0';

    -- A5 倒计时告急幽灵信号
    signal hint_on    : std_logic := '0';
    signal hint_blink : std_logic := '0';
    signal hint_mask  : std_logic_vector(7 downto 0) := (others => '0');

    signal mrow       : unsigned(2 downto 0) := (others => '0');
    signal disp_data  : std_logic_vector(31 downto 0);
    signal disp_blank : std_logic_vector(7 downto 0);

    signal win_row    : std_logic_vector(7 downto 0);
    signal prev_row   : std_logic_vector(7 downto 0);
    signal fail_row   : std_logic_vector(7 downto 0);

begin

    -- 点阵行计数器 (1 kHz 推进 -> 125 Hz 帧刷新率)
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

    -- 图案库选择锁存进程 (第二关固定阶梯，第三关 LFSR 随机抽取)
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
                        pat_sel <= rnd_val(1 downto 0);
                    else
                        pat_sel <= L2_FIXED_PAT;
                    end if;
                end if;
            end if;
        end if;
    end process;

    -- 11 个子实体例化
    u_clk : clk_gen
        port map (
            i_clk => clk, i_btn => btn, o_rst => rst,
            o_tick_1k => t_1k, o_tick_200 => t_200, o_tick_100 => t_100,
            o_tick_2hz => open, o_tick_4hz => t_4hz, o_tick_1hz => t_1hz, o_tick_40 => t_40
        );

    u_keypad : keypad_scan
        port map (
            i_clk => clk, i_rst => rst, i_tick => t_200,
            i_row => kp_row, o_col => kp_col, o_key => key,
            o_press => press, o_release => release, o_raw => kp_raw
        );

    u_fsm : game_fsm
        port map (
            i_clk => clk, i_rst => rst, i_sw => sw7,
            i_tick_1hz => t_1hz, i_tick_4hz => t_4hz, i_press => press, i_key => key,
            o_sel => sel, o_move => move, o_conf => conf, o_go => go,
            o_up => mv_up, o_down => mv_dn, o_left => mv_lf, o_right => mv_rt, o_rot => mv_rot,
            o_level => level, o_lvl3 => lvl3, o_state => state,
            o_time => gtime, o_blink => gblink,
            i_solved => solved, i_all_lock => all_lock, i_shuf_busy => shuf_busy,
            o_sound => sound
        );

    u_pieces : piece_rom
        port map (
            i_level => level, o_mask => shapes, o_h => shape_h, o_w => shape_w, o_n => piece_n
        );

    u_pattern : pattern_rom
        port map (
            i_level => level, i_pat => pat_sel, o_mask => tgt_mask
        );

    u_rng : rng_lfsr
        port map (
            i_clk => clk, i_rst => rst, i_step => rnd_step, o_val => rnd_val
        );

    u_puzzle : puzzle_ctrl
        port map (
            i_clk => clk, i_rst => rst, i_tick => t_1k,
            rnd_step => rnd_step, rnd_val => rnd_val,
            i_level => level, i_pat => pat_sel,
            i_sh0 => shapes(0), i_sh1 => shapes(1), i_sh2 => shapes(2), i_sh3 => shapes(3),
            i_h0 => shape_h(0), i_h1 => shape_h(1), i_h2 => shape_h(2), i_h3 => shape_h(3),
            i_w0 => shape_w(0), i_w1 => shape_w(1), i_w2 => shape_w(2), i_w3 => shape_w(3),
            i_target => tgt_mask, i_go => go, i_select => sel, i_move => move,
            i_confirm => conf, i_rot => mv_rot, i_up => mv_up, i_down => mv_dn,
            i_left => mv_lf, i_right => mv_rt,
            o_ori => open, o_solved => solved, o_all_lock => all_lock, o_busy => shuf_busy,
            o_sel_idx => sel_idx, o_pos => pos_dbg, o_lock => lock_dbg,
            o_scanrow => scanrow, o_rowr => eng_fr, o_rowg => eng_fg
        );

    u_disp : disp_format
        port map (
            i_state => state, i_level => level, i_lvl3 => lvl3,
            i_time => gtime, i_blink => gblink,
            o_data => disp_data, o_blank => disp_blank
        );

    u_seg : seg_scan
        port map (
            i_clk => clk, i_rst => rst, i_tick => t_1k, i_en => sw7,
            i_data => disp_data, i_blank => disp_blank,
            i_raw_en => '0', i_raw => (others => '0'),
            o_seg => seg, o_cat => cat
        );

    -- 结算图案切片
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
        prev_row <= tgt_mask( 7 downto  0) when "000",
                    tgt_mask(15 downto  8) when "001",
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

    -- A5 倒计时告急幽灵使能与 2 Hz 闪烁
    hint_on    <= '1' when (unsigned(gtime) <= 10) else '0';
    hint_blink <= hint_on and gblink;
    hint_mask  <= (others => hint_blink);

    -- 结算画面闪烁节奏 (先闪 1 秒后常亮)
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                endflash_cnt <= (others => '0'); endflash_on <= '0';
            elsif (state /= S_WIN) and (state /= S_FAIL) then
                endflash_cnt <= (others => '0'); endflash_on <= '0';
            elsif (t_4hz = '1') then
                if (endflash_cnt = 3) then endflash_on <= '1';
                else endflash_cnt <= endflash_cnt + 1; end if;
            end if;
        end if;
    end process;

    -- 点阵行切片与画面多路器
    process (state, gblink, endflash_on, mrow, eng_fr, eng_fg, win_row, fail_row, prev_row, hint_mask)
        variable lv, ev : std_logic;
        variable rw, gw : std_logic_vector(7 downto 0);
    begin
        lv := gblink;
        ev := gblink or endflash_on;

        case to_integer(mrow) is
            when 0 => rw := eng_fr(63 downto 56); gw := eng_fg(63 downto 56);
            when 1 => rw := eng_fr(55 downto 48); gw := eng_fg(55 downto 48);
            when 2 => rw := eng_fr(47 downto 40); gw := eng_fg(47 downto 40);
            when 3 => rw := eng_fr(39 downto 32); gw := eng_fg(39 downto 32);
            when 4 => rw := eng_fr(31 downto 24); gw := eng_fg(31 downto 24);
            when 5 => rw := eng_fr(23 downto 16); gw := eng_fg(23 downto 16);
            when 6 => rw := eng_fr(15 downto 8);  gw := eng_fg(15 downto 8);
            when others => rw := eng_fr(7 downto 0); gw := eng_fg(7 downto 0);
        end case;

        if (state = S_SELF_TEST) then
            mat_r <= (others => lv); mat_g <= (others => lv);
        elsif (state = S_IDLE) then
            mat_r <= (others => '0'); mat_g <= (others => '0');
        elsif (state = S_PREVIEW) then
            mat_r <= prev_row; mat_g <= (others => '0');
        elsif (state = S_WIN) then
            mat_r <= (others => '0'); mat_g <= win_row and (ev & ev & ev & ev & ev & ev & ev & ev);
        elsif (state = S_FAIL) then
            mat_r <= fail_row and (ev & ev & ev & ev & ev & ev & ev & ev); mat_g <= (others => '0');
        else
            mat_r <= rw;
            mat_g <= gw or (prev_row and (not rw) and hint_mask);
        end if;
    end process;

    u_dot : dot_matrix_scan
        port map (
            i_clk => clk, i_rst => rst, i_en => sw7,
            i_row => std_logic_vector(mrow), i_colr => mat_r, i_colg => mat_g,
            o_row => dot_row, o_colr => dot_colr, o_colg => dot_colg
        );

    u_buzz : buzzer_ctrl
        port map (
            i_clk => clk, i_rst => rst, i_en => sw7,
            i_sel => sound, i_t4 => t_4hz, o_buzz => buzz
        );

end architecture rtl;
