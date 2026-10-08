-- ============================================================================
--  game_fsm  --  master state machine : game flow, countdowns, level switching
--  Subsystem : S3 (game control)
--
--  This module owns TIME and DECISIONS.  It owns no coordinates: every spatial
--  question is answered by puzzle_ctrl.
--
--  State flow (requirement numbers in brackets):
--
--      SW7=0 ──► everything dark (B1)
--      S_SELF_TEST  2 s, 2 Hz flash (B1)
--      S_IDLE       DISP7=5, DISP0=level (B2, B3)
--        --"start"-->  S_PREVIEW
--      S_PREVIEW    5 s preview, countdown on DISP7 (B4)
--        --preview ends--> scatter pieces, S_PLAYING
--      S_PLAYING     30 s (level 1) / 40 s (level 2) countdown on DISP4:DISP3
--                    "select" cycles the selected piece (B6)
--                    arrows move it, validated by puzzle_ctrl (B7)
--                    "confirm" locks it (B8)
--                    all locked and on target  -> S_WIN (level 1 -> level 2)
--                    all locked but wrong, or timeout -> S_FAIL (B9, B10)
--      S_WIN / S_FAIL   picture shown; "start" begins a new game (B11)
--
--  "start" also works DURING play, which is requirement B11.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity game_fsm is
    port (
        i_clk      : in  std_logic;
        i_rst      : in  std_logic;                      -- active HIGH
        i_sw       : in  std_logic;                      -- SW7 system switch
        i_tick_1hz : in  std_logic;
        i_tick_2hz : in  std_logic;
        i_press    : in  std_logic;                      -- 1-clock: a key was accepted
        i_key      : in  std_logic_vector(3 downto 0);   -- accepted key code
        o_sel      : out std_logic;                      -- 1-clock: cycle selection
        o_move     : out std_logic;                      -- 1-clock: move request
        o_conf     : out std_logic;                      -- 1-clock: lock request
        o_go       : out std_logic;                      -- 1-clock: (re)scatter
        o_up       : out std_logic;
        o_down     : out std_logic;
        o_left     : out std_logic;
        o_right    : out std_logic;
        o_level    : out std_logic;                      -- '0' = level 1, '1' = level 2
        o_state    : out std_logic_vector(2 downto 0);   -- state_t
        o_time     : out std_logic_vector(5 downto 0);   -- countdown seconds
        o_blink    : out std_logic;                      -- 2 Hz blink flag
        i_solved   : in  std_logic;                      -- from puzzle_ctrl
        i_all_lock : in  std_logic;                      -- from puzzle_ctrl
        i_shuf_busy: in  std_logic;                      -- from puzzle_ctrl
        o_sound    : out std_logic_vector(2 downto 0)    -- sound effect selector
    );
end entity game_fsm;

