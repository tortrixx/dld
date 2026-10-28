-- ============================================================================
--  disp_format  ——  把游戏状态转成数码管内容
--  所属子系统：S6（显示）
--
--  各状态显示的内容：
--    S_SELF_TEST  八位全显 "8"，以 2 Hz 闪烁              （B1）
--    S_IDLE       DISP7 = "5"，DISP0 = 关卡号，其余熄灭    （B2、B3）
--    S_PREVIEW    DISP7 = 预览倒计时，DISP0 = 关卡号       （B4）
--    S_PLAYING    DISP4:DISP3 = 剩余秒数，DISP0 = 关卡号   （B5）
--    S_WIN        DISP7..DISP4 = "PASS"（通过）
--    S_FAIL       DISP7..DISP4 = "FAIL"（失败）
--
--  关卡号编码（两个输入，而不是一根 2 位总线）：
--    i_level='0'              -> 第 1 关，DISP0 = 1
--    i_level='1', i_lvl3='0'  -> 第 2 关，DISP0 = 2
--    i_level='1', i_lvl3='1'  -> 第 3 关，DISP0 = 3
--
--  注意：题目 B9 有"第二关 DISP2 显示 2"，与 B3"关数由 DISP0 显示"冲突。
--  本设计统一采用 B3 口径：关卡号只由 DISP0 显示，DISP2 始终熄灭。
--
--  数码管编号与板上一致：DISP7 在最左，位 31..28 = DISP7，位 3..0 = DISP0。
--  本模块是纯组合逻辑，不保存任何状态。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity disp_format is
    port (
        i_state : in  std_logic_vector(2 downto 0);   -- state_t
        i_level : in  std_logic;                      -- '0' = 第 1 关，'1' = 第 2/3 关
        i_lvl3  : in  std_logic;                      -- '1' = 第三关
        i_time  : in  std_logic_vector(5 downto 0);   -- 倒计时值，单位秒
        i_blink : in  std_logic;                      -- 2 Hz 闪烁标志（自检）
        o_data  : out std_logic_vector(31 downto 0);  -- 8 x BCD
        o_blank : out std_logic_vector(7 downto 0)    -- '1' = 消隐该位
    );
end entity disp_format;

architecture rtl of disp_format is

    -- 生成一位 BCD：超出 0..9 时返回 0xF，由译码器消隐。
    function bcd(v : integer) return std_logic_vector is
        variable r : std_logic_vector(3 downto 0);
    begin
        if (v < 0) or (v > 9) then
            r := "1111";
        else
            r := std_logic_vector(to_unsigned(v, 4));
        end if;
        return r;
    end function;

