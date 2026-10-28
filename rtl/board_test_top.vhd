-- ============================================================================
--  board_test_top  ——  硬件自检顶层（诊断用，不是游戏本体）
--
--  为什么需要它
--  -------------
--  课程手册固定了引脚编号，但没有说明：
--    (a) COLR0 是否是点阵最左边的物理列
--    (b) ROW0 是否是点阵最上边的物理行
--    (c) 4x4 键盘的电气极性与行列方向
--    (d) 板上的时钟选择开关是否真的在 50 MHz 档
--  这些假设只要错一个，即使游戏逻辑正确，画面也会是坏的。
--  本顶层把它们逐项隔离验证，使任何失败都不会被误判成游戏逻辑问题。
--
--  测试项目（序号显示在 8 位数码管上）：
--    0  CORNERS  四角为黄色 -> 可立即发现坐标轴镜像
--    1  ALL      全部点为黄色 -> 确认 16 路行/列驱动都工作
--    2  FRAME    空心矩形，左上角为红点 -> 给出"原点在哪里"的绝对答案
--    3  RED TOP / GREEN BOTTOM -> 区分红绿接反与行镜像
--    4  WALK     单点以 2 Hz 从左到右、再从上到下扫过
--    5  KEY      按下某键点亮其对应位置 -> 确认键盘极性与行列方向
--    6  BUTTON   冻结状态下整屏变黄 -> 确认 BTN0 通路
--    7  SEG      每 2 s 只驱动一根段线（绕过译码器）-> 读出段线顺序
--    8  DIGIT    8 位同时点亮全部段（静态 88888888）-> 确认段线全通
--    9  KEYPAD   点阵底行显示四条行线电平，按键位置画在点阵网格上
--   10  CAT      每位显示自己的位号 -> 读出位选（CAT）顺序
--
--  测试序号每 3 s 自动前进，烧录一次即可覆盖全部项目。
--  BTN0 有两种用法，由 clk_gen 的 20 ms 复位滤波区分：
--    · 短按 -> 冻结 / 解冻，可长时间观察某一项测试；
--    · 长按（>= 20 ms）-> 复位，序号回到 0（冻结期间不清）。
--  长按不会顺带切换冻结状态。
--
--  注意：测试 6 不能用"按住 BTN0"实现。BTN0 按住 >= 20 ms 会拉起 rst，
--  而 rst 会把点阵输出清零，所以"按住才变黄"在板上永远看不见。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity board_test_top is
    port (
        -- 时钟与开关
        clk      : in  std_logic;                       -- PIN_18
        sw7      : in  std_logic;                       -- PIN_125，向上 = '1'
        btn      : in  std_logic;                       -- PIN_61，BTN0，按下 = '1'
        -- 4x4 矩阵键盘
        kp_row   : in  std_logic_vector(3 downto 0);    -- PIN_111..114
        kp_col   : out std_logic_vector(3 downto 0);    -- PIN_117..120
        -- 点阵
        dot_row  : out std_logic_vector(7 downto 0);    -- PIN_8..1
        dot_colr : out std_logic_vector(7 downto 0);    -- PIN_22,21,16,15,14,13,12,11
        dot_colg : out std_logic_vector(7 downto 0);    -- PIN_45,44,43,42,41,40,39,38
        -- 数码管
        seg      : out std_logic_vector(7 downto 0);    -- PIN_62,59,58,57,55,53,52,51
        cat      : out std_logic_vector(7 downto 0);    -- PIN_63,66,67,68,69,70,30,31
        -- 蜂鸣器
        buzz     : out std_logic                        -- PIN_60
    );
end entity board_test_top;

