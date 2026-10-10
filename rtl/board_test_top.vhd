-- ============================================================================
--  board_test_top  --  硬件自检顶层
--  这是一个诊断用顶层，不是游戏本体。先烧录这个。
--
--  为什么需要它
--  -------------
--  课程手册固定了每个引脚编号（PIN NUMBER），但从未说明：
--    (a) COLR0 是否是点阵最左边的物理列，
--    (b) ROW0 是否是点阵最上边的物理行，
--    (c) 4x4 键盘的电气极性 / 行列方向，
--    (d) 板上的时钟选择开关是否真的在 50 MHz 档位。
--  这四点都是全局性假设：只要有一点错了，即使游戏逻辑正确，
--  画面看起来也是坏的。本顶层把它们逐个隔离出来，
--  这样任何失败都不会被归咎于游戏逻辑。
--
--  各项测试显示什么（测试序号显示在全部 8 位数码管上）
--  ---------------------------------------------------------------------------
--   测试 0  "CORNERS"  四个角上的点显示黄色。
--           -> 可立即识别坐标轴镜像：如果边框上的点亮了，
--              但报告的方向不对，说明 .qsf 的位序
--              反了。斜线上的单个点会有歧义，四个角不会。
--   测试 1  "ALL"      每个点都是黄色 -> 确认全部 16 个行/列驱动都工作。
--   测试 2  "FRAME"    空心矩形，其中左上角的点为红色，
--           其余边框为黄色  -> 给出「原点在哪里」的绝对答案。
--   测试 3  "RED TOP / GREEN BOTTOM"  -> 把红/绿组交换与
--           行镜像区分开（两者的修法不同）。
--   测试 4  "WALK"     单个点以 2 Hz 先从左到右、再从上到下扫过。
--           -> 在实验台上行进方向一目了然。
--   测试 5  "KEY"      按下任意键：该键点亮自己的点，
--           键码以十六进制显示在 DISP7/DISP6 上。由此确定键盘的
--           极性以及行列方向。
--   测试 6  "BUTTON"   按住 BTN0：整个点阵变黄。
--           -> 确认复位按键通路。
--
--  测试序号每 3 s 自动前进，因此烧录一次即可覆盖全部项目，
--  按最右边的键（BTN0）可将其冻结，这样就能按需
--  长时间观察某一项测试。
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
        btn      : in  std_logic;                       -- PIN_61，BTN0 = 最右边，按下 = '1'
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
    -- 元件声明。
    -- 本项目约定使用 component + 端口映射（而不是 "entity work.xxx"）：
    -- 这样显式端口映射中漏掉端口会变成编译错误，而
    -- 位置关联/省略端口则可能悄悄留下悬空信号。
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
    signal walk_cnt : unsigned(5 downto 0) := (others => '0');   -- 0..63 走动位置
    signal frozen   : std_logic := '0';
    signal btn_d    : std_logic := '0';
    signal btn_dd   : std_logic := '0';

    -- （数码管诊断信号在下面、紧挨显示逻辑处声明）

    -- 最终送往点阵的画面
    signal px_red   : std_logic_vector(63 downto 0) := (others => '0');
    signal px_grn   : std_logic_vector(63 downto 0) := (others => '0');
    -- 正在显示的行：驱动器一次只取一行，所以
    -- 诊断画面按此切片
    signal row_idx  : unsigned(2 downto 0) := (others => '0');
    signal row_r    : std_logic_vector(7 downto 0) := (others => '0');
    signal row_g    : std_logic_vector(7 downto 0) := (others => '0');

    signal disp     : std_logic_vector(31 downto 0);            -- 8 位 BCD
    -- 诊断顶层不熄灭任何一位，所以这里用常量：若声明为
    -- signal 会被报告为 "never assigned a value"。
    constant NO_BLANK : std_logic_vector(7 downto 0) := (others => '0');
    signal seg_en   : std_logic;

    -- 数码管诊断（测试 7 与 8）。
    --   测试 7：一次只驱动一根段线 -> 读出段映射
    --   测试 8：在同一个数码管位上点亮全部段 -> 读出
    --            位选（CAT）顺序
    -- 4x4 键盘网格内解码出的按键位置（测试 9）
    signal kp_row_idx : integer range 0 to 3 := 0;
    signal kp_col_idx : integer range 0 to 3 := 0;
    signal seg_raw_en : std_logic;
    signal seg_raw    : std_logic_vector(7 downto 0);
    signal walk_step  : unsigned(3 downto 0) := (others => '0');  -- 0..15
    signal walk_sec   : unsigned(2 downto 0) := (others => '0');  -- 步内的秒数

    -- 蜂鸣器：按住按键时发出简单的 1 kHz 音（验证蜂鸣器通路）
    signal buzz_r   : std_logic := '0';

