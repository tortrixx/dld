-- ============================================================================
--  buzzer_ctrl  ——  蜂鸣器音效 / 音乐播放器
--  所属子系统：S7（声音输出）
--  提高要求 A1：不同情况播放不同的提示音效或音乐。
--
--  板载蜂鸣器由 PIN_60 驱动，输入方波即可发声。因此"一个音"只是一个
--  分频比，真正的工作是决定播放哪个音、持续多久。
--
--  实现结构：
--    · 50 MHz 先 256 分频，得到 195.3125 kHz 的时间基准；
--    · 8 个音高共用一个方波发生器，半周期计数值由音高查表得到；
--    · 16 步节奏共用一个步进计数器，每 250 ms 推进一步，
--      一句 = 16 步 = 4 s 循环；
--    · 每步 4 位：bit3 = 这一步是否发声，bit2..0 = 音高索引。
--
--  音高表（目标音名 / 半周期计数值）：
--     idx 0 E5  659.3 Hz -> 148    idx 4 B5   987.8 Hz ->  99
--     idx 1 G5  784.0 Hz -> 125    idx 5 C6  1046.5 Hz ->  93
--     idx 2 A5  880.0 Hz -> 111    idx 6 E6  1318.5 Hz ->  74
--     idx 3 A#5 932.3 Hz -> 105    idx 7 G6  1568.0 Hz ->  62
--  实际频率约为 195312.5 / (2*(half+1))，受取整影响整体比目标音名
--  低约 1%，音程关系不变。这个音域落在小蜂鸣器的高效区；
--  256 分频后计数器只需 8 位。
--
--  音效码（game_fsm 产生，见 puzzle_pkg.SND_*）：
--     0000 静音        0001 自检（POST 单声）
--     0010 预览        0011 过关
--     0100 拼错        0101 按键（保留，当前不发出）
--     0110 通关        0111 失败
--     1000 第一关 BGM  1001 第二关 BGM  1011 第三关 BGM
--     1010 旋转、1100 确认、1101/1110/1111：保留码，查表落入 when others
--     时为静音；当前 game_fsm 不产生这些码。
--
--  背景音乐码 1000 / 1001 / 1011 正好等于 "10" & lvl3 & level，
--  因此 game_fsm 选曲只需拼线，不花逻辑单元。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity buzzer_ctrl is
    port (
        i_clk  : in  std_logic;                      -- 50 MHz
        i_rst  : in  std_logic;                      -- 高电平有效
        i_en   : in  std_logic;                      -- '0' = 强制静音（SW7）
        i_sel  : in  std_logic_vector(3 downto 0);   -- 音效码
        i_t4   : in  std_logic;                      -- 4 Hz tick：一步一个音
        o_buzz : out std_logic
    );
end entity buzzer_ctrl;

