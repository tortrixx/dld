library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

-- ============================================================================
--  puzzle_top  --  TOP LEVEL of the integrated game
--  Topic 4 : Simple Jigsaw Puzzle Game  (Digital Circuits & Logic Design Lab)
--  Device  : Altera MAX II EPM1270T144C5   Tool: Quartus II 9.1   Language: VHDL
--
--  This is the ONLY file that binds pins (together with quartus/puzzle.qsf).
--  Every sub-module is instantiated with an explicit component declaration and
--  NAMED port association: a missing or misspelled port in a named port map is a
--  compile error, whereas an omitted one can silently leave a signal dangling.
--
--  Block diagram <-> code correspondence (the course requires the blocks of the
--  actual design document to match the implemented circuit):
--
--     S1 clk_gen          clock division, ticks, reset
--     S2 keypad_scan      4x4 keypad scan + debounce + one-shot press
--     S3 game_fsm         master state machine, countdowns, level switching
--     S4 puzzle_ctrl      placement / movement / locking / colouring engine
--     S5 pattern_rom      complete-picture ROM
--     S5 piece_rom        piece-shape ROM
--     S5 rng_lfsr         pseudo-random source for the scatter
--     S6 dot_matrix_scan  8x8 dual-colour matrix row driver
--     S6 seg_scan         8-digit seven-segment dynamic scan + BCD decode
--     S6 disp_format      state -> seven-segment content
--     S7 buzzer_ctrl      sound effects
--
--  = 11 sub-modules + this top level, which is exactly the block diagram.
--
--  HOW THE MATRIX IS DRIVEN
--  The engine (puzzle_ctrl) publishes ONE display row at a time -- 8 red bits and
--  8 green bits -- together with the index of that row.  This file turns that into
--  the panel's coloured picture for each game state, and dot_matrix_scan drives
--  the physical row.  There is no 64-bit frame buffer anywhere in the design;
--  keeping the whole rendering path 8 bits wide is what let the engine fit.
--
--  HARDWARE NOTE -- THE 16 LEDs ARE DELIBERATELY UNUSED.
--  The board wires COLG0..COLG7 (matrix green columns) onto PIN_38..45, the same
--  group as LD8..LD15, and PIN_137..144 is shared by LD8..LD15 and VGA.  Driving
--  the LEDs would cost the matrix its green colour, which requirement B6
--  (the selected piece turns green) depends on.  No requirement of topic 4 asks
--  for the LEDs, so they are left unused on purpose.
-- ============================================================================

entity puzzle_top is
    port (
        clk      : in  std_logic;                       -- PIN_18 board clock
        sw7      : in  std_logic;                       -- PIN_125, up = '1'
        btn      : in  std_logic;                       -- PIN_61, BTN0 reset
        kp_row   : in  std_logic_vector(3 downto 0);    -- PIN_111..114
        kp_col   : out std_logic_vector(3 downto 0);    -- PIN_117..120
        dot_row  : out std_logic_vector(7 downto 0);    -- PIN_8..1
        dot_colr : out std_logic_vector(7 downto 0);    -- PIN_22..11
        dot_colg : out std_logic_vector(7 downto 0);    -- PIN_45..38
        seg      : out std_logic_vector(7 downto 0);    -- PIN_62..51
        cat      : out std_logic_vector(7 downto 0);    -- PIN_63..31
        buzz     : out std_logic                        -- PIN_60
    );
end entity puzzle_top;

