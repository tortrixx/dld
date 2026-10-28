-- ============================================================================
--  puzzle_pkg  ——  全局常量、类型与纯函数
--  题目 4：简易拼图游戏（数字电路与逻辑设计实验）
--  器件：Altera MAX II EPM1270T144C5   工具：Quartus II 9.1   语言：VHDL
--
--  本包是全工程共用约定的唯一来源：
--    · 8x8 点阵掩码的位序：位下标 = 8*row + col，bit0 = 左上角
--    · 图案 / 零片几何（由课程 PDF 图 4-1、4-2 逐像素解码）
--    · 时序常量、状态编码、键码、音效码、数码管字位码
--
--  本文件只有常量、类型和纯函数：没有信号、没有进程，
--  因此不推断出任何硬件。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

package puzzle_pkg is

    ----------------------------------------------------------------------------
    -- 1. 数组类型
    --    VHDL-93 的端口不能使用匿名数组类型，因此在这里声明一次，
    --    由 piece_rom 与 puzzle_top 共用。
    ----------------------------------------------------------------------------
    type mask_arr_t is array (0 to 3) of std_logic_vector(63 downto 0);
    type dim_arr_t  is array (0 to 3) of std_logic_vector(2 downto 0);

    constant MASK_ZERO : std_logic_vector(63 downto 0) := (others => '0');

    ----------------------------------------------------------------------------
    -- 2. 纯函数
    ----------------------------------------------------------------------------

    -- 构造只含一个格子的掩码（离线核对用，主路径未调用）。
    -- 位序号 = 8*row + col，bit0 = 左上角。
    function mk_cell(r : integer; c : integer) return std_logic_vector;

    -- 统计掩码中 '1' 的个数（测试与离线核对用）。
    function popcount(m : std_logic_vector(63 downto 0)) return integer;

    -- 把一个格子的绝对坐标转成"只含该格"的独热掩码（离线核对用）。
    -- 位序与全工程一致，因此函数体就是一次独热编码。
    function mask_to_px(row : integer; col : integer) return std_logic_vector;

    -- 把掩码整体平移 (dr, dc) 个格子，离开 8x8 区域的位被清除。
    -- 按格平移而不是直接 "sll"：后者会让一行最右的格子绕到下一行最左
    -- （即跨行"像素穿墙"）。当前主路径未调用，保留作离线核对。
    function shift_mask(m : std_logic_vector(63 downto 0);
                        dr : integer; dc : integer)
        return std_logic_vector;

    -- srl8：把一条 8 位行掩码向列号增大的方向移 dc 列，左侧补 '0'。
    -- dc 允许 -2（旋转补偿时列移位可能为负）。
    --
    -- 只做 8 位行移位、而不是对 64 位字做变距离移位：后者相当于一个
    -- 64 路交叉开关，在 EPM1270 上代价过高；按行处理则每次只需一个
    -- 8 位桶形移位器，并且可以和其它模块共用。
    function srl8(r : std_logic_vector(7 downto 0); dc : integer range -2 to 7)
        return std_logic_vector;

    -- row24：零片在锚点列 ac 处的 8 位行掩码。
    --   shp24：零片相对形状，打包成 3 个 8 位行
    --          （bit 7..0 = 第 0 行，15..8 = 第 1 行，23..16 = 第 2 行）
    --   sr   ：要取出零片自身的哪一行（0..2）
    -- 当前主路径使用 puzzle_ctrl 内的 row_mask（多一个朝向参数），
    -- 本函数保留作教学与离线核对。
    function row24(shp24 : std_logic_vector(23 downto 0);
                   sr    : integer;
                   ac    : integer) return std_logic_vector;

    ----------------------------------------------------------------------------
    -- 2b. 旋转（提高要求 A4：零片可以 90° 旋转）
    --
    -- 朝向编码（2 位）：
    --     "00" = 原始朝向      "01" = 顺时针 90°
    --     "10" = 180°          "11" = 顺时针 270°
    --
    -- 旋转在固定的 3x3 盒内完成，而不是在 ROM 里存 4 套形状：
    --   · 四块零片的包围盒都不超过 3x3，旋转只是 3x3 格阵的置换；
    --   · 渲染器一拍只算一行，所以每个调用点只需要"第 sr 行"的 3 位，
    --     即每个调用点 3 个 4 选 1 多路器，而不是把 24 位形状整体重排。
    --
    -- 【锚点补偿】在固定 3x3 盒里旋转后，紧包围盒不一定仍锚在 (0,0)：
    --   例如 1x3 横条转 90° 后会落到盒子的第 2 列。若不补偿，零片旋转时
    --   会凭空横移。补偿量由 rot_off_r / rot_off_c 给出：
    --       盒内行号 = 紧包围盒行号 sr + dr
    --       列移位   = 锚点列 ac - dc
    --   盒内坐标 (r,c)，r=0 在上、c=0 在左：
    --     "00" : out(sr,c') = in(sr, c')          "01" : out(sr,c') = in(2-c', sr)
    --     "10" : out(sr,c') = in(2-sr, 2-c')      "11" : out(sr,c') = in(c', 2-sr)
    -- 返回值是 8 位列掩码（只用低 3 位），与 srl8 的输入同格式。
    ----------------------------------------------------------------------------
    function rot_row(shp : std_logic_vector(63 downto 0);
                     ori : std_logic_vector(1 downto 0);
                     sr  : integer) return std_logic_vector;

    -- 旋转后紧包围盒在 3x3 盒内的行 / 列偏移（0..2）。
    function rot_off_r(h : std_logic_vector(2 downto 0);
                       w : std_logic_vector(2 downto 0);
                       ori : std_logic_vector(1 downto 0))
        return std_logic_vector;
    function rot_off_c(h : std_logic_vector(2 downto 0);
                       w : std_logic_vector(2 downto 0);
                       ori : std_logic_vector(1 downto 0))
        return std_logic_vector;

    -- 旋转 90°/270° 时包围盒的高与宽互换（0°/180° 不变）。
    function oh(h : std_logic_vector(2 downto 0);
                w : std_logic_vector(2 downto 0);
                ori : std_logic_vector(1 downto 0)) return std_logic_vector;
    function ow(h : std_logic_vector(2 downto 0);
                w : std_logic_vector(2 downto 0);
                ori : std_logic_vector(1 downto 0)) return std_logic_vector;

    -- 下一个朝向（每按一次【旋转】转 90°，4 次回到原样）。
    function ori_next(ori : std_logic_vector(1 downto 0)) return std_logic_vector;

    ----------------------------------------------------------------------------
    -- 3. 图案几何 —— 由课程 PDF 图 4-1、4-2 逐像素解码得到
    ----------------------------------------------------------------------------

    -- 图 4-1：第一关完整图案 = 4 行 x 3 列实心矩形，
    -- 占据点阵第 2..5 行、第 2..4 列，共 12 格。
    constant L1_TARGET_MASK : std_logic_vector(63 downto 0) :=
        "0000000000000000000111000001110000011100000111000000000000000000";

    -- 图 4-2：第一关三块散落零片，3 + 6 + 3 = 12 格（面积守恒）。
    --   P0：1x3 横条（3 格）
    constant L1_P0 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000000000000111";
    --   P1：6 格阶梯形（自上而下 3-2-1），与课程 PDF 逐格一致
    constant L1_P1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000010000001100000111";
    --   P2：L 形三格块，占据其 2x2 包围盒的 (0,1)(1,0)(1,1)（3 格）
    constant L1_P2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000001100000010";

    -- PAT0：4x4 实心方块，第 2..5 行、第 2..5 列，共 16 格。
    -- 常量名 L2_TARGET_MASK 与 L2_PAT0 指向同一幅图案。
    constant L2_TARGET_MASK : std_logic_vector(63 downto 0) :=
        "0000000000000000001111000011110000111100001111000000000000000000";

    ----------------------------------------------------------------------------
    -- 第二关 / 第三关：四块自拟异形零片 + 4 幅图案库（A2 / S1）
    --
    -- 零片（3 + 2 + 5 + 6 = 16 格）：
    --     Q0  1x3 横条  3 格      Q1  1x2 竖条  2 格
    --     ###                     #
    --                             #
    --     Q2  J 形 5 格          Q3  六格块  6 格
    --     ###                     #..
    --     ..#                     ###
    --     ..#                     .##
    --
    -- 图案库（每幅都能被这四块零片恰好铺满）：
    --     PAT0 田   4x4 实心方块      PAT1 十   胖十字（4x5）
    --     PAT2 S/Z  锯齿（4x6）       PAT3 阶梯 阶梯形（4x5）
    ----------------------------------------------------------------------------
    constant L2_PAT0 : std_logic_vector(63 downto 0) :=
        "0000000000000000001111000011110000111100001111000000000000000000";  -- 田（4x4 实心方块）
    constant L2_PAT1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000111000011111000111110000111000000000000000000";  -- 十（胖十字）
    constant L2_PAT2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000111100111100001111000000111100000000000000000";  -- S/Z 锯齿
    constant L2_PAT3 : std_logic_vector(63 downto 0) :=
        "0000000000000000001110000011110000111110000111100000000000000000";  -- 阶梯

    -- 图案库：pat_sel 为 2 位，正好 4 幅。
    type pat_arr_t is array (0 to 3) of std_logic_vector(63 downto 0);
    constant L2_PATS : pat_arr_t := (L2_PAT0, L2_PAT1, L2_PAT2, L2_PAT3);
    constant L2_PAT_N : integer := 4;

    -- 第二关使用固定图案（PAT3 阶梯）；第三关从四幅库中随机选择。
    -- 这样"多种拼图图案随机选择"（A2）放在第三关，第二关保持与第一关
    -- 同等的"图案固定"待遇，符合 B10 的"图案自拟"。
    constant L2_FIXED_PAT : std_logic_vector(1 downto 0) := "11";   -- 3 == L2_PAT3

    -- 第二关 / 第三关的四块零片（3 + 2 + 5 + 6 = 16 格）。
    -- 相对形状的位序与第一关相同：bit = 8*行 + 列，行 0 在最低 8 位。
    constant L2_P0 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000000000000111";  -- Q0 1x3 横条 3 格
    constant L2_P1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000000100000001";  -- Q1 1x2 竖条 2 格
    constant L2_P2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000001000000010000000111";  -- Q2 J 形 5 格
    constant L2_P3 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000001100000011100000001";  -- Q3 六格块 6 格

    -- 每局开始（散落）时四块零片的初始朝向。
    -- 若四块都从 ROM 的原始朝向 "00" 开始，四幅图案都存在"只平移、
    -- 不旋转"的解，旋转键就不是通关必需。改取 (1,1,2,2) 后经穷举验证：
    -- 四块都不转时无解，而允许旋转时每幅仍可解。
    -- 编码：块 k 占 ori(2k+1 downto 2k)；"01" = 顺时针 90°，
    --       "10" = 180°，"11" = 270°。
    constant PIECE_ORI_INIT : std_logic_vector(7 downto 0) := "10" & "10" & "01" & "01";

    -- 见证锚点：描述"一种"正确摆法，供离线穷举与测试核对。
    -- 注意：它们不是成功判据。成功判据是"零片并集 == 目标图案"
    -- （见 puzzle_ctrl），因此所有等价铺法都会被接受。
    constant L1_TGT0 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- (2,2)
    constant L1_TGT1 : std_logic_vector(7 downto 0) := "0011" & "0010";  -- (3,2)
    constant L1_TGT2 : std_logic_vector(7 downto 0) := "0100" & "0011";  -- (4,3)
    constant L1_TGT3 : std_logic_vector(7 downto 0) := "0000" & "0000";  -- 未使用

    -- 第二关四块零片铺满 PAT0（4x4 方块）的见证摆法。
    constant L2_TGT0 : std_logic_vector(7 downto 0) := "0101" & "0011";  -- Q0 @ (5,3)
    constant L2_TGT1 : std_logic_vector(7 downto 0) := "0100" & "0010";  -- Q1 @ (4,2)
    constant L2_TGT2 : std_logic_vector(7 downto 0) := "0010" & "0011";  -- Q2 @ (2,3)
    constant L2_TGT3 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- Q3 @ (2,2)

    -- PAT3（第二关固定图案）的第 0 种见证铺法。PAT3 有两种等价铺法，
    -- 两种都必须判成功（见 puzzle_ctrl 的整帧判据）。
    constant L2_PAT3_TGT0 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- Q0 @ (2,2)
    constant L2_PAT3_TGT1 : std_logic_vector(7 downto 0) := "0010" & "0001";  -- Q1 @ (2,1)
    constant L2_PAT3_TGT2 : std_logic_vector(7 downto 0) := "0011" & "0011";  -- Q2 @ (3,3)
    constant L2_PAT3_TGT3 : std_logic_vector(7 downto 0) := "0011" & "0010";  -- Q3 @ (3,2)

    -- 结算画面图案（自拟，要求"一眼能看懂"）。
    --   WIN  = 绿色粗对勾（24 格、笔画 3 格宽）
    --   FAIL = 红色叉
    -- 颜色本身就是判读线索：绿 = 通过、红 = 不通过（交通灯配色），
    -- 形状作为第二重线索。
    --   ..............##   row0 = 0x80
    --   ............####   row1 = 0xC0
    --   ..........######   row2 = 0xE0
    --   ........######..   row3 = 0x70
    --   ##......####....   row4 = 0x31
    --   ####..####......   row5 = 0x1B
    --   ##########......   row6 = 0x1F
    --   ..######........   row7 = 0x0E
    constant WIN_MASK : std_logic_vector(63 downto 0) :=
        "0000111000011111000110110011000101110000111000001100000010000000";

    constant FAIL_MASK : std_logic_vector(63 downto 0) :=
        "0000000011000011011001100011110000111100011001101100001100000000";

    -- 零片包围盒上限：所有零片都能装进 3x3。
    -- 正因如此，引擎只需扫描 3x3 邻域，散落算法的候选范围也是有界的。
    constant PIECE_MAX_DIM : integer := 3;

    ----------------------------------------------------------------------------
    -- 4. 时钟 / 时序常量
    --    板上时钟由 USER_BTN 选择，本设计假定为 50 MHz 档。
    --    分频链有意级联：只有第一级面对 50 MHz，后面各级只数上一级的脉冲。
    ----------------------------------------------------------------------------
    constant CLK_HZ  : integer := 50_000_000;

    -- 第 1 级：50 MHz -> 1 kHz（除以 50_000）
    constant CNT_1K  : integer := CLK_HZ / 1_000 - 1;
    -- 第 2 级：1 kHz -> 200 Hz（除以 5）：键盘扫描轮次
    constant CNT_200 : integer := 1_000 / 200 - 1;
    -- 以下三个常量在当前实现中未使用：分频链的第 4/5/6 级已合并，
    -- 由 CNT_4HZ 一条链同时派生 4 Hz、2 Hz 与 1 Hz。
    constant CNT_100 : integer := 200 / 100 - 1;
    constant CNT_2HZ : integer := 100 / 2 - 1;
    constant CNT_1HZ : integer := 100 / 1 - 1;
    -- 第 3 级：100 Hz -> 4 Hz（除以 25，250 ms 一个脉冲）。
    -- 4 Hz 用于：自检与结算画面的 2 Hz 方波（每 250 ms 翻转一次），
    -- 以及蜂鸣器的换步节拍。
    constant CNT_4HZ : integer := 100 / 4 - 1;

    -- 上电复位：数 tick_1k 脉冲，计到 CNT_POR 后释放。
    -- 由于从 0 起计，实际约为 9 个 1 ms 周期。
    constant T_POR_MS  : integer := 10;
    constant CNT_POR   : integer := T_POR_MS - 1;

    -- 复位按键消抖：连续 20 个 1 ms 高电平样本才认为按下。
    constant T_BTN_MS  : integer := 20;
    -- 当前未使用：clk_gen 直接与 T_BTN_MS 比较。
    constant CNT_BTN   : integer := T_BTN_MS - 1;

    ----------------------------------------------------------------------------
    -- 5. 游戏时序（课程要求值）
    ----------------------------------------------------------------------------
    constant T_SELFTEST : integer := 2;    -- B1/B2：自检标称 2 s
    -- 自检窗口按 250 ms 节拍倒计数：初值 7，即 8 拍（约 2 s）。
    -- 用倒计数可直接复用对局阶段的减法器与比较器。
    constant T_SELFTEST_T4 : integer := 7;
    constant T_PREVIEW  : integer := 5;    -- B4/B10：预览 5 s
    constant T_LEVEL1   : integer := 30;   -- B5：第一关限时 30 s
    constant T_LEVEL2   : integer := 40;   -- B10：第二关限时 40 s
    -- 第三关（A2 "增加游戏关数"，自拟）：图案随机，难度最高，限时放宽到 60 s。
    constant T_LEVEL3   : integer := 60;

    ----------------------------------------------------------------------------
    -- 6. 杂项
    ----------------------------------------------------------------------------
    -- 按键消抖，以 keypad_scan 的扫描轮为单位计数。
    -- 一轮扫描 = 2 个 tick_200 = 10 ms；连续 4 轮一致才接受，
    -- 即按下 / 松开各约 40 ms，可满足廉价矩阵键盘的接触抖动要求。
    constant DEBOUNCE_MAX : integer := 3;

    -- LFSR 种子：绝不能全零（全零是吸收态）。
    constant SEED_DEFAULT : std_logic_vector(7 downto 0) := x"5A";

    ----------------------------------------------------------------------------
    -- 7. 主状态机的状态编码（3 位，6 个状态）
    ----------------------------------------------------------------------------
    subtype state_t is std_logic_vector(2 downto 0);

    constant S_SELF_TEST : state_t := "000";
    constant S_IDLE      : state_t := "001";
    constant S_PREVIEW   : state_t := "010";
    constant S_PLAYING   : state_t := "011";
    constant S_WIN       : state_t := "100";
    constant S_FAIL      : state_t := "101";

    ----------------------------------------------------------------------------
    -- 8. keypad_scan 产生的键码（0 = 无键）
    ----------------------------------------------------------------------------
    constant K_NONE    : std_logic_vector(3 downto 0) := "0000";
    constant K_START   : std_logic_vector(3 downto 0) := "0001";
    constant K_SELECT  : std_logic_vector(3 downto 0) := "0010";
    constant K_CONFIRM : std_logic_vector(3 downto 0) := "0011";
    constant K_UP      : std_logic_vector(3 downto 0) := "0100";
    constant K_DOWN    : std_logic_vector(3 downto 0) := "0101";
    constant K_LEFT    : std_logic_vector(3 downto 0) := "0110";
    constant K_RIGHT   : std_logic_vector(3 downto 0) := "0111";
    -- 【旋转】键（A4）：物理位置 KEY8，键码 "1000"。
    constant K_ROT     : std_logic_vector(3 downto 0) := "1000";

    ----------------------------------------------------------------------------
    -- 9. 音效码（提高要求 A1：不同情况播放不同提示音/音乐）
    --
    -- 4 位码共 16 个场景，由 game_fsm 产生、buzzer_ctrl 解码。
    -- 两边的码表必须一一对应。
    --
    -- 背景音乐码刻意取 1000 / 1001 / 1011：正好等于 "10" & lvl3 & level，
    -- 于是 game_fsm 用两根既有寄存器拼线即可选曲，不增加逻辑单元。
    ----------------------------------------------------------------------------
    constant SND_NONE   : std_logic_vector(3 downto 0) := "0000";  -- 静音（待机）
    constant SND_SELF   : std_logic_vector(3 downto 0) := "0001";  -- 自检：POST 单声短鸣
    constant SND_PREVIEW: std_logic_vector(3 downto 0) := "0010";  -- 预览"准备"声
    constant SND_CLEAR  : std_logic_vector(3 downto 0) := "0011";  -- 过关（短上行号角）
    constant SND_WRONG  : std_logic_vector(3 downto 0) := "0100";  -- 拼错（下行警示）
    constant SND_KEY    : std_logic_vector(3 downto 0) := "0101";  -- 按键（保留，当前不发出）
    constant SND_WIN    : std_logic_vector(3 downto 0) := "0110";  -- 通关长号角
    constant SND_FAIL   : std_logic_vector(3 downto 0) := "0111";  -- 失败 / Game Over
    constant SND_BGM1   : std_logic_vector(3 downto 0) := "1000";  -- 第一关背景音乐
    constant SND_BGM2   : std_logic_vector(3 downto 0) := "1001";  -- 第二关背景音乐
    constant SND_BGM3   : std_logic_vector(3 downto 0) := "1011";  -- 第三关背景音乐
    constant SND_ROT    : std_logic_vector(3 downto 0) := "1010";  -- 旋转（保留，当前不发出）
    constant SND_CONF   : std_logic_vector(3 downto 0) := "1100";  -- 确认（保留，当前不发出）
    constant SND_SEL    : std_logic_vector(3 downto 0) := "1101";  -- 选择（保留，当前不发出）
    constant SND_MOVE   : std_logic_vector(3 downto 0) := "1110";  -- 移动（保留，当前不发出）
    constant SND_TIME   : std_logic_vector(3 downto 0) := "1111";  -- 预留（当前不发出）

    ----------------------------------------------------------------------------
    -- 10. DISP 字位码：disp_format 写入 i_data 的 4 位码 == seg_scan 的译码输入
    --
    --   0x0..0x9 = 数字，0xF = 灭，0xA..0xE = 结算画面字母。
    --   7 段管的固有限制：'S' 与 '5' 段完全一样（PASS 看起来像 PA55），
    --   'I' 只能用 '1' 的形状（FAIL 看起来像 FA1L）。结算时点阵上同时
    --   给出对勾 / 叉，语境下判读不受影响。
    ----------------------------------------------------------------------------
    constant DIG_BLANK : std_logic_vector(3 downto 0) := "1111";
    constant DIG_A     : std_logic_vector(3 downto 0) := "1010";  -- A: a b c e f g
    constant DIG_P     : std_logic_vector(3 downto 0) := "1011";  -- P: a b e f g
    constant DIG_S     : std_logic_vector(3 downto 0) := "1100";  -- S: a c d f g（= '5'）
    constant DIG_F     : std_logic_vector(3 downto 0) := "1101";  -- F: a e f g
    constant DIG_L     : std_logic_vector(3 downto 0) := "1110";  -- L: d e f
    constant DIG_I     : std_logic_vector(3 downto 0) := "0001";  -- I: 用 '1' 的形状

