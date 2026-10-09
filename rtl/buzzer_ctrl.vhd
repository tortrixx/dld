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
--  ⚠️ 2026-10-09 第 15 工作阶段（用户实机确认"音乐正常、不同场景有不同声音"后的
--     **内容升级**）：用户要求"音乐要适配场景内容" ——
--       ① 自检用**行业标准音效** → **POST 单声 ~1 kHz 短鸣**（"一短声 = 自检通过"）；
--       ② **每一关一首热门的游戏背景曲** → 1000/1001/1011 三个码分别对应三首；
--       ③ 胜负音效独特且符合行业习惯 → 胜利 = 上行大三和弦 + 顶点长音（ta-da 号角），
--          失败 = 半音下行 + 低音拖长（Game Over 的通用语汇）。
--     音高表同时从"8 个音、C6..C7"扩到 **16 个音、G5..C7**：一个八度装不下真实旋律
--     （俄罗斯方块主题要五度跳进、命运交响曲要小二度）。选 G5 为最低音是**实测**：
--     9 位计数器最大 511 拍，G5 的半周期 498 拍刚好装得下（F5 = 561 拍就要 10 位）——
--     所以扩音域**没有增加计数器位宽**。音域仍落在 v2 实机验证过的 1~2 kHz 高效区。
--
--  音高表（idx / 音名 / 频率 / 半周期拍数，f = 781250 / (2*half)）：
--     0 G5 784.0->498   4 B5  987.8->395   8 D#6 1244.5->314  12 G6 1568.0->249
--     1 G#5 830.6->470  5 C6 1046.5->373   9 E6  1318.5->296  13 G#6 1661.2->235
--  音高表（8 个音，idx / 音名 / 频率 / 半周期拍数，f = 781250 / (2*half)）：
--     0 G5 784.0->498   2 A#5 932.3->419  4 C6 1046.5->373  6 G6 1568.0->249
--     1 A5 880.0->444   3 B5  987.8->395  5 D6 1174.7->333  7 C7 2093.0->187
--
--  音效码（4 位，game_fsm 发出；每句 **8 步 x 250 ms = 2 s**，步 0..7 循环）：
--     0000  静音（待机）
--     0001  自检 = POST 单声短鸣（C6，一声；常驻 2 s，一句恰好响一次）
--     0010  预览"准备"提示              C6 -  C6 -  G6 -  -  -
--     0011  过关（G 大三和弦琶音）      G5 B5 D6 G6 G5 B5 D6 G6
--     0100  拼错（半音下行）            C6 B5 A#5 A5 G5 G5 A5 G5
--     0101  按键（高音 blip）           C7 x8
--     0110  通关胜利号角（ta-da）       G5 B5 D6 G6 -  G6 G6 G6
--     0111  失败 / Game Over            C6 A#5 A5 G5 G5 -  G5 G5
--     1000  **第一关 BGM** 俄罗斯方块 A 主题（Korobeiniki，民歌/公有领域）
--     1001  **第二关 BGM** 欢乐颂（贝多芬第九，公有领域）
--     1011  **第三关 BGM** 命运交响曲开头动机（贝多芬第五，公有领域）
--           ⚠️ 三个 BGM 码必须正好是 `"10" & lvl3 & level` 的值（1000/1001/1011），
--              这样 game_fsm 那边是**纯拼线、0 逻辑单元**。
--     1010  旋转 90°（逐级上行）        G5 A5 A#5 B5 C6 D6 G6 C7
--     1100  确认 / 锁定（G6/C6 交替）
--     1101  选中棋子（C6 轻提示）
--     1110  移动棋子（G5 最轻一触）
--     1111  预留（原"最后 5 秒催促"；本轮为装箱删掉生成端，乐句仍保留以便 16 个码两两可辨）
--  旋律写在常量表 MEL_* 里（每步 **4 位** = 1 位"这步响不响" + 3 位音高索引），
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
    -- 8 个音高的半周期（单位：**预分频后的 tick 数**，f = 781250 / (2*half)）
    --
    -- ⚠️ 2026-10-09 第 15 工作阶段（内容升级）：音高表**仍然是 8 个音、仍然 3 位索引**，
    --    但选的音换了 —— 从"C6 大调音阶"换成 **G 小调五声 / G 和声骨架**：
    --        G5 A5 A#5 B5 C6 D6 G6 C7
    --    为什么这 8 个音够用（这是本轮的**设计要点**，不是随手挑的）：
    --      三首背景曲都按"同一主音 G"移调，所需的音落在同一个 8 音集合里 ——
    --        · 俄罗斯方块 A 主题（A 小调）→ G 小调：D6 A5 A#5 C6 A#5 A5 G5 G5
    --        · 欢乐颂（C 大调）        → G 大调：B5 B5 C6 D6 D6 C6 B5 A5
    --        · 命运交响曲动机（C 小调）→ G 小调：D6 D6 D6 A#5 C6 C6 C6 A5
    --        · 胜利号角用 G 大三和弦琶音：G5 B5 D6 G6（+ 高音 C7 给按键 blip）
    --      于是**不需要把音高索引加宽到 4 位**（4 位会让旋律表多 2 个 LUT4、
    --      音高寄存器多 1 位 —— 实测整机 +3 LE，而器件只剩 2 LE 余量）。
    --      选 G5 作最低音同样是**实测边界**：9 位半周期计数器最大 511 拍，
    --      G5 的 498 拍刚好装得下（F5 = 561 拍就要 10 位 → 又要 +2 LE）。
    --
    --    idx 0 G5  784.0 -> 498     idx 4 C6 1046.5 -> 373
    --    idx 1 A5  880.0 -> 444     idx 5 D6 1174.7 -> 333
    --    idx 2 A#5 932.3 -> 419     idx 6 G6 1568.0 -> 249
    --    idx 3 B5  987.8 -> 395     idx 7 C7 2093.0 -> 187
    ----------------------------------------------------------------------------
    function note_half(n : std_logic_vector(2 downto 0))
        return unsigned is
        variable v : unsigned(8 downto 0);
    begin
        case n is
            when "000"  => v := to_unsigned(498, 9);   -- G5
            when "001"  => v := to_unsigned(444, 9);   -- A5
            when "010"  => v := to_unsigned(419, 9);   -- A#5
            when "011"  => v := to_unsigned(395, 9);   -- B5
            when "100"  => v := to_unsigned(373, 9);   -- C6（≈1 kHz，POST 自检声）
            when "101"  => v := to_unsigned(333, 9);   -- D6
            when "110"  => v := to_unsigned(249, 9);   -- G6
            when others => v := to_unsigned(187, 9);   -- C7
        end case;
        return v;
    end function;

    -- one melody = 8 steps, each 4 bits = **bit3 = 响不响**, bits 2..0 = 音高索引
    -- （写字符串就是 "1"/"0" + 3 位音高，例如 "1100" = 响 + 音高 idx 4 = C6）
    -- 音高索引：0 G5  1 A5  2 A#5  3 B5  4 C6  5 D6  6 G6  7 C7
    type mel_t is array (0 to 7) of std_logic_vector(3 downto 0);

    -- 0000 静音（idle）
    constant MEL_SILENT : mel_t := ("0000", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 0001 自检 = **行业标准的 POST 单声短鸣**：一声 ~1 kHz（C6）短鸣 = "自检通过"
    --      （PC/工控设备惯例：**一短声 = 全部通过**）。常驻 2 s，一句 2 s 循环
    --      → 自检期间恰好响一声，其余 7 步留白（不是"号角"而是"自检通过"）。
    constant MEL_SELF   : mel_t := ("1100", "0000", "0000", "0000",
                                    "0000", "0000", "0000", "0000");
    -- 0010 预览 / 倒计时"准备"提示：C6 - C6 - G6 - - -（常驻 5 s，循环）
    constant MEL_PREV   : mel_t := ("1100", "0000", "1100", "0000",
                                    "1110", "0000", "0000", "0000");
    -- 0011 过关（**瞬时事件** → 8 步全发声）：G5 B5 D6 G6 上行琶音重复
    --      （G 大三和弦琶音 = 通用的"通过/得分"语汇，任何起始步都朝上）
    constant MEL_CLEAR  : mel_t := ("1000", "1011", "1101", "1110",
                                    "1000", "1011", "1101", "1110");
    -- 0100 拼错（**瞬时事件** → 8 步全发声）：C6 B5 A#5 A5 G5 半音下行 + 低音抖动
    --      （半音下行到最低音 = 通用的"错/失败"语汇）
    constant MEL_WRONG  : mel_t := ("1100", "1011", "1010", "1001",
                                    "1000", "1000", "1001", "1000");
    -- 0101 按键（**瞬时事件** → 8 步全发声）：C7 高音短促 blip
    constant MEL_KEY    : mel_t := ("1111", "1111", "1111", "1111",
                                    "1111", "1111", "1111", "1111");
    -- 0110 **通关胜利号角（行业惯例：主和弦上行琶音 + 顶点长音"ta-da"）**：
    --      G5 B5 D6 G6 -  G6 G6 G6（最后三拍高音主音长音）。常驻 → 留休止
    constant MEL_WIN    : mel_t := ("1000", "1011", "1101", "1110",
                                    "0000", "1110", "1110", "1110");
    -- 0111 **失败 / Game Over（行业惯例：下行、结尾落在最低音并拖长）**：
    --      C6 A#5 A5 G5 G5 -  G5 G5
    constant MEL_FAIL   : mel_t := ("1100", "1010", "1001", "1000",
                                    "1000", "0000", "1000", "1000");
    -- 1000 **第一关背景音乐 = 俄罗斯方块 A 主题（Korobeiniki，俄罗斯民歌/公有领域）**
    --      原始动机 E B C D C B A A（A 小调，级数 5 2 b3 4 b3 2 1 1）→ 移到 G 小调
    --      （级数逐音不变，只是主音变成 G）：D6 A5 A#5 C6 A#5 A5 G5 G5
    constant MEL_BGM1   : mel_t := ("1101", "1001", "1010", "1100",
                                    "1010", "1001", "1000", "1000");
    -- 1001 **第二关背景音乐 = 欢乐颂（贝多芬第九，公有领域）**
    --      动机 E E F G G F E D（C 大调，级数 3 3 4 5 5 4 3 2）→ 移到 G 大调：
    --      B5 B5 C6 D6 D6 C6 B5 A5
    constant MEL_BGM2   : mel_t := ("1011", "1011", "1100", "1101",
                                    "1101", "1100", "1011", "1001");
    -- 1010 旋转 90°（**瞬时事件** → 8 步全发声）：G5 起逐级上行"嗖"一声
    constant MEL_ROT    : mel_t := ("1000", "1001", "1010", "1011",
                                    "1100", "1101", "1110", "1111");
    -- 1011 **第三关背景音乐 = 命运交响曲开头动机（贝多芬第五，公有领域）**
    --      G G G Eb | F F F D（C 小调，级数 5 5 5 b3 4 4 4 2）→ 移到 G 小调：
    --      D6 D6 D6 A#5 C6 C6 C6 A5（"命运在敲门"——最适合最后一关的紧张感）
    constant MEL_BGM3   : mel_t := ("1101", "1101", "1101", "1010",
                                    "1100", "1100", "1100", "1001");
    -- 1100 确认 / 锁定（**瞬时事件** → 8 步全发声）：G6/C6 交替 = 两声"咔哒"
    constant MEL_LOCK   : mel_t := ("1110", "1100", "1110", "1100",
                                    "1110", "1100", "1110", "1100");
    -- 1101 选中棋子（**瞬时事件** → 8 步全发声）：C6 轻提示
    constant MEL_SEL    : mel_t := ("1100", "1100", "1100", "1100",
                                    "1100", "1100", "1100", "1100");
    -- 1110 移动棋子（**瞬时事件** → 8 步全发声）：G5 最低最轻的一触
    constant MEL_MOVE   : mel_t := ("1000", "1000", "1000", "1000",
                                    "1000", "1000", "1000", "1000");
    -- 1111 最后 5 秒催促（**瞬时事件** → 8 步全发声）：C6/G5 交替 = 钟摆滴答
    constant MEL_WARN   : mel_t := ("1100", "1000", "1100", "1000",
                                    "1100", "1000", "1100", "1000");

    signal pre_cnt  : unsigned(5 downto 0) := (others => '0');   -- 64 分频计数器
    signal tick     : std_logic := '0';                          -- 781.25 kHz 时间基准
    signal step     : unsigned(2 downto 0) := (others => '0');   -- 0..7 (250 ms/step)
    signal tone_sel : std_logic_vector(2 downto 0) := "000";     -- 8 音高（上电默认 G5）
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
    --    "事件码"（0011/0100/0101/1010/1100/1101/1110）不允许出现休止步。
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
                when "1000" => tone_sel <= MEL_BGM1(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM1(to_integer(step))(3);
                when "1001" => tone_sel <= MEL_BGM2(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM2(to_integer(step))(3);
                when "1010" => tone_sel <= MEL_ROT(to_integer(step))(2 downto 0);
                               on_now   <= MEL_ROT(to_integer(step))(3);
                when "1011" => tone_sel <= MEL_BGM3(to_integer(step))(2 downto 0);
                               on_now   <= MEL_BGM3(to_integer(step))(3);
                when "1101" => tone_sel <= MEL_SEL(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SEL(to_integer(step))(3);
                when "1100" => tone_sel <= MEL_LOCK(to_integer(step))(2 downto 0);
                               on_now   <= MEL_LOCK(to_integer(step))(3);
                when "1110" => tone_sel <= MEL_MOVE(to_integer(step))(2 downto 0);
                               on_now   <= MEL_MOVE(to_integer(step))(3);
                when "1111" => tone_sel <= MEL_WARN(to_integer(step))(2 downto 0);
                               on_now   <= MEL_WARN(to_integer(step))(3);
                               -- 1111 预留：生成端（game_fsm）第 15 工作阶段为装箱删掉了
                               -- "最后 5 秒催促"，但这里保留一句**互不相同**的乐句，
                               -- 这样 16 个码的乐句仍然两两可辨（tb 会逐对比较）
                when "0000" => tone_sel <= MEL_SILENT(to_integer(step))(2 downto 0);
                               on_now   <= MEL_SILENT(to_integer(step))(3);  -- 静音（idle）
                when others => tone_sel <= "000";
                               on_now   <= '0';      -- 未定义码 → 静音（安全兜底）
            end case;
        end if;
    end process;

    half <= note_half(tone_sel);

    ----------------------------------------------------------------------------
    -- Square-wave generator (one shared oscillator for all sixteen pitches).
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
