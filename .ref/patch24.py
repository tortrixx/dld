# -*- coding: utf-8 -*-
"""让 board_test_top 适配新的按行点阵接口。

dot_matrix_scan 现在只接收**一行**（8 位）及其行号，因为整机
游戏每个扫描周期只渲染一行。诊断顶层为每个测试构造一幅
64 位画面，所以它保留一个 40 Hz 的行计数器，并为驱动
切出对应的那一行画面。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "board_test_top.vhd"
s = p.read_text(encoding="utf-8")

# ---- clk_gen 组件新增 o_tick_40 --------------------------------------
s = s.replace("""            o_tick_2hz : out std_logic;
            o_tick_1hz : out std_logic
        );
    end component;""",
              """            o_tick_2hz : out std_logic;
            o_tick_1hz : out std_logic;
            o_tick_40  : out std_logic
        );
    end component;""")

# ---- dot_matrix_scan 组件改为按行 --------------------------------
s = s.replace("""    component dot_matrix_scan
        port (
            i_clk    : in  std_logic;
            i_rst    : in  std_logic;
            i_tick   : in  std_logic;
            i_en     : in  std_logic;
            i_px_red : in  std_logic_vector(63 downto 0);
            i_px_grn : in  std_logic_vector(63 downto 0);
            o_row    : out std_logic_vector(7 downto 0);
            o_colr   : out std_logic_vector(7 downto 0);
            o_colg   : out std_logic_vector(7 downto 0)
        );
    end component;""",
              """    component dot_matrix_scan
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
    end component;""")

# ---- 新增信号 ------------------------------------------------------------
s = s.replace("""    signal px_red   : std_logic_vector(63 downto 0) := (others => '0');
    signal px_grn   : std_logic_vector(63 downto 0) := (others => '0');""",
              """    signal px_red   : std_logic_vector(63 downto 0) := (others => '0');
    signal px_grn   : std_logic_vector(63 downto 0) := (others => '0');
    -- row being displayed: the driver samples one row at a time, so the
    -- diagnostic picture is sliced to match
    signal row_idx  : unsigned(2 downto 0) := (others => '0');
    signal row_r    : std_logic_vector(7 downto 0) := (others => '0');
    signal row_g    : std_logic_vector(7 downto 0) := (others => '0');""")

# ---- tick_40 连线 -----------------------------------------------------------
s = s.replace("    signal t_1hz    : std_logic;",
              "    signal t_1hz    : std_logic;\n    signal t_40     : std_logic;")
s = s.replace("            o_tick_1hz => t_1hz\n        );",
              "            o_tick_1hz => t_1hz,\n            o_tick_40  => t_40\n        );")

# ---- 行计数器与切片 ----------------------------------------------------
s = s.replace("""    ----------------------------------------------------------------------------
    -- Dot-matrix driver
    ----------------------------------------------------------------------------""",
              """    ----------------------------------------------------------------------------
    -- Row counter and picture slice for the matrix driver.
    -- The driver takes one row at a time, so the 64-bit picture built above is
    -- sliced here.  Row 0 is the TOP logic row; dot_matrix_scan applies the
    -- measured physical row order.
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
        row_r <= px_red(63 downto 56) when 0,
                 px_red(55 downto 48) when 1,
                 px_red(47 downto 40) when 2,
                 px_red(39 downto 32) when 3,
                 px_red(31 downto 24) when 4,
                 px_red(23 downto 16) when 5,
                 px_red(15 downto  8) when 6,
                 px_red( 7 downto  0) when others;

    with to_integer(row_idx) select
        row_g <= px_grn(63 downto 56) when 0,
                 px_grn(55 downto 48) when 1,
                 px_grn(47 downto 40) when 2,
                 px_grn(39 downto 32) when 3,
                 px_grn(31 downto 24) when 4,
                 px_grn(23 downto 16) when 5,
                 px_grn(15 downto  8) when 6,
                 px_grn( 7 downto  0) when others;

    ----------------------------------------------------------------------------
    -- Dot-matrix driver
    ----------------------------------------------------------------------------""")

# ---- 端口映射 ---------------------------------------------------------------
s = s.replace("""            i_clk    => clk,
            i_rst    => rst,
            i_tick   => t_200,
            i_en     => sw7,
            i_px_red => px_red,
            i_px_grn => px_grn,
            o_row    => dot_row,
            o_colr   => dot_colr,
            o_colg   => dot_colg
        );""",
              """            i_clk   => clk,
            i_rst   => rst,
            i_en    => sw7,
            i_row   => std_logic_vector(row_idx),
            i_colr  => row_r,
            i_colg  => row_g,
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );""")

p.write_text(s, encoding="utf-8")
print("board_test_top adapted")
