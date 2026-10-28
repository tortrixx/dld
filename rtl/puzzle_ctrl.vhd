-- ============================================================================
--  puzzle_ctrl  ——  放置 / 移动 / 锁定 / 着色引擎
--  所属子系统：S4（拼图核心）
--
--  本模块掌管一切与空间有关的事情；游戏时序由 game_fsm 负责。
--
--  架构：行扫描渲染器
--  ---------------------------------------------------------------------------
--  EPM1270 只有 1270 个逻辑单元，本模块必须与其它十个模块共用。
--  如果为每块零片都保存一份 64 位覆盖掩码，代价会远超器件容量；
--  而回答"这块零片是否覆盖第 r 行第 c 列"其实只需要一个 8 位与门。
--  因此渲染器每个节拍只处理一块零片的一行：
--    · 每一拍的组合计算路径只有 8 位宽；
--    · 一行需要 npc+2 拍，8 行算完写进 64 位的 frame_r / frame_g 帧寄存器；
--    · 点阵驱动按行切片帧寄存器，看到的永远是完整的一帧。
--
--  位序约定（与 puzzle_pkg 共用）：
--      位下标 = 8*row + col，bit0 = 左上角
--      向下（row+1）= 位下标增大；向右（col+1）= 同一行内位下标增大
--      打包后的锚点是 row(3:0) & col(3:0)
--
--  颜色（B6 / B8）：
--      选中的零片      -> 绿色
--      已锁定的零片    -> 黄色（红 + 绿）
--      其余零片格子    -> 红色
--  对局中不画目标虚影；目标提示由顶层在倒计时告急时叠加。
--
--  边界与重叠（B7 / B5）：新锚点必须让形状仍在 8x8 场内，且各零片
--  不共用格子。重叠判定是精确的逐行掩码相与，不是包围盒：包围盒会
--  误拒第一关阶梯形与 L 形零片的合法移动。
--
--  成功（B9）：零片并集等于 i_target 且每块零片都已锁定。
--  判据落在"拼出来的画面"上，而不是"哪一块放在哪个锚点"上，
--  因此同一幅图案的所有等价铺法都会被接受。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

entity puzzle_ctrl is
    port (
        i_clk     : in  std_logic;
        i_rst     : in  std_logic;
        i_tick    : in  std_logic;                      -- 行渲染节拍：顶层给 1 kHz
        rnd_step  : out std_logic;
        rnd_val   : in  std_logic_vector(7 downto 0);
        i_level   : in  std_logic;                      -- '0' 第一关，'1' 第二/三关
        i_pat     : in  std_logic_vector(1 downto 0);   -- 图案库下标（用于帧快照）
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
        i_rot     : in  std_logic;                      -- 【旋转】：1 拍，顺时针 90°
        i_up      : in  std_logic;
        i_down    : in  std_logic;
        i_left    : in  std_logic;
        i_right   : in  std_logic;
        o_ori     : out std_logic_vector(7 downto 0);   -- 四块各 2 位的朝向（仿真观察）
        o_solved  : out std_logic;
        o_all_lock: out std_logic;
        o_busy    : out std_logic;
        o_sel_idx : out std_logic_vector(1 downto 0);
        o_pos     : out std_logic_vector(31 downto 0);
        o_lock    : out std_logic_vector(3 downto 0);
        o_scanrow : out std_logic_vector(2 downto 0);
        o_rowr    : out std_logic_vector(63 downto 0);  -- 红色帧
        o_rowg    : out std_logic_vector(63 downto 0)   -- 绿色帧
    );
end entity puzzle_ctrl;

