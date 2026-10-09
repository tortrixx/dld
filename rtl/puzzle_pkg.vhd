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
    --   VERIFIED to equal the union of the four L2 pieces at their witness
    --   anchors (scripts/check_geometry.py enumerates every exact tiling).
    --   An earlier literal put the square at rows 3..6 while the piece targets
    --   were at rows 2..5, so the red ghost was drawn one row below where the
    --   puzzle had to be assembled -- the player following the ghost could never
    --   match it.
    --
    -- ⚠️ 2026-10-09：这个常量**降级成"图案库的第 0 幅"**（提高要求 A2 / 自拟 S1
    --    "多种拼图图案随机选择"）。它本身**一字未改**（仍然 = 4x4 实心方块），
    --    仍叫 L2_TARGET_MASK 以便既有证据（整机 puzzle_top 的 ⑬、check_geometry
    --    的旧检查）继续有效；新名字是 L2_PAT0，实际图案库见下面「第二关图案库」。
    constant L2_TARGET_MASK : std_logic_vector(63 downto 0) :=
        "0000000000000000001111000011110000111100001111000000000000000000";

    ----------------------------------------------------------------------------
    -- 第二关 = **四块自拟异形零片的"七巧板"** + 4 幅图案库
    --          （A2 / S1；2026-10-09 第 11 工作阶段重做形状）
    --
    -- 【为什么重做】原实现第二关零片是**四块一模一样的 2x2 方块**，图案库也只能是
    --   "4x4 块网格上恰好 4 个 2x2 块"的四种放大方块。用户上板后直接问：
    --   "第二关 4 幅图案库为什么只能是 2x2 的零片来做，也可以使用其他形状吧"——
    --   而题目 B10 原文只要求"四块零片、零片图案自拟、位置随机、不能重叠"，
    --   **零片形状完全自拟**，没有任何"必须是方块"的约束。原实现是自缚手脚。
    --
    -- 【现在怎么做】四块零片 = 三种大小、四种形状（共 16 格）；图案库 = 四幅
    --   **用这四块零片恰好铺满**的、肉眼可辨的轮廓（"七巧板"玩法）：
    --
    --     Q0  1x3 横条    3 格        Q1  1x2 竖条    2 格
    --     ###                          #        （竖着放 2 格）
    --                                  #
    --     Q2  J 形 5 格               Q3  六格块      6 格
    --     ###                          #..
    --     ..#                          ###
    --     ..#                          .##
    --
    --   图案（每幅 = 上面四块的**平移**拼装；四幅互不相同）：
    --     PAT0 田   4x4 实心方块（**与原实现一字未改** → ERR-021/023 旧证据继续有效）
    --     PAT1 十   胖十字（4 行 x 5 列）
    --     PAT2 S/Z  锯齿（4 行 x 6 列）
    --     PAT3 阶梯 阶梯形（4 行 x 5 列）
    --
    -- 【可解性（死局防线）】零片**只能平移、不能旋转**（A4 明确不做），所以
    --   "恰好铺满"必须逐幅**穷举**验证：scripts/check_geometry.py 对每幅图案枚举
    --   四块零片的所有平移摆位（不信任这里的手算），要求存在恰好覆盖的解。
    --   实测：PAT0/PAT1/PAT2 各 **1 种**铺法、PAT3 **2 种**（见 docs/02 §9.2）。
    --   ⚠️ PAT0 从原实现的"4! = 24 种等价摆法"变成"1 种"：玩法从"随便填满方块"
    --      升级成真的要**拼出**轮廓。40 秒够用：散落最大位移 14 步、平均约 9 步/块。
    --
    -- 【面积账】零片与图案仍然全是**编译期常量**：piece_rom 0 LE、pattern_rom 4 LE
    --   与改版前**逐位相同** —— 换成异形零片没多花一个 LE（"装不下"的不是这里）。
    --
    -- 【选取点】每次进入 S_PREVIEW（按【开始】开局、或过关进入下一关）那**晚一拍**锁存：
    --     · **第二关**（level='1' 且 lvl3='0'）→ 恒锁 `L2_FIXED_PAT`（PAT3 阶梯，固定）
    --     · **第三关**（lvl3='1'，A2 新增）  → 锁 rng_lfsr 低 2 位 → 四幅里随机选
    --   第一关按 B4 恒为图 4-1（pattern_rom 在 level='0' 时忽略 i_pat）。
    --   ⚠️ 2026-10-09 之前是"每局第二关都随机"；现在是"第二关固定、第三关随机"，
    --      原因见上面 L2_FIXED_PAT 的说明。
    ----------------------------------------------------------------------------
    constant L2_PAT0 : std_logic_vector(63 downto 0) :=
        "0000000000000000001111000011110000111100001111000000000000000000";  -- 田（= 原图案）
    constant L2_PAT1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000111000011111000111110000111000000000000000000";  -- 十（胖十字）
    constant L2_PAT2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000111100111100001111000000111100000000000000000";  -- S/Z 锯齿
    constant L2_PAT3 : std_logic_vector(63 downto 0) :=
        "0000000000000000001110000011110000111110000111100000000000000000";  -- 阶梯

    -- 图案库：pat_sel 的 2 位正好 4 幅（不要超过 4：pat_sel 只有 2 位）
    type pat_arr_t is array (0 to 3) of std_logic_vector(63 downto 0);
    constant L2_PATS : pat_arr_t := (L2_PAT0, L2_PAT1, L2_PAT2, L2_PAT3);
    constant L2_PAT_N : integer := 4;

    -- ⚠️ 2026-10-09（用户拍板，第 12 工作阶段 / D2 设计）：**第二关图案改成固定**，
    --   不再每局随机；"多种图案随机选择"移到**新增的第三关**。
    --
    -- 【为什么改】B10 只说"完整拼图图案自拟"（= 由设计者自己定，不是题目指定），
    --   而"**多种拼图图案随机选择**"是**提高要求 2**里的内容，且与"**增加游戏关数**"
    --   写在同一条里。把随机图案放在**基本要求**的第二关上，等于把加分项提前用掉，
    --   而"增加关数"那一半一直欠账（旧文档如实记为"A2 只做了一半"）。新口径：
    --       第一关 = 图 4-1（B4 指定，固定）
    --       第二关 = **本常量指定的这一幅**（自拟但固定，与第一关同等对待 → B10 字面）
    --       第三关 = 从 L2_PATS 四幅里**随机选**（A2：增加关数 + 多种图案随机选择，见
    --                rtl/game_fsm.vhd 的 lvl3 与 rtl/puzzle_top.vhd 的 pat_sel 锁存）
    --
    -- 【为什么选 PAT3 阶梯，而不是原来的 4x4 田】
    --   ① 用户明确要求"第二关的固定图案不要用原来的 4x4"；
    --   ② PAT3 是四幅里**唯一有 2 种**等价铺法的图案（PAT0/PAT1/PAT2 各只有 1 种），
    --      于是 ERR-021 的"看画面判成败"回归用例**就落在基本要求的正常流程里** ——
    --      第二关无论玩家拼成两种等价铺法中的哪一种，都必须判成功（不再只在仿真里跑）。
    --      ⚠️ 这也意味着第二关比"唯一铺法"稍宽容：这是有意的（难度阶梯 = 第二关稍易、
    --         第三关随图案 0/1/2 最难）。
    constant L2_FIXED_PAT : std_logic_vector(1 downto 0) := "11";   -- 3 == L2_PAT3（阶梯）

    -- 第二关四块零片：3 + 2 + 5 + 6 = 16 格（== 每幅图案的 16 格）
    --   （相对形状：bit = 8*行 + 列，行 0 在最低 8 位；与第一关零片同一约定）
    constant L2_P0 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000000000000111";  -- Q0 1x3 横条 3 格
    constant L2_P1 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000000000000000100000001";  -- Q1 1x2 竖条 2 格
    constant L2_P2 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000001000000010000000111";  -- Q2 J 形 5 格
    constant L2_P3 : std_logic_vector(63 downto 0) :=
        "0000000000000000000000000000000000000000000001100000011100000001";  -- Q3 六格块 6 格

    -- Target anchors: where each piece is EXPECTED to end up.  They describe a
    -- WITNESS arrangement and are verified against the pictures by
    -- scripts/check_geometry.py (which enumerates every exact tiling).
    --
    -- ⚠️ ERR-021: these constants are **NOT** the success test any more.  Comparing
    --    each piece's anchor with the value below rejects every equivalent tiling:
    --    level 2 used to be four IDENTICAL 2x2 squares (24 equivalent placements, 1
    --    accepted) and level 1's rectangle has 2 equivalent tilings (1 accepted), so a
    --    player who assembled the picture correctly was still told "wrong".
    --    puzzle_ctrl compares the assembled picture (union of the pieces) with the
    --    target mask.  Solved offline by exhaustive search (.ref/solve_l1.py).
    constant L1_TGT0 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- (2,2)
    constant L1_TGT1 : std_logic_vector(7 downto 0) := "0011" & "0010";  -- (3,2)
    constant L1_TGT2 : std_logic_vector(7 downto 0) := "0100" & "0011";  -- (4,3)
    constant L1_TGT3 : std_logic_vector(7 downto 0) := "0000" & "0000";  -- unused

    -- Level-2 witness: the four self-designed pieces tile PAT0 (the 4x4 square,
    -- rows 2..5 x cols 2..5) exactly as (5,3) (4,2) (2,3) (2,2) for Q0..Q3.
    --   PAT0's tiling is UNIQUE (check_geometry.py enumerates it), so this witness
    --   set == the only solution; tb_piece_rom ⑧ checks that.
    constant L2_TGT0 : std_logic_vector(7 downto 0) := "0101" & "0011";  -- Q0 @ (5,3)
    constant L2_TGT1 : std_logic_vector(7 downto 0) := "0100" & "0010";  -- Q1 @ (4,2)
    constant L2_TGT2 : std_logic_vector(7 downto 0) := "0010" & "0011";  -- Q2 @ (2,3)
    constant L2_TGT3 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- Q3 @ (2,2)

    -- ⚠️ 2026-10-09（D2）：第二关的**固定图案**现在换成了 PAT3（阶梯，见 L2_FIXED_PAT），
    --   所以它的见证铺法也要有常量（check_geometry.py 用它核对"文档里的锚点 == 穷举
    --   出来的第 0 种铺法"）。PAT3 有 **2 种**铺法，这里是第 0 种；第 1 种由
    --   scripts/check_geometry.py 打印，并由 scripts/check_plans.py 复核
    --   "两种铺法都必须判成功"（ERR-021 回归）。
    --   L2_TGT0..3（上面那组）保留不动：它们描述的是**图案库第 0 幅（田）**的唯一铺法，
    --   现在那一幅只出现在**第三关的随机池**里，旧证据（ERR-021/023）继续有效。
    constant L2_PAT3_TGT0 : std_logic_vector(7 downto 0) := "0010" & "0010";  -- Q0 @ (2,2)
    constant L2_PAT3_TGT1 : std_logic_vector(7 downto 0) := "0010" & "0001";  -- Q1 @ (2,1)
    constant L2_PAT3_TGT2 : std_logic_vector(7 downto 0) := "0011" & "0011";  -- Q2 @ (3,3)
    constant L2_PAT3_TGT3 : std_logic_vector(7 downto 0) := "0011" & "0010";  -- Q3 @ (3,2)

    -- Result-picture masks shown at the end of a game (self-designed).
    --
    -- Requirement side (B9/B10): 拼图失败 → 点阵显示"失败图案"；第一关过关、第二关拼成
    -- → 点阵显示"胜利图案".  图案本身没有规定，要求只有一个：**一眼能看懂**。
    -- 自拟改进项 S5 还要求"闪示，便于远距离判读"。
    --
    -- WIN : **粗对勾**（成功）—— 24 格，笔画 3 格宽，从右上扫到左下、填满整屏。
    --       历史：最早是"1 格宽的细对勾"→ 上板反馈"勾不出形状、不直观"→ 改成黄色笑脸
    --       → 上板再看仍觉得"笑脸不够直观"→ 2026-10-09 换回**粗对勾**
    --       → 2026-10-09 用户再拍板：**只点绿列**，做成"绿对勾 / 红叉"的交通灯配色。
    --       为什么对勾最直观：✓ / ✗ 是"对/错"的通用符号。
    --       ⚠️ 颜色：胜利 = **绿**（只点绿列）、失败 = **红**（只点红列），互为反色，
    --          颜色本身就是判读线索（交通灯：绿=通过、红=不通过）；
    --          形状（对勾 vs 叉）作为第二重线索。改法在 puzzle_top 的 S_WIN 分支。
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

    -- FAIL : a cross（红色；与绿色的胜利对勾互为反色 —— 交通灯配色）
    constant FAIL_MASK : std_logic_vector(63 downto 0) :=
        "0000000011000011011001100011110000111100011001101100001100000000";

    -- Bounding-box limit of every piece: all pieces (level 1 and level 2, the new
    -- self-designed level-2 shapes included) fit in a 3x3 box.  This is what lets
    -- the engine scan a 3x3 neighbourhood instead of the whole panel, and it is
    -- also the precondition of the scatter's bounded-candidate arithmetic.
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
    -- ⚠️ stage 6 : 100 Hz -> **4 Hz**（divide by 25，= 250 ms 一个脉冲）
    --    2026-10-09 第 11 工作阶段（全项目审计发现，ERR-038）：B1 要求自检"以 **2 Hz**
    --    闪烁"。原来的做法是"每个 tick_2hz（500 ms）翻转一次 blink_r"，得到的是
    --    **1 s 周期 = 1 Hz** 的方波 —— 只有要求的一半，而且四处注释/文档都按 2 Hz 记账
    --    （与 ERR-031 同类的"2 倍算错"）。2 Hz 方波需要**每 250 ms 翻转一次**，
    --    所以这里加一路 4 Hz 节拍：game_fsm 在它上面翻转 → 真正的 2 Hz、50% 占空。
    --    tick_2hz 继续保留（蜂鸣器节奏、旧断言都用它），语义不再当"闪烁"。
    constant CNT_4HZ : integer := 100 / 4 - 1;

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
    -- 第三关（A2"增加游戏关数"的扩展关，2026-10-09）：题目**没有规定**，自拟。
    -- 与第二关同为 40 s：零片、图案库完全一样，唯一区别是图案**从四幅里随机选**。
    constant T_LEVEL3   : integer := 40;   -- A2    : level-3 time limit 40 s（自拟）

    ----------------------------------------------------------------------------
    -- 6. Misc
    ----------------------------------------------------------------------------
    -- Key debounce, counted in **scan rounds** of keypad_scan.
    --
    -- ⚠️ 2026-10-09 更正（ERR-031）：**一轮扫描 = 2 个 tick_200 = 10 ms，不是 5 ms。**
    --    keypad_scan 的相序是 SC_ALL_HIGH（等 tick）→ SC_ALL_LOW（**再等一个 tick**）
    --    → SC_SETTLE（64 拍）→ SC_RELEASE（相 0 是 1 拍 + 相 1/2/3 各 64 拍 = 193 拍；
    --      审计注：相 0 只有 1 拍是 `settle` 没在离开 SC_SETTLE 时清零造成的，
    --      功能上无害——采样恰好落在相切换那一拍，列 0 仍能被识别（ERR-039b 记录，未改））
    --      → 回 SC_ALL_HIGH；两个等待相
    --    各吃一个 200 Hz 周期，所以**消抖级每 10 ms 才采一个样**。仿真测试台独立
    --    按相序推出同样的结论（sim/tb_keypad_scan.py："一轮扫描 = 2 个 tick"）。
    --    旧注释/文档写"16 轮 = 80 ms"是把这个 2 倍算漏了：真实值是 **160 ms** ——
    --    按一下要 160 ms 才被接受、松开也要 160 ms 才被接受，手感明显迟钝
    --    （用户 2026-10-09 上板反馈"防抖时间有点长"）。
    --
    -- 现值 = DEBOUNCE_MAX+1 = **4 轮 = 40 ms**：按下后 4 个连续"干净"采样（40 ms
    --    连续一致读数、**样与样相隔 10 ms**）才改 stable（所以 4 个样横跨 30 ms，
    --    "按下 → 接受"才是 4 轮 = 40 ms）；脉冲本身还要**再晚一个采样拍**（RTL 里脉冲判定
    --    读的是同拍旧值），再算上打键落点相对扫描相位最多 10 ms 的抖动，
    --    **按下 → o_press 实测约 45 ms**（原来 16 轮 = 165 ms），松开同样约 50 ms；
    --    连按可达 ~12 次/秒（原来 ~3 次/秒）。证据：sim/tb_keypad_scan.py ⑨
    --    （实测 o_press 在 9T、o_release 在 63T；T = 8 us 仿真 = 5 ms 板上）。
    --    40 ms 的确认窗口对廉价矩阵键盘的接触抖动（典型几 ms）仍很宽裕。
    --    ⚠️ 改这个常量必须同步改 sim/tb_puzzle_top.py 的 DB_ROUNDS（按键计划按轮排期）
    --       与 sim/tb_keypad_scan.py 的断言 ⑨。
    constant DEBOUNCE_MAX : integer := 3;

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