architecture rtl of board_test_top is

    ----------------------------------------------------------------------------
    -- 元件声明。本项目统一使用 component + 具名端口映射，而不是
    -- "entity work.xxx"：漏写端口会变成编译错误，避免悬空信号。
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

    -- 测试序列控制
    signal test_idx : unsigned(3 downto 0) := (others => '0');
    signal sec_cnt  : unsigned(1 downto 0) := (others => '0');   -- 0..2 = 3 s
    signal walk_cnt : unsigned(5 downto 0) := (others => '0');   -- 0..63
    signal frozen   : std_logic := '0';
    signal btn_d    : std_logic := '0';
    signal btn_dd   : std_logic := '0';

    -- 最终送往点阵的画面
    signal px_red   : std_logic_vector(63 downto 0) := (others => '0');
    signal px_grn   : std_logic_vector(63 downto 0) := (others => '0');
    -- 正在显示的行：驱动器一次只取一行
    signal row_idx  : unsigned(2 downto 0) := (others => '0');
    signal row_r    : std_logic_vector(7 downto 0) := (others => '0');
    signal row_g    : std_logic_vector(7 downto 0) := (others => '0');

    signal disp     : std_logic_vector(31 downto 0);            -- 8 位 BCD
    -- 诊断顶层不熄灭任何一位
    constant NO_BLANK : std_logic_vector(7 downto 0) := (others => '0');
    signal seg_en   : std_logic;

    -- 数码管诊断（测试 7、8、10）
    signal kp_row_idx : integer range 0 to 3 := 0;
    signal kp_col_idx : integer range 0 to 3 := 0;
    signal seg_raw_en : std_logic;
    signal seg_raw    : std_logic_vector(7 downto 0);
    signal walk_step  : unsigned(3 downto 0) := (others => '0');  -- 0..15
    signal walk_sec   : unsigned(2 downto 0) := (others => '0');  -- 步内秒数

    -- 按住按键时发出 1 kHz 音，用于验证蜂鸣器通路
    signal buzz_r   : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- 原始键号 -> 键盘网格位置，供测试 9 在点阵上画点。
    -- 注意 key 是 keypad_scan 的原始键号 4*行 + 列，不是游戏键码 K_*。
    -- 位置故意在网格上分散开，行列顺序若搞错会表现为明显错误的位置。
    ----------------------------------------------------------------------------
    process (key)
    begin
        case key is
            when "1010" => kp_row_idx <= 0; kp_col_idx <= 0;   -- KEY7
            when "1011" => kp_row_idx <= 0; kp_col_idx <= 1;   -- KEY8
            when "0001" => kp_row_idx <= 0; kp_col_idx <= 3;   -- KEY14
            when "0101" => kp_row_idx <= 1; kp_col_idx <= 0;   -- KEY10
            when "0010" => kp_row_idx <= 1; kp_col_idx <= 1;   -- KEY15
            when "0111" => kp_row_idx <= 1; kp_col_idx <= 2;   -- KEY12
            when "0011" => kp_row_idx <= 1; kp_col_idx <= 3;   -- KEY16
            when "0110" => kp_row_idx <= 2; kp_col_idx <= 3;   -- KEY11
            -- 未映射（含 "0000" = 无键、KEY13 不可用）
            when others    => kp_row_idx <= 2; kp_col_idx <= 0;
        end case;
    end process;

    ----------------------------------------------------------------------------
    -- 时钟与复位。复位只由 BTN0 产生：按住 >= 20 ms 拉高 o_rst。
    -- 本顶层没有游戏的自检状态，所以 BTN0 同时用作"冻结"键，
    -- 两种用法靠 20 ms 滤波区分。
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
            -- 本诊断顶层不使用 press / release，显式悬空
            o_press   => open,
            o_release => open,
            o_raw     => kp_raw
        );

    ----------------------------------------------------------------------------
    -- 冻结控制：短按 BTN0 切换 frozen，长按 = 复位。
    --
    -- 在**松手沿**切换，理由：
    --   · 短按（松手时还没到 20 ms）：rst 从未有效，同步器保住了"按下"，
    --     松手时能采到下降沿 -> 切换 frozen；
    --   · 长按（>= 20 ms）：rst 把同步器清零过，松手时没有下降沿
    --     -> 不切换，长按只复位。
    -- frozen 刻意不接复位：复位不应顺手解冻，否则无法冻结观察某一项。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                -- 只清边沿检测历史，不清 frozen
                btn_d  <= '0';
                btn_dd <= '0';
            else
                btn_d  <= btn;
                btn_dd <= btn_d;
                if (btn_dd = '1') and (btn_d = '0') then   -- 松手沿
                    frozen <= not frozen;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 测试序号序列器：每 3 秒在 tick_1hz 上自动前进。
    -- 复位时清 test_idx 有条件：冻结期间不清，避免长按复位把正在观察的
    -- 测试项踢回 test 0。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                sec_cnt  <= (others => '0');
                if (frozen = '0') then
                    test_idx <= (others => '0');
                end if;
            else
                if (frozen = '0') and (t_1hz = '1') then
                    if (sec_cnt = 2) then
                        sec_cnt  <= (others => '0');
                        test_idx <= test_idx + 1;               -- 13 -> 0 回绕
                    else
                        sec_cnt <= sec_cnt + 1;
                    end if;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 段走动计数器（测试 7）：每 2 秒一步，共 16 步 0..15。
    -- 测试 7 只使用步 0..7，一次驱动一根段线 AA..AP。
    -- 测试 8 不步进：静态点亮所有段。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                walk_step <= (others => '0');
                walk_sec  <= (others => '0');
            elsif (test_idx = 7) then
                if (t_1hz = '1') then
                    if (walk_sec = 1) then
                        walk_sec  <= (others => '0');
                        walk_step <= walk_step + 1;         -- 15 -> 0 回绕
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
    -- 数码管诊断线（段线旁路，只由测试 7 与 8 使用）。
    --   测试 7：一次一根段线拉高，操作者观察哪一根物理段点亮。
    --   测试 8：所有段线同时拉高。注意位选无法旁路，阴极始终由
    --           seg_scan 自己的扫描计数器驱动，所以看到的是 8 位同时全亮；
    --           它只能确认"共用段线全通、8 位都亮"，读不出 CAT 顺序。
    ----------------------------------------------------------------------------
    seg_raw_en <= '1' when ((test_idx = 7) or (test_idx = 8)) else '0';

    process (test_idx, walk_step)
        variable v : std_logic_vector(7 downto 0);
        variable s : integer range 0 to 15;
    begin
        v := (others => '0');
        s := to_integer(walk_step);

        if (test_idx = 7) then
            -- i_raw 位索引 == 段号：bit0=AA ... bit6=AG，bit7=AP
            if (s < 8) then
                v(s) := '1';
            end if;
        else
            -- 测试 8：所有段线拉高
            v := (others => '1');
        end if;

        seg_raw <= v;
    end process;

    ----------------------------------------------------------------------------
    -- 测试 4 的走动计数器：2 Hz，0..63
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
    -- 图案生成器。
    -- 掩码为 64 位，位下标 = 8*row + col，bit0 = 左上角；写成位串时
    -- bit63 在最左边，因此每个点的位置都明确可审计。
    ----------------------------------------------------------------------------
    process (test_idx, walk_cnt, key, frozen, sw7, kp_row, kp_row_idx, kp_col_idx)
        variable v_red : std_logic_vector(63 downto 0);
        variable v_grn : std_logic_vector(63 downto 0);
        variable v_row : integer range 0 to 7;
        variable v_col : integer range 0 to 7;
        -- 键码从 1 开始（K_NONE = 0），拆分行列前先减一
        variable v_key : unsigned(3 downto 0);
    begin
        v_red := (others => '0');
        v_grn := (others => '0');

        case to_integer(test_idx) is

            -- 测试 0：四个角为黄色
            when 0 =>
                v_red(0)  := '1'; v_red(7)  := '1';
                v_red(56) := '1'; v_red(63) := '1';
                v_grn := v_red;

            -- 测试 1：全部为黄色
            when 1 =>
                v_red := (others => '1');
                v_grn := (others => '1');

            -- 测试 2：空心边框；左上角的点为红色，其余边框为黄色
            when 2 =>
                for c in 0 to 7 loop
                    v_grn(c)      := '1';      -- 顶行（第 0 行）
                    v_grn(56 + c) := '1';      -- 底行（第 7 行）
                end loop;
                for r in 0 to 7 loop
                    v_grn(8 * r)     := '1';   -- 左列（第 0 列）
                    v_grn(8 * r + 7) := '1';   -- 右列（第 7 列）
                end loop;
                v_red(0) := '1';               -- 左上角标记
                v_grn(0) := '0';

            -- 测试 3：上半部分红色，下半部分绿色
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

            -- 测试 4：单个走动的点，先从左到右、再从上到下
            when 4 =>
                v_row := to_integer(walk_cnt) / 8;
                v_col := to_integer(walk_cnt) mod 8;
                v_red(8 * v_row + v_col) := '1';
                v_grn(8 * v_row + v_col) := '1';        -- 黄色，便于观察

            -- 测试 5：原始键号 -> 按阅读顺序摆放的位置
            when 5 =>
                if (key /= K_NONE) then
                    v_key := unsigned(key) - 1;                         -- K_START=1 -> 0
                    v_row := to_integer(v_key(3 downto 2));             -- 键组
                    v_col := to_integer(v_key(1 downto 0));             -- 组内
                    v_red(8 * v_row + v_col) := '1';
                    v_grn(8 * v_row + v_col) := '1';
                end if;

            -- 测试 6：BTN0 通路 -> 冻结时整屏黄色。
            -- 不能用"按住 btn"：按住 >= 20 ms 会拉高 rst，点阵被清零，
            -- "按住才变黄"永远看不见。改用松手后仍保持的 frozen。
            when 6 =>
                if (frozen = '1') then
                    v_red := (others => '1');
                    v_grn := (others => '1');
                end if;

            -- 测试 9：键盘识别。
            --   点阵第 7 行显示四条原始行线的电平：红 = 读到 '0'，绿 = '1'；
            --   其余各行显示原始键号对应的位置。
            when 9 =>
                -- 原始行线放在最下面一行，便于观察空闲极性
                for c in 0 to 3 loop
                    if (kp_row(c) = '0') then
                        v_red(8 * 7 + c) := '1';
                    else
                        v_grn(8 * 7 + c) := '1';
                    end if;
                end loop;

                -- 查表得到的位置上画一个点（key = "0000" = 无键按下）
                if (key /= K_NONE) then
                    v_red(8 * kp_row_idx + kp_col_idx) := '1';
                    v_grn(8 * kp_row_idx + kp_col_idx) := '1';
                end if;

            -- 测试 7、8、10..15：点阵保持全暗（观察对象是数码管）
            when others =>
                v_red := (others => '0');
                v_grn := (others => '0');

        end case;

        -- 全局开关 B1：SW7=0 熄灭所有显示器件
        if (sw7 = '0') then
            v_red := (others => '0');
            v_grn := (others => '0');
        end if;

        px_red <= v_red;
        px_grn <= v_grn;
    end process;

    ----------------------------------------------------------------------------
    -- 点阵行计数器与画面切片。
    -- 驱动器一次只取一行，第 0 行是逻辑最上一行；dot_matrix_scan 内部
    -- 再施加实测得到的物理行序。切片时第 0 行取 px(7..0)。
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
    -- 点阵驱动器
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
    -- 数码管内容。
    --
    --  测试 0..7 ：每一位都显示测试序号（同一个数字铺满 8 位）。
    --  测试 8    ：段线旁路，i_data 不起作用（见上面的 seg_raw）。
    --  测试 9    ：DISP0 = 原始键号，其余位熄灭；
    --              10..15 会显示为 A/P/S/F/L（15 为灭），这是 7 段管的限制。
    --  测试 10   ：每一位显示自己的位号（见下）。
    --  测试 11..15：两位十进制序号（十位恒为 1 + 个位）重复 4 遍。
    --
    --  说明：测试 0..9 的默认分支只取 test_idx 的低 3 位，因为
    --  测试 8/9 的序号显示会被上面两项覆盖，不影响可读性。
    ----------------------------------------------------------------------------
    process (test_idx, key)
        variable v_nib  : std_logic_vector(3 downto 0);
        variable v_disp : std_logic_vector(31 downto 0);
    begin
        v_disp := (others => '0');

        if (to_integer(test_idx) >= 10) then
            -- 10..15：两位十进制并重复 4 遍（每对相邻位 = 十位 "1" + 个位）
            for d in 0 to 3 loop
                v_disp(8 * d + 7 downto 8 * d + 4) := "0001";                        -- 十位 = 1
                v_disp(8 * d + 3 downto 8 * d)     := std_logic_vector(test_idx - 10); -- 个位 0..5
            end loop;
        else
            -- 0..9：8 位都显示同一个数字
            v_nib := '0' & std_logic_vector(test_idx(2 downto 0));
            for d in 0 to 7 loop
                v_disp(4 * d + 3 downto 4 * d) := v_nib;
            end loop;
        end if;

        if (test_idx = 9) then
            -- DISP0 = 原始键号，其余数码管位熄灭
            v_disp := (others => '0');
            v_disp(3 downto 0) := key;
        end if;

        if (test_idx = 10) then
            -- 每一位显示自己的位号：DISP7=0, DISP6=1, ... DISP0=7。
            -- 从左到右读出的数字序列就是 CAT 位选顺序。
            for d in 0 to 7 loop
                v_disp(4 * d + 3 downto 4 * d) := std_logic_vector(to_unsigned(7 - d, 4));
            end loop;
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
    -- 蜂鸣器：按住任意键时发出 1 kHz 方波，可独立验证蜂鸣器通路。
    -- SW7=0 时静音。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                buzz_r <= '0';
            elsif (t_1k = '1') then
                buzz_r <= not buzz_r;      -- 1 kHz 方波
            end if;
        end if;
    end process;

    buzz <= buzz_r when ((sw7 = '1') and (key /= K_NONE)) else '0';

end architecture rtl;