architecture rtl of puzzle_ctrl is

    ----------------------------------------------------------------------------
    -- 精确重叠判定辅助函数。
    --
    -- 零片形状并不都是矩形，用包围盒求交会误拒合法移动。本函数返回
    -- 一块零片对某一面板行贡献的 8 位掩码；调用方把候选行与其它零片
    -- 的行掩码相与，即可得到精确的重叠结果。
    --
    -- 旋转在这一级完成：只对 3 位行做置换，而不是把 24 位形状整体转一遍。
    -- sr/ac 都是紧包围盒坐标：sr = 面板行 - 锚点行，ac = 锚点列。
    ----------------------------------------------------------------------------
    function row_mask(shp : std_logic_vector(63 downto 0);
                      h   : std_logic_vector(2 downto 0);
                      w   : std_logic_vector(2 downto 0);
                      ori : std_logic_vector(1 downto 0);
                      sr  : integer range 0 to 2;
                      ac  : integer range 0 to 7) return std_logic_vector is
        variable dr : integer range 0 to 2;
        variable dc : integer range 0 to 2;
    begin
        dr := to_integer(unsigned(rot_off_r(h, w, ori)));
        dc := to_integer(unsigned(rot_off_c(h, w, ori)));
        return srl8(rot_row(shp, ori, sr + dr), ac - dc);
    end function;

    ----------------------------------------------------------------------------
    -- 选择 / 确认时跳过已锁定的零片（B8"锁定后不可再选择及移动"）。
    -- 全锁时停在原处。
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

    -- 零片状态：pos 每块 8 位（行 3:0 & 列 3:0），locked 每块 1 位，ori 每块 2 位
    signal pos    : std_logic_vector(31 downto 0) := (others => '0');
    signal locked : std_logic_vector(3 downto 0)  := (others => '0');
    signal sel    : unsigned(1 downto 0) := (others => '0');
    signal ori    : std_logic_vector(7 downto 0) := (others => '0');
    signal mv_rot : std_logic := '0';        -- 本次移动请求其实是"旋转"
    signal chk_rot: std_logic := '0';        -- 正在检查的候选是旋转后的形状
    signal chk_ori: std_logic_vector(1 downto 0) := (others => '0');
    signal chk_h0 : std_logic_vector(2 downto 0) := "001";  -- 候选原始高（旋转前）
    signal chk_w0 : std_logic_vector(2 downto 0) := "001";  -- 候选原始宽（旋转前）
    signal sel_p  : std_logic_vector(7 downto 0);

    type sh_t is (SH_IDLE, SH_TRY, SH_CHK, SH_NEXT, SH_DONE);
    type chk_t is (CH_IDLE, CH_RUN, CH_DONE);
    signal chk      : chk_t := CH_IDLE;
    signal chk_kind : std_logic := '0';
    signal chk_hit  : std_logic := '0';
    signal chk_pos  : std_logic_vector(7 downto 0) := (others => '0');
    signal chk_shp  : std_logic_vector(63 downto 0) := (others => '0');

    ----------------------------------------------------------------------------
    -- 重叠检查引擎：串行化 + 资源共享。
    --
    -- 一拍只算一个 row_mask：先按候选自己的行号算出候选本行（chk_crow），
    -- 随后每拍与一个邻块比较。判定结果与"一拍并行算 5 个 row_mask"相同，
    -- 但只剩一份移位器，面积显著减小。
    -- 这里的"拍"是 i_clk（不受 i_tick 门控），一次检查约 5~16 个时钟。
    ----------------------------------------------------------------------------
    signal chk_me   : unsigned(1 downto 0) := (others => '0');  -- 候选是哪一块
    signal chk_sr   : unsigned(1 downto 0) := (others => '0');  -- 候选自己的行号
    signal chk_srmax: unsigned(1 downto 0) := (others => '0');  -- 候选行数-1
    signal chk_slot : unsigned(1 downto 0) := (others => '0');  -- 正在比对的邻块
    signal chk_ld   : std_logic := '0';                         -- 下一拍先算候选本行
    signal chk_prowr: unsigned(3 downto 0) := (others => '0');  -- 候选本行所在的面板行
    signal chk_crow : std_logic_vector(7 downto 0) := (others => '0');

    -- 待处理的移动提议：把"夹紧 + 边界判定"与锚点选择分到相邻两拍
    signal mv_pend  : std_logic := '0';
    signal mv_anchor: std_logic_vector(7 downto 0) := (others => '0');
    signal mv_dir   : std_logic_vector(3 downto 0) := (others => '0');
    signal mv_clamp : std_logic_vector(7 downto 0) := (others => '0');
    signal mv_sel   : unsigned(1 downto 0) := (others => '0');
    signal mv_go    : std_logic := '0';

    -- 已寄存的散落操作数
    signal sc_hh    : std_logic_vector(2 downto 0) := (others => '0');
    signal sc_ww    : std_logic_vector(2 downto 0) := (others => '0');
    signal sc_cand  : std_logic_vector(7 downto 0) := (others => '0');
    signal sc_ok    : std_logic := '0';
    signal sh     : sh_t := SH_IDLE;
    signal sh_k   : unsigned(1 downto 0) := (others => '0');
    signal sh_att : unsigned(3 downto 0) := (others => '0');

    signal mv     : std_logic := '0';
    signal alllock_r : std_logic;

    signal scanrow : unsigned(2 downto 0) := (others => '0');  -- 正在扫描的行
    signal frow    : unsigned(2 downto 0) := (others => '0');  -- 正在构建的行
    signal frame_r : std_logic_vector(63 downto 0) := (others => '0');
    signal frame_g : std_logic_vector(63 downto 0) := (others => '0');

    ----------------------------------------------------------------------------
    -- 渲染器串行化：一拍只算一块零片。
    --   ph = 0       准备第 0 块的行掩码
    --   ph = 1..npc  累加第 ph-1 块，同时准备下一块
    --   ph = npc+1   发布本行
    -- 一帧 = 8 行 x (npc+2) 拍：第一关 8x5 = 40 拍（25 Hz），
    -- 第二/三关 8x6 = 48 拍（约 21 Hz）。
    -- 只剩一份 row_mask，且可与重叠引擎在时间上复用。
    ----------------------------------------------------------------------------
    signal ph      : unsigned(2 downto 0) := (others => '0');
    signal bp      : std_logic_vector(7 downto 0) := (others => '0');  -- 备好的行掩码
    signal sp      : unsigned(3 downto 0) := (others => '0');          -- 备好的列移位 + 2
    signal op      : std_logic := '0';                                 -- 该行在零片内
    signal cov_a   : std_logic_vector(7 downto 0) := (others => '0');  -- 本行已被覆盖
    signal kc_a    : std_logic_vector(7 downto 0) := (others => '0');  -- 本行已锁定的
    signal sl_a    : std_logic_vector(7 downto 0) := (others => '0');  -- 本行选中的
    signal row_new : std_logic := '0';       -- 上一拍发布了一整行

    -- 行渲染的两拍流水：第一拍算这一行，第二拍并入帧并跑整帧判据
    signal row_a  : unsigned(2 downto 0) := (others => '0');
    signal red_a  : std_logic_vector(7 downto 0) := (others => '0');
    signal grn_a  : std_logic_vector(7 downto 0) := (others => '0');
    signal bad_a  : std_logic := '0';

    ----------------------------------------------------------------------------
    -- 成功判据 = "拼出来的画面 == 目标图案"（B9）。
    --
    -- 把每块零片的锚点与写死的目标比较是过强判据：同一幅画面可以有
    -- 多种等价摆法，玩家无从分辨该把哪一块放到哪里。改为比较零片
    -- 并集与目标掩码，所有等价铺法都会被接受。
    --
    -- 只在整帧画完时发布判据，并检查这一帧内 pos / level / pat 没有变过，
    -- 否则一帧可能混着两种摆法或两幅图案的行。
    ----------------------------------------------------------------------------
    signal frm_bad   : std_logic := '0';      -- 当前帧出现过行不匹配
    signal frm_ok    : std_logic := '0';      -- 上一整帧（且未被扰动）并集 == 目标
    signal frm_valid : std_logic := '0';      -- 上一整帧是"干净"的一帧
    signal pos_cnt   : unsigned(3 downto 0) := (others => '0');  -- 每次提交 pos 时 +1
    signal p_frm     : unsigned(3 downto 0) := (others => '0');
    signal lvl_frm   : std_logic := '0';
    signal pat_frm   : std_logic_vector(1 downto 0) := (others => '0');

