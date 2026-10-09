-- ============================================================================
--  puzzle_ctrl  --  placement / movement / locking / colouring engine
--  Subsystem : S4 (puzzle core).  Owns everything spatial; holds no game timing.
--
--  ---------------------------------------------------------------------------
--  ARCHITECTURE: ROW-SCAN RENDERER  (why this file is shaped this way)
--  ---------------------------------------------------------------------------
--  The EPM1270 has 1270 logic cells and this module must share them with ten
--  others.  Four earlier versions were BUILT AND MEASURED, not guessed:
--
--    v1  64-bit variable-distance shift per piece               -> 4690 cells
--    v2  8-bit row shift via a per-row CASE helper              -> 2969 cells
--    v3  loops with variable-indexed array reads                -> 2995 cells
--    v4  fixed-shift 64-bit footprint registers + render mux    -> 2350 cells
--        measured breakdown: 504 registers, 1717 LUT-only cells
--
--  The measurements showed the cost is not one bad statement but the element of
--  holding 64-bit per-piece footprints at all: answering "does this piece cover
--  row r column c" needs an 8-bit AND, yet the 64-bit version materialises the
--  whole mask to get there.
--
--  v5 therefore renders ONE ROW PER SCAN TICK.  That costs nothing extra -- the
--  dot-matrix driver already scans one row at a time -- so the engine simply
--  computes the row the driver is about to display.  Every colour decision is
--  8 bits wide and the frame is produced over 8 ticks, i.e. the refresh period.
--
--  ⚠️ 审计更正（2026-10-09 第 11 工作阶段）：这一段原来写 "Nothing 64-bit is stored.
--     State: four piece anchors (8 bits each) + four locked flags." —— **是错的**：
--     引擎内部有 frame_r/frame_g（各 64 位，共 128 个触发器）以及 chk_shp(64)、
--     pos_frm(32)、chk_orow/chk_prow 等（本模块 FF 约 345 个，见 docs/02 §4）。
--     真实成立的说法是：**每一拍的组合计算路径只有 8 位宽**（一拍只算一行的
--     row_mask 并把它并进帧），这才是"引擎能塞进 EPM1270"的原因；64 位的帧寄存器
--     仍然存在，而且顶层就是靠它按 mrow 切片的（ERR-027 之后扫描 125 Hz、内容 25 Hz
--     不同源也不会错行）。
--
--  Bit convention (shared with puzzle_pkg):
--      bit index = 8*row + col,  bit 0 = TOP-LEFT cell
--      DOWN (row+1) = higher bit indices, RIGHT (col+1) = higher bits in a row
--      a packed anchor is row(3:0) & col(3:0)
--
--  Colours (B6 / B8): selected -> GREEN, locked -> YELLOW (red AND green), and
--  any remaining target-picture cell -> RED ghost.
--
--  Bounds and overlap (B7 / B5): a move is accepted only if the new anchor keeps
--  the shape inside the 8x8 field AND the pieces do not share a cell.  The
--  overlap test is EXACT (row masks ANDed), not a bounding box: a bounding box
--  would reject legal moves of the cross and of the L-tromino in level 1.
--
--  Success (B9) is decided on the ASSEMBLED PICTURE, not on piece identities:
--  o_solved rises when the union of the pieces equals i_target AND every piece is
--  locked.  See the ERR-021 note at the signal declarations -- comparing anchor
--  numbers against hardcoded targets made equivalent tilings fail.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity puzzle_ctrl is
    port (
        i_clk     : in  std_logic;
        i_rst     : in  std_logic;
        i_tick    : in  std_logic;                      -- 行渲染节拍：顶层给 **200 Hz**
                                                        -- （画面内容 25 Hz 更新；**扫描**在
                                                        -- 顶层另走 1 kHz → 125 Hz，见下）
        rnd_step  : out std_logic;
        rnd_val   : in  std_logic_vector(7 downto 0);
        i_level   : in  std_logic;                      -- '0' level 1, '1' level 2/3
                                                        -- （⚠️ D2 起是三关：第二关与
                                                        --   第三关共用 '1' —— 本模块只关心
                                                        --   "三块还是四块"，关口编号由
                                                        --   game_fsm 的 lvl3 负责）
        i_pat     : in  std_logic_vector(1 downto 0);   -- 图案库下标（A2/S1）：
                                                        -- 与 i_level 一起决定 i_target
                                                        -- （顶层 pattern_rom 按 (level,pat)
                                                        --  选图案）；只用于"整帧判据是否
                                                        -- 干净"的快照比较，见下方注释
        i_sh0     : in  std_logic_vector(63 downto 0);
        i_sh1     : in  std_logic_vector(63 downto 0);
        i_sh2     : in  std_logic_vector(63 downto 0);
        i_sh3     : in  std_logic_vector(63 downto 0);
        i_h0      : in  std_logic_vector(2 downto 0);
        i_h1      : in  std_logic_vector(2 downto 0);
        i_h2      : in  std_logic_vector(2 downto 0);
        i_h3      : in  std_logic_vector(2 downto 0);
        i_w0      : in  std_logic_vector(2 downto 0);
        i_w1      : in  std_logic_vector(2 downto 0);
        i_w2      : in  std_logic_vector(2 downto 0);
        i_w3      : in  std_logic_vector(2 downto 0);
        i_target  : in  std_logic_vector(63 downto 0);
        i_go      : in  std_logic;
        i_select  : in  std_logic;
        i_move    : in  std_logic;
        i_confirm : in  std_logic;
        i_up      : in  std_logic;
        i_down    : in  std_logic;
        i_left    : in  std_logic;
        i_right   : in  std_logic;
        o_solved  : out std_logic;
        o_all_lock: out std_logic;
        o_busy    : out std_logic;
        o_sel_idx : out std_logic_vector(1 downto 0);
        o_pos     : out std_logic_vector(31 downto 0);
        o_lock    : out std_logic_vector(3 downto 0);
        o_scanrow : out std_logic_vector(2 downto 0);
        o_rowr    : out std_logic_vector(63 downto 0);  -- red   frame
        o_rowg    : out std_logic_vector(63 downto 0)   -- green frame
    );
