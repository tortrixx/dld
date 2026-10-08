-- ============================================================================
--  keypad_diag_top  --  KEYPAD MAP MEASUREMENT (authoritative pin constraints)
--
--  PURPOSE
--  -------
--  The keypad now responds, but the physical position of each key is still an
--  assumption.  This build removes every assumption: it shows the raw key index
--  that the scanner measures (4*row + column, row 0 = top) AND the game key that
--  the current map derives from it, so the two can be compared in one glance.
--
--  DISPLAY
--      DISP7 DISP6 = raw key index (0..15) as a TWO-DIGIT decimal (tens, units).
--                    Read them together, e.g. "1" "2" = key index 12.
--                    (Previously DISP7 held the raw 4-bit code directly, but the
--                     BCD decoder renders 10..15 as BLANK, so key indexes >= 10
--                     were unreadable.  Split into tens/units fixes that.)
--      DISP5      = a press counter (increments on every accepted new key)
--      DISP4      = number of DISTINCT key indexes seen so far (capped at 9)
--      DISP3      = decoded game key digit
--                      1=UP 2=START 3=DOWN 4=LEFT 5=RIGHT 6=SELECT 7=CONFIRM
--                      0=no key / unmapped
--      DISP2..DISP0 = live binary of the row lines ROW1 ROW2 ROW3 (raw
--                     electrical state, useful for spotting floating rows)
--
--  PROCEDURE
--  ---------
--  Press each key in turn and read the two digits (DISP7 DISP6).  That number is
--  the ONLY thing needed to fix the map.
--  NOTE: key index 0 is indistinguishable from "no key pressed" (the scanner
--  reports 0 = K_NONE), so KEY13 (bottom-left) is EXPECTED to show nothing and
--  must never be given a game function.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity keypad_diag_top is
    port (
        clk      : in  std_logic;
        sw7      : in  std_logic;
        btn      : in  std_logic;
        kp_row   : in  std_logic_vector(3 downto 0);
        kp_col   : out std_logic_vector(3 downto 0);
        dot_row  : out std_logic_vector(7 downto 0);
        dot_colr : out std_logic_vector(7 downto 0);
        dot_colg : out std_logic_vector(7 downto 0);
        seg      : out std_logic_vector(7 downto 0);
        cat      : out std_logic_vector(7 downto 0);
        buzz     : out std_logic
    );
end entity keypad_diag_top;

architecture rtl of keypad_diag_top is

    signal rst     : std_logic;
    signal t_1k    : std_logic;
    signal t_200   : std_logic;
    signal t_100   : std_logic;
    signal t_2hz   : std_logic;
    signal t_1hz   : std_logic;
    signal t_40    : std_logic;

    signal key     : std_logic_vector(3 downto 0);   -- raw key index from the scanner
    signal press   : std_logic;
    signal release : std_logic;
    signal kp_raw  : std_logic_vector(3 downto 0);

    signal kdec    : std_logic_vector(3 downto 0);   -- decoded game key
    signal npress  : unsigned(3 downto 0) := (others => '0');
    signal nseen   : unsigned(3 downto 0) := (others => '0');
    signal seen    : std_logic_vector(15 downto 0) := (others => '0');

    signal disp    : std_logic_vector(31 downto 0);

    -- decode table (mirror of game_fsm.key_of so the display shows the SAME map).
    -- ⚠️ 这两处必须一致：以前这里和 game_fsm 不是同一张表，DISP3 会给出误导性的
    --    "功能"读数（DISP7 = 原始键号才是权威读数，与映射无关）。
    -- 物理对照见 rtl/game_fsm.vhd 的注释（板子丝印 KEY1..KEY16）。
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
            when others => return K_NONE;     -- 含 "0000" = 无键（KEY13 不可用）
        end case;
    end function;

    -- game key -> a single display digit
    function key_digit(k : std_logic_vector(3 downto 0))
        return std_logic_vector is
    begin
        case k is
            when K_UP      => return "0001";
            when K_START   => return "0010";
            when K_DOWN    => return "0011";
            when K_LEFT    => return "0100";
            when K_RIGHT   => return "0101";
            when K_SELECT  => return "0110";
            when K_CONFIRM => return "0111";
            when others    => return "0000";
        end case;
    end function;

begin

    u_clk : entity work.clk_gen
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

    u_keypad : entity work.keypad_scan
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

    kdec <= key_of(key);

    -- count presses and how many distinct keys have been seen
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') or (sw7 = '0') then
                npress <= (others => '0');
                nseen  <= (others => '0');
                seen   <= (others => '0');
            else
                if (press = '1') then
                    npress <= npress + 1;
                end if;
                if (release = '1') and (nseen < 15) then
                    null;                        -- placeholder, kept explicit
                end if;
                if (press = '1') and (seen(to_integer(unsigned(key))) = '0') then
                    seen(to_integer(unsigned(key))) <= '1';
                    nseen <= nseen + 1;
                end if;
            end if;
        end if;
    end process;

    -- 原始键号用**两位十进制**显示：DISP7 = 十位(0/1)、DISP6 = 个位(0~9)。
    -- 为什么不用原来"DISP7 直接放 4 位键号"：BCD 译码器把 10~15 译成**空白**，
    -- 于是键号 ≥10 的键（KEY1~KEY4、KEY7、KEY8）根本读不出来 —— 拆成十位/个位后
    -- 0~15 全部可读（例如 KEY1 显示 "1""2"）。
    process (key)
        variable k : integer range 0 to 15;
    begin
        k := to_integer(unsigned(key));
        if (k >= 10) then
            disp(31 downto 28) <= "0001";                                  -- 十位 = 1
            disp(27 downto 24) <= std_logic_vector(to_unsigned(k - 10, 4));-- 个位
        else
            disp(31 downto 28) <= "0000";                                  -- 十位 = 0
            disp(27 downto 24) <= std_logic_vector(to_unsigned(k, 4));     -- 个位
        end if;
    end process;
    disp(23 downto 20) <= std_logic_vector(npress);      -- press counter
    disp(19 downto 16) <= std_logic_vector(nseen);       -- distinct keys seen
    disp(15 downto 12) <= key_digit(kdec);              -- decoded game key
    disp(11 downto 8)  <= "000" & kp_row(1);
    disp(7 downto 4)   <= "000" & kp_row(2);
    disp(3 downto 0)   <= "000" & kp_row(3);

    u_seg : entity work.seg_scan
        port map (
            i_clk    => clk,
            i_rst    => rst,
            i_tick   => t_200,
            i_en     => sw7,
            i_data   => disp,
            i_blank  => (others => '0'),
            i_raw_en => '0',
            i_raw    => (others => '0'),
            o_seg    => seg,
            o_cat    => cat
        );

    u_dot : entity work.dot_matrix_scan
        port map (
            i_clk   => clk,
            i_rst   => rst,
            i_en    => '0',
            i_row   => "000",
            i_colr  => (others => '0'),
            i_colg  => (others => '0'),
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );

    buzz <= '0';

end architecture rtl;