begin

    process (i_state, i_level, i_lvl3, i_time, i_blink)
        variable d    : std_logic_vector(31 downto 0);
        variable bl   : std_logic_vector(7 downto 0);
        variable t    : integer range 0 to 99;
        variable tens : integer range 0 to 9;
        variable ones : integer range 0 to 9;
        variable lvlv : integer range 1 to 3;
    begin
        d  := (others => '0');
        bl := (others => '1');            -- 默认全部消隐
        t  := to_integer(unsigned(i_time));

        -- 关卡号：1 / 2 / 3
        if (i_level = '0') then
            lvlv := 1;
        elsif (i_lvl3 = '1') then
            lvlv := 3;
        else
            lvlv := 2;
        end if;

        case i_state is

            ------------------------------------------------------------------
            -- B1 自检：八位全显 "8"，以 2 Hz 闪烁。
            -- i_blink 为 '1' 时点亮，因此亮 / 灭各占 250 ms。
            ------------------------------------------------------------------
            when S_SELF_TEST =>
                for k in 0 to 7 loop
                    d(4 * k + 3 downto 4 * k) := bcd(8);
                    if (i_blink = '1') then
                        bl(k) := '0';
                    else
                        bl(k) := '1';
                    end if;
                end loop;

            ------------------------------------------------------------------
            -- B2 空闲：DISP7 = "5"，DISP0 = 关卡号，其余熄灭。
            ------------------------------------------------------------------
            when S_IDLE =>
                d(31 downto 28) := bcd(5);
                bl(7) := '0';
                d(3 downto 0) := bcd(lvlv);
                bl(0) := '0';

            ------------------------------------------------------------------
            -- B4 预览：DISP7 = 倒计时，DISP0 = 关卡号。
            ------------------------------------------------------------------
            when S_PREVIEW =>
                d(31 downto 28) := bcd(t);
                bl(7) := '0';
                d(3 downto 0) := bcd(lvlv);
                bl(0) := '0';

            ------------------------------------------------------------------
            -- B5 对局中：DISP4:DISP3 = 剩余秒数，DISP0 = 关卡号。
            --
            -- 十位 / 个位用查找表拆开，而不是写 "/ 10" 与 "mod 10"：
            -- 后者会让 Quartus 推断出 lpm_divide，其进位链成为关键路径；
            -- 64 项查找表等价于一个小 ROM，面积和时序都更好。
            ------------------------------------------------------------------
            when S_PLAYING =>
                case t is
                    when 0  => tens := 0; ones := 0;
                    when 1  => tens := 0; ones := 1;
                    when 2  => tens := 0; ones := 2;
                    when 3  => tens := 0; ones := 3;
                    when 4  => tens := 0; ones := 4;
                    when 5  => tens := 0; ones := 5;
                    when 6  => tens := 0; ones := 6;
                    when 7  => tens := 0; ones := 7;
                    when 8  => tens := 0; ones := 8;
                    when 9  => tens := 0; ones := 9;
                    when 10 => tens := 1; ones := 0;
                    when 11 => tens := 1; ones := 1;
                    when 12 => tens := 1; ones := 2;
                    when 13 => tens := 1; ones := 3;
                    when 14 => tens := 1; ones := 4;
                    when 15 => tens := 1; ones := 5;
                    when 16 => tens := 1; ones := 6;
                    when 17 => tens := 1; ones := 7;
                    when 18 => tens := 1; ones := 8;
                    when 19 => tens := 1; ones := 9;
                    when 20 => tens := 2; ones := 0;
                    when 21 => tens := 2; ones := 1;
                    when 22 => tens := 2; ones := 2;
                    when 23 => tens := 2; ones := 3;
                    when 24 => tens := 2; ones := 4;
                    when 25 => tens := 2; ones := 5;
                    when 26 => tens := 2; ones := 6;
                    when 27 => tens := 2; ones := 7;
                    when 28 => tens := 2; ones := 8;
                    when 29 => tens := 2; ones := 9;
                    when 30 => tens := 3; ones := 0;
                    when 31 => tens := 3; ones := 1;
                    when 32 => tens := 3; ones := 2;
                    when 33 => tens := 3; ones := 3;
                    when 34 => tens := 3; ones := 4;
                    when 35 => tens := 3; ones := 5;
                    when 36 => tens := 3; ones := 6;
                    when 37 => tens := 3; ones := 7;
                    when 38 => tens := 3; ones := 8;
                    when 39 => tens := 3; ones := 9;
                    when others =>
                        -- 40..63（第二关上限 40，第三关上限 60）
                        if (t >= 40) and (t < 50) then
                            tens := 4; ones := t - 40;
                        elsif (t >= 50) and (t < 60) then
                            tens := 5; ones := t - 50;
                        else
                            tens := 6; ones := t - 60;
                        end if;
                end case;

                d(19 downto 16) := bcd(tens);    -- DISP4
                bl(4) := '0';
                d(15 downto 12) := bcd(ones);    -- DISP3
                bl(3) := '0';

                d(3 downto 0) := bcd(lvlv);      -- DISP0
                bl(0) := '0';

            ------------------------------------------------------------------
            -- 结算画面：用数码管拼出 "PASS" / "FAIL"。
            -- 码值见 puzzle_pkg 的 DIG_*；'S' 与 '5' 同形、'I' 用 '1' 的
            -- 形状，是 7 段管的固有限制（报告中如实说明）。
            ------------------------------------------------------------------
            when S_WIN =>
                d(31 downto 28) := DIG_P;  bl(7) := '0';
                d(27 downto 24) := DIG_A;  bl(6) := '0';
                d(23 downto 20) := DIG_S;  bl(5) := '0';
                d(19 downto 16) := DIG_S;  bl(4) := '0';

            when S_FAIL =>
                d(31 downto 28) := DIG_F;  bl(7) := '0';
                d(27 downto 24) := DIG_A;  bl(6) := '0';
                d(23 downto 20) := DIG_I;  bl(5) := '0';
                d(19 downto 16) := DIG_L;  bl(4) := '0';

            when others =>
                null;

        end case;

        o_data  <= d;
        o_blank <= bl;
    end process;

end architecture rtl;