begin

    o_lock    <= locked;
    o_ori     <= ori;
    o_sel_idx <= std_logic_vector(sel);
    o_pos     <= pos;
    o_scanrow <= std_logic_vector(scanrow);
    -- 帧寄存器就是输出：点阵驱动按行切片它们
    o_rowr <= frame_r;
    o_rowg <= frame_g;

    with sel select
        sel_p <= pos(31 downto 24) when "00",
                 pos(23 downto 16) when "01",
                 pos(15 downto 8)  when "10",
                 pos(7 downto 0)   when others;

    ----------------------------------------------------------------------------
    -- 全部锁定：直接相等比较，无循环、无变址读取。
    -- 这里只回答"是否全部已确认锁定"；画面是否正确由整帧判据回答。
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

    -- 成功 = 整帧画面 == 目标图案 且 全部零片已确认锁定
    o_solved   <= frm_ok and alllock_r;
    -- 对外"全部锁定"还要等一帧把画面判据算完（最多 1 帧），
    -- 否则刚确认最后一块的那一拍会拿上一帧的旧判据。
    o_all_lock <= alllock_r and frm_valid;
    o_busy     <= '0' when (sh = SH_IDLE) else '1';

    ----------------------------------------------------------------------------
    -- 行扫描渲染器（第一拍）。
    -- 对正在构建的行 r，从每块零片的 3x3 相对形状中取出对应行，
    -- 按锚点列移位，然后合并：
    --     红 = 不属于选中零片的零片格子
    --     绿 = 选中零片的格子，或任一已锁定零片的格子
    --
    -- 流水安排：
    --   (a) 累加相位：消费上一拍备好的 bp/sp/op，只需 srl8 + 或门，很浅；
    --   (b) 准备相位：为下一拍算好行掩码（旋转 + 锚点补偿，较深）。
    -- 将两者拆到相邻两拍，避免深组合链直接挂在帧寄存器前面。
    ----------------------------------------------------------------------------
    process (i_clk)
        variable r      : integer;
        variable prow   : integer;
        variable srow   : integer;

        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable hh     : integer;
        variable npc    : integer;
        variable rw     : std_logic_vector(7 downto 0);   -- 未使用（保留）
        variable cov    : std_logic_vector(7 downto 0);
        variable kc     : std_logic_vector(7 downto 0);
        variable tgtrow : std_logic_vector(7 downto 0);
        variable redrow : std_logic_vector(7 downto 0);
        variable selrow : std_logic_vector(7 downto 0);
        variable grnrow : std_logic_vector(7 downto 0);
        variable islck0 : boolean;
        variable bad    : std_logic;
        variable orik   : std_logic_vector(1 downto 0);   -- 本拍这块零片的朝向
        variable kk     : integer range 0 to 3;           -- 正在累加哪一块
        variable hraw   : std_logic_vector(2 downto 0);
        variable wraw   : std_logic_vector(2 downto 0);
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                frow    <= (others => '0');
                scanrow <= (others => '0');
                row_a   <= (others => '0');
                red_a   <= (others => '0');
                grn_a   <= (others => '0');
                bad_a   <= '0';
                ph      <= (others => '0');
                cov_a   <= (others => '0');
                kc_a    <= (others => '0');
                sl_a    <= (others => '0');
                row_new <= '0';
                bp      <= (others => '0');
                sp      <= (others => '0');
                op      <= '0';
            elsif (i_tick = '1') then
                r := to_integer(frow);
                if (i_level = '0') then npc := 3; else npc := 4; end if;

                if (to_integer(ph) = npc + 1) then
                    ------------------------------------------------------------
                    -- 发布相位：输入全是寄存器（cov_a/kc_a/sl_a），
                    -- 配色与整帧判据不挂在 row_mask 的组合链后面。
                    ------------------------------------------------------------
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

                    -- 整帧判据：8 行的 cov 都等于目标行 <=> 零片并集 == 目标图案
                    if (cov_a = tgtrow) then bad := '0'; else bad := '1'; end if;

                    -- 绿 = 选中块或已锁定块；红 = 覆盖格 - 选中块。
                    -- 对局态不画目标虚影。
                    redrow := cov_a and (not sl_a);
                    grnrow := kc_a or sl_a;

                    row_a   <= frow;
                    red_a   <= redrow;
                    grn_a   <= grnrow;
                    bad_a   <= bad;
                    row_new <= '1';
                    ph      <= (others => '0');
                    cov_a   <= (others => '0');
                    kc_a    <= (others => '0');
                    sl_a    <= (others => '0');

                    -- 扫描行跟随正在构建的行
                    if (frow = 7) then
                        frow <= (others => '0');
                    else
                        frow <= frow + 1;
                    end if;
                    scanrow <= frow;
                else
                    row_new <= '0';      -- 本拍不是"发布整行"那一拍

                    ------------------------------------------------------------
                    -- (a) 累加相位：消费上一拍备好的 bp/sp/op
                    ------------------------------------------------------------
                    if (to_integer(ph) >= 1) then
                        kk := to_integer(ph) - 1;
                        if (op = '1') then
                            rw := srl8(bp, to_integer(sp) - 2);
                            cov := cov_a or rw;
                            if (locked(kk) = '1') then
                                kc := kc_a or rw;
                            else
                                kc := kc_a;
                            end if;
                            if (to_integer(sel) = kk) and (locked(kk) = '0') then
                                selrow := sl_a or rw;
                            else
                                selrow := sl_a;
                            end if;
                        else
                            cov    := cov_a;
                            kc     := kc_a;
                            selrow := sl_a;
                        end if;
                        cov_a <= cov;
                        kc_a  <= kc;
                        sl_a  <= selrow;
                    end if;

                    ------------------------------------------------------------
                    -- (b) 准备相位：为下一拍算好行掩码（旋转 + 锚点补偿）
                    --     ph = 0 备第 0 块；ph = 1..npc-1 备第 ph 块。
                    ------------------------------------------------------------
                    if (to_integer(ph) <= npc - 1) then
                        case to_integer(ph) is
                            when 0 =>
                                pk := pos(31 downto 24); shp := i_sh0; orik := ori(1 downto 0);
                                hraw := i_h0; wraw := i_w0;
                            when 1 =>
                                pk := pos(23 downto 16); shp := i_sh1; orik := ori(3 downto 2);
                                hraw := i_h1; wraw := i_w1;
                            when 2 =>
                                pk := pos(15 downto 8); shp := i_sh2; orik := ori(5 downto 4);
                                hraw := i_h2; wraw := i_w2;
                            when others =>
                                pk := pos(7 downto 0); shp := i_sh3; orik := ori(7 downto 6);
                                hraw := i_h3; wraw := i_w3;
                        end case;

                        srow := r - to_integer(unsigned(pk(7 downto 4)));
                        hh := to_integer(unsigned(oh(hraw, wraw, orik)));
                        if (srow >= 0) and (srow < hh) then
                            op <= '1';
                            bp <= rot_row(shp, orik,
                                          srow + to_integer(unsigned(rot_off_r(hraw, wraw, orik))));
                            sp <= to_unsigned(to_integer(unsigned(pk(3 downto 0)))
                                              - to_integer(unsigned(rot_off_c(hraw, wraw, orik))) + 2, 4);
                        else
                            op <= '0';
                        end if;
                    end if;

                    ph <= ph + 1;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 行渲染第二拍：把第一拍算好的行并进帧，并运行整帧判据协议。
    --
    -- 拆成两拍是为了把"行掩码计算"与"帧更新 + 判据"分开：
    -- 第一拍只算一行，第二拍只做寄存器写入与比较，关键路径因此缩短。
    -- 帧头（第 0 行）拍快照 pos/level/pat，帧尾（第 7 行）发布判据；
    -- 只有整帧内这三个量都没变过，判据才可信。
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
                p_frm     <= (others => '0');
                lvl_frm   <= '0';
                pat_frm   <= (others => '0');
            elsif (i_tick = '1') then
              -- 一行要 npc+2 拍才算完；只在刚发布一行时动作
              if (row_new = '1') then
                rb := to_integer(row_a);

                if (rb = 0) then
                    -- 帧头：重启本帧的失配累加器，并快照本帧依赖的量
                    frm_bad <= bad_a;
                    p_frm   <= pos_cnt;
                    lvl_frm <= i_level;
                    pat_frm <= i_pat;
                elsif (rb = 7) then
                    -- 帧尾：只有本帧内 pos/level/pat 都没变，判据才有效
                    if (p_frm = pos_cnt) and (lvl_frm = i_level) and (pat_frm = i_pat) then
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

                -- ---- 把流水后的这一行并进帧 -------------------
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
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 主时序进程：两个严格串行化的任务
    --   (a) 散落序列器：把零片随机放置到互不重叠的位置
    --   (b) 移动 / 旋转校验：夹紧、边界判定、重叠检查
    -- 两者共用同一套重叠检查引擎。检查引擎每拍只算一个 row_mask，
    -- 因此同一时刻只有一次 row_mask 求值。
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
        variable acv    : integer range 0 to 7;   -- 正在检查的槽位的锚点列
        variable ov     : std_logic_vector(1 downto 0);  -- 邻块朝向
        variable ohv, owv : std_logic_vector(2 downto 0);  -- 邻块原始高宽
        variable rw     : std_logic_vector(7 downto 0);   -- 未使用（保留）
        variable lvl2   : boolean;   -- "不是第一关"：四块零片 / 四槽可选
        variable xr, xc : integer;                        -- 有界候选
        variable hraw, wraw : integer range 0 to 7;       -- 原始高宽（旋转前）
        variable cand_o : std_logic_vector(1 downto 0);   -- 候选朝向
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                pos <= (others => '0');
                locked <= (others => '0');
                sel <= (others => '0');
                pos_cnt <= (others => '0');
                sh <= SH_IDLE;
                sh_k <= (others => '0');
                sh_att <= (others => '0');
                mv <= '0';
                mv_pend <= '0';
                mv_go <= '0';
                mv_clamp <= (others => '0');
                mv_sel <= (others => '0');
                chk <= CH_IDLE;
                chk_sr <= (others => '0');
                chk_slot <= (others => '0');
                chk_srmax <= (others => '0');
                chk_ld <= '0';
                chk_crow <= (others => '0');
                chk_prowr <= (others => '0');
                chk_rot <= '0';
                chk_ori <= (others => '0');
                ori     <= PIECE_ORI_INIT;   -- 初始朝向非零，旋转成为必需步骤
                mv_rot  <= '0';
                rnd_step <= '0';
            else
                rnd_step <= '0';
                lvl2 := (i_level = '1');

                ----------------------------------------------------------------
                -- (1) 按键 —— 只在两个引擎都不忙时处理
                ----------------------------------------------------------------
                if (sh = SH_IDLE) and (chk = CH_IDLE) then
                    if (i_go = '1') then
                        -- 散落：清零锁定与选择，恢复初始朝向
                        sh     <= SH_TRY;
                        sh_k   <= (others => '0');
                        sh_att <= (others => '0');
                        sel    <= (others => '0');
                        locked <= (others => '0');
                        ori    <= PIECE_ORI_INIT;
                    elsif (i_confirm = '1') then
                        case to_integer(sel) is
                            when 0      => locked(0) <= '1';
                            when 1      => locked(1) <= '1';
                            when 2      => locked(2) <= '1';
                            when others => locked(3) <= '1';
                        end case;
                        -- 确认后自动跳到下一个未锁定的零片（B8）
                        sel <= next_unlocked(sel, locked, lvl2);
                    elsif (i_select = '1') then
                        -- 【选择】跳过已锁定的零片（B8）
                        sel <= next_unlocked(sel, locked, lvl2);
                    elsif (i_rot = '1') then
                        -- 【旋转】走同一套流水：方向位全 0，候选形状用"朝向 + 1"
                        mv     <= '1';
                        mv_rot <= '1';
                        mv_dir <= "0000";
                    elsif (i_move = '1') then
                        mv <= '1';
                        -- 方向必须与移动请求同一拍锁存：game_fsm 的方向位
                        -- 只与 o_move 同拍有效，晚一拍采会得到全 0。
                        mv_dir <= i_up & i_down & i_left & i_right;
                    end if;
                end if;

                ----------------------------------------------------------------
                -- (2) 移动请求启动校验引擎
                ----------------------------------------------------------------
                -- 第 1 级：锁存提议（方向已随请求一起锁存）
                if (mv = '1') and (chk = CH_IDLE) then
                    mv       <= '0';
                    mv_pend  <= '1';
                    mv_anchor<= sel_p;
                end if;

                -- 第 2a 级：夹紧到 0..7，结果落寄存器
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

                -- 第 2b 级：边界 + 锁定检查，然后启动重叠检查引擎
                if (mv_go = '1') and (chk = CH_IDLE) then
                    mv_go <= '0';

                    cr := to_integer(unsigned(mv_clamp(7 downto 4)));
                    cc := to_integer(unsigned(mv_clamp(3 downto 0)));
                    case to_integer(mv_sel) is
                        when 0      => hraw := to_integer(unsigned(i_h0)); wraw := to_integer(unsigned(i_w0));
                                       shp := i_sh0; cand_o := ori(1 downto 0);
                        when 1      => hraw := to_integer(unsigned(i_h1)); wraw := to_integer(unsigned(i_w1));
                                       shp := i_sh1; cand_o := ori(3 downto 2);
                        when 2      => hraw := to_integer(unsigned(i_h2)); wraw := to_integer(unsigned(i_w2));
                                       shp := i_sh2; cand_o := ori(5 downto 4);
                        when others => hraw := to_integer(unsigned(i_h3)); wraw := to_integer(unsigned(i_w3));
                                       shp := i_sh3; cand_o := ori(7 downto 6);
                    end case;
                    -- 旋转请求 = 同一个锚点 + 朝向 +1（90°/270° 时高宽互换）
                    if (mv_rot = '1') then
                        cand_o := ori_next(cand_o);
                        mv_rot <= '0';
                    end if;
                    if (cand_o(0) = '1') then hh := wraw; ww := hraw;
                    else                      hh := hraw; ww := wraw; end if;

                    -- 边界：解析式判定，使用旋转之后的高宽。
                    -- 转到一半转出点阵的请求直接不启动检查（等效于拒绝），
                    -- B7"不能移出 8x8"对旋转同样成立。
                    if (cr + hh <= 8) and (cc + ww <= 8)
                       and (locked(to_integer(mv_sel)) = '0') then
                        chk_pos  <= mv_clamp;
                        chk_shp  <= shp;
                        chk_ori  <= cand_o;
                        chk_h0   <= std_logic_vector(to_unsigned(hraw, 3));
                        chk_w0   <= std_logic_vector(to_unsigned(wraw, 3));
                        chk_rot  <= mv_rot;
                        chk_srmax<= to_unsigned(hh - 1, 2);
                        chk_me   <= mv_sel;
                        chk_kind <= '0';                 -- '0' = 移动（含旋转）
                        chk      <= CH_RUN;
                        chk_sr   <= (others => '0');
                        chk_slot <= (others => '0');
                        chk_ld   <= '1';                 -- 第一拍：候选本行
                        chk_hit  <= '0';
                    end if;
                end if;

                ----------------------------------------------------------------
                -- (3) 散落：逐块提出候选锚点，跑同一套重叠引擎。
                --     采用拒绝采样；重试 16 次仍失败则用确定性兜底锚点，
                --     保证散落一定能结束。
                ----------------------------------------------------------------
                if (sh = SH_TRY) and (chk = CH_IDLE) then
                    rnd_step <= '1';

                    -- 按当前朝向取包围盒，使候选范围与渲染/检查一致
                    case to_integer(sh_k) is
                        when 0      => hh := to_integer(unsigned(oh(i_h0, i_w0, ori(1 downto 0))));
                                       ww := to_integer(unsigned(ow(i_h0, i_w0, ori(1 downto 0))));
                        when 1      => hh := to_integer(unsigned(oh(i_h1, i_w1, ori(3 downto 2))));
                                       ww := to_integer(unsigned(ow(i_h1, i_w1, ori(3 downto 2))));
                        when 2      => hh := to_integer(unsigned(oh(i_h2, i_w2, ori(5 downto 4))));
                                       ww := to_integer(unsigned(ow(i_h2, i_w2, ori(5 downto 4))));
                        when others => hh := to_integer(unsigned(oh(i_h3, i_w3, ori(7 downto 6))));
                                       ww := to_integer(unsigned(ow(i_h3, i_w3, ori(7 downto 6))));
                    end case;

                    -- 合法锚点范围 0..(8-hh)，故除数为 9-hh。
                    -- 因为随机数 x 在 0..7、除数 >= 4，恒有 x < 2*ch，
                    -- 所以"x mod ch"等价于一次条件相减，避免变除数除法器。
                    ch := 9 - hh;  if (ch < 1) then ch := 1; end if;
                    cw := 9 - ww;  if (cw < 1) then cw := 1; end if;

                    -- 流水第 1 级：锁存操作数与两个取模结果
                    sc_hh   <= std_logic_vector(to_unsigned(hh, 3));
                    sc_ww   <= std_logic_vector(to_unsigned(ww, 3));
                    xr := to_integer(unsigned(rnd_val(2 downto 0)));
                    xc := to_integer(unsigned(rnd_val(5 downto 3)));
                    if (xr >= ch) then xr := xr - ch; end if;
                    if (xc >= cw) then xc := xc - cw; end if;
                    sc_cand <= std_logic_vector(to_unsigned(xr, 4)) &
                               std_logic_vector(to_unsigned(xc, 4));
                    sh <= SH_CHK;
                end if;

                ----------------------------------------------------------------
                -- 流水第 2 级：在已寄存的操作数上启动重叠检查
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
                    chk_ori <= ori(2 * to_integer(sh_k) + 1 downto 2 * to_integer(sh_k));
                    case to_integer(sh_k) is
                        when 0      => chk_h0 <= i_h0; chk_w0 <= i_w0;
                        when 1      => chk_h0 <= i_h1; chk_w0 <= i_w1;
                        when 2      => chk_h0 <= i_h2; chk_w0 <= i_w2;
                        when others => chk_h0 <= i_h3; chk_w0 <= i_w3;
                    end case;
                    chk_rot <= '0';
                    chk_srmax <= resize(unsigned(sc_hh) - 1, 2);
                    chk_me  <= sh_k;
                    chk_kind <= '1';                     -- '1' = 散落
                    chk     <= CH_RUN;
                    chk_sr  <= (others => '0');
                    chk_slot<= (others => '0');
                    chk_ld  <= '1';
                    chk_hit <= '0';
                end if;

                ----------------------------------------------------------------
                -- (4) 重叠检查引擎（串行化）
                --
                -- 一拍只算一个 row_mask：先按候选自己的行号 sr 算出候选
                -- 本行（chk_crow），随后每拍与一个邻块比较。
                -- 与"一拍并行算 5 个 row_mask"的判定结果逐条相同，
                -- 只是把并行的 4 份移位器换成时间上复用的 1 份。
                ----------------------------------------------------------------
                case chk is
                    when CH_IDLE =>
                        null;

                    when CH_RUN =>
                        if (chk_ld = '1') then
                            -- 候选自己第 chk_sr 行，搬到锚点列后的 8 位掩码
                            chk_crow <= row_mask(chk_shp, chk_h0, chk_w0, chk_ori,
                                                 to_integer(chk_sr),
                                                 to_integer(unsigned(chk_pos(3 downto 0))));
                            -- 循环不变量：候选本行落在面板第几行
                            chk_prowr <= resize(unsigned(chk_pos(7 downto 4))
                                                + chk_sr, 4);
                            chk_ld   <= '0';
                            chk_slot <= (others => '0');
                        else
                            -- 一个邻块一拍（chk_slot = 0 .. npc-1）
                            if (chk_crow /= x"00") and (chk_slot /= chk_me)
                               and ((chk_slot < 3) or lvl2) then
                                case to_integer(chk_slot) is
                                    when 0 =>
                                        prow := to_integer(unsigned(pos(31 downto 28)));
                                        acv  := to_integer(unsigned(pos(27 downto 24)));
                                        shp  := i_sh0; ohv := i_h0; owv := i_w0;
                                        ov   := ori(1 downto 0);
                                    when 1 =>
                                        prow := to_integer(unsigned(pos(23 downto 20)));
                                        acv  := to_integer(unsigned(pos(19 downto 16)));
                                        shp  := i_sh1; ohv := i_h1; owv := i_w1;
                                        ov   := ori(3 downto 2);
                                    when 2 =>
                                        prow := to_integer(unsigned(pos(15 downto 12)));
                                        acv  := to_integer(unsigned(pos(11 downto 8)));
                                        shp  := i_sh2; ohv := i_h2; owv := i_w2;
                                        ov   := ori(5 downto 4);
                                    when others =>
                                        prow := to_integer(unsigned(pos(7 downto 4)));
                                        acv  := to_integer(unsigned(pos(3 downto 0)));
                                        shp  := i_sh3; ohv := i_h3; owv := i_w3;
                                        ov   := ori(7 downto 6);
                                end case;
                                -- 邻块自己的行号 = 候选本行所在面板行 - 邻块锚点行
                                srow := to_integer(chk_prowr) - prow;
                                if (srow >= 0) and (srow <= 2) then
                                    if (chk_crow and row_mask(shp, ohv, owv, ov, srow, acv)) /= x"00" then
                                        chk_hit <= '1';
                                    end if;
                                end if;
                            end if;

                            -- 推进扫描：邻块走完 -> 候选下一行；候选行走完 -> 判定
                            if (chk_slot = 3) or ((not lvl2) and (chk_slot = 2)) then
                                chk_slot <= (others => '0');
                                if (chk_sr = chk_srmax) then
                                    chk <= CH_DONE;
                                else
                                    chk_sr <= chk_sr + 1;
                                    chk_ld <= '1';
                                end if;
                            else
                                chk_slot <= chk_slot + 1;
                            end if;
                        end if;

                    when CH_DONE =>
                        chk <= CH_IDLE;
                        if (chk_hit = '0') then
                            -- 接受：提交锚点或朝向
                            if (chk_kind = '0') then
                                if (chk_rot = '1') then
                                    -- 旋转检查通过：只提交朝向，锚点不动
                                    case to_integer(chk_me) is
                                        when 0      => ori(1 downto 0) <= ori_next(ori(1 downto 0));
                                        when 1      => ori(3 downto 2) <= ori_next(ori(3 downto 2));
                                        when 2      => ori(5 downto 4) <= ori_next(ori(5 downto 4));
                                        when others => ori(7 downto 6) <= ori_next(ori(7 downto 6));
                                    end case;
                                else
                                case to_integer(sel) is
                                    when 0      => pos(31 downto 24) <= chk_pos;
                                    when 1      => pos(23 downto 16) <= chk_pos;
                                    when 2      => pos(15 downto 8)  <= chk_pos;
                                    when others => pos(7 downto 0)   <= chk_pos;
                                end case;
                                end if;
                                pos_cnt <= pos_cnt + 1;
                            else
                                case to_integer(sh_k) is
                                    when 0      => pos(31 downto 24) <= chk_pos;
                                    when 1      => pos(23 downto 16) <= chk_pos;
                                    when 2      => pos(15 downto 8)  <= chk_pos;
                                    when others => pos(7 downto 0)   <= chk_pos;
                                end case;
                                pos_cnt <= pos_cnt + 1;
                                sh_att <= (others => '0');
                                sh     <= SH_NEXT;
                            end if;
                        else
                            if (chk_kind = '0') then
                                -- 移动被拒绝：引擎静默不改画面
                                null;
                            elsif (sh_att = 15) then
                                -- 确定性兜底，保证散落总能结束
                                sh_att <= (others => '0');
                                case to_integer(sh_k) is
                                    when 0      => pos(31 downto 24) <= "0000" & "0000";
                                    when 1      => pos(23 downto 16) <= "0000" & "0100";
                                    when 2      => pos(15 downto 8)  <= "0100" & "0000";
                                    when others => pos(7 downto 0)   <= "0100" & "0100";
                                end case;
                                pos_cnt <= pos_cnt + 1;
                                sh <= SH_NEXT;
                            else
                                -- 重试必须回到 SH_TRY 重新采样；
                                -- 留在 SH_CHK 会反复检查同一个已寄存的候选。
                                sh_att <= sh_att + 1;
                                sh     <= SH_TRY;
                            end if;
                        end if;

                    when others =>
                        chk <= CH_IDLE;
                end case;

                -- 推进到下一块零片，或结束散落
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
