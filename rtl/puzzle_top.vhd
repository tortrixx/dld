library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.puzzle_pkg.ALL;

-- ============================================================================
--  puzzle_top  --  整机顶层
--  题目 4：简易拼图游戏（数字电路与逻辑设计实验）
--  器件：Altera MAX II EPM1270T144C5   工具：Quartus II 9.1   语言：VHDL
--
--  这是唯一绑定引脚的文件（与 quartus/puzzle.qsf 一起）。
--  每个子模块都用显式 component 声明与具名端口关联来实例化：
--  具名端口映射里少写或写错端口是编译错误，
--  而被省略的那个却可能悄悄留下悬空信号。
--
--  框图 <-> 代码对应关系（课程要求实际设计文档中的框图
--  与所实现的电路一致）：
--
--     S1 clk_gen          时钟分频、tick、复位
--     S2 keypad_scan      4x4 键盘扫描 + 消抖 + 按键单次触发
--     S3 game_fsm         主状态机、倒计时、关卡切换
--     S4 puzzle_ctrl      摆放 / 移动 / 锁定 / 着色引擎
--     S5 pattern_rom      完整图案 ROM
--     S5 piece_rom        零片形状 ROM
--     S5 rng_lfsr         散落用的伪随机数源
--     S6 dot_matrix_scan  8x8 双色点阵行驱动
--     S6 seg_scan         8 位数码管动态扫描 + BCD 译码
--     S6 disp_format      状态 -> 数码管内容
--     S7 buzzer_ctrl      音效
--
--  = 11 个子模块 + 本顶层，与框图完全一致。
--
--  点阵是如何驱动的
--  引擎（puzzle_ctrl）每次只发布一行显示内容 —— 8 个红位与
--  8 个绿位 —— 以及该行的行号。本文件把它变成
--  每个游戏状态下面板的彩色画面，再由 dot_matrix_scan 驱动
--  物理行。整个设计里没有任何 64 位帧缓存；
--  把整条渲染通路保持 8 位宽，正是引擎能装得下的原因。
--
--  硬件说明 —— 这 16 个 LED 是故意不用的。
--  板子把 COLG0..COLG7（点阵绿色列）接到 PIN_38..45，与 LD8..LD15
--  同一组，而 PIN_137..144 由 LD8..LD15 与 VGA 共用。驱动
--  LED 就会让点阵失去绿色，而要求 B6
--  （选中的零片变绿）正依赖这一点。题目 4 没有任何要求
--  用到这些 LED，所以故意把它们留着不用。
-- ============================================================================

entity puzzle_top is
    port (
        clk      : in  std_logic;                       -- PIN_18 板载时钟
        sw7      : in  std_logic;                       -- PIN_125，拨上 = '1'
        btn      : in  std_logic;                       -- PIN_61，BTN0 复位
        kp_row   : in  std_logic_vector(3 downto 0);    -- PIN_111..114
        kp_col   : out std_logic_vector(3 downto 0);    -- PIN_117..120
        dot_row  : out std_logic_vector(7 downto 0);    -- PIN_8..1
        dot_colr : out std_logic_vector(7 downto 0);    -- PIN_22..11
        dot_colg : out std_logic_vector(7 downto 0);    -- PIN_45..38
        seg      : out std_logic_vector(7 downto 0);    -- PIN_62..51
        cat      : out std_logic_vector(7 downto 0);    -- PIN_63..31
        buzz     : out std_logic                        -- PIN_60
    );
end entity puzzle_top;