end entity puzzle_ctrl;

architecture rtl of puzzle_ctrl is

    ----------------------------------------------------------------------------
    -- EXACT overlap test helper.
    --
    -- The shapes are NOT all rectangles (level 1 uses a cross and an L-tromino),
    -- so intersecting bounding boxes would reject legal moves.  This returns the
    -- 8 bits a piece contributes to ONE panel row; the caller ANDs the candidate
    -- row against the other pieces' rows.
    --
    -- Deliberately a small single-purpose function: an earlier version took four
    -- (anchor, shape) pairs and looped over eight rows inside, which made every
    -- call site replicate 32 evaluations and cost ~1500 logic cells.
    --
    -- ar/ac are the piece anchor, row the panel row, sr the piece's own row.
    -- All indices are guaranteed in range by the caller's guards, because a
    -- subprogram is elaborated at compile time.
    ----------------------------------------------------------------------------
    function row_mask(shp : std_logic_vector(63 downto 0);
                      sr  : integer;
                      ac  : integer) return std_logic_vector is
        variable base : std_logic_vector(7 downto 0) := (others => '0');
    begin
        if (sr = 0) then
            base := shp(7 downto 0);
        elsif (sr = 1) then
            base := shp(15 downto 8);
        elsif (sr = 2) then
            base := shp(23 downto 16);
        else
            base := (others => '0');
        end if;
        return srl8(base, ac);
    end function;

    ----------------------------------------------------------------------------
    -- ⚠️ ERR-035（2026-10-09 第 11 工作阶段，全项目审计发现）：B8 原文是"零片移到合适
    --    位置后按【确认】键变为黄色显示，同时**不可再选择及移动**"。
    --    "不可移动"早就挡住了（移动路径要求 `locked(sel)='0'`），但"**不可再选择**"
    --    没有实现：`sel` 照旧循环，转回已锁定的零片时渲染器把它的红列灭掉（把它并进
    --    selrow → 只亮绿）→ 玩家看到**黄块变绿**，直接违反 B8 的可见语义。
    --    修法：选择/确认推进 `sel` 时**跳过已锁定的零片**（全锁时停在原处）。
    --    另外渲染器也加了一道防御（不把已锁定零片当"选中的"着色），两处一起保证
    --    "锁定 = 黄且不可选中"这条不变量。
    ----------------------------------------------------------------------------
    function next_unlocked(cur  : unsigned(1 downto 0);
                           lk   : std_logic_vector(3 downto 0);
                           lvl2 : boolean) return unsigned is
        variable n   : integer;
        variable top : integer;
    begin
        if lvl2 then top := 4; else top := 3; end if;
        n := to_integer(cur);
        for i in 1 to 4 loop
            n := n + 1;
            if (n >= top) then n := 0; end if;
            if (lk(n) = '0') then
                return to_unsigned(n, 2);
            end if;
        end loop;
        return cur;                          -- 全部已锁定：停在原处
    end function;

    signal pos    : std_logic_vector(31 downto 0) := (others => '0');
    signal locked : std_logic_vector(3 downto 0)  := (others => '0');
    signal sel    : unsigned(1 downto 0) := (others => '0');
    signal sel_p  : std_logic_vector(7 downto 0);

    type sh_t is (SH_IDLE, SH_TRY, SH_CHK, SH_NEXT, SH_DONE);
    type chk_t is (CH_IDLE, CH_RUN, CH_DONE);
    signal chk      : chk_t := CH_IDLE;
    signal chk_kind : std_logic := '0';
    signal chk_row  : unsigned(3 downto 0) := (others => '0');
    signal chk_hit  : std_logic := '0';
    signal chk_pos  : std_logic_vector(7 downto 0) := (others => '0');
    signal chk_shp  : std_logic_vector(63 downto 0) := (others => '0');
    signal chk_h    : std_logic_vector(2 downto 0) := (others => '0');
    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');
    signal chk_orow : unsigned(3 downto 0) := (others => '0');  -- pipelined row index
    -- Panel row that chk_orow was derived from.  chk_orow is registered, so the
    -- candidate's own row arrives one cycle late; the other pieces MUST be
    -- compared at that same (older) panel row, otherwise the exact overlap test
    -- compares the candidate's row r against the neighbours' row r+1 and both
    -- misses real overlaps and rejects legal moves (see ERR-016).
    signal chk_prow : unsigned(3 downto 0) := (others => '0');
    -- pending move proposal (pipelined so the clamp + bounds test is not
    -- chained after the anchor select in the same clock)
    signal mv_pend  : std_logic := '0';
    signal mv_anchor: std_logic_vector(7 downto 0) := (others => '0');
    signal mv_dir   : std_logic_vector(3 downto 0) := (others => '0');
    -- ERR-033b：移动校验再拆一拍（夹紧后的锚点 + 当时选中的槽都先落寄存器）
    signal mv_clamp : std_logic_vector(7 downto 0) := (others => '0');
    signal mv_sel   : unsigned(1 downto 0) := (others => '0');
    signal mv_go    : std_logic := '0';
    -- registered scatter operands (pipelining -- see the header note)
    signal sc_hh    : std_logic_vector(2 downto 0) := (others => '0');
    signal sc_ww    : std_logic_vector(2 downto 0) := (others => '0');
    signal sc_cand  : std_logic_vector(7 downto 0) := (others => '0');
    signal sc_ok    : std_logic := '0';
    signal sh     : sh_t := SH_IDLE;
    signal sh_k   : unsigned(1 downto 0) := (others => '0');
    signal sh_att : unsigned(3 downto 0) := (others => '0');

    signal mv     : std_logic := '0';
    signal alllock_r : std_logic;

    signal scanrow : unsigned(2 downto 0) := (others => '0');  -- row being scanned
    signal frow    : unsigned(2 downto 0) := (others => '0');  -- row being built
    signal frame_r : std_logic_vector(63 downto 0) := (others => '0');
    signal frame_g : std_logic_vector(63 downto 0) := (others => '0');

    -- ERR-033（2026-10-09 第 11 工作阶段）：行渲染的**两拍流水**中间寄存器。
    -- 第一拍（下面的渲染进程）只算"这一行"（red_a/grn_a/bad_a + 行号 row_a），
    -- 第二拍（紧随其后的进程）才把这一行并进 frame 并跑整帧判据协议。
    signal row_a  : unsigned(2 downto 0) := (others => '0');
    signal red_a  : std_logic_vector(7 downto 0) := (others => '0');
    signal grn_a  : std_logic_vector(7 downto 0) := (others => '0');
    signal bad_a  : std_logic := '0';

    ----------------------------------------------------------------------------
    -- ⚠️ ERR-021 : 成功判据 = 「**拼出来的画面** == 目标图案」
    --
    -- 要求 B9 的原话是"位置和形状与初始拼图一致"，H8 把它读成"零片要拼回原图案"，
    -- 也就是**玩家看到的那幅画面**必须等于目标图案。而最初的实现比的是
    -- "第 k 块的锚点 == 写死的 L*_TGT[k]"，这是一个**过强**的判据：零片只要形状
    -- 允许，同"一幅画面"可以有多种等价摆法，玩家无从分辨该把哪一块放到哪里。
    --
    -- 实测（tb_puzzle_ctrl 断言 ⑭，修复前 r10 复现）：
    --   · 第二关四块是**完全相同**的 2x2 方块，填满 4x4 方块的摆法有 4! = 24 种，
    --     画面逐格都一样，而锚点判据只认其中 1 种 → 拼对了按"确认"仍然出叉；
    --   · 第一关的 4x3 矩形也有 2 种等价铺法（.ref/solve_l1.py 早就数出来过，
    --     但当时只当成"可解性通过"，没意识到另一条铺法会被误判）→ 命中率只有 1/2。
    --
    -- 修法：不给零片编号，直接比**并集**。渲染器本来就一拍算一行的
    -- "本行被零片覆盖的格子"（cov）和"目标图案本行的格子"（tgtrow），所以
    -- "8 行的 cov 都等于 tgtrow"就等价于"零片并集 == 目标图案"，判定几乎不花面积。
    --
    -- 只在**整帧画完**时发布判据，而且要求这一帧里 pos/level 没变过
    -- （pos_frm/lvl_frm 快照）：否则一帧可能混着两种摆法的行，把错的看成对的。
    signal frm_bad   : std_logic := '0';      -- 当前帧出现过行不匹配
    signal frm_ok    : std_logic := '0';      -- 上一整帧（且未被扰动）并集 == 目标
    signal frm_valid : std_logic := '0';      -- 上一整帧是"干净"的一帧（判据可用）
    signal pos_frm   : std_logic_vector(31 downto 0) := (others => '0');
    signal lvl_frm   : std_logic := '0';
    -- ⚠️ 2026-10-09（A2/S1）：i_target 现在由 (i_level, i_pat) 一起决定，所以"本帧干净"
    --    的快照必须**同时**跟踪 pat —— 只跟踪 level 的话，图案库切换（开局那一拍）
    --    可能让一帧里混着两幅图案的行，判据就不可信了。成本只有 2 个寄存器 + 比较。
    -- ⚠️ 2026-10-09（D2 三关）：**第二关→第三关时 i_level 不变**（若第三关恰好抽到
    --    PAT3，连 i_pat 也不变）→ 这份快照分辨不出"换关"。**不影响判决**：换关一定伴随
    --    一次新的散落（pos 变、locked 清零），而判决还要求 shuf_seen='1'（本局必须看见过
    --    散落忙态）且 i_shuf_busy='0' —— 见 game_fsm 与 sim/tb_puzzle_top 的三关连过场景。
    --    没有为此再加一位（那会动到既有高扇出网、又占面积，实测代价见 docs/06 §13.3）。
    signal pat_frm   : std_logic_vector(1 downto 0) := (others => '0');

