-- ============================================================================
--  puzzle_pkg  --  global constants, types and pure functions
--  Topic 4 : Simple Jigsaw Puzzle Game  (Digital Circuits & Logic Design Lab)
--  Target  : Altera MAX II  EPM1270T144C5   /   Quartus II 9.1   /   VHDL
--
--  This package is the SINGLE SOURCE OF TRUTH for:
--    * bit-order convention of the 8x8 dot-matrix masks
--    * pattern / piece geometry (decoded from the course PDF figures)
--    * all timing constants and state encodings
--
--  NOTE: this file contains constants and pure functions only -- no signals,
--        no processes, therefore it infers no hardware at all.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

package puzzle_pkg is

    ----------------------------------------------------------------------------
    -- 1. Array types (a VHDL-93 port cannot use an anonymous array type,
    --    so the types must be declared once here and shared by every module)
    ----------------------------------------------------------------------------
    type mask_arr_t is array (0 to 3) of std_logic_vector(63 downto 0);
    type dim_arr_t  is array (0 to 3) of std_logic_vector(2 downto 0);

    constant MASK_ZERO : std_logic_vector(63 downto 0) := (others => '0');

    ----------------------------------------------------------------------------
    -- 2. Pure functions
    --    mk_cell(row, col) : build a one-cell mask
    --      bit index = 8*row + col,  bit0 = top-left corner
    --      So inside one row, column 0 is bit 0 (NOT the MSB).
    --      Column 0 is the left-most column on the panel.
    --      => moving RIGHT by one column = shift the whole 64-bit mask LEFT.
    --         (a plain "sll 1" is safe here because it is applied per row and
    --          the mask is re-normalised by the ROM constants, see docs)
    ----------------------------------------------------------------------------
    function mk_cell(r : integer; c : integer) return std_logic_vector;

    -- number of '1' bits -- used by self-check / offline verification only
    function popcount(m : std_logic_vector(63 downto 0)) return integer;

    -- mask_to_px : convert an absolute 8x8 mask into the 64-bit pixel mask used
    -- by dot_matrix_scan.  bit index = 8*row + col, bit0 = top-left.
    -- NOTE the two conventions are DIFFERENT:
    --   * puzzle masks (this package, from the PDF figures) use bit0 = TOP-LEFT
    --     and are written as bit strings with the LEFT-most dot at bit63.
    --   * the pixel mask for the display uses bit0 = TOP-LEFT as well, but is
    --     built so that a plain shift moves right within a row safely.
    --   This function is the ONLY place the two meet.
    function mask_to_px(row : integer; col : integer) return std_logic_vector;

    -- shift_mask : move a mask by (dr, dc) cells, clearing anything that would
    -- leave the 8x8 field.  A plain "sll" cannot be used: shifting a mask left
    -- by 1 makes the right-most cell of row r wrap into the left-most cell of
    -- row r+1 (the classic "pixel walks through the wall" bug).
    function shift_mask(m : std_logic_vector(63 downto 0);
                        dr : integer; dc : integer)
        return std_logic_vector;

    -- srl8 : shift ONE 8-bit row RIGHT by dc columns (towards higher column
    -- numbers), filling with '0'.  "Right" in the panel sense: the piece's
    -- relative column k is placed at panel column k + dc.
    -- Kept separate (and only 8 bits wide) because a variable-distance shift of
    -- a 64-bit word is a 64x6 crossbar: using it inside the engine cost 4690
    -- logic cells on a 1270-cell device.  Shifting 8-bit rows instead is cheap.
    function srl8(r : std_logic_vector(7 downto 0); dc : integer)
        return std_logic_vector;

    -- row24 : 8-bit row mask of a piece at anchor column 'ac'.
    --   shp24 : the piece's relative shape, packed as 3 rows of 8 bits
    --           (bits 7..0 = row 0, 15..8 = row 1, 23..16 = row 2)
    --   sr    : which of the piece's own rows to fetch (0..2)
    -- Returns the 8 bits that this row contributes to the panel row it lands on.
    -- Used for EXACT overlap tests: a bounding-box test over-approximates for the
    -- cross and the L-tromino used by level 1, so legal moves would be rejected.
    function row24(shp24 : std_logic_vector(23 downto 0);
                   sr    : integer;
                   ac    : integer) return std_logic_vector;

    ----------------------------------------------------------------------------
    -- 3. Pattern geometry -- DECODED FROM THE COURSE PDF FIGURES (pixel exact)
    --    See docs/00 sections 4.5 for the decoding evidence.
    ----------------------------------------------------------------------------

    -- FIG 4-1 : level-1 complete picture = a solid 4-row x 3-col rectangle
    --           occupying matrix rows 2..5, cols 2..4  -> 12 cells
    constant L1_TARGET_MASK : std_logic_vector(63 downto 0) :=
        "0000000000000000000111000001110000011100000111000000000000000000";

    -- FIG 4-2 : level-1 three loose pieces  3 + 6 + 3 = 12 cells (area conserved)
    --   P1 : 1x3 horizontal bar        (3 cells)
    constant L1_P0 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000000000000111";
    --   P2 : 6-cell staircase (3-2-1)
    --        ⚠️ 2026-10-09 更正：这里原来写的是 "cross shape"，与实际掩码和课程 PDF 都不符 ——
    --        掩码是 3-2-1 阶梯形（行5 col7 / 行6 col6,7 / 行7 col5,6,7）。依据：
    --        `docs/03` §2 第 2 行——已用 `.ref/solve_l1.py` 对 **课程 PDF 图 4-2 逐像素解码**
    --        核对过：PDF 里这一块就是 6 格阶梯形，三块形状逐格一致。
    --        这属于 ERR-027 那类"注释与现实不符"，只是这次错的是注释而不是设计。
    --        （面积 3+6+3 = 12，与 1×3 横条、L 形三格块一起恰好铺满目标；
    --          由 scripts/check_geometry.py 的"目标图案 == 零片并集"检查保证。）
    constant L1_P1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000010000001100000111";
    --   P3 : L-tromino, cells at (0,1)(1,0)(1,1) of its 2x2 bbox   (3 cells)
    constant L1_P2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000001100000010";

    -- Level-2 complete picture (self-designed, see docs/02):
    --   solid 4x4 square, rows 2..5, cols 2..5  -> 16 cells
    --   VERIFIED to equal the union of the four L2 pieces at their target
    --   anchors (scripts/check_geometry.py).  An earlier literal put the square
    --   at rows 3..6 while the piece targets were at rows 2..5, so the red ghost
    --   was drawn one row below where the puzzle had to be assembled -- the
    --   player following the ghost could never match it.
    constant L2_TARGET_MASK : std_logic_vector(63 downto 0) :=
        "0000000000000000001111000011110000111100001111000000000000000000";

    -- Level-2 four pieces  4 + 4 + 4 + 4 = 16 cells (area conserved)
    --   Q0..Q3 : 2x2 squares that tile the 4x4 target above
    constant L2_P0 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000001100000011";
    constant L2_P1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000001100000011";
    constant L2_P2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000001100000011";
    constant L2_P3 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000001100000011";

    -- Target anchors: where each piece is EXPECTED to end up.  They describe the
    -- intended arrangement and are verified against the pictures by
    -- scripts/check_geometry.py ("target picture == union of the pieces at these
    -- anchors").
    --
    -- ⚠️ ERR-021: these constants are **NOT** the success test any more.  Comparing
    --    each piece's anchor with the value below rejects every equivalent tiling:
    --    level 2 is four IDENTICAL 2x2 squares (24 equivalent placements, 1 accepted)
    --    and level 1's rectangle has 2 equivalent tilings (1 accepted), so a player
    --    who assembled the picture correctly was still told "wrong".
    --    puzzle_ctrl now compares the assembled picture (union of the pieces) with
    --    the target mask.  Solved offline by exhaustive search (.ref/solve_l1.py).
    constant L1_TGT0 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- (2,2)
    constant L1_TGT1 : std_logic_vector(7 downto 0) := "0011" & "0010";  -- (3,2)
    constant L1_TGT2 : std_logic_vector(7 downto 0) := "0100" & "0011";  -- (4,3)
    constant L1_TGT3 : std_logic_vector(7 downto 0) := "0000" & "0000";  -- unused

    -- Level-2 targets: the four 2x2 squares tile the 4x4 block at rows 2..5 x
    -- cols 2..5 as (2,2) (2,4) (4,2) (4,4).  (Any permutation of the four is an
    -- equally correct assembly -- see the ERR-021 note above.)
    constant L2_TGT0 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- (2,2)
    constant L2_TGT1 : std_logic_vector(7 downto 0) := "0010" & "0100";  -- (2,4)
    constant L2_TGT2 : std_logic_vector(7 downto 0) := "0100" & "0010";  -- (4,2)
    constant L2_TGT3 : std_logic_vector(7 downto 0) := "0100" & "0100";  -- (4,4)

    -- Result-picture masks shown at the end of a game (self-designed).
    --
    -- Requirement side (B9/B10): 拼图失败 → 点阵显示"失败图案"；第一关过关、第二关拼成
    -- → 点阵显示"胜利图案".  图案本身没有规定，要求只有一个：**一眼能看懂**。
    -- 自拟改进项 S5 还要求"闪示，便于远距离判读"。
    --
    -- WIN : **粗对勾**（成功）—— 24 格，笔画 3 格宽，从右上扫到左下、填满整屏。
    --       历史：最早是"1 格宽的细对勾"→ 上板反馈"勾不出形状、不直观"→ 改成黄色笑脸
    --       → 上板再看仍觉得"笑脸不够直观"→ 2026-10-09 用户拍板换回**对勾，但要粗**。
    --       为什么对勾最直观：✓ / ✗ 是"对/错"的通用符号，而**红色对勾**正是中国阅卷的
    --       "答对"记号，比笑脸更贴近直觉。
    --       ⚠️ 颜色：胜利与失败都点**红**列，两者靠**形状**区分（对勾 vs 叉）。
    --          想要更强的远距离对比，把 puzzle_top 的 S_WIN 分支改成只点绿列即可
    --          （那里注释写了改法）。
    --       ⚠️ 方向：对勾是**斜的、左右/上下都不对称**，所以它同时是 ERR-015
    --          （取行时把画面上下颠倒）的天然回归判据 —— scripts/check_geometry.py
    --          检查"最高行只出现在右半边、最低行只出现在左半边"，颠倒或镜像会立刻失败。
    --   ..............##   row0 = 0x80
    --   ............####   row1 = 0xC0
    --   ..........######   row2 = 0xE0
    --   ........######..   row3 = 0x70
    --   ##......####....   row4 = 0x31   <- 短臂起点（左）
    --   ####..####......   row5 = 0x1B
    --   ##########......   row6 = 0x1F   <- 两臂交汇
    --   ..######........   row7 = 0x0E   <- 顶点（左半边）
    constant WIN_MASK : std_logic_vector(63 downto 0) :=
        "0000111000011111000110110011000101110000111000001100000010000000";

    -- FAIL : a cross（红色；靠形状与胜利的粗对勾区分）
    constant FAIL_MASK : std_logic_vector(63 downto 0) :=
        "0000000011000011011001100011110000111100011001101100001100000000";

    -- Bounding-box limit of every piece: all pieces fit in 3x3
    constant PIECE_MAX_DIM : integer := 3;

    ----------------------------------------------------------------------------
    -- 4. Clock / timing constants
    --    Board clock is selected by the USER_BTN on the top-right corner and
    --    read from the FREQ LED row.  This design assumes the 50 MHz position.
    --    Counter chain is CASCADED on purpose: only the first stage ever sees
    --    50 MHz, the following stages just count pulses from the previous one.
    ----------------------------------------------------------------------------
    constant CLK_HZ  : integer := 50_000_000;

    -- stage 1 : 50 MHz -> 1 kHz   (divide by 50_000)
    constant CNT_1K  : integer := CLK_HZ / 1_000 - 1;
    -- stage 2 : 1 kHz  -> 200 Hz  (divide by 5)      : dot-matrix / keypad scan
    constant CNT_200 : integer := 1_000 / 200 - 1;
    -- stage 3 : 200 Hz -> 100 Hz  (divide by 2)      : 100 Hz time base
    constant CNT_100 : integer := 200 / 100 - 1;
    -- stage 4 : 100 Hz -> 2 Hz    (divide by 50)     : blink / self-test flash
    constant CNT_2HZ : integer := 100 / 2 - 1;
    -- stage 5 : 100 Hz -> 1 Hz    (divide by 100)    : second counter
    constant CNT_1HZ : integer := 100 / 1 - 1;

    -- power-on reset : count tick_1k pulses, so only a 4-bit counter is needed
    -- ⚠️ 实测（tb_clk_gen）：释放发生在 por_cnt 到达 CNT_POR 时，即 **9** 个 1 ms 刻度，
    --    不是 10 个（常量名 T_POR_MS 与计数差一）。功能上无害（9 ms 与 10 ms 对
    --    一个人机接口设计没有区别），因此保持与板上一致的行为，只更正了注释。
    constant T_POR_MS  : integer := 10;
    constant CNT_POR   : integer := T_POR_MS - 1;      -- 饱和值：计到它就释放

    -- reset push-button debounce (counts tick_1k = 1 ms)
    constant T_BTN_MS  : integer := 20;
    constant CNT_BTN   : integer := T_BTN_MS - 1;

    ----------------------------------------------------------------------------
    -- 5. Game timing (course requirement values, do not change casually)
    ----------------------------------------------------------------------------
    constant T_SELFTEST : integer := 2;    -- B1/B2 : self-test lasts 2 s
    constant T_PREVIEW  : integer := 5;    -- B4/B10: preview lasts 5 s
    constant T_LEVEL1   : integer := 30;   -- B5    : level-1 time limit 30 s
    constant T_LEVEL2   : integer := 40;   -- B10   : level-2 time limit 40 s

    ----------------------------------------------------------------------------
    -- 6. Misc
    ----------------------------------------------------------------------------
    -- key debounce, counted in 200 Hz scan rounds -> 16 rounds = 80 ms
    constant DEBOUNCE_MAX : integer := 15;

    -- LFSR seed : must NEVER be all zero (all-zero is the absorbing state)
    constant SEED_DEFAULT : std_logic_vector(7 downto 0) := x"5A";

    ----------------------------------------------------------------------------
    -- 7. State encoding of the master FSM (3 bits, 6 states)
    ----------------------------------------------------------------------------
    subtype state_t is std_logic_vector(2 downto 0);

    constant S_SELF_TEST : state_t := "000";
    constant S_IDLE      : state_t := "001";
    constant S_PREVIEW   : state_t := "010";
    constant S_PLAYING   : state_t := "011";
    constant S_WIN       : state_t := "100";
    constant S_FAIL      : state_t := "101";

    ----------------------------------------------------------------------------
    -- 8. Key codes produced by keypad_scan (0 = no key)
    ----------------------------------------------------------------------------
    constant K_NONE    : std_logic_vector(3 downto 0) := "0000";
    constant K_START   : std_logic_vector(3 downto 0) := "0001";  -- "start"
    constant K_SELECT  : std_logic_vector(3 downto 0) := "0010";  -- "select"
    constant K_CONFIRM : std_logic_vector(3 downto 0) := "0011";  -- "confirm"
    constant K_UP      : std_logic_vector(3 downto 0) := "0100";  -- "up"
    constant K_DOWN    : std_logic_vector(3 downto 0) := "0101";  -- "down"
    constant K_LEFT    : std_logic_vector(3 downto 0) := "0110";  -- "left"
    constant K_RIGHT   : std_logic_vector(3 downto 0) := "0111";  -- "right"

    ----------------------------------------------------------------------------
    -- 9. DISP 字位码：disp_format 往 i_data 里放的 4 位码 == seg_scan 的译码输入
    --
    --   0x0..0x9 = 数字（BCD），0xF = 灭，**0xA..0xE = 结算画面用的字母**
    --   （2026-10-08 由用户拍板：胜利显示 "PASS"、失败显示 "FAIL"；此前是随意挑的
    --     "75"/"00"，被问"75 是什么意思"时无法自解释）。
    --
    --   ⚠️ 7 段管的固有限制（必须如实写进报告，不是 bug）：
    --      · 'S' 与 '5' 的段完全一样 → "PASS" 看上去像 "PA55"；
    --      · 'I' 只能用 "1" 的形状 → "FAIL" 看上去像 "FA1L"。
    --      结算时点阵上同时给出笑脸/叉，语境下判读不受影响。
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

    -- Convert an absolute cell (row, col) into the display pixel mask.
    -- The display mask uses the SAME bit convention (bit 8*row + col, bit0 =
    -- top-left), so this is a one-hot encode.  It exists as a function so that
    -- no module ever hand-writes a mask literal for a single cell.
    function mask_to_px(row : integer; col : integer) return std_logic_vector is
        variable v : std_logic_vector(63 downto 0) := (others => '0');
    begin
        if (row >= 0) and (row <= 7) and (col >= 0) and (col <= 7) then
            v(8 * row + col) := '1';
        end if;
        return v;
    end function;

    -- Move every '1' in m by (dr, dc) cells.  Anything pushed outside the 8x8
    -- field is DROPPED, which is what requirement B7 ("a piece may not leave the
    -- 8x8 area") relies on: the caller can test for loss instead of having to
    -- pre-clamp, and a naive whole-vector "sll" can never leak a cell from the
    -- end of one row into the start of the next.
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

    -- Shift one 8-bit row RIGHT (towards higher column numbers) by dc columns,
    -- filling the vacated left end with '0'.
    --
    -- ⚠️ ERR-019: the FIRST version of this function wrote
    --        v := '0' & r(7 downto 1)
    --    which moves every bit from index i+1 down to index i -- i.e. towards
    --    LOWER indices, which in this project's convention (bit = 8*row + col,
    --    bit0 = left-most column) is a shift to the LEFT.  Placing a piece at
    --    anchor column ac needs the row to move RIGHT by ac, so every piece with
    --    ac > 0 was drawn at the wrong columns and lost cells off the left edge
    --    (a 1x3 bar at anchor column 2 rendered as a single dot at column 0).
    --    The same function feeds the overlap checker, so the collision test was
    --    wrong too.  Caught by simulation (tb_puzzle_ctrl assertion ⑧: the
    --    selected piece rendered nothing at all); see docs/06.
    --
    --    Written as a 7-way mux tree over dc, NOT as a per-bit indexed loop:
    --    the indexed form made Quartus build an adder-compare-select network per
    --    bit, which was the critical path (41.5 MHz instead of 50+).
    function srl8(r : std_logic_vector(7 downto 0); dc : integer)
        return std_logic_vector is
        variable rb, sb, v : std_logic_vector(7 downto 0);
    begin
        -- ⚠️ 面积与方向都要照顾到（这一条是实测出来的，不是推理）：
        --   直接写成 `v := r(6 downto 0) & '0'` 虽然方向对，却让 fitter 从
        --   958 LE 涨到 1201 LE —— 因为"往位号大的方向移"会把零片形状里
        --   **低列**的格子搬到高列，综合器再也没法把 ac≥3 的那几路常量折叠掉；
        --   反过来写成"往位号小的方向移"时，形状格子很快被移出边界，整片逻辑
        --   被剪掉一大半。
        --   所以这里走一个**等价改写**：先按位倒序（纯走线，零逻辑）→ 用便宜的
        --   左移形式 → 再倒序回来。数学上 v(j) = rb_shift(...) 的倒序 =
        --   原方向右移 dc： v(j) = r(j - dc)。实测回到 967 LE。
        rb := r(0) & r(1) & r(2) & r(3) & r(4) & r(5) & r(6) & r(7);
        case dc is
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
        -- NOTE: 'base' is initialised and every branch assigns it, because a
        -- subprogram is ELABORATED AT COMPILE TIME: a branch that can produce no
        -- value makes Quartus fail with "expression has 0 elements" instead of
        -- inferring a latch.
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

end package body puzzle_pkg;