architecture rtl of puzzle_top is

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

    component game_fsm
        port (
            i_clk       : in  std_logic;
            i_rst       : in  std_logic;
            i_sw        : in  std_logic;
            i_tick_1hz  : in  std_logic;
            i_tick_4hz  : in  std_logic;
            i_press     : in  std_logic;
            i_key       : in  std_logic_vector(3 downto 0);
            o_sel       : out std_logic;
            o_move      : out std_logic;
            o_conf      : out std_logic;
            o_go        : out std_logic;
            o_up        : out std_logic;
            o_down      : out std_logic;
            o_left      : out std_logic;
            o_right     : out std_logic;
            o_rot       : out std_logic;
            o_level     : out std_logic;
            o_lvl3      : out std_logic;
            o_state     : out std_logic_vector(2 downto 0);
            o_time      : out std_logic_vector(5 downto 0);
            o_blink     : out std_logic;
            i_solved    : in  std_logic;
            i_all_lock  : in  std_logic;
            i_shuf_busy : in  std_logic;
            o_sound     : out std_logic_vector(3 downto 0)
        );
    end component;

    component piece_rom
        port (
            i_level : in  std_logic;
            o_mask  : out mask_arr_t;
            o_h     : out dim_arr_t;
            o_w     : out dim_arr_t;
            o_n     : out std_logic_vector(2 downto 0)
        );
    end component;

    component pattern_rom
        port (
            i_level : in  std_logic;
            i_pat   : in  std_logic_vector(1 downto 0);
            o_mask  : out std_logic_vector(63 downto 0)
        );
    end component;

    component rng_lfsr
        port (
            i_clk  : in  std_logic;
            i_rst  : in  std_logic;
            i_step : in  std_logic;
            o_val  : out std_logic_vector(7 downto 0)
        );
    end component;

    component puzzle_ctrl
        port (
            i_clk     : in  std_logic;
            i_rst     : in  std_logic;
            i_tick    : in  std_logic;
            rnd_step  : out std_logic;
            rnd_val   : in  std_logic_vector(7 downto 0);
            i_level   : in  std_logic;
            i_pat     : in  std_logic_vector(1 downto 0);
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
            i_rot     : in  std_logic;
            i_up      : in  std_logic;
            i_down    : in  std_logic;
            i_left    : in  std_logic;
            i_right   : in  std_logic;
            o_ori     : out std_logic_vector(7 downto 0);
            o_solved  : out std_logic;
            o_all_lock: out std_logic;
            o_busy    : out std_logic;
            o_sel_idx : out std_logic_vector(1 downto 0);
            o_pos     : out std_logic_vector(31 downto 0);
            o_lock    : out std_logic_vector(3 downto 0);
            o_scanrow : out std_logic_vector(2 downto 0);
            o_rowr    : out std_logic_vector(63 downto 0);
            o_rowg    : out std_logic_vector(63 downto 0)
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

    component disp_format
        port (
            i_state : in  std_logic_vector(2 downto 0);
            i_level : in  std_logic;
            i_lvl3  : in  std_logic;
            i_time  : in  std_logic_vector(5 downto 0);
            i_blink : in  std_logic;
            o_data  : out std_logic_vector(31 downto 0);
            o_blank : out std_logic_vector(7 downto 0)
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

    component buzzer_ctrl
        port (
            i_clk  : in  std_logic;
            i_rst  : in  std_logic;
            i_en   : in  std_logic;
            i_sel  : in  std_logic_vector(3 downto 0);   -- A1 v2：4 位码（16 个场景）
            i_t4   : in  std_logic;
            o_buzz : out std_logic
        );
    end component;

    ----------------------------------------------------------------------------
    -- 内部连线
    ----------------------------------------------------------------------------
    signal rst      : std_logic;
    signal t_1k     : std_logic;
    signal t_200    : std_logic;
    signal t_100    : std_logic;
    signal t_4hz    : std_logic;
    signal t_1hz    : std_logic;
    signal t_40     : std_logic;

    signal key      : std_logic_vector(3 downto 0);
    signal press    : std_logic;
    signal release  : std_logic;
    signal kp_raw   : std_logic_vector(3 downto 0);

    signal sel, move, conf, go : std_logic;
    signal mv_up, mv_dn, mv_lf, mv_rt : std_logic;
    signal mv_rot   : std_logic;                     -- A4：旋转键（game_fsm -> 引擎）
    signal level    : std_logic;
    signal lvl3     : std_logic;                     -- 第三关（A2 增加关数）
    signal state    : std_logic_vector(2 downto 0);
    signal gtime    : std_logic_vector(5 downto 0);
    signal gblink   : std_logic;
    signal sound    : std_logic_vector(3 downto 0);

    signal solved   : std_logic;
    signal all_lock : std_logic;
    signal shuf_busy: std_logic;
    signal sel_idx  : std_logic_vector(1 downto 0);
    signal pos_dbg  : std_logic_vector(31 downto 0);
    signal lock_dbg : std_logic_vector(3 downto 0);
    signal scanrow  : std_logic_vector(2 downto 0);

    signal rnd_val  : std_logic_vector(7 downto 0);
    signal rnd_step : std_logic;

    signal shapes   : mask_arr_t;
    signal shape_h  : dim_arr_t;
    signal shape_w  : dim_arr_t;
    signal piece_n  : std_logic_vector(2 downto 0);
    signal tgt_mask : std_logic_vector(63 downto 0);

    -- 图案库的选择结果（进入预览时锁存：第二关**恒**为固定 PAT3、第三关随机；见下面进程）
    signal pat_sel  : std_logic_vector(1 downto 0) := L2_FIXED_PAT;
    signal state_q  : std_logic_vector(2 downto 0) := S_SELF_TEST;  -- 上一拍的状态

    -- 引擎输出：每个颜色平面一帧完整的 64 位数据
    signal eng_fr   : std_logic_vector(63 downto 0);
    signal eng_fg   : std_logic_vector(63 downto 0);

    -- 最终送给点阵驱动的行
    signal mat_r    : std_logic_vector(7 downto 0);
    signal mat_g    : std_logic_vector(7 downto 0);

    -- 结算画面（WIN/FAIL）的闪示节奏：数 2 Hz 半周期，数满后常亮
    signal endflash_cnt : unsigned(2 downto 0) := (others => '0');
    signal endflash_on  : std_logic := '0';

    ----------------------------------------------------------------------------
    -- ⭐ 2026-10-10 第 18 工作阶段：**倒计时告急时显示"目标幽灵"**（降低难度的主要手段）
    --
    -- 【为什么加这个】用户反馈"每一关我感觉难度都比较大"。查到的实证结论指向同一个根因：
    --   **预览只有 5 秒（B4 明文，不可改），之后对局中完全看不到目标图案** ——
    --   于是玩家要做的是"**回忆**"而不是"**识别**"，而人因工程里"识别远比回忆容易"
    --   （NN/g 的经典结论），无障碍设计准则也明确要求"允许在对局中提醒当前目标"
    --   （Game Accessibility Guidelines：*在对局中指示／
    --   允许提醒当前目标*，最佳实践含"长时间无进展时自动触发"）。
    --   所以**不是**把图案改简单（那会变无聊，用户明确不要），而是**在玩家卡住时把目标还给他**。
    --
    -- 【具体行为】倒计时 **≤ 10 秒** 时，把"**目标图案里还没有被零片盖住的格子**"
    --   用红列显示出来。零片本身**一点不变**（该红的红、该绿的绿、锁定的还是黄），所以：
    --     · 拼对的格子被零片盖住 ⇒ 幽灵自然消失 ⇒ **顺带成了"还差哪几格"的进度提示**；
    --     · 拼错 / 还没拼的地方会亮出来 ⇒ 最后 10 秒从"干着急"变成"看得见目标"。
    --   ⚠️ 只在**倒计时告急**时出现，不是全程常显 —— 既保留"自己解出来"的成就感，
    --      也不至于把解谜退化成"描红"（这正是用户说的"不要特别简单无聊"）。
    --
    -- 【面积】**实测 +12 LE**（`gtime <= 10` 的 6 位比较 + 每行红列一个 4 输入 LUT4；
--   见 `docs/05` §1A''''.1 的面积账，不要把它当成估算值）。
    --   这 10 LE 来自**同一轮把【确认】/【旋转】的按键音效删掉所省下的 9 LE**
    --   —— 即"把打扰背景音乐的按键音，换成真正帮玩家看见目标的提示"，是本轮最划算的一笔交换。
    ----------------------------------------------------------------------------
    signal hint_on   : std_logic := '0';
    signal hint_mask : std_logic_vector(7 downto 0) := (others => '0');

    -- 点阵驱动当前点亮的行
    signal mrow      : unsigned(2 downto 0) := (others => '0');
    signal disp_data  : std_logic_vector(31 downto 0);
    signal disp_blank : std_logic_vector(7 downto 0);

    -- 特殊状态的行数据源
    signal win_row  : std_logic_vector(7 downto 0);
    signal prev_row : std_logic_vector(7 downto 0);  -- 目标图案的行
    signal fail_row : std_logic_vector(7 downto 0);

begin

    ----------------------------------------------------------------------------
    -- 点阵行计数器。它与引擎的帧渲染器走同一个 tick：
    -- 驱动点亮当前稳定帧的第 r 行，
    -- 同时引擎为下一帧重建第 r 行。若让两者走
    -- 不同的 tick（40 Hz 扫描 vs 200 Hz 渲染），显示的行与
    -- 渲染的行就会互不相关，看起来就是闪烁。
    --
    -- ⚠️ 2026-10-08 用户反馈"点阵和数码管都闪得比较明显" —— 根因就是这里的**节拍**：
    --    原来 mrow 走 tick_200（200 Hz），8 行轮一遍 = 8×5 ms = 40 ms，
    --    帧刷新率只有 **25 Hz**，低于临界闪烁融合（LED 一般要 > 60 Hz）→ 肉眼可见闪。
    --    上一条注释说的"40 Hz 扫描 vs 200 Hz 渲染不同源"是**错行**问题，当时把两边都
    --    改成 200 Hz 消掉了错行，但帧率仍是 25 Hz，闪依旧在。
    --    现在统一改走 **tick_1k**（1 kHz）：8 行 = 8 ms → **125 Hz**；
    --    占空比仍是 1/8，亮度不变，只是不再闪。引擎渲染器（puzzle_ctrl）与
    --    数码管位选（seg_scan）**同步改成 1 kHz**，三者不再有错行问题。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                mrow <= (others => '0');
            elsif (t_1k = '1') then
                mrow <= mrow + 1;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 图案的选择点（B10 第二关固定 / A2 第三关随机；2026-10-09 第 12 工作阶段改版）
    --
    -- 时机：每次**进入 S_PREVIEW 的那一拍**（按【开始】开局，或过关后进入下一关）
    --       锁存一次，图案必须在**预览开始前**定下来。
    -- 选什么：
    --   · **第三关**（lvl3='1'，A2 新增关）→ 锁 `rnd_val` 低 2 位 → 四幅库随机选
    --     （这就是提高要求 2 的"多种拼图图案随机选择"）。散落用的随机数由
    --     puzzle_ctrl 在进入对局后继续推进**同一个** LFSR，而这里只在预览起点采样
    --     一次，所以两者互不干扰；上一局的散落已把 LFSR 推进了若干步（步数还随拒绝
    --     采样变化），故**重开一局第三关图案会变**。
    --   · **第二关**（lvl3='0'）→ 恒锁 `L2_FIXED_PAT`（PAT3 阶梯，**固定**）。
    --     B10 只说"完整拼图图案自拟"（= 设计者自定，不是题目指定），没说每局要变；
    --     "随机选择"是**提高要求 2** 的内容，所以放在第三关（详见 puzzle_pkg 的
    --     L2_FIXED_PAT 说明）。
    --   · **第一关**：i_level='0' 时 pattern_rom 恒输出图 4-1（B4 指定），pat_sel 被忽略。
    --
    -- ⚠️ pat_sel 要比 state 晚一拍才更新（state 是寄存器），这一个时钟里预览会显示
    --    上一幅图案的一行 —— 肉眼不可见（行扫描 1 ms），而且 puzzle_ctrl 的"整帧判据"
    --    同时快照了 pat（pat_frm），图案切换的那一帧会被判为"不干净"而不发布判据。
    --    ⚠️ 第二关→第三关时 `i_level` 与（若第三关恰好抽到 PAT3）`i_pat` 都可能不变，
    --       所以 puzzle_ctrl 的整帧快照**分辨不出换关**；这不影响判决：换关一定伴随
    --       一次新的散落（pos 变、locked 清零），而判决还要求 `shuf_seen='1'`
    --       （本局必须看见过散落忙态）且 `i_shuf_busy='0'` —— 见 puzzle_ctrl 的
    --       ERR-024/033 说明与 sim/tb_puzzle_top 的三关连过场景。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                state_q <= S_SELF_TEST;
                pat_sel <= L2_FIXED_PAT;
            else
                state_q <= state;
                if (state = S_PREVIEW) and (state_q /= S_PREVIEW) then
                    if (lvl3 = '1') then
                        pat_sel <= rnd_val(1 downto 0);   -- 第三关：四幅库随机（A2）
                    else
                        pat_sel <= L2_FIXED_PAT;          -- 第二关：固定 PAT3（B10）
                    end if;
                end if;
            end if;
        end if;
    end process;

    -- S1：时钟、tick、复位
    u_clk : clk_gen
        port map (
            i_clk      => clk,
            i_btn      => btn,
            o_rst      => rst,
            o_tick_1k  => t_1k,
            o_tick_200 => t_200,
            o_tick_100 => t_100,
            o_tick_2hz => open,          -- 第 16 工作阶段：game_fsm 已删 i_tick_2hz，无人读
            o_tick_4hz => t_4hz,
            o_tick_1hz => t_1hz,
            o_tick_40  => t_40
        );

    -- S2：键盘
    u_keypad : keypad_scan
        port map (
            i_clk     => clk,
            i_rst     => rst,
            i_tick    => t_200,
            i_row     => kp_row,
            o_col     => kp_col,
            o_key     => key,
            o_press   => press,
            o_release => release,
            o_raw     => kp_raw
        );

    -- S3：主状态机
    u_fsm : game_fsm
        port map (
            i_clk       => clk,
            i_rst       => rst,
            i_sw        => sw7,
            i_tick_1hz  => t_1hz,
            i_tick_4hz  => t_4hz,
            i_press     => press,
            i_key       => key,
            o_sel       => sel,
            o_move      => move,
            o_conf      => conf,
            o_go        => go,
            o_up        => mv_up,
            o_down      => mv_dn,
            o_left      => mv_lf,
            o_right     => mv_rt,
            o_rot       => mv_rot,
            o_level     => level,
            o_state     => state,
            o_time      => gtime,
            o_blink     => gblink,
            i_solved    => solved,
            i_all_lock  => all_lock,
            i_shuf_busy => shuf_busy,
            o_sound     => sound,
            o_lvl3      => lvl3
        );

    -- S5：零片形状库与完整图案
    u_pieces : piece_rom
        port map (
            i_level => level,
            o_mask  => shapes,
            o_h     => shape_h,
            o_w     => shape_w,
            o_n     => piece_n
        );

    u_pattern : pattern_rom
        port map (
            i_level => level,
            i_pat   => pat_sel,
            o_mask  => tgt_mask
        );

    -- S5：随机数源
    u_rng : rng_lfsr
        port map (
            i_clk  => clk,
            i_rst  => rst,
            i_step => rnd_step,
            o_val  => rnd_val
        );

    -- ⚠️ ERR-023：引擎**始终**拿到真实的目标图案。
    --
    -- 成功判定（ERR-021）是把拼好的画面与目标图案比较，
    -- 所以对局中把 i_target 置零会让该判定根本无法满足：
    -- 实测到的现象是"第一关拼对了、按下确认，
    -- 游戏却仍然显示十字"。
    --
    -- 早先置零的理由 —— "对局中不要把零片藏在红色
    -- 轮廓下面"（ERR-013）—— 现在已在引擎内部处理：
    -- 它干脆不画目标幽灵（见 puzzle_ctrl 的 ERR-023 说明）。
    -- 预览仍然显示完整图案，来自 tgt_mask，经 prev_row 送出。

    -- S4：拼图核心
    u_puzzle : puzzle_ctrl
        port map (
            i_clk     => clk,
            i_rst     => rst,
            i_tick    => t_1k,          -- 引擎行渲染节拍 = **1 kHz**（8 行 = 8 ms → 内容 125 Hz）
                                        -- ⚠️ 2026-10-09 第 13 工作阶段实测：把它从 200 Hz 提到
                                        -- 1 kHz 在本版是 **±0 LE**（早先那一版曾测到 +76 LE，
                                        -- 那是当时的结构），而 Fmax 反而 52.57 → 56.23 MHz。
                                        -- 现在它与点阵扫描（mrow，也走 t_1k）**同源同速**，
                                        -- 画面不会再"渲染比扫描慢一拍"。见 docs/05 §1.2。
            rnd_step  => rnd_step,
            rnd_val   => rnd_val,
            i_level   => level,
            i_pat     => pat_sel,
            i_sh0     => shapes(0),
            i_sh1     => shapes(1),
            i_sh2     => shapes(2),
            i_sh3     => shapes(3),
            i_h0      => shape_h(0),
            i_h1      => shape_h(1),
            i_h2      => shape_h(2),
            i_h3      => shape_h(3),
            i_w0      => shape_w(0),
            i_w1      => shape_w(1),
            i_w2      => shape_w(2),
            i_w3      => shape_w(3),
            i_target  => tgt_mask,
            i_go      => go,
            i_select  => sel,
            i_move    => move,
            i_confirm => conf,
            i_rot     => mv_rot,
            i_up      => mv_up,
            i_down    => mv_dn,
            i_left    => mv_lf,
            i_right   => mv_rt,
            o_ori     => open,          -- A4：仅供模块级仿真观察（顶层不引出引脚）
            o_solved  => solved,
            o_all_lock=> all_lock,
            o_busy    => shuf_busy,
            o_sel_idx => sel_idx,
            o_pos     => pos_dbg,
            o_lock    => lock_dbg,
            o_scanrow => scanrow,
            o_rowr    => eng_fr,
            o_rowg    => eng_fg
        );

    -- S6：数码管内容 + 扫描
    u_disp : disp_format
        port map (
            i_state => state,
            i_level => level,
            i_lvl3  => lvl3,
            i_time  => gtime,
            i_blink => gblink,
            o_data  => disp_data,
            o_blank => disp_blank
        );

    u_seg : seg_scan
        port map (
            i_clk    => clk,
            i_rst    => rst,
            i_tick   => t_1k,           -- 1 kHz：8 位轮一遍 = 8 ms -> 125 Hz/位
                                        -- （原来 200 Hz -> 25 Hz/位，用户反馈"数码管也闪"）
            i_en     => sw7,
            i_data   => disp_data,
            i_blank  => disp_blank,
            i_raw_en => '0',
            i_raw    => (others => '0'),
            o_seg    => seg,
            o_cat    => cat
        );

    ----------------------------------------------------------------------------
    -- 从 64 位图案里取出某一行。
    -- 用于胜利/失败画面，它们是整幅图案常量而不是
    -- 拼装出来的零片。掩码约定是位下标 = 8*row + col，
    -- 第 0 行在最上方，所以逻辑第 0 行是位 7..0。
    ----------------------------------------------------------------------------
    -- 注意切片顺序：本项目的约定是 bit = 8*row + col，所以
    -- 逻辑第 0 行是位 7..0（而不是最上面那一片）。第 0 行读 63..56
    -- 会让两幅结算画面都上下镜像显示。
    with std_logic_vector(mrow) select
        win_row <= WIN_MASK( 7 downto  0) when "000",
                   WIN_MASK(15 downto  8) when "001",
                   WIN_MASK(23 downto 16) when "010",
                   WIN_MASK(31 downto 24) when "011",
                   WIN_MASK(39 downto 32) when "100",
                   WIN_MASK(47 downto 40) when "101",
                   WIN_MASK(55 downto 48) when "110",
                   WIN_MASK(63 downto 56) when others;

    -- 预览行：完整图案，按包（package）内的约定切片，
    -- 第 0 行占据位 7..0（而不是引擎内部 MSB 在前的布局）。
    with std_logic_vector(mrow) select
        prev_row <= tgt_mask(7 downto 0)   when "000",
                    tgt_mask(15 downto 8)  when "001",
                    tgt_mask(23 downto 16) when "010",
                    tgt_mask(31 downto 24) when "011",
                    tgt_mask(39 downto 32) when "100",
                    tgt_mask(47 downto 40) when "101",
                    tgt_mask(55 downto 48) when "110",
                    tgt_mask(63 downto 56) when others;

    with std_logic_vector(mrow) select
        fail_row <= FAIL_MASK( 7 downto  0) when "000",
                    FAIL_MASK(15 downto  8) when "001",
                    FAIL_MASK(23 downto 16) when "010",
                    FAIL_MASK(31 downto 24) when "011",
                    FAIL_MASK(39 downto 32) when "100",
                    FAIL_MASK(47 downto 40) when "101",
                    FAIL_MASK(55 downto 48) when "110",
                    FAIL_MASK(63 downto 56) when others;

    ----------------------------------------------------------------------------
    -- ⭐ 第 18 工作阶段：幽灵提示的使能与"整行掩码"
    --   `gtime` 是 FSM 的倒计时寄存器（预览=5、对局=30/40/60、其它态无意义）。
    --   ⚠️ 只在 **S_PLAYING** 的显示分支里用到（见下面 mat_r 那一行），
    --      所以"待机/预览/结算态的 cnt 也可能 ≤10"不会造成任何可见影响
--      （那些分支各自强制赋值，根本不读 hint_mask）。
--      ⚠️ 本注释早先写"待机时 cnt=7"是错的：自检是**数到 cnt=0 才进待机**
--         （game_fsm），且进 S_IDLE 时不重装 cnt ⇒ 待机态 cnt=**0**。
    ----------------------------------------------------------------------------
    hint_on   <= '1' when (unsigned(gtime) <= 10) else '0';
    hint_mask <= (others => hint_on);

    ----------------------------------------------------------------------------
    -- 结算画面的闪烁节奏：先闪 **2 个 2 Hz 周期**（4 个半周期 = 1 s，抓注意力），
    -- 然后常亮（远距离读图）。离开 WIN/FAIL 立刻复位。
    --
    -- ⚠️ ERR-038（2026-10-09 第 11 工作阶段，审计发现）：原来数的是 **t_2hz**（500 ms
    --    一个脉冲），4 个脉冲 = **2 s** —— 而注释与文档都写"2 个 2 Hz 周期 = 1 s"，
    --    又是"把 tick_2hz 当 2 Hz 节拍"的 2 倍记账错误（真正的 2 Hz 半周期是 250 ms）。
    --    现在数 **t_4hz**（250 ms）：4 个半周期 = **1 s**，与文档一致。
    ----------------------------------------------------------------------------
    process (clk)
    begin
        if rising_edge(clk) then
            if (rst = '1') then
                endflash_cnt <= (others => '0');
                endflash_on  <= '0';
            elsif (state /= S_WIN) and (state /= S_FAIL) then
                endflash_cnt <= (others => '0');
                endflash_on  <= '0';
            elsif (t_4hz = '1') then
                if (endflash_cnt = 3) then
                    endflash_on <= '1';          -- 4 个 250 ms 半周期后：常亮
                else
                    endflash_cnt <= endflash_cnt + 1;
                end if;
            end if;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- 各状态下的点阵内容。
    --   SELF_TEST : 整屏黄色，以 2 Hz 闪烁   （要求 B1）
    --   WIN       : 胜利画面（**绿色**粗对勾），先闪后常亮
    --   FAIL      : 失败画面（**红色**叉），先闪后常亮
    --   其它      : 引擎渲染出的内容（预览 / 对局）
    --
    -- ⚠️ 结算画面的演进（都来自上板反馈）：
    --   2026-10-08 ① "细对勾闪得效果不好" → 换成**黄色笑脸**（细线勾不出形状）；
    --              ② 闪烁节奏改成**先闪 2 个 2 Hz 周期再常亮**（一直闪不利于远距离读图，
    --                 这是自拟改进项 S5 的原意）；自检（B1）仍无条件 2 Hz 闪。
    --   2026-10-09 ③ 上板再看，笑脸仍"不够直观" → 换回**粗红对勾**（24 格、笔画 3 格宽）：
    --                 ✓/✗ 是通用"对/错"符号，红色对勾正是中国阅卷的"答对"记号。
    --              ④ 用户再拍板：**只点绿列** → **绿色粗对勾 / 红色叉**的交通灯配色。
    --                 绿=通过、红=不通过，颜色本身就是第一判读线索（不再只靠形状区分）；
    --                 实现即 S_WIN 分支里"mat_g ← win_row、mat_r ← 全 0"一行改动。
    ----------------------------------------------------------------------------
    -- ⚠️ 2026-10-10 第 18 工作阶段（收尾审查发现）：敏感表**必须包含 `hint_mask`** ——
    --    第 739 行读它，漏列会让**仿真模型**与综合结果不一致（幽灵最多晚 1 ms 出现/消失，
    --    因为 mrow 每 1 ms 变一次会顺带重算）。Quartus 按真实组合函数综合、硬件不受影响，
    --    但"仿真里对的"是仿真能不能当证据的前提。
    process (state, gblink, endflash_on, mrow, eng_fr, eng_fg, win_row, fail_row, prev_row,
             hint_mask)
        variable lv  : std_logic;
        variable ev  : std_logic;        -- 结算画面的亮度：闪烁相位 or 常亮
        variable rw  : std_logic_vector(7 downto 0);
        variable gw  : std_logic_vector(7 downto 0);
    begin
        lv := gblink;
        ev := gblink or endflash_on;

        -- 从 64 位图案里切出驱动正在点亮的行。
        -- 位下标 = 8*row + col，第 0 行在最上，所以第 0 行是最上面那一片。
        case to_integer(mrow) is
            when 0      => rw := eng_fr(63 downto 56); gw := eng_fg(63 downto 56);
            when 1      => rw := eng_fr(55 downto 48); gw := eng_fg(55 downto 48);
            when 2      => rw := eng_fr(47 downto 40); gw := eng_fg(47 downto 40);
            when 3      => rw := eng_fr(39 downto 32); gw := eng_fg(39 downto 32);
            when 4      => rw := eng_fr(31 downto 24); gw := eng_fg(31 downto 24);
            when 5      => rw := eng_fr(23 downto 16); gw := eng_fg(23 downto 16);
            when 6      => rw := eng_fr(15 downto 8);  gw := eng_fg(15 downto 8);
            when others => rw := eng_fr(7 downto 0);   gw := eng_fg(7 downto 0);
        end case;

        if (state = S_SELF_TEST) then
            -- 整屏黄色，以 2 Hz 闪烁（要求 B1）
            mat_r <= (others => lv);
            mat_g <= (others => lv);
        elsif (state = S_IDLE) then
            -- B2：待机时点阵是全暗的。这里绝不能显示
            -- 引擎帧：零片还没有散落（散落发生在
            -- 开始对局时），否则它们会全部堆在锚点 (0,0) 上。
            mat_r <= (others => '0');
            mat_g <= (others => '0');
        elsif (state = S_PREVIEW) then
            -- B4：显示完整图案。它是包里的常量，所以直接
            -- 从目标掩码里切出来 —— 引擎不参与。
            mat_r <= prev_row;
            mat_g <= (others => '0');
        elsif (state = S_WIN) then
            -- 胜利：**绿色粗对勾**（2026-10-09 用户拍板：改成"绿对勾 / 红叉"的
            --   交通灯配色）。绿 = 通过、红 = 不通过，颜色本身就是第一判读线索，
            --   比"同色靠形状区分"更直观，也不会和失败画面混淆。
            --   实现 = 只点绿列（红列全 0）：下面两行的 mat_g 用 win_row，mat_r 清零。
            --   历史：细红对勾 → 黄笑脸 → 粗红对勾 → **粗绿对勾**。
            mat_r <= (others => '0');
            mat_g <= win_row and (ev & ev & ev & ev & ev & ev & ev & ev);
        elsif (state = S_FAIL) then
            -- 失败：**红色**粗叉（只点红列，与绿色的胜利对勾互为反色）
            mat_r <= fail_row and (ev & ev & ev & ev & ev & ev & ev & ev);
            mat_g <= (others => '0');
        else
            -- S_PLAYING：来自引擎的拼装画面
            -- ⭐ 第 18 工作阶段：倒计时告急（≤10 s）时叠加"目标幽灵" ——
            --    只画"目标里有、而零片没盖住"的格子（红列），零片本身不变。
            --    `rw`/`gw` 分别是被选中的那块（绿）与其余零片（红），所以
            --    ⚠️ 颜色与等价式的**准确写法**（第 18 工作阶段收尾审查更正，此前这里写反了）：
            --      `gw` = **选中块 ∪ 已锁定块**（绿/黄），`rw` = **其余零片**（红）——
            --      见 `puzzle_ctrl` 的 `redrow := cov and not sl` / `grnrow := locked or sl`。
            --      幽灵项 = `prev_row and not gw`，再与 `rw` 相或 ⇒
            --      **被未锁定的非选中零片占住的目标格**虽然幽灵位仍为 1，但那一格本来就被
            --      `rw` 点亮（红），所以**可见像素**恰好等于"目标格且没被零片盖住"。
            --      实现里不能写成 `not rw and not gw` —— 那会把未落在目标上的零片红列抹掉。
            --      合成一行只要 1 个 LUT4/位。
            mat_r <= rw or (prev_row and (not gw) and hint_mask);
            mat_g <= gw;
        end if;
    end process;

    ----------------------------------------------------------------------------
    -- S6：点阵驱动。
    -- i_row 来自本文件的行计数器（mrow），它按 tick_1k 推进：
    -- 8 行 = 8 ms -> **125 Hz** 帧刷新率。改版前 mrow 走 tick_200，帧率只有
    -- 25 Hz，肉眼可见闪（用户 2026-10-08 上板反馈）。
    ----------------------------------------------------------------------------
    u_dot : dot_matrix_scan
        port map (
            i_clk   => clk,
            i_rst   => rst,
            i_en    => sw7,
            i_row   => std_logic_vector(mrow),
            i_colr  => mat_r,
            i_colg  => mat_g,
            o_row   => dot_row,
            o_colr  => dot_colr,
            o_colg  => dot_colg
        );

    -- S7：声音
    u_buzz : buzzer_ctrl
        port map (
            i_clk  => clk,
            i_rst  => rst,
            i_en   => sw7,
            i_sel  => sound,
            i_t4   => t_4hz,
            o_buzz => buzz
        );

end architecture rtl;
