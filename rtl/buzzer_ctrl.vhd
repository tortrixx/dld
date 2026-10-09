-- ============================================================================
--  buzzer_ctrl  --  提示音效 / 音乐
--  Subsystem : S7 (sound output)
--  Improvement requirement A1 ("不同情况下播放不同的提示音效或音乐").
--
--  The board's buzzer is driven on PIN_60: writing a square wave in the audio
--  band makes it sound.  A "note" is therefore just a divider ratio, and the
--  real work is deciding WHICH note to play and FOR HOW LONG.
--
--  ---------------------------------------------------------------------------
--  ⚠️ 2026-10-09 第 13 工作阶段（A1 "统筹设计"，用户要求"确保氛围/趣味/质量"）：
--     从"4 个固定音 + 每 500 ms 换一次音"升级成**真正的旋律播放器**：
--       · 8 个音高（G4 A4 B4 C5 D5 E5 G5 C6 —— 半周期常数见下面 NOTE_HALF）；
--       · 每段音效 = 8 步 x 250 ms = **2 秒的小乐句**（step 0..7 循环）；
--       · 旋律写在常量表 MEL_* 里（每步 4 位 = 3 位音高 + 1 位"这步响不响"），
--         换旋律只改表，不碰任何逻辑 —— 这就是讲义"资源共享"里说的
--         "把耗资源的模块做成一份、用选择/复用的方式共享"：8 个音高共用**一个**
--         方波发生器，8 步节奏共用**一个**步进计数器。
--
--  Sound codes (from game_fsm) / 旋律：
--     000  silent            静音
--     001  self-test         G4 A4 B4 C5 C5 - - -     上行号角（B1 自检）
--     010  preview           A4 A4 A4 - A4 A4 - -     两声短提示
--     011  level cleared     C5 C5 E5 E5 G5 - - -     上行（过关）
--     100  wrong assembly    E5 E5 C5 C5 A4 - - -     下行（拼错）
--     101  key click         D5 - - - - - - -         单击
--     110  victory           C5 E5 G5 C6 G5 C6 C6 -   长号角（通关）
--     111  failure           B4 A4 G4 G4 G4 - - -     下行（超时）
--
--  节拍用 **i_t4 = 4 Hz（250 ms）**：一次换一个音，2 s 一句。
--  ⚠️ 原来接的是 tick_2hz（500 ms），乐句会拖成 4 s、听不出旋律。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity buzzer_ctrl is
    port (
        i_clk  : in  std_logic;
        i_rst  : in  std_logic;                      -- active HIGH
        i_en   : in  std_logic;                      -- '0' = force silence (SW7)
        i_sel  : in  std_logic_vector(2 downto 0);   -- sound code
        i_t4   : in  std_logic;                      -- 4 Hz tick (250 ms)：一步一个音
        o_buzz : out std_logic
    );
end entity buzzer_ctrl;