architecture rtl of buzzer_ctrl is

    ----------------------------------------------------------------------------
    -- 预分频：50 MHz / 256 = 195.3125 kHz。
    -- 下游都数这个 tick，所以半周期计数器只需 8 位（最大值 148）。
    ----------------------------------------------------------------------------
    constant PRE_DIV : integer := 256;

    ----------------------------------------------------------------------------
    -- 8 个音高的半周期（单位：预分频后的 tick 数）
    ----------------------------------------------------------------------------
    function note_half(n : std_logic_vector(2 downto 0))
        return unsigned is
        variable v : unsigned(7 downto 0);
    begin
        case n is
            when "000"  => v := to_unsigned(148, 8);   -- E5
            when "001"  => v := to_unsigned(125, 8);   -- G5
            when "010"  => v := to_unsigned(111, 8);   -- A5
            when "011"  => v := to_unsigned(105, 8);   -- A#5
            when "100"  => v := to_unsigned(99, 8);    -- B5
            when "101"  => v := to_unsigned(93, 8);    -- C6（约 1 kHz，POST 自检声）
            when "110"  => v := to_unsigned(74, 8);    -- E6
            when others => v := to_unsigned(62, 8);    -- G6
        end case;
        return v;
    end function;

    -- 一段旋律 = 16 步，每步 4 位：bit3 = 发声，bit2..0 = 音高索引。
    -- 换旋律只改常量表，不碰逻辑。
    type mel_t is array (0 to 15) of std_logic_vector(3 downto 0);

    -- 0000 静音
    constant MEL_SILENT : mel_t := ("0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 0001 自检：POST"一短声 = 自检通过"惯例。
    -- 第 0 步和第 8 步各一声 C6；自检窗口恒为 8 个旋律步，
    -- 因此无论从哪一步开始，都必然恰好听到一声。
    constant MEL_SELF   : mel_t := ("1101", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000",
                                    "1101", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 0010 预览：上行纯五度 A5 -> E6，总长 0.75 s，全系统最短的提示音。
    constant MEL_PREV   : mel_t := ("1010", "1110", "1110", "0000",
                                    "0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 0011 过关：C6 E6 G6 E6 上行琶音回旋（大三和弦 = 通用的"通过"语汇）。
    -- 事件音只保持 2 个旋律步，而步进计数器自由走，因此整句必须每步都发声。
    constant MEL_CLEAR  : mel_t := ("1101", "1110", "1111", "1110",
                                    "1101", "1110", "1111", "1110",
                                    "1101", "1110", "1111", "1110",
                                    "1101", "1110", "1111", "1110");
    -- 0100 拼错：E6 起纯下行 + 低音抖动 ×2（每步都发声，理由同上）。
    constant MEL_WRONG  : mel_t := ("1110", "1101", "1100", "1011",
                                    "1010", "1001", "1000", "1001",
                                    "1110", "1101", "1100", "1011",
                                    "1010", "1001", "1000", "1001");
    -- 0101 按键：G6 高音短促 blip（保留码，当前不发出）。
    constant MEL_KEY    : mel_t := ("1111", "1111", "1111", "1111",
                                    "1111", "1111", "1111", "1111",
                                    "1111", "1111", "1111", "1111",
                                    "1111", "1111", "1111", "1111");
    -- 0110 通关：最高音区、同音反复 + 拖长，收在 G6。
    constant MEL_WIN    : mel_t := ("1111", "0000", "1111", "0000",
                                    "1111", "0000", "1111", "1111",
                                    "1111", "0000", "1110", "1110",
                                    "0000", "1111", "1111", "1111");
    -- 0111 失败：从最高音区大跳落到最低音 E5，并保持 2 步站住。
    constant MEL_FAIL   : mel_t := ("1110", "0000", "1010", "0000",
                                    "1000", "1000", "0000", "0000",
                                    "0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 1000 第一关 BGM：Overworld 主题开头，用"下一个要响的音"填满休止，
    -- 使 16 步全部发声，形成连贯的旋律线。
    constant MEL_BGM1   : mel_t := ("1110", "1110", "1110", "1110",
                                    "1101", "1101", "1110", "1111",
                                    "1111", "1001", "1001", "1001",
                                    "1001", "1001", "1001", "1001");
    -- 1001 第二关 BGM：低音区块状脉冲，E5 -> G5 -> A5 -> E5，每音 4 拍。
    -- 三关 BGM 的区别主要靠音区与换音速率，而不是靠休止的疏密。
    constant MEL_BGM2   : mel_t := ("1000", "1000", "1000", "1000",
                                    "1001", "1001", "1001", "1001",
                                    "1010", "1010", "1010", "1010",
                                    "1000", "1000", "1000", "1000");
    -- 1010 旋转（保留，当前不发出；查表臂已省略 -> 静音）。
    constant MEL_ROT    : mel_t := ("1000", "1001", "1010", "1011",
                                    "1100", "1101", "1110", "1111",
                                    "1000", "1001", "1010", "1011",
                                    "1100", "1101", "1110", "1111");
    -- 1011 第三关 BGM：在 G5..E6 之间快速换音（15 个相邻音对里换 14 次）。
    constant MEL_BGM3   : mel_t := ("1001", "1100", "1101", "1110",
                                    "1101", "1100", "1001", "1100",
                                    "1101", "1110", "1110", "1101",
                                    "1100", "1001", "1100", "1101");
    -- 1100 确认（保留，当前不发出；查表臂已省略 -> 静音）。
    constant MEL_LOCK   : mel_t := ("1111", "1101", "1111", "1101",
                                    "1111", "1101", "1111", "1101",
                                    "1111", "1101", "1111", "1101",
                                    "1111", "1101", "1111", "1101");
    -- 1101 选择（保留）
    constant MEL_SEL    : mel_t := ("1101", "1101", "1101", "1101",
                                    "1101", "1101", "1101", "1101",
                                    "1101", "1101", "1101", "1101",
                                    "1101", "1101", "1101", "1101");
    -- 1110 移动（保留）
    constant MEL_MOVE   : mel_t := ("1000", "1000", "1000", "1000",
                                    "1000", "1000", "1000", "1000",
                                    "1000", "1000", "1000", "1000",
                                    "1000", "1000", "1000", "1000");
    -- 1111 计时催促（保留）
    constant MEL_WARN   : mel_t := ("1101", "1000", "1101", "1000",
                                    "1101", "1000", "1101", "1000",
                                    "1101", "1000", "1101", "1000",
                                    "1101", "1000", "1101", "1000");

    signal pre_cnt  : unsigned(7 downto 0) := (others => '0');   -- 256 分频计数器
    signal tick     : std_logic := '0';                          -- 195.3125 kHz
    signal step     : unsigned(3 downto 0) := (others => '0');   -- 0..15（每步 250 ms）
    signal tone_sel : std_logic_vector(2 downto 0) := "000";     -- 8 个音高
    signal on_now   : std_logic := '0';
    signal cnt      : unsigned(7 downto 0) := (others => '0');   -- 半周期计数器
    signal half     : unsigned(7 downto 0) := (others => '0');
    signal wave     : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- 预分频：50 MHz -> 195.3125 kHz
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                pre_cnt <= (others => '0');
            elsif (pre_cnt >= PRE_DIV - 1) then
                pre_cnt <= (others => '0');
            else
                pre_cnt <= pre_cnt + 1;
            end if;
        end if;
    end process;

    tick <= '1' when (pre_cnt >= PRE_DIV - 1) else '0';

    ----------------------------------------------------------------------------
    -- 步进计数器：每 250 ms 推进一步，16 步一循环。
    -- 计数器自由运行，换码时不清零；因此瞬时事件的乐句必须每步都发声，
    -- 否则事件落在休止步上就等于"按了没反应"。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                step <= (others => '0');
            elsif (i_t4 = '1') then
                step <= step + 1;             -- 4 位自然回绕，旋律循环
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 旋律查表：按"码 & 步"选音高与发声门控。
    -- 输出寄存（4 个触发器），把查表与后面的半周期比较器切开，缩短关键路径。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            case i_sel is
                when "0001" => tone_sel <= MEL_SELF(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SELF(to_integer(step))(3);
                when "0010" => tone_sel <= MEL_PREV(to_integer(step))(2 downto 0);
                               on_now   <= MEL_PREV(to_integer(step))(3);
                when "0011" => tone_sel <= MEL_CLEAR(to_integer(step))(2 downto 0);
                               on_now   <= MEL_CLEAR(to_integer(step))(3);
                when "0100" => tone_sel <= MEL_WRONG(to_integer(step))(2 downto 0);
                               on_now   <= MEL_WRONG(to_integer(step))(3);
                when "0101" => tone_sel <= MEL_KEY(to_integer(step))(2 downto 0);
                               on_now   <= MEL_KEY(to_integer(step))(3);
                when "0110" => tone_sel <= MEL_WIN(to_integer(step))(2 downto 0);
                               on_now   <= MEL_WIN(to_integer(step))(3);
                when "0111" => tone_sel <= MEL_FAIL(to_integer(step))(2 downto 0);
                               on_now   <= MEL_FAIL(to_integer(step))(3);
                when "1000" => tone_sel <= MEL_BGM1(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM1(to_integer(step))(3);
                when "1001" => tone_sel <= MEL_BGM2(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM2(to_integer(step))(3);
                when "1011" => tone_sel <= MEL_BGM3(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM3(to_integer(step))(3);
                -- 1010 / 1100 等保留码没有查表臂，落入 when others -> 静音
                when "0000" => tone_sel <= MEL_SILENT(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SILENT(to_integer(step))(3);
                when others => tone_sel <= "000";
                               on_now   <= '0';      -- 未定义码 -> 静音
            end case;
        end if;
    end process;

    half <= note_half(tone_sel);

    ----------------------------------------------------------------------------
    -- 方波发生器：所有音高共用一个振荡器。
    -- cnt 数到 half 就翻转并清零；cnt 数的是预分频后的 tick。
    -- 用"相等"而不是"大于等于"：cnt 从 0 逐 1 加到 half 必然恰好相等，
    -- 而相等比较比进位链便宜。
    --
    -- 每个 i_t4（换步）脉冲把 cnt 清零：让每个旋律步都从干净相位起振，
    -- 避免换到更高音时新的 half 小于当前 cnt、要等计数器回绕才对齐。
    -- 换步那一拍只清 cnt、不翻 wave，因此不会多出一次翻转。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                cnt  <= (others => '0');
                wave <= '0';
            elsif (i_t4 = '1') or (tick = '1') then
                if (i_t4 = '1') then
                    cnt <= (others => '0');
                elsif (cnt = half) then
                    cnt  <= (others => '0');
                    wave <= not wave;
                else
                    cnt <= cnt + 1;
                end if;
            end if;
        end if;
    end process;

    o_buzz <= wave when ((i_en = '1') and (on_now = '1')) else '0';

end architecture rtl;