architecture rtl of game_fsm is

    ----------------------------------------------------------------------------
    -- KEY MAP -- the ONE place where a keypad position becomes a game key.
    --
    -- The scanner reports the plain index  4*row + column  where **row 0 is the
    -- BOTTOM physical row** (the board's silkscreen labels the rows ROW3 at the
    -- top down to ROW0 at the bottom -- see the board manual, 附图26) and column 0
    -- is the LEFT-most column (COL0..COL3 printed left to right).
    --
    -- The board's keys are printed KEY1..KEY16, reading left-to-right and
    -- top-to-bottom, so the physical grid and the reported index are:
    --
    --            COL0   COL1   COL2   COL3
    --   ROW3     KEY1   KEY2   KEY3   KEY4        index 12..15
    --   ROW2     KEY5   KEY6   KEY7   KEY8        index  8..11
    --   ROW1     KEY9   KEY10  KEY11  KEY12       index  4.. 7
    --   ROW0     KEY13  KEY14  KEY15  KEY16       index  0.. 3   <- bottom
    --
    -- CONFIRMED ON THE BENCH (2026-10-08): KEY14 (= index 1) starts the game,
    -- KEY16 (= index 3) selects a piece.  Both are kept where the player already
    -- knows them: the bottom-left / bottom-right corners of the control pad.
    --
    -- ⚠️ index 0 IS UNUSABLE: the scanner reports K_NONE ("0000") when no key is
    --    pressed, so KEY13 is indistinguishable from "nothing pressed".  It must
    --    never be given a game function (the old table mapped it to LEFT, which
    --    was dead code -- caught by simulation, see docs/06 / tb_puzzle_top ⑧).
    --
    -- The seven controls are clustered in ONE contiguous 3x3 block at the bottom
    -- right, with the arrows in the standard "plus" arrangement (centre = confirm,
    -- exactly like a numeric keypad):
    --
    --            COL1    COL2      COL3
    --   ROW2     KEY6    KEY7      KEY8
    --                    [UP]
    --   ROW1     KEY10   KEY11     KEY12
    --            [LEFT]  [CONFIRM] [RIGHT]
    --   ROW0     KEY14   KEY15     KEY16
    --            [START] [DOWN]    [SELECT]
    --
    -- Everything else returns K_NONE.  If a bench measurement ever shows a
    -- different physical position, change ONLY this function.
    ----------------------------------------------------------------------------
    function key_of(idx : std_logic_vector(3 downto 0))
        return std_logic_vector is
    begin
        case idx is
            when "0001" => return K_START;    -- KEY14  (bench-confirmed)
            when "0011" => return K_SELECT;   -- KEY16  (bench-confirmed)
            when "1010" => return K_UP;       -- KEY7   upper arm of the plus
            when "0010" => return K_DOWN;     -- KEY15  lower arm of the plus
            when "0101" => return K_LEFT;     -- KEY10  left arm of the plus
            when "0111" => return K_RIGHT;    -- KEY12  right arm of the plus
            when "0110" => return K_CONFIRM;  -- KEY11  centre of the plus
            when others => return K_NONE;     -- incl. "0000" = no key (KEY13)
        end case;
    end function;

    signal st      : state_t := S_SELF_TEST;
    signal level   : std_logic := '0';
    signal cnt     : unsigned(5 downto 0) := (others => '0');
    signal selfc   : unsigned(1 downto 0) := (others => '0');   -- self-test seconds

    -- one-cycle command strobes handed to puzzle_ctrl, created in the outputs
    -- section below
    signal req_go  : std_logic := '0';
    signal move_r  : std_logic := '0';

    signal up_r, down_r, left_r, right_r : std_logic := '0';
    signal sel_r, conf_r : std_logic := '0';
    signal sound_r : std_logic_vector(2 downto 0) := "000";
    signal sound_p : std_logic_vector(2 downto 0) := "000";
    -- 2 Hz SQUARE WAVE for the blinks.
    -- The tick from clk_gen is a ONE-CLOCK pulse (10 ms wide), so using
    -- it directly as a blink LEVEL leaves the display lit for a single
    -- clock per 500 ms -- effectively invisible.  This toggle turns it into
    -- a 50 % duty square wave, which is what B1 ("flashing at 2 Hz") means.
    signal blink_r : std_logic := '0';
    signal kdec    : std_logic_vector(3 downto 0) := K_NONE;  -- decoded game key
    signal go_done : std_logic := '0';   -- scatter already requested this session

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
    -- Countdown / state register.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                st    <= S_SELF_TEST;
                level <= '0';
                cnt   <= (others => '0');
                selfc <= (others => '0');
            elsif (i_sw = '0') then
                -- B1: with the switch off the whole system is held at the top of
                -- the sequence, so switching back on always shows a fresh
                -- self-test / idle rather than resuming a half-played game.
                st    <= S_SELF_TEST;
                level <= '0';
                cnt   <= (others => '0');
                selfc <= (others => '0');
            else
                case st is

                    when S_SELF_TEST =>
                        if (i_tick_1hz = '1') then
                            if (selfc = 1) then            -- 2 seconds
                                selfc <= (others => '0');
                                st    <= S_IDLE;
                            else
                                selfc <= selfc + 1;
                            end if;
                        end if;

                    when S_IDLE =>
                        if (i_press = '1') and (kdec = K_START) then
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';                  -- a new game starts at level 1
                            st    <= S_PREVIEW;
                        end if;

                    when S_PREVIEW =>
                        if (i_press = '1') and (kdec = K_START) then
                            -- B11: start again at any time
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';
                            st    <= S_PREVIEW;
                        elsif (i_tick_1hz = '1') then
                            if (cnt <= 1) then
                                -- Preview over.  Load the level's TIME LIMIT here
                                -- (requirement B5 = 30 s, B10 = 40 s).  This was
                                -- missing: cnt stayed at 1 from the preview, so
                                -- the first playing tick immediately timed out and
                                -- the game ended after under a second.
                                if (level = '0') then
                                    cnt <= to_unsigned(T_LEVEL1, 6);
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
                            st    <= S_PREVIEW;
                        elsif (i_solved = '1') and (shuf_seen = '1')
                              and (i_shuf_busy = '0') then
                            if (level = '0') then
                                level <= '1';              -- B9: go to level 2
                                cnt   <= to_unsigned(T_PREVIEW, 6);
                                st    <= S_PREVIEW;
                            else
                                st <= S_WIN;               -- B10: victory
                            end if;
                        elsif (i_all_lock = '1') and (shuf_seen = '1')
                              and (i_shuf_busy = '0') then
                            st <= S_FAIL;                  -- B9: wrong assembly
                        elsif (i_tick_1hz = '1') then
                            if (cnt <= 1) then
                                st <= S_FAIL;              -- B9/B10: timeout
                            else
                                cnt <= cnt - 1;
                            end if;
                        end if;

                    when S_WIN | S_FAIL =>
                        if (i_press = '1') and (kdec = K_START) then
                            cnt   <= to_unsigned(T_PREVIEW, 6);
                            level <= '0';
                            st    <= S_PREVIEW;            -- B11
                        end if;

                    when others =>
                        st <= S_SELF_TEST;
                end case;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Command decoding: key strobes for puzzle_ctrl.
    --   start   -> handled by the state register above
    --   select  -> cycle the selected piece            (B6)
    --   confirm -> lock the selected piece             (B8)
    --   arrows  -> move the selected piece             (B7)
    -- Movement and locking are only accepted while actually playing.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sel_r   <= '0';
                conf_r  <= '0';
                up_r    <= '0'; down_r  <= '0';
                left_r  <= '0'; right_r <= '0';
                move_r  <= '0';
                req_go  <= '0';
                shuf_seen <= '0';
            else
                -- defaults: every command is a one-clock strobe
                sel_r  <= '0';
                conf_r <= '0';
                move_r <= '0';
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
                        when others    => null;
                    end case;
                end if;

                -- scatter request: raised when playing begins, held until the
                -- engine reports it is no longer busy.  Using a request/ack
                -- handshake (instead of one strobe) means the scatter can never
                -- be missed, however long it takes.
                -- Scatter request: ONE request per play session.
                -- Without the go_done memory, the handshake re-fires the moment
                -- the engine returns to idle, so the engine was being re-scattered
                -- continuously -- which clears sel/locked every time and keeps the
                -- engine busy, so no key could ever have an effect.
                if (st /= S_PLAYING) then
                    req_go  <= '0';
                    go_done <= '0';                -- re-arm for the next session
                elsif (req_go = '0') and (go_done = '0') and (i_shuf_busy = '0') then
                    req_go <= '1';                 -- one request...
                elsif (i_shuf_busy = '1') then
                    req_go  <= '0';                -- ...accepted by the engine
                    go_done <= '1';                -- never request again this session
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
    -- Sound effect selection (improvement requirement A1).  Each situation gets
    -- its own code; buzzer_ctrl turns the code into an audible pattern.
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                blink_r <= '0';
            elsif (i_tick_2hz = '1') then
                blink_r <= not blink_r;      -- 2 Hz square wave, 50 % duty
            end if;
        end if;
    end process;

    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sound_p <= "000";
            else
                -- register the code: it feeds buzzer_ctrl, whose oscillator then
                -- drives the buzz pin, and chaining all of that combinationally
                -- after the state decode was the reported critical path
                sound_p <= sound_r;
            end if;
        end if;
    end process;

    process (st, i_press, i_key, i_solved, i_all_lock, shuf_seen)
    begin
        case st is
            when S_SELF_TEST => sound_r <= "001";        -- power-on jingle
            when S_IDLE      => sound_r <= "000";        -- silent
            when S_PREVIEW   => sound_r <= "010";        -- preview beep
            when S_PLAYING =>
                -- ERR-024: 判据齐备（散落已跑过）之前的残留状态不许出声
                if (i_solved = '1') and (shuf_seen = '1') then
                    sound_r <= "011";                    -- correct: rising beep
                elsif (i_all_lock = '1') and (shuf_seen = '1') then
                    sound_r <= "100";                    -- wrong: falling beep
                elsif (i_press = '1') then
                    sound_r <= "101";                    -- key click
                else
                    sound_r <= "000";
                end if;
            when S_WIN  => sound_r <= "110";             -- victory jingle
            when S_FAIL => sound_r <= "111";             -- failure jingle
            when others => sound_r <= "000";
        end case;
    end process;

    ----------------------------------------------------------------------------
    -- Outputs
    ----------------------------------------------------------------------------
    -- the scanner's raw key index is decoded into a game key in one place
    kdec <= key_of(i_key);

    o_state    <= st;
    o_level    <= level;
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
    o_sound    <= sound_p;

end architecture rtl;