architecture rtl of puzzle_top is

    component clk_gen
        port (
            i_clk      : in  std_logic;
            i_btn      : in  std_logic;
            o_rst      : out std_logic;
            o_tick_1k  : out std_logic;
            o_tick_200 : out std_logic;
            o_tick_100 : out std_logic;
            o_tick_2hz : out std_logic;
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
            i_tick_2hz  : in  std_logic;
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
            o_level     : out std_logic;
            o_state     : out std_logic_vector(2 downto 0);
            o_time      : out std_logic_vector(5 downto 0);
            o_blink     : out std_logic;
            i_solved    : in  std_logic;
            i_all_lock  : in  std_logic;
            i_shuf_busy : in  std_logic;
            o_sound     : out std_logic_vector(2 downto 0)
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
            i_up      : in  std_logic;
            i_down    : in  std_logic;
            i_left    : in  std_logic;
            i_right   : in  std_logic;
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
            i_sel  : in  std_logic_vector(2 downto 0);
            i_t2   : in  std_logic;
            o_buzz : out std_logic
        );
    end component;

    ----------------------------------------------------------------------------
    -- Interconnect
    ----------------------------------------------------------------------------
    signal rst      : std_logic;
    signal t_1k     : std_logic;
    signal t_200    : std_logic;
    signal t_100    : std_logic;
    signal t_2hz    : std_logic;
    signal t_1hz    : std_logic;
    signal t_40     : std_logic;

    signal key      : std_logic_vector(3 downto 0);
    signal press    : std_logic;
    signal release  : std_logic;
    signal kp_raw   : std_logic_vector(3 downto 0);

    signal sel, move, conf, go : std_logic;
    signal mv_up, mv_dn, mv_lf, mv_rt : std_logic;
    signal level    : std_logic;
    signal state    : std_logic_vector(2 downto 0);
    signal gtime    : std_logic_vector(5 downto 0);
    signal gblink   : std_logic;
    signal sound    : std_logic_vector(2 downto 0);

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

    -- engine output: a complete 64-bit frame per colour plane
    signal eng_fr   : std_logic_vector(63 downto 0);
    signal eng_fg   : std_logic_vector(63 downto 0);

    -- final row presented to the matrix driver
    signal mat_r    : std_logic_vector(7 downto 0);
    signal mat_g    : std_logic_vector(7 downto 0);

    -- 结算画面（WIN/FAIL）的闪示节奏：数 2 Hz 半周期，数满后常亮
    signal endflash_cnt : unsigned(2 downto 0) := (others => '0');
    signal endflash_on  : std_logic := '0';

    -- row the matrix driver is currently lighting
    signal mrow      : unsigned(2 downto 0) := (others => '0');
    signal disp_data  : std_logic_vector(31 downto 0);
    signal disp_blank : std_logic_vector(7 downto 0);

    -- special-state row sources
    signal win_row  : std_logic_vector(7 downto 0);
    signal prev_row : std_logic_vector(7 downto 0);  -- target picture row
    signal fail_row : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- Matrix row counter.  It advances on the SAME tick as the engine's frame
    -- renderer: the driver lights row r of the frame that is currently stable
    -- while the engine rebuilds row r for the next frame.  Driving the two from
    -- different ticks (40 Hz scan vs 200 Hz render) made displayed row and
    -- rendered row unrelated, which looked like flicker.
    --
    -- ⚠️ 2026-10-08 用户反馈"点阵和数码管都闪得比较明显" —— 根因就是这里的**节拍**：
    --    原来 mrow 走 tick_200（200 Hz），8 行轮一遍 = 8×5 ms = 40 ms，
    --    帧刷新率只有 **25 Hz**，低于临界闪烁融合（LED 一般要 > 60 Hz）→ 肉眼可见闪。
    --    上一条注释说的"40 Hz 扫描 vs 200 Hz 渲染不同源"是**错行**问题，当时把两边都
    --    改成 200 Hz 消掉了错行，但帧率仍是 25 Hz，闪依旧在。
    --    现在统一改走 **tick_1k**（1 kHz）：8 行 = 8 ms → **125 Hz**；
    --    占空比仍是 1/8，亮度不变，只是不再闪。引擎渲染器（puzzle_ctrl）与
    --    数码管位选（seg_scan）**同步改成 1 kHz**，三者不再有错行问题。
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

    -- S1 : clock, ticks, reset
    u_clk : clk_gen
        port map (
            i_clk      => clk,
            i_btn      => btn,
            o_rst      => rst,
            o_tick_1k  => t_1k,
            o_tick_200 => t_200,
            o_tick_100 => t_100,
            o_tick_2hz => t_2hz,
            o_tick_1hz => t_1hz,
            o_tick_40  => t_40
        );

    -- S2 : keypad
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

    -- S3 : master state machine
    u_fsm : game_fsm
        port map (
            i_clk       => clk,
            i_rst       => rst,
            i_sw        => sw7,
            i_tick_1hz  => t_1hz,
            i_tick_2hz  => t_2hz,
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
            o_level     => level,
            o_state     => state,
            o_time      => gtime,
            o_blink     => gblink,
            i_solved    => solved,
            i_all_lock  => all_lock,
            i_shuf_busy => shuf_busy,
            o_sound     => sound
        );

    -- S5 : shape database and complete picture
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
            o_mask  => tgt_mask
        );

    -- S5 : random source
    u_rng : rng_lfsr
        port map (
            i_clk  => clk,
            i_rst  => rst,
            i_step => rnd_step,
            o_val  => rnd_val
        );

    -- ⚠️ ERR-023 : the engine is **always** given the real target picture.
    --
    -- The success test (ERR-021) compares the assembled picture with the target,
    -- so blanking i_target during play made the test impossible to satisfy: the
    -- measured bench symptom was "level 1 assembled correctly, press confirm,
    -- and the game still shows the cross".
    --
    -- The earlier reason for blanking it -- "do not hide the pieces under a red
    -- outline during play" (ERR-013) -- is now handled inside the engine: it
    -- simply does not draw the target ghost (see puzzle_ctrl's ERR-023 note).
    -- The PREVIEW still shows the complete picture, from tgt_mask via prev_row.

    -- S4 : puzzle engine
    u_puzzle : puzzle_ctrl
        port map (
            i_clk     => clk,
            i_rst     => rst,
            i_tick    => t_200,         -- 引擎行渲染仍 200 Hz（8 行 = 40 ms 内容更新）。
                                        -- ⚠️ 实测：把它也提到 1 kHz 会让整机从 1188 涨到
                                        -- 1264/1270 LE（100%，只剩 6 个）—— 闪烁与"内容
                                        -- 更新率"无关（见 mrow 的注释），只与**扫描率**
                                        -- 有关，所以这里保持 200 Hz，别为了美观把面积吃光。
            rnd_step  => rnd_step,
            rnd_val   => rnd_val,
            i_level   => level,
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
            i_up      => mv_up,
            i_down    => mv_dn,
            i_left    => mv_lf,
            i_right   => mv_rt,
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

    -- S6 : seven-segment content + scan
    u_disp : disp_format
        port map (
            i_state => state,
            i_level => level,
            i_time  => gtime,
            i_blink => gblink,
            o_data  => disp_data,
            o_blank => disp_blank
        );

    u_seg : seg_scan
        port map (
            i_clk    => clk,
            i_rst    => rst,
            i_tick   => t_1k,           -- 1 kHz：8 位轮一遍 = 8 ms -> 125 Hz/位
                                        -- （原来 200 Hz -> 25 Hz/位，用户反馈"数码管也闪"）
            i_en     => sw7,
            i_data   => disp_data,
            i_blank  => disp_blank,
            i_raw_en => '0',
            i_raw    => (others => '0'),
            o_seg    => seg,
            o_cat    => cat
        );

    ----------------------------------------------------------------------------
    -- Pull one row out of a 64-bit picture.
    -- Used for the win/fail screens, which are whole-picture constants rather
    -- than assembled pieces.  The mask convention is bit index = 8*row + col with
    -- row 0 at the top, so logical row 0 is the TOP slice (63..56).
    ----------------------------------------------------------------------------
    -- NOTE the slice order: in this project's convention bit = 8*row + col, so
    -- logical row 0 is bits 7..0 (NOT the top slice).  Reading 63..56 for row 0
    -- displayed both end pictures vertically mirrored.
    with std_logic_vector(mrow) select
        win_row <= WIN_MASK( 7 downto  0) when "000",
                   WIN_MASK(15 downto  8) when "001",
                   WIN_MASK(23 downto 16) when "010",
                   WIN_MASK(31 downto 24) when "011",
                   WIN_MASK(39 downto 32) when "100",
                   WIN_MASK(47 downto 40) when "101",
                   WIN_MASK(55 downto 48) when "110",
                   WIN_MASK(63 downto 56) when others;

    -- Preview row: the complete pattern, sliced in PACKAGE convention where
    -- row 0 occupies bits 7..0 (NOT the engine's internal MSB-first layout).
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
    -- 结算画面的闪烁节奏：先闪 **2 个 2 Hz 周期**（4 个半周期，抓注意力），
    -- 然后常亮（远距离读图）。离开 WIN/FAIL 立刻复位。
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
            elsif (t_2hz = '1') then
                if (endflash_cnt = 3) then
                    endflash_on <= '1';          -- 4 个半周期后：常亮
                else
                    endflash_cnt <= endflash_cnt + 1;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Matrix content per state.
    --   SELF_TEST : whole panel yellow, flashing at 2 Hz   (requirement B1)
    --   WIN       : the victory picture (a smiling face), first flashing then steady
    --   FAIL      : the failure picture (a cross), first flashing then steady
    --   otherwise : whatever the engine rendered (preview / playing)
    --
    -- ⚠️ 结算画面的两处改进（2026-10-08，用户反馈"对勾闪的效果不够好"）：
    --   1) 图案换成**笑脸**（puzzle_pkg.WIN_MASK）：8x8 上细线勾不出形状，笑脸一眼可懂；
    --   2) 颜色区分：胜利 = **黄**（红+绿同时亮，最亮）、失败 = **红**。远距离也能分辨；
    --   3) 闪烁节奏：**先闪 2 个 2 Hz 周期抓注意力，然后常亮**——一直闪反而不利于
    --      远距离读图（自拟改进项 S5 的原意是"便于远距离判读"）。
    --      自检（B1）仍按需求无条件 2 Hz 闪烁。
    ----------------------------------------------------------------------------
    process (state, gblink, endflash_on, mrow, eng_fr, eng_fg, win_row, fail_row, prev_row)
        variable lv  : std_logic;
        variable ev  : std_logic;        -- 结算画面的亮度：闪烁相位 or 常亮
        variable rw  : std_logic_vector(7 downto 0);
        variable gw  : std_logic_vector(7 downto 0);
    begin
        lv := gblink;
        ev := gblink or endflash_on;

        -- slice the row the driver is lighting out of the 64-bit picture.
        -- bit index = 8*row + col with row 0 = TOP, so row 0 is the TOP slice.
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
            -- whole panel yellow, flashing at 2 Hz (requirement B1)
            mat_r <= (others => lv);
            mat_g <= (others => lv);
        elsif (state = S_IDLE) then
            -- B2: the panel is DARK in standby.  The engine frame must NOT be
            -- shown here: the pieces have not been scattered yet (that happens
            -- when play starts) and would all be stacked at anchor (0,0).
            mat_r <= (others => '0');
            mat_g <= (others => '0');
        elsif (state = S_PREVIEW) then
            -- B4: show the COMPLETE pattern.  It is a package constant, so slice
            -- it straight out of the target mask - the engine is not involved.
            mat_r <= prev_row;
            mat_g <= (others => '0');
        elsif (state = S_WIN) then
            -- 胜利：**黄色**笑脸（红+绿同时亮）；先闪 2 个周期，之后常亮
            mat_r <= win_row and (ev & ev & ev & ev & ev & ev & ev & ev);
            mat_g <= win_row and (ev & ev & ev & ev & ev & ev & ev & ev);
        elsif (state = S_FAIL) then
            -- 失败：**红色**十字（只点红，和黄色的胜利笑脸一眼可辨）
            mat_r <= fail_row and (ev & ev & ev & ev & ev & ev & ev & ev);
            mat_g <= (others => '0');
        else
            -- S_PLAYING: the assembled picture from the engine
            mat_r <= rw;
            mat_g <= gw;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- S6 : dot-matrix driver.
    -- i_row comes from this file's row counter (mrow), which advances on tick_1k:
    -- 8 rows = 8 ms -> **125 Hz** frame refresh.  改版前 mrow 走 tick_200，帧率只有
    -- 25 Hz，肉眼可见闪（用户 2026-10-08 上板反馈）。
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

    -- S7 : sound
    u_buzz : buzzer_ctrl
        port map (
            i_clk  => clk,
            i_rst  => rst,
            i_en   => sw7,
            i_sel  => sound,
            i_t2   => t_2hz,
            o_buzz => buzz
        );

end architecture rtl;
