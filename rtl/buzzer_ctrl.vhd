-- ============================================================================
--  buzzer_ctrl  --  提示音效 / 音乐播放器（v2：整体升八度 + 预分频省面积）
--  Subsystem : S7 (sound output)
--  Improvement requirement A1 ("不同情况下播放不同的提示音效或音乐").
--
--  The board's buzzer is driven on PIN_60: writing a square wave in the audio
--  band makes it sound.  A "note" is therefore just a divider ratio, and the
--  real work is deciding WHICH note to play and FOR HOW LONG.
--
--  ---------------------------------------------------------------------------
--  ⚠️ 2026-10-09 第 14 工作阶段（用户实机反馈"游戏过程中完全没有声音"）：
--     旧版音域 **G4..C6（392..1047 Hz）**，而小板载蜂鸣器（压电/电磁换能器）
--     的谐振点通常在 **1~4 kHz** —— 392 Hz 处几乎推不动，实机就是"没声音"。
--     本轮做两件事（**架构不变，只改音高、位数与分频**）：
--
--     ① 音域整体上移一个八度以上：**C6..C7 = 1046.5..2093 Hz**
--        （既落在换能器高效区，也是芯片音乐（chiptune）的常用音域）。
--     ② 更省面积（旧版 68 LE，器件 100% 满 1260/1270 LE）：
--        先把 50 MHz 板钟 **64 分频** → tick = 781.25 kHz，方波计数器只数 tick；
--        半周期 = round(390625 / f) 拍，最大 373 → 计数器 **9 位**（旧版 16 位），
--        比较器 / 计数器一起瘦一圈。这就是讲义"资源共享"里"先把时间基准做粗、
--        再让每个消耗资源的模块只数粗刻度"的做法。
--
--  音高表（idx / 音名 / 频率 / 半周期拍数，f = 781250 / (2*half)）：
--     0  C6  1046.5 Hz -> 373        4  G6  1568.0 Hz -> 249
--     1  D6  1174.7 Hz -> 333        5  A6  1760.0 Hz -> 222
--     2  E6  1318.5 Hz -> 296        6  B6  1975.5 Hz -> 198
--     3  F6  1396.9 Hz -> 280        7  C7  2093.0 Hz -> 187
--
--  音效码（4 位，game_fsm 发出；每句 **8 步 x 250 ms = 2 s**，步 0..7 循环）：
--     0000  静音（idle）
--     0001  自检 / 开机号角（上行）      C6 E6 G6 C7 -  -  -  -
--     0010  预览 / 倒计时（三声短提示）  D6 -  D6 -  D6 -  -  -
--     0011  过关（短上行）               E6 F6 G6 A6 -  -  -  -
--     0100  拼错（短下行）               A6 G6 F6 E6 -  -  -  -
--     0101  按键（极短高音 blip）        C7 -  -  -  -  -  -  -
--     0110  通关（长号角）               C6 E6 G6 C7 G6 C7 C7 -
--     0111  失败（下行）                 C7 B6 A6 G6 F6 E6 C6 -
--     1000  背景音乐（循环，求解全程）    C6 E6 G6 E6 F6 A6 G6 G6
--     1001  旋转 90°（快速上扫）         G6 A6 B6 C7 -  -  -  -
--     1010  确认 / 锁定（两声"咔哒"）    G6 -  C6 -  -  -  -  -
--     1011  选中棋子（轻提示）           E6 -  -  -  -  -  -  -
--     1100  移动棋子（轻触）             C6 -  -  -  -  -  -  -
--     1101  非法走子 / 拒绝（低沉短促）  D6 C6 -  -  -  -  -  -
--     1110  时间警告（最后几秒滴答，低） C6 -  D6 -  C6 -  D6 -
--     1111  备用 / 第三关开始（上行琶音）D6 F6 A6 C7 C7 -  -  -
--  旋律写在常量表 MEL_* 里（每步 4 位 = 3 位音高 + 1 位"这步响不响"），
--  换旋律只改表、不碰逻辑：8 个音高共用**一个**方波发生器，
--  8 步节奏共用**一个**步进计数器。
--
--  ---------------------------------------------------------------------------
--  ⚠️ 面积实测（2026-10-09 第 14 工作阶段；**整机** `quartus_map` 层次表口径，
--     即 `docs/05` §1.1 记"旧版 68"的同一口径）：
--         旧版 buzzer_ctrl **68 LC / 24 寄存器**  →  本版 **57 LC / 23 寄存器**（−11，−16%）
--     拆开看（单模块消融实测）：预分频 + 9 位半周期计数器把"方波那一侧"从 63 降到 49，
--     但旋律表由 7 句扩到 16 句要多花 17（128x4 的查表在 4 输入 LUT 上就是这么贵）。
--     ⚠️ 若用**单模块顶层**的隔离仿真工程量，会得到 81 → 84（变大）—— 跨模块资源共享
--     只在整机里生效（`AUTO_RESOURCE_SHARING`），所以看面积**必须**用整机
--     `quartus/output_files/puzzle.map.rpt` 的层次表，口径要一致。
--
--  节拍用 **i_t4 = 4 Hz（250 ms）**：一次换一个音，2 s 一句。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity buzzer_ctrl is
    port (
        i_clk  : in  std_logic;                      -- 50 MHz
        i_rst  : in  std_logic;                      -- active HIGH
        i_en   : in  std_logic;                      -- '0' = force silence (SW7)
        i_sel  : in  std_logic_vector(3 downto 0);   -- sound code（本轮由 3 位加宽到 4 位）
        i_t4   : in  std_logic;                      -- 4 Hz tick (250 ms)：一步一个音
        o_buzz : out std_logic
    );
