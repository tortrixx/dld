-- ============================================================================
--  disp_format  ——  把游戏状态转成数码管内容
--  子系统：S6（显示）
--
--  决定显示内容的需求：
--    B1  自检：八个数码管全部显示 "8"，以 2 Hz 闪烁
--    B2  空闲      ：DISP7 显示 "5"，DISP0 显示 "1"（第 1 关），其余消隐
--    B3  关卡编号由 DISP0 显示
--    B4  预览      ：DISP7 显示 5 s 预览的倒计时
--    B5  游戏中    ：DISP4:DISP3 显示两位剩余时间
--    B9  第 2 关   ：DISP2 额外显示 "2"
--    B10 第 2 关   ：完整图案自行设计但固定不变（PAT3）
--    A2  第 3 关   ：新增关卡（增加游戏关数）；图案从四张图案库中
--                    随机抽取 —— 显示部分不关心是哪一张，
--                    它只在 DISP0 上显示关卡编号
--
--  关卡编码（2026-10-09 / D2）：两个输入，刻意不用一根 2 位总线
--    i_level='0'            -> 第 1 关        DISP0 = 1
--    i_level='1', i_lvl3='0'-> 第 2 关        DISP0 = 2, DISP2 = '2' (B9)
--    i_level='1', i_lvl3='1'-> 第 3 关 (A2)   DISP0 = 3, DISP2 消隐
--  用两个信号而不是 2 位关卡值的原因：见 rtl/game_fsm.vhd ——
--  在这个已占用 98% 的器件上，加宽原有的关卡网络损失了 2~5 MHz 的 Fmax。
--
--  数码管编号（与板上一致：DISP7 是最左边一位）：
--    位 31..28 = DISP7，位 27..24 = DISP6，... 位 3..0 = DISP0
--
--  本模块是纯组合逻辑。它不保存任何状态 —— 决定这些数字是什么
--  是状态机的职责，决定它们如何布局
--  才是本模块的职责。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity disp_format is
    port (
        i_state : in  std_logic_vector(2 downto 0);   -- state_t
        i_level : in  std_logic;                      -- '0' = 第 1 关，'1' = 第 2/3 关
        i_lvl3  : in  std_logic;                      -- '1' = 第三关（A2）
        i_time  : in  std_logic_vector(5 downto 0);   -- 倒计时值，单位秒
        i_blink : in  std_logic;                      -- 2 Hz 闪烁标志（自检）
        o_data  : out std_logic_vector(31 downto 0);  -- 8 x BCD
        o_blank : out std_logic_vector(7 downto 0)    -- '1' = 消隐该位
    );
end entity disp_format;

architecture rtl of disp_format is

    -- 辅助函数：生成一位 BCD，以及一个消隐标志
    function bcd(v : integer) return std_logic_vector is
        variable r : std_logic_vector(3 downto 0);
    begin
        if (v < 0) or (v > 9) then
            r := "1111";          -- 超出范围 -> 译码器会把它消隐
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

        -- B3：DISP0 始终显示当前关卡 —— 1、2 或（A2 的）3。
        if (i_level = '0') then
            lvlv := 1;
        elsif (i_lvl3 = '1') then
            lvlv := 3;
        else
            lvlv := 2;
        end if;

        case i_state is

            ------------------------------------------------------------------
            -- B1 自检：八个数码管全显 "8"，以 2 Hz 闪烁。
            -- i_blink 在 2 Hz 周期的前半段为 '1'，因此在 i_blink=0 时消隐
            -- 正好得到 2 Hz 的亮/灭闪烁。
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
            -- B2 空闲：DISP7 = "5"，DISP0 = 关卡，其余全灭。
            -- DISP7 上的 "5" 是需求原文规定的空闲画面；DISP0 上的关卡
            -- 数字同时满足 B3。
            ------------------------------------------------------------------
            when S_IDLE =>
                d(31 downto 28) := bcd(5);
                bl(7) := '0';
                d(3 downto 0) := bcd(lvlv);
                bl(0) := '0';

            ------------------------------------------------------------------
            -- B4 预览：DISP7 倒计时，DISP0 显示关卡。
            ------------------------------------------------------------------
            when S_PREVIEW =>
                d(31 downto 28) := bcd(t);
                bl(7) := '0';
                d(3 downto 0) := bcd(lvlv);
                bl(0) := '0';

            ------------------------------------------------------------------
            -- B5 游戏中：DISP4:DISP3 = 剩余秒数（两位），
            -- DISP0 = 关卡，且在第二关时 DISP2 = "2"（要求 B9）。
            --   ⚠️ 2026-10-09（D2）：DISP2 只在**第二关**亮 —— B9 的原文是
            --      "游戏进入第二关，数码管DISP2 显示'2'"；第三关（A2 新增，题目
            --      没有规定）与第一关一样熄灭。这条口径是否要改成"第二关起一直亮
            --      / 第三关改亮 '3'"，用户 2026-10-09 决定**先问老师**，
            --      见 docs/06 §12、HANDOFF §1.4b（Q2b）。
            --
            -- 十位/个位的拆分用的是查找表，而不是 "/ 10" 和 "mod 10"。
            -- Quartus 为这个除法推断出 lpm_divide，而报告的关键路径
            -- （26 ns，也就是只有 39 MHz）正好穿过它的
            -- 进位链。64 项的查找表就是一个小 ROM，能把
            -- 除法器从设计中彻底去掉。
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
                    when others =>                 -- 40..63（第二关的上限是 40）
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

                if (i_level = '1') and (i_lvl3 = '0') then
                    d(11 downto 8) := bcd(2);    -- DISP2：仅第二关（B9）
                    bl(2) := '0';
                end if;

            ------------------------------------------------------------------
            -- 胜利 / 失败：结算画面用**数码管拼字**（2026-10-08 用户拍板）
            --   S_WIN  → DISP7..DISP4 = "PASS"
            --   S_FAIL → DISP7..DISP4 = "FAIL"
            --   原来只是随意挑的 "75"/"00"（唯一理由是"和其它状态都不重复"），
            --   被问"75 是什么"时无法自解释；现在改成一眼能读懂的结算信息。
            --   码值定义在 puzzle_pkg 的 DIG_*；'S' 与 '5' 同形、'I' 用 '1' 的形状
            --   （7 段管的固有限制，报告里如实写明）。
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