begin

    ----------------------------------------------------------------------------
    -- 键码 -> 键盘网格位置，供诊断显示使用。
    -- 键码布局故意在网格上分散开，这样行列顺序若搞错，
    -- 表现出来的是明显错误的「位置」，而不仅仅是
    -- 一个数字不对。
    ----------------------------------------------------------------------------
    process (key)
    begin
        case key is
            when K_UP      => kp_row_idx <= 0; kp_col_idx <= 0;
            when K_START   => kp_row_idx <= 0; kp_col_idx <= 3;
            when K_LEFT    => kp_row_idx <= 1; kp_col_idx <= 0;
            when K_DOWN    => kp_row_idx <= 1; kp_col_idx <= 1;
            when K_RIGHT   => kp_row_idx <= 1; kp_col_idx <= 2;
            when K_SELECT  => kp_row_idx <= 1; kp_col_idx <= 3;
            when K_CONFIRM => kp_row_idx <= 2; kp_col_idx <= 3;
            when others    => kp_row_idx <= 2; kp_col_idx <= 0;
        end case;
    end process;

    ----------------------------------------------------------------------------
    -- 复位仅由 BTN0 产生。游戏自身的 2 秒自检在这里
    -- 不参与，所以 BTN0 可以纯粹当作「按住查看」键使用。
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
            -- o_press / o_release / o_raw 是给游戏本体和 .vwf
            -- 波形用的；本诊断顶层用不到它们，所以
            -- 悬空处理。具名关联使这一点显式且安全。
            o_press   => open,
            o_release => open,
            o_raw     => kp_raw
        );

    ----------------------------------------------------------------------------
    -- 冻结控制：按下 BTN0 切换 "frozen"。
    -- clk_gen 产生的复位本身就来自 BTN0，所以按键
    -- 必须在这里做边沿检测，而不能在按住时用 t_1k 采样。
    -- 因为 BTN0 是外部引脚，所以保留两级同步器。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                btn_d  <= '0';
                btn_dd <= '0';
                frozen <= '0';
            else
                btn_d  <= btn;
                btn_dd <= btn_d;
                if (btn_d = '1') and (btn_dd = '0') then
                    frozen <= not frozen;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 测试序号序列器：每 3 秒在 tick_1hz 上自动前进。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                test_idx <= (others => '0');
                sec_cnt  <= (others => '0');
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
    -- 段 / 位走动计数器（测试 7 与 8）。
    -- 每 2 秒一步，共 16 步 0..15，所以一整轮为 32 s：
    --   测试 7：步 0..7  一次驱动一个段 AA..AP（AP 最后）
    --   测试 8：步 0..7  一次在 CAT0..CAT7 之一上点亮全部段
    -- 每步保持 2 s，使该图案在实验台上极易辨认。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                walk_step <= (others => '0');
                walk_sec  <= (others => '0');
            elsif ((test_idx = 7) or (test_idx = 8)) then
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
    -- 驱动数码管诊断线。
    --
    -- 测试 7：一次一根段线拉高，绕过译码器。
    --          下面扫描计数器的 'idx' 选取当前步，操作者
    --          观察哪一个「物理」段点亮。
    -- 测试 8：每个数码管位上所有段线都拉高，但位选
    --          图案只让一个阴极拉低，因此只有一位
    --          数码管点亮。由此读出 CAT 顺序。
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
            -- 测试 8：所有段点亮；由 seg_scan 恰好选中一位数码管
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
    -- 掩码为 64 位，位索引 = 8*row + col，bit0 = 左上角的点，且在
    -- 一行之内第 0 列就是 bit 0。把它们写成位串（bit63 在最左）
    -- 可以让每一个点的位置都明确、可审计。
    ----------------------------------------------------------------------------
    process (test_idx, walk_cnt, key, btn, sw7)
        variable v_red : std_logic_vector(63 downto 0);
        variable v_grn : std_logic_vector(63 downto 0);
        variable v_row : integer range 0 to 7;
        variable v_col : integer range 0 to 7;
        -- 键码从 1 开始（K_NONE = 0），所以拆分前先减一
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

            -- 测试 5：键盘 -> 它在点阵上的自身位置
            when 5 =>
                if (key /= K_NONE) then
                    v_key := unsigned(key) - 1;                         -- K_START=1 -> 0
                    v_row := to_integer(v_key(3 downto 2));             -- 键组
                    v_col := to_integer(v_key(1 downto 0));             -- 组内
                    v_red(8 * v_row + v_col) := '1';
                    v_grn(8 * v_row + v_col) := '1';
                end if;

            -- 测试 6：BTN0 -> 按住时整个点阵为黄色
            when 6 =>
                if (btn = '1') then
                    v_red := (others => '1');
                    v_grn := (others => '1');
                end if;

            -- 测试 9：键盘识别。
            --   点阵第 7 行显示四条原始行线的电平（颜色 = 电平）：
            --       红色 = 该行线读到 '0'
            --       绿色 = 该行线读到 '1'
            --   其余各行显示解码出的按键位置。
            when 9 =>
                -- 原始行线放在最下面一行，以便看到空闲极性
                for c in 0 to 3 loop
                    if (kp_row(c) = '0') then
                        v_red(8 * 7 + c) := '1';
                    else
                        v_grn(8 * 7 + c) := '1';
                    end if;
                end loop;

                -- 解码出的按键画在它自己的网格位置上
                if (key /= K_NONE) then
                    v_red(8 * kp_row_idx + kp_col_idx) := '1';
                    v_grn(8 * kp_row_idx + kp_col_idx) := '1';
                end if;

            -- 测试 7：7 段数码管的段识别。
            --   点阵保持全暗；请看数码管显示。
            --   每 2 s 恰好驱动一根段线（绕过译码器），
            --   bit0=AA ... bit6=AG，bit7=AP。记下哪一个「物理」段点亮。
            -- 测试 8：7 段数码管的位（DIGIT）位置识别。
            --   每 2 s 在恰好一个数码管位上驱动全部段。
            -- 测试 9：所有数码管位上的全部段点亮（静态 "88888888"）。
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
    -- 点阵驱动器的行计数器与画面切片。
    -- 驱动器一次只取一行，所以上面构造的 64 位画面在
    -- 这里切片。第 0 行是逻辑上的最上一行；dot_matrix_scan 施加
    -- 实测得到的物理行序。
    --
    -- ⚠️ ERR-039（2026-10-09 第 11 工作阶段，全项目审计发现）：这里原来把
    --    row_idx=0 切到 px(63..56)。本文件的画图约定是 "bit = 8*row+col、
    --    **bit0 = 左上角**"（同文件 :390 的注释就是这么写的），所以 px(63..56)
    --    是**第 7 行（最下一行）** —— 自检画面被**上下镜像**显示了，而 puzzle_top
    --    的同一段切片是 px(7..0)（正确）。已在下面改成 px(7..0)。
    --    ⚠️ 上板复核：test 2 的红色标记（画面左上角那一点）现在应出现在
    --    **左上角**；若仍出现在左下角，说明 dot_matrix_scan 的行序还要反过来
    --    （那会连带影响整机画面方向）—— 这条要人工上板确认，见 HANDOFF §7⓪。
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
    --  测试 0..6：每一位都显示测试序号，这样操作者总能
    --              知道当前屏幕上跑的是哪一项测试。
    --  测试 7    ：段识别测试。所有数码管位显示相同的
    --              值，这正是要点所在 —— 它把段线与位选线
    --              隔离开来。显示的数码管值每 2 s 循环
    --              经过 SEG_SUB_BCD 中的各个值。
    --
    -- 因为译码器位于 seg_scan 中，无法直接请求单根段；
    -- 只能请求合法的 BCD 数字。这就是测试 7 使用
    -- SEG_SUB_BCD 中那些「只亮一段」数字的原因。
    ----------------------------------------------------------------------------
    ----------------------------------------------------------------------------
    -- 数码管内容：每一位都显示 4 位测试序号，这样
    -- 操作者总能知道当前屏幕上跑的是哪一项测试。测试 7 与 8 用
    -- 原始段图案取代译码后的内容（见上面的 seg_raw）。
    ----------------------------------------------------------------------------
    process (test_idx, key)
        variable v_nib  : std_logic_vector(3 downto 0);
        variable v_disp : std_logic_vector(31 downto 0);
    begin
        v_nib := '0' & std_logic_vector(test_idx(2 downto 0));
        v_disp := (others => '0');
        for d in 0 to 7 loop
            v_disp(4 * d + 3 downto 4 * d) := v_nib;
        end loop;

        if (test_idx = 9) then
            -- DISP1:DISP0 = 解码后的键码（0..7），其余数码管位熄灭
            v_disp := (others => '0');
            v_disp(3 downto 0) := key;
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
    -- 蜂鸣器：由按住的键门控的 1 kHz。可独立于游戏的音效
    -- 验证蜂鸣器通路。SW7=0 时同样静音。
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