end package puzzle_pkg;


package body puzzle_pkg is

    function mk_cell(r : integer; c : integer) return std_logic_vector is
        variable v : std_logic_vector(63 downto 0) := (others => '0');
    begin
        v(8 * r + c) := '1';
        return v;
    end function;

    function popcount(m : std_logic_vector(63 downto 0)) return integer is
        variable n : integer range 0 to 64 := 0;
    begin
        for i in 0 to 63 loop
            if m(i) = '1' then
                n := n + 1;
            end if;
        end loop;
        return n;
    end function;

    -- 独热编码：位序与显示掩码一致，bit0 = 左上角。
    function mask_to_px(row : integer; col : integer) return std_logic_vector is
        variable v : std_logic_vector(63 downto 0) := (others => '0');
    begin
        if (row >= 0) and (row <= 7) and (col >= 0) and (col <= 7) then
            v(8 * row + col) := '1';
        end if;
        return v;
    end function;

    -- 逐行、逐格平移，越界位直接丢弃，因此不会有跨行回绕。
    function shift_mask(m : std_logic_vector(63 downto 0);
                        dr : integer; dc : integer)
        return std_logic_vector is
        variable v  : std_logic_vector(63 downto 0) := (others => '0');
        variable tr : integer;
        variable tc : integer;
        variable rowbits : std_logic_vector(7 downto 0);
    begin
        for r in 0 to 7 loop
            tr := r + dr;
            if (tr >= 0) and (tr <= 7) then
                rowbits := m(8 * r + 7 downto 8 * r);
                for c in 0 to 7 loop
                    tc := c + dc;
                    if (tc >= 0) and (tc <= 7) then
                        if rowbits(c) = '1' then
                            v(8 * tr + tc) := '1';
                        end if;
                    end if;
                end loop;
            end if;
        end loop;
        return v;
    end function;

    -- 8 位行移位，返回 v(j) = r(j - dc)，越界补 0。
    --
    -- 实现细节：先按位倒序（纯连线）→ 用左移形式移位 → 再倒序回来。
    -- 直接写"向右移"会让形状中低列的格子被搬到高列，综合器无法把
    -- 高列那几路常量折叠掉，面积反而增大；倒序后左移的写法能让
    -- 移到边界外的逻辑被大量剪除。两种写法在数学上等价。
    function srl8(r : std_logic_vector(7 downto 0); dc : integer range -2 to 7)
        return std_logic_vector is
        variable rb, sb, v : std_logic_vector(7 downto 0);
    begin
        rb := r(0) & r(1) & r(2) & r(3) & r(4) & r(5) & r(6) & r(7);
        case dc is
            -- 负移位供旋转后的锚点补偿使用。
            when -1     => sb := rb(6 downto 0) & '0';
            when -2     => sb := rb(5 downto 0) & "00";
            when 0      => sb := rb;
            when 1      => sb := '0'         & rb(7 downto 1);
            when 2      => sb := "00"        & rb(7 downto 2);
            when 3      => sb := "000"       & rb(7 downto 3);
            when 4      => sb := "0000"      & rb(7 downto 4);
            when 5      => sb := "00000"     & rb(7 downto 5);
            when 6      => sb := "000000"    & rb(7 downto 6);
            when 7      => sb := "0000000"   & rb(7);
            when others => sb := (others => '0');
        end case;
        v := sb(0) & sb(1) & sb(2) & sb(3) & sb(4) & sb(5) & sb(6) & sb(7);
        return v;
    end function;

    function row24(shp24 : std_logic_vector(23 downto 0);
                   sr    : integer;
                   ac    : integer) return std_logic_vector is
        variable base : std_logic_vector(7 downto 0) := (others => '0');
    begin
        -- base 必须初始化且每个分支都赋值：子程序在编译期展开，
        -- 若某个分支得不到值，Quartus 会报 "expression has 0 elements"。
        if (sr = 0) then
            base := shp24(7 downto 0);
        elsif (sr = 1) then
            base := shp24(15 downto 8);
        elsif (sr = 2) then
            base := shp24(23 downto 16);
        else
            base := (others => '0');
        end if;
        return srl8(base, ac);
    end function;

    ----------------------------------------------------------------------------
    -- 旋转原语：只在 3x3 盒内做坐标置换，返回"第 sr 行"的 3 位。
    -- 循环变量 c 是编译期常量（0/1/2），所以每个输出位只在 4 个固定的
    -- shp 位之间选择，综合成 3 个 4 选 1 多路器，而不是动态索引整条 64 位。
    ----------------------------------------------------------------------------
    function rot_row(shp : std_logic_vector(63 downto 0);
                     ori : std_logic_vector(1 downto 0);
                     sr  : integer) return std_logic_vector is
        variable v  : std_logic_vector(7 downto 0) := (others => '0');
        variable r0 : integer range 0 to 2 := 0;
        variable c0 : integer range 0 to 2 := 0;
    begin
        if (sr >= 0) and (sr <= 2) then
            for c in 0 to 2 loop
                case ori is
                    when "00"   => r0 := sr;     c0 := c;        -- 原样
                    when "01"   => r0 := 2 - c;  c0 := sr;       -- 顺时针 90°
                    when "10"   => r0 := 2 - sr; c0 := 2 - c;    -- 180°
                    when others => r0 := c;      c0 := 2 - sr;   -- 顺时针 270°
                end case;
                v(c) := shp(8 * r0 + c0);
            end loop;
        end if;
        return v;
    end function;

    ----------------------------------------------------------------------------
    -- 旋转后紧包围盒在 3x3 盒内的偏移：
    --     dr:  "00"/"01" -> 0    "10" -> 3-h    "11" -> 3-w
    --     dc:  "00"      -> 0    "01" -> 3-h    "10" -> 3-w    "11" -> 0
    -- 返回 2 位向量而不是 integer：VHDL 的 integer 是 32 位，用 integer
    -- 返回会让综合器先按 32 位计算，综合出的面积更大。
    ----------------------------------------------------------------------------
    function rot_off_r(h : std_logic_vector(2 downto 0);
                       w : std_logic_vector(2 downto 0);
                       ori : std_logic_vector(1 downto 0))
        return std_logic_vector is
    begin
        case ori is
            when "10"   => return std_logic_vector(to_unsigned(3, 3) - unsigned(h));
            when "11"   => return std_logic_vector(to_unsigned(3, 3) - unsigned(w));
            when others => return "000";
        end case;
    end function;

    function rot_off_c(h : std_logic_vector(2 downto 0);
                       w : std_logic_vector(2 downto 0);
                       ori : std_logic_vector(1 downto 0))
        return std_logic_vector is
    begin
        case ori is
            when "01"   => return std_logic_vector(to_unsigned(3, 3) - unsigned(h));
            when "10"   => return std_logic_vector(to_unsigned(3, 3) - unsigned(w));
            when others => return "000";
        end case;
    end function;

    function oh(h : std_logic_vector(2 downto 0);
                w : std_logic_vector(2 downto 0);
                ori : std_logic_vector(1 downto 0)) return std_logic_vector is
    begin
        if (ori(0) = '1') then return w; else return h; end if;
    end function;

    function ow(h : std_logic_vector(2 downto 0);
                w : std_logic_vector(2 downto 0);
                ori : std_logic_vector(1 downto 0)) return std_logic_vector is
    begin
        if (ori(0) = '1') then return h; else return w; end if;
    end function;

    function ori_next(ori : std_logic_vector(1 downto 0)) return std_logic_vector is
        variable n : unsigned(1 downto 0);
    begin
        n := unsigned(ori) + 1;                  -- 2 位自然回绕，4 次一循环
        return std_logic_vector(n);
    end function;

end package body puzzle_pkg;