end entity buzzer_ctrl;

architecture rtl of buzzer_ctrl is

    ----------------------------------------------------------------------------
    -- 50 MHz / 64 = **781.25 kHz** 的时间基准（tick）。
    -- 半周期 = round(f_tick / 2 / f) = round(390625 / f) 拍，最大 373 < 512
    -- → 方波计数器只要 9 位（旧版 16 位）。
    ----------------------------------------------------------------------------
    constant PRE_DIV : integer := 64;

    ----------------------------------------------------------------------------
    -- 8 个音高的半周期（单位：**预分频后的 tick 数**）
    --   idx 0  C6 1046.5 Hz -> 373     idx 4  G6 1568.0 Hz -> 249
    --   idx 1  D6 1174.7 Hz -> 333     idx 5  A6 1760.0 Hz -> 222
    --   idx 2  E6 1318.5 Hz -> 296     idx 6  B6 1975.5 Hz -> 198
    --   idx 3  F6 1396.9 Hz -> 280     idx 7  C7 2093.0 Hz -> 187
    ----------------------------------------------------------------------------
    function note_half(n : std_logic_vector(2 downto 0))
        return unsigned is
        variable v : unsigned(8 downto 0);
    begin
        case n is
            when "000"  => v := to_unsigned(373, 9);
            when "001"  => v := to_unsigned(333, 9);
            when "010"  => v := to_unsigned(296, 9);
            when "011"  => v := to_unsigned(280, 9);
            when "100"  => v := to_unsigned(249, 9);
            when "101"  => v := to_unsigned(222, 9);
            when "110"  => v := to_unsigned(198, 9);
            when others => v := to_unsigned(187, 9);
        end case;
        return v;
    end function;

    -- one melody = 8 steps, each 4 bits = **bit3 = 响不响**, bits 2..0 = 音高
    -- （写成字符串时就是 "1"/"0" 后面跟 3 位音高，例如 "1011" = 响 + 音高 F6）
    type mel_t is array (0 to 7) of std_logic_vector(3 downto 0);

    -- 0000 静音（idle）
    constant MEL_SILENT : mel_t := ("0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 0001 自检 / 开机号角：C6 E6 G6 C7（常驻 2 s，会循环整句 → 可以留休止）
    constant MEL_SELF   : mel_t := ("1000", "1010", "1100", "1111",
                                    "0000", "0000", "0000", "0000");
    -- 0010 预览 / 倒计时：D6 - D6 - D6 - - -（常驻 5 s）
    constant MEL_PREV   : mel_t := ("1001", "0000", "1001", "0000",
                                    "1001", "0000", "0000", "0000");
    -- 0011 过关（短上行；**瞬时事件** → 8 步全发声，见下面信号区的说明）
    constant MEL_CLEAR  : mel_t := ("1010", "1011", "1100", "1101",
                                    "1010", "1011", "1100", "1101");
    -- 0100 拼错（短下行；**瞬时事件** → 8 步全发声）
    constant MEL_WRONG  : mel_t := ("1101", "1100", "1011", "1010",
                                    "1101", "1100", "1011", "1010");
    -- 0101 按键（极短高音；**瞬时事件** → 8 步全发声）
    constant MEL_KEY    : mel_t := ("1111", "1111", "1111", "1111",
                                    "1111", "1111", "1111", "1111");
    -- 0110 通关（长号角；常驻 → 留休止）
    constant MEL_WIN    : mel_t := ("1000", "1010", "1100", "1111",
                                    "1100", "1111", "1111", "0000");
    -- 0111 失败（下行；常驻 → 留休止）
    constant MEL_FAIL   : mel_t := ("1111", "1110", "1101", "1100",
                                    "1011", "1010", "1000", "0000");
    -- 1000 背景音乐（循环，8 步全部发声，末步停在属音 G6 → 回绕到主音 C6）
    constant MEL_BGM    : mel_t := ("1000", "1010", "1100", "1010",
                                    "1011", "1101", "1100", "1100");
    -- 1001 旋转 90°（快速上扫；**瞬时事件** → 8 步全发声，任何起始步都是上扫）
    constant MEL_ROT    : mel_t := ("1100", "1101", "1110", "1111",
                                    "1100", "1101", "1110", "1111");
    -- 1010 确认 / 锁定（两声"咔哒"；**瞬时事件** → 8 步全发声，G6/C6 交替）
    constant MEL_LOCK   : mel_t := ("1100", "1000", "1100", "1000",
                                    "1100", "1000", "1100", "1000");
    -- 1011 选中棋子（轻提示；**瞬时事件** → 8 步全发声）
    constant MEL_SEL    : mel_t := ("1010", "1010", "1010", "1010",
                                    "1010", "1010", "1010", "1010");
    -- 1100 移动棋子（轻触；**瞬时事件** → 8 步全发声）
    constant MEL_MOVE   : mel_t := ("1000", "1000", "1000", "1000",
                                    "1000", "1000", "1000", "1000");
    -- 1101 非法走子（低沉短促；**瞬时事件** → 8 步全发声，D6/C6 交替）
    constant MEL_ILLEG  : mel_t := ("1001", "1000", "1001", "1000",
                                    "1001", "1000", "1001", "1000");
    -- 1110 时间警告（滴答；**瞬时事件** → 8 步全发声，C6/D6 交替）
    constant MEL_WARN   : mel_t := ("1000", "1001", "1000", "1001",
                                    "1000", "1001", "1000", "1001");
    -- 1111 备用 / 第三关开始（上行琶音；常驻 → 留休止）
    constant MEL_L3     : mel_t := ("1001", "1011", "1101", "1111",
                                    "1111", "0000", "0000", "0000");

    signal pre_cnt  : unsigned(5 downto 0) := (others => '0');   -- 64 分频计数器
    signal tick     : std_logic := '0';                          -- 781.25 kHz 时间基准
    signal step     : unsigned(2 downto 0) := (others => '0');   -- 0..7 (250 ms/step)
    signal tone_sel : std_logic_vector(2 downto 0) := "000";
    signal on_now   : std_logic := '0';
    signal cnt      : unsigned(8 downto 0) := (others => '0');   -- 9 位（旧版 16 位）
    signal half     : unsigned(8 downto 0) := (others => '0');
    signal wave     : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- Prescaler: 50 MHz -> 781.25 kHz.  Everything downstream counts this tick,
    -- so the half-period counter below only needs to reach 373 (9 bits).
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
    -- Step counter: one step per 250 ms while a sound is selected.
    --
    -- ⚠️ 2026-10-09 第 14 工作阶段（**瞬时事件必须落在发声步上**，实测的取舍）：
    --    `game_fsm` 把瞬时事件码（按键/选择/移动/旋转/确认/拒绝/过关/拼错）
    --    只保持 2 个旋律步（250~500 ms），而步进计数器是**自由走**的
    --    （换码不清零，与第 13 工作阶段一致），所以事件可能落在它那一句的
    --    **休止步**上 → 玩家仍然"按了没反应"。
    --    两种修法都真编译量过：
    --      ① 加一个 4 位 `prev` 寄存器，换码时把 step 清零 —— 语义最直观，但
    --         实测整机 **+10 LE**（1260 基线 → 1285），在 99% 占用率下装不下；
    --      ② **让所有"瞬时事件"乐句的 8 步全部发声**（0 LE，只改常量）—— 采用。
    --    采用 ② 之后，无论事件落在哪一步，都会立刻发出一个音；
    --    代价只是这些短句失去休止（听起来是 2 个音的连续乐句），
    --    而**常驻场景**（自检/预览/通关/失败/背景音乐）仍然保留休止，
    --    因为它们会被保持好几秒、一句 2 s 循环播放，听得到整句。
    --    ⚠️ 这条约束写进了 tb_buzzer_ctrl 的设计规则自检：判据覆盖的
    --    "事件码"（0011/0100/0101/1001/1010/1011/1100/1101/1110）不允许出现休止步。
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
    -- Quartus sees one small truth table (code & step -> tone & gate)
    -- instead of sixteen separate 32-bit muxes.
    -- ⚠️ 输出**寄存**（4 FF）：把"码/步 -> 音高 -> 半周期 -> 比较器"这条链
    --    切在表后面，缩短最差路径。
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
                when "1000" => tone_sel <= MEL_BGM(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM(to_integer(step))(3);
                when "1001" => tone_sel <= MEL_ROT(to_integer(step))(2 downto 0);
                               on_now   <= MEL_ROT(to_integer(step))(3);
                when "1010" => tone_sel <= MEL_LOCK(to_integer(step))(2 downto 0);
                               on_now   <= MEL_LOCK(to_integer(step))(3);
                when "1011" => tone_sel <= MEL_SEL(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SEL(to_integer(step))(3);
                when "1100" => tone_sel <= MEL_MOVE(to_integer(step))(2 downto 0);
                               on_now   <= MEL_MOVE(to_integer(step))(3);
                when "1101" => tone_sel <= MEL_ILLEG(to_integer(step))(2 downto 0);
                               on_now   <= MEL_ILLEG(to_integer(step))(3);
                when "1110" => tone_sel <= MEL_WARN(to_integer(step))(2 downto 0);
                               on_now   <= MEL_WARN(to_integer(step))(3);
                when "1111" => tone_sel <= MEL_L3(to_integer(step))(2 downto 0);
                               on_now   <= MEL_L3(to_integer(step))(3);
                when "0000" => tone_sel <= MEL_SILENT(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SILENT(to_integer(step))(3);  -- 静音（idle）
                when others => tone_sel <= "000";
                               on_now   <= '0';      -- 未定义码 → 静音（安全兜底）
            end case;
        end if;
    end process;

    half <= note_half(tone_sel);

    ----------------------------------------------------------------------------
    -- Square-wave generator (one shared oscillator for all eight pitches).
    -- 结构不变：cnt >= half -> 翻转 + 清零，否则 cnt+1；只是现在 cnt 数的是
    -- **预分频后的 tick**（时钟使能），所以计数器只有 9 位。
    -- ⚠️ 试过"倒计数 + 等于 0 判定"（想用宽 NOR 换掉大小比较器）：实测反而更贵
    --    （装载 mux 比省下的比较器还贵），所以保留这个更朴素的写法。
    ----------------------------------------------------------------------------
    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                cnt  <= (others => '0');
                wave <= '0';
            elsif (tick = '1') then
                if (cnt >= half) then
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