architecture rtl of buzzer_ctrl is

    ----------------------------------------------------------------------------
    -- 8 note pitches.  A square wave of frequency f is produced by toggling every
    -- half period, i.e. every  25_000_000 / f  board clocks (50 MHz).
    --   0 G4 392 Hz -> 63776     4 D5 587 Hz -> 42589
    --   1 A4 440 Hz -> 56818     5 E5 659 Hz -> 37936
    --   2 B4 494 Hz -> 50607     6 G5 784 Hz -> 31888
    --   3 C5 523 Hz -> 47778     7 C6 1047 Hz -> 23878
    -- All fit in 16 bits (the largest is 63776 < 65536), which is why the
    -- counter below is 16 bits wide -- NOT 17 as in the old 4-tone version.
    ----------------------------------------------------------------------------
    function note_half(n : std_logic_vector(2 downto 0))
        return unsigned is
        variable v : unsigned(15 downto 0);
    begin
        case n is
            when "000"  => v := to_unsigned(63776, 16);
            when "001"  => v := to_unsigned(56818, 16);
            when "010"  => v := to_unsigned(50607, 16);
            when "011"  => v := to_unsigned(47778, 16);
            when "100"  => v := to_unsigned(42589, 16);
            when "101"  => v := to_unsigned(37936, 16);
            when "110"  => v := to_unsigned(31888, 16);
            when others => v := to_unsigned(23878, 16);
        end case;
        return v;
    end function;

    -- one melody = 8 steps, each 4 bits = **bit3 = 响不响**, bits 2..0 = 音高
    -- （写成字符串时就是 "1"/"0" 后面跟 3 位音高，例如 "1011" = 响 + 音高 C5）
    type mel_t is array (0 to 7) of std_logic_vector(3 downto 0);

    constant MEL_SELF   : mel_t := ("1000", "1001", "1010", "1011",
                                    "1011", "0000", "0000", "0000");
    constant MEL_PREV   : mel_t := ("1001", "1001", "1001", "0000",
                                    "1001", "1001", "0000", "0000");
    constant MEL_CLEAR  : mel_t := ("1011", "1011", "1101", "1101",
                                    "1110", "0000", "0000", "0000");
    constant MEL_WRONG  : mel_t := ("1101", "1101", "1011", "1011",
                                    "1001", "0000", "0000", "0000");
    constant MEL_KEY    : mel_t := ("1100", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    constant MEL_WIN    : mel_t := ("1011", "1101", "1110", "1111",
                                    "1110", "1111", "1111", "0000");
    constant MEL_FAIL   : mel_t := ("1010", "1001", "1000", "1000",
                                    "1000", "0000", "0000", "0000");

    signal step     : unsigned(2 downto 0) := (others => '0');   -- 0..7 (250 ms/step)
    signal tone_sel : std_logic_vector(2 downto 0) := "000";
    signal on_now   : std_logic := '0';
    signal cnt      : unsigned(15 downto 0) := (others => '0');
    signal half     : unsigned(15 downto 0) := to_unsigned(63776, 16);
    signal wave     : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- Step counter: one step per 250 ms while a sound is selected.
    --
    -- ⚠️ 2026-10-09（第 13 工作阶段，实测更正）：**换码不再把步进清零**了 ——
    --    旧版本有一个 `prev` 寄存器，换码时 phase 归零；现在只有 i_rst 清 step，
    --    旋律按 (i_sel, step) 查表继续走。tb_buzzer_ctrl 断言 ⑫ 就是按这个新语义测的
    --    （换码后 step 保持、直接按新码的当前步发声）。
    --
    -- ⚠️ 已知局限（**如实记录，未修** —— 不是本轮引入的退化）：game_fsm 里
    --    "过关 011 / 拼错 100 / 按键 101" 三个码只有**1 个时钟**（i_press / i_solved
    --    是单拍脉冲，拼错/过关随后立刻换到 S_FAIL / S_PREVIEW），而旋律播放器需要
    --    码保持 ≥1 步（250 ms）才成句 —— 所以这三个码实际只发出 ~20 ns 的毛刺，
    --    等于听不见。**旧版（4 定音 + 500 ms 节奏）在这三个码上同样是 1 个时钟的门**
    --    （`on_now` 只在那一拍有效），所以**行为没有变差**。
    --    真正想修：在 game_fsm 给瞬时码加一个 2 位保持计数器（约 13 LE），
    --    或把"过关"改成 S_PREVIEW 的常驻码；当前余量（1260/1270 LE）放不下。
    --    状态保持的四个码（001 自检 / 010 预览 / 110 胜利 / 111 失败）**能完整成句**。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                step <= (others => '0');
            elsif (i_t4 = '1') then
                step <= step + 1;             -- 3 bits: wraps 7 -> 0, melody loops
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Melody lookup.  Each arm reads a CONSTANT array with a runtime index, so
    -- Quartus sees one small 6-input truth table (code & step -> tone & gate)
    -- instead of seven separate 32-bit muxes.
    -- ⚠️ 输出**寄存**（+4 FF，实测把"码/步 -> 音高 -> 半周期 -> 比较器"这条链
    --    切在表后面；不寄存时它就成了全设计的最差路径之一）。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            case i_sel is
                when "001"  => tone_sel <= MEL_SELF(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SELF(to_integer(step))(3);
                when "010"  => tone_sel <= MEL_PREV(to_integer(step))(2 downto 0);
                               on_now   <= MEL_PREV(to_integer(step))(3);
                when "011"  => tone_sel <= MEL_CLEAR(to_integer(step))(2 downto 0);
                               on_now   <= MEL_CLEAR(to_integer(step))(3);
                when "100"  => tone_sel <= MEL_WRONG(to_integer(step))(2 downto 0);
                               on_now   <= MEL_WRONG(to_integer(step))(3);
                when "101"  => tone_sel <= MEL_KEY(to_integer(step))(2 downto 0);
                               on_now   <= MEL_KEY(to_integer(step))(3);
                when "110"  => tone_sel <= MEL_WIN(to_integer(step))(2 downto 0);
                               on_now   <= MEL_WIN(to_integer(step))(3);
                when "111"  => tone_sel <= MEL_FAIL(to_integer(step))(2 downto 0);
                               on_now   <= MEL_FAIL(to_integer(step))(3);
                when others => tone_sel <= "000";
                               on_now   <= '0';      -- "000" = silent
            end case;
        end if;
    end process;

    half <= note_half(tone_sel);

    ----------------------------------------------------------------------------
    -- Square-wave generator (one shared oscillator for all eight pitches)
    ----------------------------------------------------------------------------
    -- ⚠️ 试过"倒计数 + 等于 0 判定"（想用宽 NOR 换掉 16 位大小比较器）：
    --    实测 **buzzer_ctrl 68 -> 72 cells，反而贵 4 个**（装载 mux 比省下的比较器更贵），
    --    所以保留这个更朴素的写法。负结果记在 docs/05。
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                cnt  <= (others => '0');
                wave <= '0';
            elsif (cnt >= half) then
                cnt  <= (others => '0');
                wave <= not wave;
            else
                cnt <= cnt + 1;
            end if;
        end if;
    end process;

    o_buzz <= wave when ((i_en = '1') and (on_now = '1')) else '0';

end architecture rtl;
