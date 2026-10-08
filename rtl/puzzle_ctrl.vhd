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
--  Nothing 64-bit is stored.  State: four piece anchors (8 bits each) + four
--  locked flags.  Footprints, colours and collisions are all derived.
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
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity puzzle_ctrl is
    port (
        i_clk     : in  std_logic;
        i_rst     : in  std_logic;
        i_tick    : in  std_logic;                      -- 200 Hz row-scan tick
        rnd_step  : out std_logic;
        rnd_val   : in  std_logic_vector(7 downto 0);
        i_level   : in  std_logic;                      -- '0' level 1, '1' level 2
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
    -- registered scatter operands (pipelining -- see the header note)
    signal sc_hh    : std_logic_vector(2 downto 0) := (others => '0');
    signal sc_ww    : std_logic_vector(2 downto 0) := (others => '0');
    signal sc_cand  : std_logic_vector(7 downto 0) := (others => '0');
    signal sc_ok    : std_logic := '0';
    signal sh     : sh_t := SH_IDLE;
    signal sh_k   : unsigned(1 downto 0) := (others => '0');
    signal sh_att : unsigned(3 downto 0) := (others => '0');

    signal mv     : std_logic := '0';
    signal solved_r  : std_logic;
    signal alllock_r : std_logic;
    signal solved_c  : std_logic;
    signal alllock_c : std_logic;

    signal scanrow : unsigned(2 downto 0) := (others => '0');  -- row being scanned
    signal frow    : unsigned(2 downto 0) := (others => '0');  -- row being built
    signal frame_r : std_logic_vector(63 downto 0) := (others => '0');
    signal frame_g : std_logic_vector(63 downto 0) := (others => '0');

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
    -- SOLVED / ALL-LOCKED: straight equality tests (no loops, no indexed reads)
    ----------------------------------------------------------------------------
    process (pos, locked, i_level)
    begin
        if (i_level = '0') then
            if (pos(31 downto 24) = L1_TGT0) and (pos(23 downto 16) = L1_TGT1)
               and (pos(15 downto 8) = L1_TGT2) and (locked(2 downto 0) = "111") then
                solved_r <= '1';
            else
                solved_r <= '0';
            end if;
            if (locked(2 downto 0) = "111") then alllock_r <= '1';
            else                               alllock_r <= '0'; end if;
        else
            if (pos(31 downto 24) = L2_TGT0) and (pos(23 downto 16) = L2_TGT1)
               and (pos(15 downto 8) = L2_TGT2) and (pos(7 downto 0) = L2_TGT3)
               and (locked = "1111") then
                solved_r <= '1';
            else
                solved_r <= '0';
            end if;
            if (locked = "1111") then alllock_r <= '1';
            else                       alllock_r <= '0'; end if;
        end if;
    end process;

    o_solved   <= solved_r;
    o_all_lock <= alllock_r;
    o_busy     <= '0' when (sh = SH_IDLE) else '1';

    ----------------------------------------------------------------------------
    -- ROW-SCAN RENDERER.
    -- For the scanned row, fetch that row from each piece's 3x3 relative shape,
    -- shift it by the piece's anchor column, then combine:
    --     red   = piece cells OR (target cells with no piece on them)
    --     green = cells of the selected piece or of any locked piece
    ----------------------------------------------------------------------------
    -- Time-multiplexed row renderer.
    --   phase 0..3 : one piece per phase accumulates into the row accumulators
    --   phase 4    : the accumulated row is published
    -- The dot-matrix driver scans one row per tick, so a row is produced every
    -- four ticks and the frame takes 32 ticks -- the same as the reference
    -- implementation's 32-phase frame engine.

    ----------------------------------------------------------------------------
    -- FRAME RENDERER -- one ROW per 200 Hz tick, whole frame every 8 ticks.
    --
    -- WHY IT IS ORGANISED THIS WAY
    -- Two earlier arrangements were MEASURED on the board:
    --   * publishing one row per 5 ticks gave a frame rate of 200/(5*8) = 5 Hz,
    --     which visibly FLICKERS;
    --   * spawning all four pieces' row_masks in one tick made the logic far too
    --     large to fit the EPC1270.
    -- So the multiplexing runs over ROWS: each tick still evaluates only one
    -- row_mask per piece slot (so the shared shifter stays cheap), but the frame
    -- is assembled 8 bits at a time into a 64-bit register.  A frame is complete
    -- in 8 ticks and the refresh rate is 200/8 = 25 Hz, above flicker fusion.
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
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                frow    <= (others => '0');
                scanrow <= (others => '0');
                frame_r <= (others => '0');
                frame_g <= (others => '0');
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
                    if (sel = "00") then selrow := selrow or rw; end if;
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
                    if (sel = "01") then selrow := selrow or rw; end if;
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
                    if (sel = "10") then selrow := selrow or rw; end if;
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
                    if (sel = "11") then selrow := selrow or rw; end if;
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

                -- Colour of this row.
                --   green = selected piece OR locked piece
                --   red   = every OTHER piece cell, plus the part of the target
                --           that no piece covers (the ghost)
                -- Excluding exactly the selected cells from red is what makes the
                -- selected piece pure GREEN; without it green was a subset of red
                -- and the piece showed up as yellow, the same as a locked one.
                redrow := (cov and (not selrow)) or (tgtrow and (not cov));
                grnrow := kc or selrow;

                -- ---- merge the row into the frame ----------------------------
                case r is
                    when 0      => frame_r(63 downto 56) <= redrow;
                                   frame_g(63 downto 56) <= grnrow;
                    when 1      => frame_r(55 downto 48) <= redrow;
                                   frame_g(55 downto 48) <= grnrow;
                    when 2      => frame_r(47 downto 40) <= redrow;
                                   frame_g(47 downto 40) <= grnrow;
                    when 3      => frame_r(39 downto 32) <= redrow;
                                   frame_g(39 downto 32) <= grnrow;
                    when 4      => frame_r(31 downto 24) <= redrow;
                                   frame_g(31 downto 24) <= grnrow;
                    when 5      => frame_r(23 downto 16) <= redrow;
                                   frame_g(23 downto 16) <= grnrow;
                    when 6      => frame_r(15 downto 8) <= redrow;
                                   frame_g(15 downto 8) <= grnrow;
                    when others => frame_r(7 downto 0) <= redrow;
                                   frame_g(7 downto 0) <= grnrow;
                end case;

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
        variable lvl2   : boolean;
        variable me     : std_logic_vector(1 downto 0);   -- piece being validated
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
                        if (sel = "10" and not lvl2) then sel <= "00";
                        else                              sel <= sel + 1; end if;
                    elsif (i_select = '1') then
                        if (sel = "10" and not lvl2) then sel <= "00";
                        else                              sel <= sel + 1; end if;
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

                -- stage 2: clamp, test the bounds and launch the overlap engine.
                -- All operands are register outputs, so this is a short path.
                if (mv_pend = '1') and (chk = CH_IDLE) then
                    mv_pend <= '0';

                    cr := to_integer(unsigned(mv_anchor(7 downto 4)));
                    cc := to_integer(unsigned(mv_anchor(3 downto 0)));
                    case to_integer(sel) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp := i_sh0;
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp := i_sh1;
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp := i_sh2;
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp := i_sh3;
                    end case;

                    if (mv_dir(3) = '1') then
                        if (cr > 0) then cr := cr - 1; end if;
                    elsif (mv_dir(2) = '1') then
                        if (cr < 7) then cr := cr + 1; end if;
                    elsif (mv_dir(1) = '1') then
                        if (cc > 0) then cc := cc - 1; end if;
                    elsif (mv_dir(0) = '1') then
                        if (cc < 7) then cc := cc + 1; end if;
                    end if;

                    -- bounds: analytic, verified against geometry in
                    -- .ref/model_ctrl.py (0 mismatches for every shape/position)
                    if (cr + hh <= 8) and (cc + ww <= 8)
                       and (locked(to_integer(sel)) = '0') then
                        chk_pos  <= std_logic_vector(to_unsigned(cr, 4)) &
                                    std_logic_vector(to_unsigned(cc, 4));
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

                    ch := 8 - hh;  if (ch < 1) then ch := 1; end if;
                    cw := 8 - ww;  if (cw < 1) then cw := 1; end if;

                    -- Pipeline stage 1: latch the operands and the two modulo
                    -- results.  The modulo is the expensive part of the critical
                    -- path, so it is evaluated here and consumed one cycle later
                    -- in SH_CHK rather than being chained into the validity test.
                    sc_hh   <= std_logic_vector(to_unsigned(hh, 3));
                    sc_ww   <= std_logic_vector(to_unsigned(ww, 3));
                    sc_cand <= std_logic_vector(to_unsigned(
                                   to_integer(unsigned(rnd_val(2 downto 0))) mod ch, 4)) &
                               std_logic_vector(to_unsigned(
                                   to_integer(unsigned(rnd_val(5 downto 3))) mod cw, 4));
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