begin

    o_lock    <= locked;
    o_sel_idx <= std_logic_vector(sel);
    o_pos     <= pos;
    o_scanrow <= std_logic_vector(scanrow);
    -- the frame registers ARE the outputs: the matrix driver slices them
    o_rowr <= frame_r;
    o_rowg <= frame_g;

    with sel select
        sel_p <= pos(31 downto 24) when "00",
                 pos(23 downto 16) when "01",
                 pos(15 downto 8)  when "10",
                 pos(7 downto 0)   when others;

    ----------------------------------------------------------------------------
    -- ALL-LOCKED : straight equality test (no loops, no indexed reads)
    --
    -- ⚠️ ERR-021: "零片都到位了吗"不再由这里回答。这里只回答"是不是全部已确认锁定"；
    --    画面是否正确由下面的整帧判据（frm_ok）回答 —— 玩家能看到的只有零片的并集。
    ----------------------------------------------------------------------------
    process (locked, i_level)
    begin
        if (i_level = '0') then
            if (locked(2 downto 0) = "111") then alllock_r <= '1';
            else                               alllock_r <= '0'; end if;
        else
            if (locked = "1111") then alllock_r <= '1';
            else                       alllock_r <= '0'; end if;
        end if;
    end process;

    -- 成功 = 整帧画面 == 目标图案 **且** 全部零片已确认锁定
    o_solved   <= frm_ok and alllock_r;
    -- 对外"全部锁定"的含义是"判据齐备"：还要等一个完整且未被扰动的帧把画面判据
    -- 算完（最多 1 帧 = 40 ms）。否则刚确认最后一块的那一拍会拿上一帧的旧判据，
    -- 拼对了也会被判成失败 —— 那正是本次要修的症状，不能在新判据里再留一次。
    o_all_lock <= alllock_r and frm_valid;
    o_busy     <= '0' when (sh = SH_IDLE) else '1';

    ----------------------------------------------------------------------------
    -- ROW-SCAN RENDERER.
    -- For the scanned row, fetch that row from each piece's 3x3 relative shape,
    -- shift it by the piece's anchor column, then combine:
    --     red   = piece cells that are NOT the selected one
    --     green = cells of the selected piece or of any locked piece
    --
    -- ⚠️ 审计更正（2026-10-09 第 11 工作阶段）：这里原来还写着"phase 0..3 每相一块、
    --    phase 4 发布、一帧 32 拍"——那是**更早的 32 相版本**的遗留注释，与实现无关。
    --    实际实现是：**一拍算一行**（同一拍里把 4 块零片各自的 row_mask 并起来），
    --    8 拍一帧；顶层 i_tick 接 tick_200 → 一帧 40 ms（内容 25 Hz），而**显示扫描**
    --    走 tick_1k（8 ms = 125 Hz，ERR-027）——两者节拍不同源也不会错行，因为整帧
    --    存在 frame_r/frame_g 里、顶层只按 mrow 切片。
    ----------------------------------------------------------------------------

    ----------------------------------------------------------------------------
    -- FRAME RENDERER -- one ROW per i_tick, whole frame every 8 ticks.
    --                       （第 11 工作阶段起：并入帧与判据协议在**下一拍**，
    --                         见 ERR-033 的两拍流水）
    --
    -- WHY IT IS ORGANISED THIS WAY
    -- Two earlier arrangements were MEASURED on the board:
    --   * publishing one row per 5 ticks gave a frame rate of 200/(5*8) = 5 Hz,
    --     which visibly FLICKERS;
    --   * spawning all four pieces' row_masks in one tick made the logic far too
    --     large to fit the EPC1270.
    -- So the multiplexing runs over ROWS: each tick still evaluates only one
    -- row_mask per piece slot (so the shared shifter stays cheap), but the frame
    -- is assembled 8 bits at a time into a 64-bit register.
    --
    -- ⚠️ 2026-10-08 更正："200/8 = 25 Hz, above flicker fusion" 是**错的**：
    --    25 Hz 对 LED 明显可见闪（用户上板反馈"点阵和数码管都闪"）。
    --    但要分清两件事：
    --      · **闪烁 = 亮度调制**，只取决于**扫描率**。顶层把点阵行计数器 mrow 与数码管
    --        位选 seg_scan 都改成 1 kHz → 8 行/位 = 8 ms → **125 Hz**，闪就没了
    --        （占空比仍 1/8，亮度不变）；
    --      · **本模块的 i_tick 仍保持 200 Hz**（内容 25 Hz 更新）。实测把它也提到 1 kHz
    --        会让整机 1188 → **1264 / 1270 LE（100%，只剩 6 个）**，+76 LE 换一个
    --        "移动零片时画面滚动 ≤40 ms 的涂抹感"——不值，所以没改。
    --    每拍的组合逻辑量**没有变化**（仍然一拍只算一行的 row_mask），与节拍无关。
    --
    -- The 64-bit frame is simply held; the matrix driver slices the row it is
    -- scanning, so the panel never sees a partially built row and no lockstep
    -- handshake is needed.
    --
    -- Bit convention: bit index = 8*row + col, row 0 = TOP, so logical row 0 is
    -- the TOP slice (63..56).
    ----------------------------------------------------------------------------
    process (i_clk)
        variable r      : integer;
        variable prow   : integer;
        variable srow   : integer;
        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable hh     : integer;
        variable npc    : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable cov    : std_logic_vector(7 downto 0);
        variable kc     : std_logic_vector(7 downto 0);
        variable tgtrow : std_logic_vector(7 downto 0);
        variable redrow : std_logic_vector(7 downto 0);
        variable selrow : std_logic_vector(7 downto 0);
        variable grnrow : std_logic_vector(7 downto 0);
        variable islck0 : boolean;
        variable bad    : std_logic;      -- ERR-021: 本行 cov 是否 != 目标图案本行
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                frow    <= (others => '0');
                scanrow <= (others => '0');
                row_a   <= (others => '0');
                red_a   <= (others => '0');
                grn_a   <= (others => '0');
                bad_a   <= '0';
            elsif (i_tick = '1') then
                r   := to_integer(frow);
                cov    := (others => '0');
                kc     := (others => '0');
                selrow := (others => '0');

                if (i_level = '0') then npc := 3; else npc := 4; end if;

                -- ---- piece 0 -------------------------------------------------
                pk := pos(31 downto 24); shp := i_sh0;
                hh := to_integer(unsigned(i_h0));
                srow := r - to_integer(unsigned(pk(7 downto 4)));
                if (srow >= 0) and (srow < hh) then
                    rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                    cov := cov or rw;
                    if (locked(0) = '1') then kc := kc or rw; end if;
                    if (sel = "00") and (locked(0) = '0') then selrow := selrow or rw; end if;
                end if;

                -- ---- piece 1 -------------------------------------------------
                if (npc > 1) then
                    pk := pos(23 downto 16); shp := i_sh1;
                    hh := to_integer(unsigned(i_h1));
                    srow := r - to_integer(unsigned(pk(7 downto 4)));
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(1) = '1') then kc := kc or rw; end if;
                    if (sel = "01") and (locked(1) = '0') then selrow := selrow or rw; end if;
                    end if;
                end if;

                -- ---- piece 2 -------------------------------------------------
                if (npc > 2) then
                    pk := pos(15 downto 8); shp := i_sh2;
                    hh := to_integer(unsigned(i_h2));
                    srow := r - to_integer(unsigned(pk(7 downto 4)));
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(2) = '1') then kc := kc or rw; end if;
                    if (sel = "10") and (locked(2) = '0') then selrow := selrow or rw; end if;
                    end if;
                end if;

                -- ---- piece 3 (level 2 only) ----------------------------------
                if (npc > 3) then
                    pk := pos(7 downto 0); shp := i_sh3;
                    hh := to_integer(unsigned(i_h3));
                    srow := r - to_integer(unsigned(pk(7 downto 4)));
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(3) = '1') then kc := kc or rw; end if;
                    if (sel = "11") and (locked(3) = '0') then selrow := selrow or rw; end if;
                    end if;
                end if;

                -- ---- target row for the ghost --------------------------------
                case r is
                    when 0      => tgtrow := i_target(7 downto 0);
                    when 1      => tgtrow := i_target(15 downto 8);
                    when 2      => tgtrow := i_target(23 downto 16);
                    when 3      => tgtrow := i_target(31 downto 24);
                    when 4      => tgtrow := i_target(39 downto 32);
                    when 5      => tgtrow := i_target(47 downto 40);
                    when 6      => tgtrow := i_target(55 downto 48);
                    when others => tgtrow := i_target(63 downto 56);
                end case;

                -- ---- ERR-021: 整帧画面判据 -----------------------------------
                -- cov = 本行被零片覆盖的格子并集，tgtrow = 目标图案本行的格子。
                -- 8 行的 cov 全等 tgtrow  <=>  零片并集 == 目标图案。
                -- 这就是 B9"位置和形状与初始拼图一致"的可执行定义：与"哪一块在哪"
                -- 无关，只与玩家看到的画面有关（等价摆法必须算成功）。
                if (cov = tgtrow) then bad := '0'; else bad := '1'; end if;

                -- Colour of this row.
                --   green = selected piece OR locked piece
                --   red   = every piece cell that is not the selected one
                -- Excluding exactly the selected cells from red is what makes the
                -- selected piece pure GREEN; without it green was a subset of red
                -- and the piece showed up as yellow, the same as a locked one.
                --
                -- ⚠️ ERR-023 : the target "ghost" is NOT drawn any more.  The engine
                -- frame is only ever displayed while S_PLAYING (puzzle_top's state
                -- mux shows the pattern / win / fail pictures in every other state),
                -- and during play a red ghost outline must not sit under the pieces
                -- (ERR-013).  That was previously achieved by blanking i_target at
                -- the top level -- which also killed the ERR-021 success test,
                -- because the test compares the assembled picture with i_target.
                -- Now i_target always carries the real picture (the test needs it)
                -- and the ghost is simply not drawn here.
                redrow := cov and (not selrow);
                grnrow := kc or selrow;

                -- ---- 第一拍的结果进流水寄存器（ERR-033）-----------------------
                -- 并入 frame 与整帧判据协议都在**下一拍**做（见紧跟着的进程），
                -- 这样"锚点 → 形状移位 → 帧寄存器"这条最长路径被切成两半。
                row_a <= frow;
                red_a <= redrow;
                grn_a <= grnrow;
                bad_a <= bad;

                -- the scanned row follows the row being built, one tick behind
                if (frow = 7) then
                    frow <= (others => '0');
                else
                    frow <= frow + 1;
                end if;
                scanrow <= frow;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- ERR-033：行渲染的**第二拍** —— 把第一拍算好的行并进帧，并跑整帧判据协议。
    --
    -- 为什么必须拆（实测，不是推理）：整机 1254 LE 时最差路径就是
    --   `pos[12] → frame_g[53]`，slack 只有 **+0.023 ns**（Fmax 50.06 MHz，等于没有余量）；
    --   一旦打开 `AUTO_RESOURCE_SHARING`（省 64 LE），同一个路径变成 **−2.714 ns**。
    --   拆成两拍后：本拍只做"并入帧 + 帧头/帧尾判据"，与第一拍的 row_mask 计算
    --   互相独立 → 面积只多 20 个寄存器（LE 几乎不变），余量却回到几个 ns。
    --
    -- 语义与拆之前**逐拍等价**：原来第 N 拍算第 r 行并并进帧；现在第 N 拍算、第 N+1 拍并。
    -- "干净帧"判据仍然只比较**同一帧**内看到的 pos/level/pat（窗口整体后移一拍）。
    ----------------------------------------------------------------------------
    process (i_clk)
        variable rb : integer;
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                frame_r   <= (others => '0');
                frame_g   <= (others => '0');
                frm_bad   <= '0';
                frm_ok    <= '0';
                frm_valid <= '0';
                pos_frm   <= (others => '0');
                lvl_frm   <= '0';
                pat_frm   <= (others => '0');
            elsif (i_tick = '1') then
                rb := to_integer(row_a);

                if (rb = 0) then
                    -- 帧头：重启本帧的失配累加器，并把本帧各行结果所依赖的东西
                    -- （零片锚点、关卡、图案下标）拍个快照
                    frm_bad <= bad_a;
                    pos_frm <= pos;
                    lvl_frm <= i_level;
                    pat_frm <= i_pat;
                elsif (rb = 7) then
                    -- 帧尾：发布判据。"干净"= 这一帧里 pos、level 与图案下标都没变过，
                    -- 否则 8 行可能取自两种不同摆法/两幅不同图案，错的会被看成对的。
                    -- 跟踪 level **和 pat** 就够：i_target 与 i_sh* 都由 puzzle_top 的
                    -- pattern_rom / piece_rom 直接按 (level, pat) 选择，两者没变
                    -- ⇒ 目标图案与零片形状都没变（这条接线约定必须保持）。
                    if (pos_frm = pos) and (lvl_frm = i_level) and (pat_frm = i_pat) then
                        frm_valid <= '1';
                        if (frm_bad = '0') and (bad_a = '0') then
                            frm_ok <= '1';
                        else
                            frm_ok <= '0';
                        end if;
                    else
                        frm_valid <= '0';
                        frm_ok    <= '0';
                    end if;
                    frm_bad <= '0';
                else
                    frm_bad <= frm_bad or bad_a;
                end if;

                -- ---- merge the pipelined row into the frame -------------------
                case rb is
                    when 0      => frame_r(63 downto 56) <= red_a;
                                   frame_g(63 downto 56) <= grn_a;
                    when 1      => frame_r(55 downto 48) <= red_a;
                                   frame_g(55 downto 48) <= grn_a;
                    when 2      => frame_r(47 downto 40) <= red_a;
                                   frame_g(47 downto 40) <= grn_a;
                    when 3      => frame_r(39 downto 32) <= red_a;
                                   frame_g(39 downto 32) <= grn_a;
                    when 4      => frame_r(31 downto 24) <= red_a;
                                   frame_g(31 downto 24) <= grn_a;
                    when 5      => frame_r(23 downto 16) <= red_a;
                                   frame_g(23 downto 16) <= grn_a;
                    when 6      => frame_r(15 downto 8) <= red_a;
                                   frame_g(15 downto 8) <= grn_a;
                    when others => frame_r(7 downto 0) <= red_a;
                                   frame_g(7 downto 0) <= grn_a;
                end case;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- Main sequential process.
    --
    -- Two strictly serialised tasks:
    --   (a) the scatter sequencer, which places the pieces at random
    --   (b) the validation of the requested move (move vs overlap check)
    -- plus a small overlap-check engine that tests one panel row per tick into an
    -- accumulator.  Serialising the check is what keeps ONE row_mask evaluation
    -- alive at a time; the unrolled version instantiated 32 of them.
    ----------------------------------------------------------------------------
    process (i_clk)
        variable cr, cc : integer;
        variable hh, ww : integer;
        variable ok     : boolean;
        variable npos   : std_logic_vector(7 downto 0);
        variable cand   : std_logic_vector(7 downto 0);
        variable ch, cw : integer;
        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable prow   : integer;
        variable srow   : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable lvl2   : boolean;   -- "不是第一关"：四块零片 / 四槽可选
                                     -- （D2 起覆盖第二关与第三关，名字沿用历史；语义 == i_level='1'）
        variable me     : std_logic_vector(1 downto 0);   -- piece being validated
        variable xr, xc : integer;                        -- ERR-032: bounded candidates
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                pos <= (others => '0');
                locked <= (others => '0');
                sel <= (others => '0');
                sh <= SH_IDLE;
                sh_k <= (others => '0');
                sh_att <= (others => '0');
                mv <= '0';
                mv_pend <= '0';
                mv_go <= '0';
                mv_clamp <= (others => '0');
                mv_sel <= (others => '0');
                chk <= CH_IDLE;
                chk_orow <= (others => '1');
                chk_prow <= (others => '1');
                rnd_step <= '0';
            else
                rnd_step <= '0';
                lvl2 := (i_level = '1');

                ----------------------------------------------------------------
                -- (1) Buttons -- only while neither engine is busy
                ----------------------------------------------------------------
                if (sh = SH_IDLE) and (chk = CH_IDLE) then
                    if (i_go = '1') then
                        sh     <= SH_TRY;
                        sh_k   <= (others => '0');
                        sh_att <= (others => '0');
                        sel    <= (others => '0');
                        locked <= (others => '0');
                    elsif (i_confirm = '1') then
                        case to_integer(sel) is
                            when 0      => locked(0) <= '1';
                            when 1      => locked(1) <= '1';
                            when 2      => locked(2) <= '1';
                            when others => locked(3) <= '1';
                        end case;
                        -- ERR-035：确认后自动跳到下一个**未锁定**的零片（B8）
                        sel <= next_unlocked(sel, locked, lvl2);
                    elsif (i_select = '1') then
                        -- ERR-035：【选择】跳过已锁定的零片（B8 不可再选择）
                        sel <= next_unlocked(sel, locked, lvl2);
                    elsif (i_move = '1') then
                        mv <= '1';
                        -- ⚠️ ERR-020: 方向必须与移动请求**同一拍**锁存。
                        -- 原来把 `mv_dir <= i_up & ...` 放在下面的 mv 阶段（晚一拍），
                        -- 而 game_fsm 的 up_r/down_r/left_r/right_r 只与 o_move **同拍**
                        -- 有效一个时钟 → 等 mv 阶段再采时方向已经撤销，锁进去恒为
                        -- "0000" → 夹紧不生效、位置变成原地重算，**方向键完全不动**。
                        -- 实测证据：tb_puzzle_top 断言 ⑧（方向协议不变量）修复前失败：
                        -- FSM 发了 3 次方向脉冲，而 u_puzzle|mv_dir 全程没有一次非 0。
                        mv_dir <= i_up & i_down & i_left & i_right;
                    end if;
                end if;

                ----------------------------------------------------------------
                -- (2) A move request starts the validation engine
                ----------------------------------------------------------------
                -- stage 1: latch the proposal (the anchor; the direction was
                -- already latched together with the request -- see ERR-020)
                if (mv = '1') and (chk = CH_IDLE) then
                    mv       <= '0';
                    mv_pend  <= '1';
                    mv_anchor<= sel_p;
                end if;

                -- stage 2a（ERR-033b）：只做"夹紧"并把结果落寄存器。
                -- 拆出来的原因：渲染器流水化之后，最差路径变成
                --   `mv_anchor → 夹紧 → 边界比较 → chk_shp`（slack −0.19 ns）。
                if (mv_pend = '1') and (chk = CH_IDLE) then
                    mv_pend <= '0';

                    cr := to_integer(unsigned(mv_anchor(7 downto 4)));
                    cc := to_integer(unsigned(mv_anchor(3 downto 0)));
                    if (mv_dir(3) = '1') then
                        if (cr > 0) then cr := cr - 1; end if;
                    elsif (mv_dir(2) = '1') then
                        if (cr < 7) then cr := cr + 1; end if;
                    elsif (mv_dir(1) = '1') then
                        if (cc > 0) then cc := cc - 1; end if;
                    elsif (mv_dir(0) = '1') then
                        if (cc < 7) then cc := cc + 1; end if;
                    end if;
                    mv_clamp <= std_logic_vector(to_unsigned(cr, 4)) &
                                std_logic_vector(to_unsigned(cc, 4));
                    mv_sel   <= sel;
                    mv_go    <= '1';
                end if;

                -- stage 2b：边界 + 锁定检查，然后启动重叠检查引擎。
                -- 操作数全是寄存器输出（mv_clamp / mv_sel / i_h* / i_w* / locked）。
                if (mv_go = '1') and (chk = CH_IDLE) then
                    mv_go <= '0';

                    cr := to_integer(unsigned(mv_clamp(7 downto 4)));
                    cc := to_integer(unsigned(mv_clamp(3 downto 0)));
                    case to_integer(mv_sel) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp := i_sh0;
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp := i_sh1;
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp := i_sh2;
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp := i_sh3;
                    end case;

                    -- bounds: analytic, verified against geometry in
                    -- .ref/model_ctrl.py (0 mismatches for every shape/position)
                    if (cr + hh <= 8) and (cc + ww <= 8)
                       and (locked(to_integer(mv_sel)) = '0') then
                        chk_pos  <= mv_clamp;
                        chk_shp  <= shp;
                        chk_h    <= std_logic_vector(to_unsigned(hh, 3));
                        chk_w    <= std_logic_vector(to_unsigned(ww, 3));
                        chk_kind <= '0';                 -- '0' = move
                        chk      <= CH_RUN;
                        chk_row  <= (others => '0');
                        chk_hit  <= '0';
                        -- first comparison cycle must evaluate NOTHING: force the
                        -- pipelined row index out of range so row_mask returns 0
                        -- and the neighbour compare is skipped (see ERR-016)
                        chk_orow <= (others => '1');
                        chk_prow <= (others => '1');
                    end if;
                end if;

                ----------------------------------------------------------------
                -- (3) Scatter: each turn proposes an anchor, then runs the SAME
                --     overlap engine.  Rejection sampling with a deterministic
                --     fallback, so a scatter always completes.
                ----------------------------------------------------------------
                if (sh = SH_TRY) and (chk = CH_IDLE) then
                    rnd_step <= '1';

                    case to_integer(sh_k) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0));
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1));
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2));
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3));
                    end case;

                    -- ⚠️ ERR-037（2026-10-09 第 11 工作阶段，全项目审计发现）：这里原来写
                    --   `ch := 8 - hh` / `cw := 8 - ww`，于是候选锚点只取 0..(7-hh)，
                    --   而合法上界是 0..(8-hh)（移动路径的判据是 `cr + hh <= 8`）——
                    --   **最后一行/最后一列永远抽不到**，而且 0..7 mod 7 让锚点 0 的概率
                    --   是其它值的 2 倍（分布既截断又不均匀）。修法：除数改成 `9 - hh`。
                    --   对本设计所有零片（hh ≤ 3）恒有 ch ∈ {6,7,8} ≥ 4、x ≤ 7 < 2*ch，
                    --   所以下面"一次条件相减"的等价改写依然成立。
                    ch := 9 - hh;  if (ch < 1) then ch := 1; end if;
                    cw := 9 - ww;  if (cw < 1) then cw := 1; end if;

                    -- Pipeline stage 1: latch the operands and the two modulo
                    -- results.  The modulo is the expensive part of the critical
                    -- path, so it is evaluated here and consumed one cycle later
                    -- in SH_CHK rather than being chained into the validity test.
                    sc_hh   <= std_logic_vector(to_unsigned(hh, 3));
                    sc_ww   <= std_logic_vector(to_unsigned(ww, 3));
                    -- ⚠️ ERR-032（2026-10-09，第 11 工作阶段）：原来这里是
                    --     `x mod ch` / `x mod cw`，x = rnd_val(2:0) ∈ 0..7。
                    --   零片都是 2x2 时 ch = cw = 7 是**常量**，综合器把取模折叠成
                    --   LUT；第 11 工作阶段零片改成 3/2/5/6 格的异形后 ch/cw 随
                    --   零片变化（6/7/8，由 sh_k 选择）→ 真的实例化出两个
                    --   **变除数除法器**（lpm_divide）：实测整机 Fmax
                    --   **44.77 → 36.68 MHz**（最差 slack −7.3 ns、TNS −926 ns）。
                    --   修法：x ∈ 0..7 且 ch ≥ 4（所有零片包围盒 ≤ 4x4，本设计 ≤3x3）
                    --   ⇒ x < 2*ch ⇒ **x mod ch == (x - ch if x >= ch else x)**，
                    --   一次"比较 + 条件相减"即可，**候选序列逐拍完全相同**（行为等价）。
                    --   实测（同一版本 RTL，只差这一处）：Fmax 36.68 → **50.06 MHz**
                    --   （TNS −926 → 0），面积 1246 → **1254 LE（+8）**。
                    --   ⚠️ 对**旧的**四块 2x2 版本（除数恒定），同样的替换是 −1.7 MHz/+12 LE
                    --      （那次取模本来就是常量、被折叠了），所以当时没做 ——
                    --      这个优化**只在除数真的变化时才有意义**。
                    --   前置条件（零片包围盒 ≤ 4x4）由 scripts/check_geometry.py 断言。
                    xr := to_integer(unsigned(rnd_val(2 downto 0)));
                    xc := to_integer(unsigned(rnd_val(5 downto 3)));
                    if (xr >= ch) then xr := xr - ch; end if;
                    if (xc >= cw) then xc := xc - cw; end if;
                    sc_cand <= std_logic_vector(to_unsigned(xr, 4)) &
                               std_logic_vector(to_unsigned(xc, 4));
                    sh <= SH_CHK;
                end if;

                ----------------------------------------------------------------
                -- Pipeline stage 2: start the overlap check on the registered
                -- operand set.
                ----------------------------------------------------------------
                if (sh = SH_CHK) and (chk = CH_IDLE) then
                    case to_integer(sh_k) is
                        when 0      => shp := i_sh0;
                        when 1      => shp := i_sh1;
                        when 2      => shp := i_sh2;
                        when others => shp := i_sh3;
                    end case;

                    chk_pos <= sc_cand;
                    chk_shp <= shp;
                    chk_h   <= sc_hh;
                    chk_w   <= sc_ww;
                    chk_kind <= '1';                     -- '1' = scatter
                    chk     <= CH_RUN;
                    chk_row <= (others => '0');
                    chk_hit <= '0';
                    chk_orow <= (others => '1');         -- see ERR-016
                    chk_prow <= (others => '1');
                end if;

                ----------------------------------------------------------------
                -- (4) Overlap engine: one panel row per tick
                ----------------------------------------------------------------
                case chk is
                    when CH_IDLE =>
                        null;

                    when CH_RUN =>
                        chk_row <= chk_row + 1;
                        -- Pipeline: the zero-based row for the candidate is
                        -- registered here and consumed by the comparison below on
                        -- the FOLLOWING cycle.  Computing it combinationally and
                        -- feeding it straight into srl8 put a 26 ns path through
                        -- the row subtract, the range test and the shift.
                        --
                        -- ⚠️ ERR-016a: chk_orow is REGISTERED, so the candidate row
                        -- consumed below belongs to the PREVIOUS panel row.  The
                        -- neighbour comparison must therefore use that same panel
                        -- row (chk_prow), not the current chk_row -- otherwise the
                        -- candidate's row r is compared against the neighbours'
                        -- row r+1.  The measured symptom was a legal scatter being
                        -- rejected (producing a fallback anchor) AND an illegal
                        -- overlapping scatter being accepted.
                        chk_orow <= resize(chk_row -
                                           unsigned(chk_pos(7 downto 4)), 4);
                        chk_prow <= chk_row;
                        -- Nine cycles are needed, not eight: the first one only
                        -- primes the pipeline (chk_orow/chk_prow = "1111"), so the
                        -- evaluated panel rows are -1, 0, ... 7.
                        if (chk_row = 9) then
                            chk <= CH_DONE;
                        else
                            -- candidate's mask for this panel row (index pipelined)
                            rw := row_mask(chk_shp, to_integer(chk_orow),
                                           to_integer(unsigned(chk_pos(3 downto 0))));
                            if (rw /= x"00") then
                                -- ⚠️ ERR-017: which piece is being validated is
                                -- 'sel' for a MOVE but 'sh_k' for a SCATTER.  The
                                -- original masks used 'sel' for both; during a
                                -- scatter sel is always 0, so the candidate was
                                -- never compared against piece 0 (two pieces could
                                -- land on the same cells) and was wrongly compared
                                -- against its own pre-scatter anchor.
                                if (chk_kind = '0') then
                                    me := std_logic_vector(sel);
                                else
                                    me := std_logic_vector(sh_k);
                                end if;
                                -- compare against every other live piece, one at
                                -- a time using the same shared row_mask
                                prow := to_integer(unsigned(pos(31 downto 28)));
                                srow := to_integer(chk_prow) - prow;
                                if (me /= "00") then
                                    if (srow >= 0) and (srow <= 2) then
                                        if (rw and row_mask(i_sh0, srow,
                                                to_integer(unsigned(pos(27 downto 24))))) /= x"00" then
                                            chk_hit <= '1';
                                        end if;
                                    end if;
                                end if;
                                prow := to_integer(unsigned(pos(23 downto 20)));
                                srow := to_integer(chk_prow) - prow;
                                if (me /= "01") then
                                    if (srow >= 0) and (srow <= 2) then
                                        if (rw and row_mask(i_sh1, srow,
                                                to_integer(unsigned(pos(19 downto 16))))) /= x"00" then
                                            chk_hit <= '1';
                                        end if;
                                    end if;
                                end if;
                                prow := to_integer(unsigned(pos(15 downto 12)));
                                srow := to_integer(chk_prow) - prow;
                                if (me /= "10") then
                                    if (srow >= 0) and (srow <= 2) then
                                        if (rw and row_mask(i_sh2, srow,
                                                to_integer(unsigned(pos(11 downto 8))))) /= x"00" then
                                            chk_hit <= '1';
                                        end if;
                                    end if;
                                end if;
                                if (lvl2) then
                                    prow := to_integer(unsigned(pos(7 downto 4)));
                                    srow := to_integer(chk_prow) - prow;
                                    if (me /= "11") then
                                        if (srow >= 0) and (srow <= 2) then
                                            if (rw and row_mask(i_sh3, srow,
                                                    to_integer(unsigned(pos(3 downto 0))))) /= x"00" then
                                                chk_hit <= '1';
                                            end if;
                                        end if;
                                    end if;
                                end if;
                            end if;
                        end if;

                    when CH_DONE =>
                        chk <= CH_IDLE;
                        if (chk_hit = '0') then
                            -- accept: commit the anchor
                            if (chk_kind = '0') then
                                case to_integer(sel) is
                                    when 0      => pos(31 downto 24) <= chk_pos;
                                    when 1      => pos(23 downto 16) <= chk_pos;
                                    when 2      => pos(15 downto 8)  <= chk_pos;
                                    when others => pos(7 downto 0)   <= chk_pos;
                                end case;
                            else
                                case to_integer(sh_k) is
                                    when 0      => pos(31 downto 24) <= chk_pos;
                                    when 1      => pos(23 downto 16) <= chk_pos;
                                    when 2      => pos(15 downto 8)  <= chk_pos;
                                    when others => pos(7 downto 0)   <= chk_pos;
                                end case;
                                sh_att <= (others => '0');
                                sh     <= SH_NEXT;
                            end if;
                        else
                            if (chk_kind = '0') then
                                null;                    -- move simply rejected
                            elsif (sh_att = 15) then
                                -- deterministic fallback so a scatter always ends
                                sh_att <= (others => '0');
                                case to_integer(sh_k) is
                                    when 0      => pos(31 downto 24) <= "0000" & "0000";
                                    when 1      => pos(23 downto 16) <= "0000" & "0100";
                                    when 2      => pos(15 downto 8)  <= "0100" & "0000";
                                    when others => pos(7 downto 0)   <= "0100" & "0100";
                                end case;
                                sh <= SH_NEXT;
                            else
                                -- ⚠️ ERR-018a: a retry MUST go back to SH_TRY.
                                -- Staying in SH_CHK re-ran the check on the SAME
                                -- registered candidate (sc_cand was only latched in
                                -- SH_TRY), so all 16 "attempts" tested one single
                                -- position: rejection sampling never resampled and
                                -- the first conflict always ended in the hardcoded
                                -- fallback anchor -- which is NOT overlap-checked
                                -- (ERR-018b), so two pieces could end up on the
                                -- same cells.  Simulated evidence: tb_puzzle_ctrl
                                -- round 4, P1@(0,4) falling back onto P0@(1,4).
                                sh_att <= sh_att + 1;
                                sh     <= SH_TRY;
                            end if;
                        end if;

                    when others =>
                        chk <= CH_IDLE;
                end case;

                -- advance to the next piece, or finish the scatter
                if (sh = SH_NEXT) then
                    if ((sh_k = 2) and (not lvl2)) or (sh_k = 3) then
                        sh <= SH_DONE;
                    else
                        sh_k <= sh_k + 1;
                        sh   <= SH_TRY;
                    end if;
                end if;

                if (sh = SH_DONE) then
                    sh <= SH_IDLE;
                end if;
            end if;
        end if;
    end process;

end architecture rtl;
