-- ============================================================================
--  board_test_top  --  HARDWARE SELF-TEST TOP LEVEL
--  This is a DIAGNOSTIC top level, not the game.  Burn this first.
--
--  Why it exists
--  -------------
--  The course manual fixes every PIN NUMBER, but it never states:
--    (a) whether COLR0 is the left-most physical column of the matrix,
--    (b) whether ROW0 is the top-most physical row of the matrix,
--    (c) the electrical polarity / row-column direction of the 4x4 keypad,
--    (d) whether the board clock selector really sits on the 50 MHz position.
--  All four are GLOBAL assumptions: if one is wrong, the game looks broken even
--  though its logic is correct.  This top level isolates them one at a time so a
--  failure can never be blamed on the game logic.
--
--  What each test shows  (index is shown on ALL 8 digits)
--  ---------------------------------------------------------------------------
--   Test 0  "CORNERS"  four corner dots YELLOW.
--           -> identifies axis mirroring immediately: if the border dots light
--              but the reported orientation is wrong, the .qsf bit order is
--              reversed.  A diagonal single dot would be ambiguous; corners are not.
--   Test 1  "ALL"      every dot YELLOW -> confirms all 16 row/column drivers work.
--   Test 2  "FRAME"    hollow rectangle, with the TOP-LEFT corner dot RED and the
--           remaining border YELLOW  -> gives an absolute "where is the origin" answer.
--   Test 3  "RED TOP / GREEN BOTTOM"  -> separates RED/GREEN bank swapping from
--           row mirroring (the two have different fixes).
--   Test 4  "WALK"     a single dot sweeps left->right then top->bottom at 2 Hz.
--           -> the direction of travel is unambiguous on the bench.
--   Test 5  "KEY"      press any key: the pressed key lights its own dot, and the
--           key code is shown on DISP7/DISP6 as hex.  This settles the keypad
--           polarity and its row/column direction.
--   Test 6  "BUTTON"   hold BTN0: whole matrix turns YELLOW.
--           -> confirms the reset key path.
--
--  Test index auto-advances every 3 s so a single burn covers everything, and
--  pressing the RIGHT-MOST key (BTN0) freezes it, so a test can be examined for
--  as long as needed.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity board_test_top is
    port (
        -- clock and switch
        clk      : in  std_logic;                       -- PIN_18
        sw7      : in  std_logic;                       -- PIN_125, up = '1'
        btn      : in  std_logic;                       -- PIN_61, BTN0 = right-most, press = '1'
        -- 4x4 matrix keypad
        kp_row   : in  std_logic_vector(3 downto 0);    -- PIN_111..114
        kp_col   : out std_logic_vector(3 downto 0);    -- PIN_117..120
        -- dot matrix
        dot_row  : out std_logic_vector(7 downto 0);    -- PIN_8..1
        dot_colr : out std_logic_vector(7 downto 0);    -- PIN_22,21,16,15,14,13,12,11
        dot_colg : out std_logic_vector(7 downto 0);    -- PIN_45,44,43,42,41,40,39,38
        -- seven-segment
        seg      : out std_logic_vector(7 downto 0);    -- PIN_62,59,58,57,55,53,52,51
        cat      : out std_logic_vector(7 downto 0);    -- PIN_63,66,67,68,69,70,30,31
        -- buzzer
        buzz     : out std_logic                        -- PIN_60
    );
end entity board_test_top;

architecture rtl of board_test_top is

    ----------------------------------------------------------------------------
    -- Component declarations.
    -- The project convention is component + port map (NOT "entity work.xxx"):
    -- a missing port in an explicit port map is then a compile error, whereas a
    -- positional/omitted one can silently leave a signal dangling.
    ----------------------------------------------------------------------------
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

    signal rst      : std_logic;
    signal t_1k     : std_logic;
    signal t_200    : std_logic;
    signal t_100    : std_logic;
    signal t_2hz    : std_logic;
    signal t_1hz    : std_logic;
    signal t_40     : std_logic;

    signal key      : std_logic_vector(3 downto 0);
    signal kp_raw   : std_logic_vector(3 downto 0);

    -- test sequencing
    signal test_idx : unsigned(3 downto 0) := (others => '0');
    signal sec_cnt  : unsigned(1 downto 0) := (others => '0');   -- 0..2 = 3 s
    signal walk_cnt : unsigned(5 downto 0) := (others => '0');   -- 0..63 walk position
    signal frozen   : std_logic := '0';
    signal btn_d    : std_logic := '0';
    signal btn_dd   : std_logic := '0';

    -- (segment diagnostics are declared further down, next to the display logic)

    -- final picture sent to the matrix
    signal px_red   : std_logic_vector(63 downto 0) := (others => '0');
    signal px_grn   : std_logic_vector(63 downto 0) := (others => '0');
    -- row being displayed: the driver samples one row at a time, so the
    -- diagnostic picture is sliced to match
    signal row_idx  : unsigned(2 downto 0) := (others => '0');
    signal row_r    : std_logic_vector(7 downto 0) := (others => '0');
    signal row_g    : std_logic_vector(7 downto 0) := (others => '0');

    signal disp     : std_logic_vector(31 downto 0);            -- 8 digits of BCD
    -- the diagnostic top level blanks no digit, so this is a constant: as a
    -- signal it would be reported as "never assigned a value".
    constant NO_BLANK : std_logic_vector(7 downto 0) := (others => '0');
    signal seg_en   : std_logic;

    -- Segment diagnostics (tests 7 and 8).
    --   test 7 : drive ONE segment line at a time -> reads off the segment map
    --   test 8 : light ALL segments on ONE digit position -> reads off the
    --            digit-select (CAT) order
    -- decoded key position inside the 4x4 keypad grid (test 9)
    signal kp_row_idx : integer range 0 to 3 := 0;
    signal kp_col_idx : integer range 0 to 3 := 0;
    signal seg_raw_en : std_logic;
    signal seg_raw    : std_logic_vector(7 downto 0);
    signal walk_step  : unsigned(3 downto 0) := (others => '0');  -- 0..15
    signal walk_sec   : unsigned(2 downto 0) := (others => '0');  -- seconds within step

    -- buzzer : a simple 1 kHz tone while a key is held (proves the buzzer path)
    signal buzz_r   : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- Key code -> keypad grid position, for the diagnostic display.
    -- The code layout is deliberately spread over the grid so that a wrong
    -- row/column order shows up as a visibly wrong POSITION rather than as
    -- a merely wrong number.
    ----------------------------------------------------------------------------
    process (key)
    begin
        case key is
            when K_UP      => kp_row_idx <= 0; kp_col_idx <= 0;
            when K_START   => kp_row_idx <= 0; kp_col_idx <= 3;
            when K_LEFT    => kp_row_idx <= 1; kp_col_idx <= 0;
            when K_DOWN    => kp_row_idx <= 1; kp_col_idx <= 1;
            when K_RIGHT   => kp_row_idx <= 1; kp_col_idx <= 2;
            when K_SELECT  => kp_row_idx <= 1; kp_col_idx <= 3;
            when K_CONFIRM => kp_row_idx <= 2; kp_col_idx <= 3;
            when others    => kp_row_idx <= 2; kp_col_idx <= 0;
        end case;
    end process;

    ----------------------------------------------------------------------------
    -- Reset generated from BTN0 only.  The game's own 2-second self-test is NOT
    -- involved here, so BTN0 can be used purely as the "hold to inspect" key.
    ----------------------------------------------------------------------------
    u_clk : clk_gen
        port map (
            i_clk      => clk,
            i_btn      => btn,
            o_rst      => rst,
            o_tick_1k  => t_1k,
            o_tick_200 => t_200,
            o_tick_100 => t_100,
            o_tick_2hz => t_2hz,
            o_tick_4hz => open,
            o_tick_1hz => t_1hz,
            o_tick_40  => t_40
        );

    u_keypad : keypad_scan
        port map (
            i_clk     => clk,
            i_rst     => rst,
            i_tick    => t_200,
            i_row     => kp_row,
            o_col     => kp_col,
            o_key     => key,
            -- o_press / o_release / o_raw exist for the game and for the .vwf
            -- waveform; this diagnostic top level has no use for them, so they
            -- are left open.  Named association makes that explicit and safe.
            o_press   => open,
            o_release => open,
            o_raw     => kp_raw
        );

    ----------------------------------------------------------------------------
    -- Freeze control : BTN0 press toggles "frozen".
    -- The reset generated by clk_gen is derived from BTN0 itself, so the button
    -- must be edge-detected here rather than sampled with t_1k while it is held.
    -- The two-stage synchroniser is kept because BTN0 is an external pin.
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                btn_d  <= '0';
                btn_dd <= '0';
                frozen <= '0';
            else
                btn_d  <= btn;
                btn_dd <= btn_d;
                if (btn_d = '1') and (btn_dd = '0') then
                    frozen <= not frozen;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Test index sequencer : auto-advance every 3 seconds on tick_1hz.
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                test_idx <= (others => '0');
                sec_cnt  <= (others => '0');
            else
                if (frozen = '0') and (t_1hz = '1') then
                    if (sec_cnt = 2) then
                        sec_cnt  <= (others => '0');
                        test_idx <= test_idx + 1;               -- wraps 13 -> 0
                    else
                        sec_cnt <= sec_cnt + 1;
                    end if;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Segment / digit walk counter (tests 7 and 8).
    -- One step per 2 seconds, 16 steps 0..15, so a full round is 32 s:
    --   test 7 : steps 0..7  drive segment AA..AP one at a time (AP last)
    --   test 8 : steps 0..7  light all segments on CAT0..CAT7 one at a time
    -- Keeping 2 s per step makes the pattern trivially readable on a bench.
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                walk_step <= (others => '0');
                walk_sec  <= (others => '0');
            elsif ((test_idx = 7) or (test_idx = 8)) then
                if (t_1hz = '1') then
                    if (walk_sec = 1) then
                        walk_sec  <= (others => '0');
                        walk_step <= walk_step + 1;         -- wraps 15 -> 0
                    else
                        walk_sec <= walk_sec + 1;
                    end if;
                end if;
            else
                walk_step <= (others => '0');
                walk_sec  <= (others => '0');
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Drive the segment diagnostic lines.
    --
    -- Test 7 : one segment line HIGH at a time, decoder bypassed.
    --          The scan counter 'idx' below picks the current step, and the
    --          operator watches which PHYSICAL segment lights.
    -- Test 8 : all segment lines HIGH on every digit, but the DIGIT-SELECT
    --          pattern puts exactly one cathode LOW, so a single digit position
    --          lights up.  That reads off the CAT order.
    ----------------------------------------------------------------------------
    seg_raw_en <= '1' when ((test_idx = 7) or (test_idx = 8)) else '0';

    process (test_idx, walk_step)
        variable v : std_logic_vector(7 downto 0);
        variable s : integer range 0 to 15;
    begin
        v := (others => '0');
        s := to_integer(walk_step);

        if (test_idx = 7) then
            -- i_raw bit index == segment number: bit0=AA ... bit6=AG, bit7=AP
            if (s < 8) then
                v(s) := '1';
            end if;
        else
            -- test 8 : every segment on; exactly one digit is selected by seg_scan
            v := (others => '1');
        end if;

        seg_raw <= v;
    end process;

    ----------------------------------------------------------------------------
    -- Walk counter for test 4 : 2 Hz, 0..63
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                walk_cnt <= (others => '0');
            elsif (t_2hz = '1') then
                walk_cnt <= walk_cnt + 1;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Pattern generator.
    -- Masks are 64-bit, bit index = 8*row + col, bit0 = TOP-LEFT dot, and within
    -- a row column 0 is bit 0.  Writing them as bit strings (bit63 on the left)
    -- keeps the position of every single dot explicit and auditable.
    ----------------------------------------------------------------------------
    process (test_idx, walk_cnt, key, btn, sw7)
        variable v_red : std_logic_vector(63 downto 0);
        variable v_grn : std_logic_vector(63 downto 0);
        variable v_row : integer range 0 to 7;
        variable v_col : integer range 0 to 7;
        -- key codes are 1-based (K_NONE = 0), so subtract one before splitting
        variable v_key : unsigned(3 downto 0);
    begin
        v_red := (others => '0');
        v_grn := (others => '0');

        case to_integer(test_idx) is

            -- Test 0 : four corners YELLOW
            when 0 =>
                v_red(0)  := '1'; v_red(7)  := '1';
                v_red(56) := '1'; v_red(63) := '1';
                v_grn := v_red;

            -- Test 1 : everything YELLOW
            when 1 =>
                v_red := (others => '1');
                v_grn := (others => '1');

            -- Test 2 : hollow frame; TOP-LEFT dot RED, rest of frame YELLOW
            when 2 =>
                for c in 0 to 7 loop
                    v_grn(c)      := '1';      -- top row    (row 0)
                    v_grn(56 + c) := '1';      -- bottom row (row 7)
                end loop;
                for r in 0 to 7 loop
                    v_grn(8 * r)     := '1';   -- left column  (col 0)
                    v_grn(8 * r + 7) := '1';   -- right column (col 7)
                end loop;
                v_red(0) := '1';               -- top-left corner marker
                v_grn(0) := '0';

            -- Test 3 : top half RED, bottom half GREEN
            when 3 =>
                for r in 0 to 3 loop
                    for c in 0 to 7 loop
                        v_red(8 * r + c) := '1';
                    end loop;
                end loop;
                for r in 4 to 7 loop
                    for c in 0 to 7 loop
                        v_grn(8 * r + c) := '1';
                    end loop;
                end loop;

            -- Test 4 : single walking dot, left->right then top->bottom
            when 4 =>
                v_row := to_integer(walk_cnt) / 8;
                v_col := to_integer(walk_cnt) mod 8;
                v_red(8 * v_row + v_col) := '1';
                v_grn(8 * v_row + v_col) := '1';        -- yellow, easy to see

            -- Test 5 : keypad -> its own position on the matrix
            when 5 =>
                if (key /= K_NONE) then
                    v_key := unsigned(key) - 1;                         -- K_START=1 -> 0
                    v_row := to_integer(v_key(3 downto 2));             -- key group
                    v_col := to_integer(v_key(1 downto 0));             -- within group
                    v_red(8 * v_row + v_col) := '1';
                    v_grn(8 * v_row + v_col) := '1';
                end if;

            -- Test 6 : BTN0 -> whole matrix YELLOW while held
            when 6 =>
                if (btn = '1') then
                    v_red := (others => '1');
                    v_grn := (others => '1');
                end if;

            -- Test 9 : KEYPAD identification.
            --   matrix row 7 shows the four RAW row-line levels (colour = level):
            --       red   = that row line reads '0'
            --       green = that row line reads '1'
            --   the remaining rows show the decoded key position.
            when 9 =>
                -- raw row lines on the bottom row, so the idle polarity is visible
                for c in 0 to 3 loop
                    if (kp_row(c) = '0') then
                        v_red(8 * 7 + c) := '1';
                    else
                        v_grn(8 * 7 + c) := '1';
                    end if;
                end loop;

                -- decoded key drawn at its own grid position
                if (key /= K_NONE) then
                    v_red(8 * kp_row_idx + kp_col_idx) := '1';
                    v_grn(8 * kp_row_idx + kp_col_idx) := '1';
                end if;

            -- Test 7 : 7-segment SEGMENT identification.
            --   The matrix stays dark; look at the DISPLAY.
            --   Every 2 s exactly one segment line is driven (decoder bypassed),
            --   bit0=AA ... bit6=AG, bit7=AP.  Note which PHYSICAL segment lights.
            -- Test 8 : 7-segment DIGIT-position identification.
            --   Every 2 s ALL segments are driven on exactly ONE digit position.
            -- Test 9 : all segments on all digits (static "88888888").
            when others =>
                v_red := (others => '0');
                v_grn := (others => '0');

        end case;

        -- global switch B1 : SW7=0 blanks every display device
        if (sw7 = '0') then
            v_red := (others => '0');
            v_grn := (others => '0');
        end if;

        px_red <= v_red;
        px_grn <= v_grn;
    end process;

    ----------------------------------------------------------------------------
    -- Row counter and picture slice for the matrix driver.
    -- The driver takes one row at a time, so the 64-bit picture built above is
    -- sliced here.  Row 0 is the TOP logic row; dot_matrix_scan applies the
    -- measured physical row order.
    --
    -- ⚠️ ERR-039（2026-10-09 第 11 工作阶段，全项目审计发现）：这里原来把
    --    row_idx=0 切到 px(63..56)。本文件的画图约定是 "bit = 8*row+col、
    --    **bit0 = 左上角**"（同文件 :390 的注释就是这么写的），所以 px(63..56)
    --    是**第 7 行（最下一行）** —— 自检画面被**上下镜像**显示了，而 puzzle_top
    --    的同一段切片是 px(7..0)（正确）。已在下面改成 px(7..0)。
    --    ⚠️ 上板复核：test 2 的红色标记（画面左上角那一点）现在应出现在
    --    **左上角**；若仍出现在左下角，说明 dot_matrix_scan 的行序还要反过来
    --    （那会连带影响整机画面方向）—— 这条要人工上板确认，见 HANDOFF §7⓪。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                row_idx <= (others => '0');
            elsif (t_40 = '1') then
                row_idx <= row_idx + 1;
            end if;
        end if;
    end process;

    with to_integer(row_idx) select
        row_r <= px_red( 7 downto  0) when 0,
                 px_red(15 downto  8) when 1,
                 px_red(23 downto 16) when 2,
                 px_red(31 downto 24) when 3,
                 px_red(39 downto 32) when 4,
                 px_red(47 downto 40) when 5,
                 px_red(55 downto 48) when 6,
                 px_red(63 downto 56) when others;

    with to_integer(row_idx) select
        row_g <= px_grn( 7 downto  0) when 0,
                 px_grn(15 downto  8) when 1,
                 px_grn(23 downto 16) when 2,
                 px_grn(31 downto 24) when 3,
                 px_grn(39 downto 32) when 4,
                 px_grn(47 downto 40) when 5,
                 px_grn(55 downto 48) when 6,
                 px_grn(63 downto 56) when others;

    ----------------------------------------------------------------------------
    -- Dot-matrix driver
    ----------------------------------------------------------------------------
    u_dot : dot_matrix_scan
        port map (
            i_clk   => clk,
            i_rst   => rst,
            i_en    => sw7,
            i_row   => std_logic_vector(row_idx),
            i_colr  => row_r,
            i_colg  => row_g,
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );

    ----------------------------------------------------------------------------
    -- Seven-segment content.
    --
    --  Test 0..6 : every digit shows the TEST INDEX, so the operator can always
    --              tell which test is on screen.
    --  Test 7    : a segment-identification test.  All digits show the SAME
    --              value, which is the point -- it isolates the segment lines
    --              from the digit-select lines.  The displayed digit cycles
    --              through the values in SEG_SUB_BCD every 2 s.
    --
    -- Because the decoder lives in seg_scan, a single segment cannot be
    -- requested directly; only legal BCD digits can.  That is why test 7 uses
    -- the "one segment only" digits identified in SEG_SUB_BCD.
    ----------------------------------------------------------------------------
    ----------------------------------------------------------------------------
    -- Seven-segment content : every digit shows the 4-bit test index, so the
    -- operator can always tell which test is on screen.  Tests 7 and 8 replace
    -- the decoded content with a raw segment pattern (see seg_raw above).
    ----------------------------------------------------------------------------
    process (test_idx, key)
        variable v_nib  : std_logic_vector(3 downto 0);
        variable v_disp : std_logic_vector(31 downto 0);
    begin
        v_nib := '0' & std_logic_vector(test_idx(2 downto 0));
        v_disp := (others => '0');
        for d in 0 to 7 loop
            v_disp(4 * d + 3 downto 4 * d) := v_nib;
        end loop;

        if (test_idx = 9) then
            -- DISP1:DISP0 = decoded key code (0..7), all other digits blanked
            v_disp := (others => '0');
            v_disp(3 downto 0) := key;
        end if;
        disp <= v_disp;
    end process;

    seg_en <= sw7;

    u_seg : seg_scan
        port map (
            i_clk    => clk,
            i_rst    => rst,
            i_tick   => t_200,
            i_en     => seg_en,
            i_data   => disp,
            i_blank  => NO_BLANK,
            i_raw_en => seg_raw_en,
            i_raw    => seg_raw,
            o_seg    => seg,
            o_cat    => cat
        );

    ----------------------------------------------------------------------------
    -- Buzzer : 1 kHz gated by a held key.  Proves the buzzer path independently
    -- of the game's sound effects.  Also silent when SW7=0.
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                buzz_r <= '0';
            elsif (t_1k = '1') then
                buzz_r <= not buzz_r;      -- 1 kHz square wave
            end if;
        end if;
    end process;

    buzz <= buzz_r when ((sw7 = '1') and (key /= K_NONE)) else '0';

end architecture rtl;
