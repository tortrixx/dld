/**
 * timeline.ts —— 时序与数据流的**真值表**（供「时序播放器」用）
 *
 * 每一条文字都能指到仓库里的出处；这四段时序覆盖了别人最难看懂的四件事：
 *   ① 节拍链：50 MHz 怎么变成 125 Hz 帧扫描与 25/21 Hz 内容刷新
 *   ② 一次按键：从手指按下到画面变化，中间到底经过了多少毫秒、串了几级流水
 *   ③ 一局流程：自检 → 待机 → 预览 → 对局 → 胜负，每段的时长打哪来
 *   ④ 旋转的几何：为什么"盒内转 + 补锚点偏移"是等价的，以及拒绝的条件
 *
 * ⚠️ 这里**不能凭印象写**。核实过的一处反例：早先文档/摘要里流传"引擎 i_tick 接 tick_200、
 *    所以内容刷新是 25/21 Hz"—— 源码里是 `u_puzzle.i_tick => t_1k`（rtl/puzzle_top.vhd:520），
 *    25/21 Hz 的真正来源是"一行 npc+2 拍 × 8 行 = 40/48 拍（每拍 1 ms）"（docs/02:240-248）。
 *    所以下面写的是 1 kHz + 40/48 拍，不是"接在 200 Hz 上"。
 */

/** 流水线上的一节：名字 + 一行注解（注解里带真实常量/数值）。 */
export interface FlowNode {
  readonly name: string;
  readonly sub: string;
  /** 这一节属于哪一层，用于上色（core = 决策/引擎，io = 驱动，in = 板级）。 */
  readonly kind?: 'in' | 'core' | 'io' | 'out';
}

/** 流水线上两个节点之间的箭头：箭头上的标注就是流过的信号名。 */
export interface FlowLink {
  readonly label: string;
}

export interface FlowStep {
  readonly title: string;
  readonly detail: string;
  /** 出处（仓库相对路径 + 行号，可选）。 */
  readonly cite?: string;
  /** 这一拍高亮的节点下标（对应 nodes）。 */
  readonly active: readonly number[];
  /** 这一拍正在传输的箭头下标（对应 links，长度 = nodes.length − 1）。 */
  readonly busyLinks?: readonly number[];
  /** 这一拍占多少「演示时间」（毫秒，仅影响播放节奏，不代表真实时长）。 */
  readonly holdMs: number;
  /** 真实时间刻度（显示在时间轴上，例如 "0 ms" / "40 ms"）。 */
  readonly clock?: string;
  /** 可选的量化数值条：0..1，用来直观表示"走到哪了"。 */
  readonly progress?: number;
}

export interface FlowScenario {
  readonly id: string;
  readonly title: string;
  readonly subtitle: string;
  readonly blurb: string;
  readonly nodes: readonly FlowNode[];
  readonly links: readonly FlowLink[];
  readonly steps: readonly FlowStep[];
  /** 这一场景要不要同时显示点阵/数码管「仪表」（用规则模型实算）。 */
  readonly instrument?: 'frame' | 'row' | 'none';
}

export const FLOW_SCENARIOS: readonly FlowScenario[] = [
  /* ------------------------------------------------------------------ *
   * ① 节拍链
   * ------------------------------------------------------------------ */
  {
    id: 'clocks',
    title: '节拍链',
    subtitle: '50 MHz → 125 Hz 帧扫描',
    blurb:
      '整机只有第一级面对 50 MHz：后面每一级只数上一级来的脉冲。这条链决定了"画面多久刷一遍""按键多久扫一次""倒计时多久减 1"。',
    instrument: 'row',
    nodes: [
      { name: 'clk 50 MHz', sub: 'PIN_18 · 20 ns', kind: 'in' },
      { name: '÷50 000', sub: 'CNT_1K = 49 999', kind: 'in' },
      { name: 't_1k  1 ms', sub: '1 kHz', kind: 'core' },
      { name: '÷5  /  ÷2', sub: 't_200 5 ms / t_100 10 ms', kind: 'core' },
      { name: '÷25 / ÷4', sub: 't_4hz 250 ms / t_1hz 1 s', kind: 'core' },
      { name: 'mrow 8 行', sub: '8 ms ⇒ 125 Hz 帧', kind: 'io' },
    ],
    links: [
      { label: 'clk' },
      { label: 't_1k' },
      { label: 't_200' },
      { label: 't_4hz / t_1hz' },
      { label: '行推进' },
    ],
    steps: [
      {
        title: '板级时钟进来',
        detail:
          '开发板提供 50 MHz（周期 20 ns），由 USER_BTN 选择档位；本设计假定选在 50 MHz 档，所以时序约束写的是 20 ns。',
        cite: 'quartus/puzzle.sdc · quartus/puzzle.qsf:43',
        active: [0],
        holdMs: 900,
        clock: '0 ns',
        progress: 0.05,
      },
      {
        title: '第 1 级：50 MHz → 1 kHz',
        detail:
          'CNT_1K = CLK_HZ/1000 − 1 = 49 999。这是整条链里**唯一**面对 50 MHz 的计数器，后面所有级都只数上一级来的脉冲。',
        cite: 'rtl/puzzle_pkg.vhd:388 · rtl/clk_gen.vhd:124',
        active: [1, 2],
        busyLinks: [0, 1],
        holdMs: 1000,
        clock: '1 ms',
        progress: 0.2,
      },
      {
        title: '第 2/3 级：键盘与中间时基',
        detail:
          't_1k ÷5 ⇒ t_200（5 ms，键盘扫描用它）；t_200 二分频 ⇒ t_100（10 ms，顶层没有读者，保留在链里）。',
        cite: 'rtl/puzzle_pkg.vhd:393',
        active: [3],
        busyLinks: [2],
        holdMs: 1000,
        clock: '5 ms',
        progress: 0.35,
      },
      {
        title: '第 4/5 级：闪烁与秒',
        detail:
          't_100 ÷25 ⇒ t_4hz（250 ms）：自检整屏闪、告急幽灵、结算"先闪后常亮"、以及蜂鸣器换步都借它；t_4hz ÷4 ⇒ t_1hz（1 s），倒计时每秒减 1。',
        cite: 'rtl/puzzle_pkg.vhd:399 · rtl/puzzle_pkg.vhd:407',
        active: [4],
        busyLinks: [3],
        holdMs: 1000,
        clock: '250 ms',
        progress: 0.5,
      },
      {
        title: '行推进：8 行 = 8 ms ⇒ 125 Hz',
        detail:
          '顶层的 mrow 每 t_1k 推进一行，8 行走完一屏 ⇒ 帧扫描 125 Hz、占空比 1/8。数码管位选（seg_scan.i_tick）也走 t_1k ⇒ 每位同样 125 Hz。',
        cite: 'rtl/puzzle_top.vhd:367 · docs/02-模块详细设计.md:237',
        active: [5],
        busyLinks: [4],
        holdMs: 1200,
        clock: '8 ms',
        progress: 0.72,
      },
      {
        title: '引擎同源同速（不是"接在 200 Hz 上"）',
        detail:
          'puzzle_ctrl.i_tick 也接 t_1k，所以它与点阵扫描**同源同速**；一行的渲染要 npc+2 拍（第一关 5 拍、二三关 6 拍），一帧 8 行 ⇒ 40 / 48 拍 = 40 / 48 ms，即内容刷新 25 / 21 Hz。',
        cite: 'rtl/puzzle_top.vhd:520 · docs/02-模块详细设计.md:240',
        active: [2, 5],
        busyLinks: [1, 4],
        holdMs: 1400,
        clock: '40 ms / 48 ms',
        progress: 0.9,
      },
      {
        title: '为什么不是"刷一次画一屏"',
        detail:
          '扫描率决定"闪不闪"（125 Hz 远高于临界闪烁融合约 60 Hz），内容率决定"画面多久变一次"。两者分开是**面积**决定的：早期版本把两边都放在 200 Hz，帧率只有 25 Hz，上板肉眼可见闪。',
        cite: 'docs/02-模块详细设计.md:282',
        active: [5],
        holdMs: 1400,
        clock: '125 Hz vs 25 Hz',
        progress: 1,
      },
    ],
  },

  /* ------------------------------------------------------------------ *
   * ② 一次按键
   * ------------------------------------------------------------------ */
  {
    id: 'keypress',
    title: '一次按键',
    subtitle: '按下 → 画面变化',
    blurb:
      '这是整机里**跨模块最多**的一条路：物理按键 → 扫描消抖 → 单拍脉冲 → 状态机译码 → 引擎三级流水 → 下一帧可见。也是当初最出问题的一段（ERR-020 / ERR-031 都在这）。',
    instrument: 'frame',
    nodes: [
      { name: '手指按下', sub: '机械触点抖动', kind: 'in' },
      { name: 'keypad_scan', sub: '四相扫描 @200 Hz', kind: 'io' },
      { name: '消抖 4 轮', sub: '40 ms', kind: 'io' },
      { name: 'o_press 单拍', sub: '实测 ≈45 ms', kind: 'core' },
      { name: 'game_fsm', sub: 'key_of() 译码', kind: 'core' },
      { name: '命令锁存', sub: '同拍 · 1 clk = 20 ns', kind: 'core' },
      { name: 'puzzle_ctrl', sub: '夹紧→边界→重叠', kind: 'core' },
      { name: '下一帧可见', sub: '≤ 40 / 48 ms', kind: 'out' },
    ],
    links: [
      { label: 'kp_row' },
      { label: '干净采样' },
      { label: 'o_key/o_press' },
      { label: '键号' },
      { label: '脉冲' },
      { label: 'i_up…/i_move' },
      { label: 'cov/kc/sl' },
    ],
    steps: [
      {
        title: 't = 0：触点闭合（带抖动）',
        detail:
          '廉价矩阵键盘的接触抖动典型是几毫秒量级，所以"按下一次"在电气上是一串毛刺，不能直接当按键用。',
        cite: 'rtl/puzzle_pkg.vhd:487',
        active: [0],
        holdMs: 800,
        clock: '0 ms',
        progress: 0.04,
      },
      {
        title: '四相扫描：每 10 ms 才采一个样',
        detail:
          '扫描状态机走 ALL_HIGH（等 1 个 t_200）→ ALL_LOW（**再等 1 个**）→ SETTLE(64 拍) → RELEASE（相 0 一拍 + 相 1/2/3 各 64 拍）。两个等待相各吃一个 200 Hz 周期 ⇒ **一轮 = 2 × 5 ms = 10 ms**，不是 5 ms。',
        cite: 'rtl/keypad_scan.vhd:72 · rtl/puzzle_pkg.vhd:465',
        active: [1],
        busyLinks: [0, 1],
        holdMs: 1100,
        clock: '10 ms / 轮',
        progress: 0.2,
      },
      {
        title: '消抖：4 轮 = 40 ms',
        detail:
          'DEBOUNCE_MAX = 3 ⇒ 需要 **4 个连续一致**的干净采样（样与样相隔 10 ms）才改 stable。按下→接受 = 4 轮 = 40 ms（改之前是 16 轮 = **160 ms**，用户上板反馈"防抖时间有点长"）。',
        cite: 'rtl/puzzle_pkg.vhd:477 · docs/06-硬件调试记录.md（ERR-031）',
        active: [2],
        busyLinks: [1],
        holdMs: 1300,
        clock: '40 ms',
        progress: 0.36,
      },
      {
        title: 'o_press：一个时钟宽的单拍脉冲',
        detail:
          '接受条件 = stable ≠ K_NONE 且 stable ≠ key_r，所以"按住"只发一次，"换键"当新按下。实测按下→o_press 约 45 ms（脉冲判定还读同拍旧值、再加按键落点相对扫描相位的 ≤10 ms 抖动）。',
        cite: 'rtl/keypad_scan.vhd:305 · sim/rounds/keypad_scan/r24.md 断言 ⑨',
        active: [3],
        busyLinks: [2],
        holdMs: 1100,
        clock: '≈45 ms',
        progress: 0.5,
      },
      {
        title: 'game_fsm 译码：原始键号 → 游戏键',
        detail:
          '扫描器只报"4×行＋列"的原始键号，游戏含义由 key_of() 一个函数决定（【开始】=1/KEY14、【选择】=3/KEY16、十字=10/2/5/7、中心=6、旋转=11）。',
        cite: 'rtl/game_fsm.vhd:139',
        active: [4],
        busyLinks: [3],
        holdMs: 1000,
        clock: '同拍',
        progress: 0.62,
      },
      {
        title: '命令与方向必须同拍锁存（ERR-020 的教训）',
        detail:
          '方向脉冲与移动请求都只有**一个时钟宽（20 ns）**。当初把方向锁存放在引擎流水的第二级，第 T+1 拍采方向时脉冲已经撤销 ⇒ mv_dir 恒为 0、四个方向键全部失效，而上板"看起来没事"。修法：搬进 i_move = \'1\' 那一拍。',
        cite: 'docs/06-硬件调试记录.md（ERR-020）· rtl/game_fsm.vhd:391',
        active: [5],
        busyLinks: [4],
        holdMs: 1300,
        clock: '1 clk = 20 ns',
        progress: 0.72,
      },
      {
        title: '引擎三级流水：夹紧 → 边界 → 重叠',
        detail:
          '先把锚点夹紧到 0..7，再查"旋转后包围盒装得下"，最后跑**串行**重叠引擎（一拍比一个邻块，省逻辑）。任何一级不过就整个请求作废 —— 位置不变，而且硬件上**没有提示音**（+5 LE 装不下，已回退）。',
        cite: 'rtl/puzzle_ctrl.vhd:801 · rtl/puzzle_ctrl.vhd:850',
        active: [6],
        busyLinks: [5],
        holdMs: 1300,
        clock: '数拍',
        progress: 0.85,
      },
      {
        title: '下一帧可见',
        detail:
          '位置变了不会立刻重画整屏：引擎逐行重建，一帧 40/48 拍 ⇒ 变更最多在 40/48 ms 后的那一帧里出现（观感上是"逐行滚过"的轻微涂抹，是面积换来的，不是缺陷）。',
        cite: 'docs/02-模块详细设计.md:248',
        active: [6, 7],
        busyLinks: [6],
        holdMs: 1300,
        clock: '≤ 40 / 48 ms',
        progress: 1,
      },
    ],
  },

  /* ------------------------------------------------------------------ *
   * ③ 一局流程
   * ------------------------------------------------------------------ */
  {
    id: 'match',
    title: '一局流程',
    subtitle: '自检 → 胜负',
    blurb:
      '主状态机只有 6 个状态、3 位编码。下表把每一段的时长与判据都摊开：时长全部来自题目要求或明确的取舍，判据只有两条 —— 并集等于目标图案、且全部零片已锁定。',
    instrument: 'frame',
    nodes: [
      { name: 'S_SELF_TEST', sub: '8 × 250 ms', kind: 'core' },
      { name: 'S_IDLE', sub: '等待【开始】', kind: 'core' },
      { name: 'S_PREVIEW', sub: '5 s · DISP7 倒数', kind: 'core' },
      { name: 'S_PLAYING', sub: '30 / 40 / 60 s', kind: 'core' },
      { name: 'S_WIN', sub: '绿对勾 · PASS', kind: 'out' },
      { name: 'S_FAIL', sub: '红叉 · FAIL', kind: 'out' },
    ],
    links: [
      { label: '自检完' },
      { label: 'K_START' },
      { label: '预览到点' },
      { label: 'solved / timeout' },
      { label: 'all_lock / timeout' },
    ],
    steps: [
      {
        title: '上电复位：约 9 ms',
        detail:
          'por_cnt 数 tick_1k 到 CNT_POR = T_POR_MS − 1 = 9 就释放（注释记 10 ms、实测 9 个刻度，功能无差别，注释已更正）。按键复位另走 20 ms 消抖。o_rst = 上电 or 按键。',
        cite: 'rtl/puzzle_pkg.vhd:413 · rtl/clk_gen.vhd:236',
        active: [0],
        holdMs: 900,
        clock: '≈9 ms',
        progress: 0.06,
      },
      {
        title: 'B1 自检：整屏黄 + 2 Hz，数码管 8 位全 "8"',
        detail:
          '窗口数 **8 个 t_4hz**。这是 ERR-051 的修法：旧实现数 2 个 tick_1hz，SW7 关→开重入时只走 1 s（B2 明文要求 2 s）；改数 4 Hz 之后窗口恒为 8 个旋律步，恰好含一个发声步。',
        cite: 'rtl/puzzle_pkg.vhd:423 · rtl/puzzle_pkg.vhd:442',
        active: [0],
        holdMs: 1300,
        clock: '2 s（复位路径）',
        progress: 0.18,
      },
      {
        title: 'B2 待机：点阵全灭、DISP7=5、DISP0=1',
        detail: '其余数码管位全部消隐。此时点阵不画引擎帧 —— 零片还没散落，否则会全堆在锚点 (0,0) 上。',
        cite: 'rtl/puzzle_top.vhd:731 · rtl/disp_format.vhd:117',
        active: [1],
        holdMs: 1000,
        clock: '不定长',
        progress: 0.28,
      },
      {
        title: 'B4/B10 预览：5 秒，DISP7 倒数',
        detail:
          '点阵直接画**目标图案常量**（引擎不参与），DISP7 从 5 倒数到 1；DISP0 显示当前关数。第一关恒为图 4-1；第二关恒为阶梯形；第三关从四幅库里随机选。',
        cite: 'rtl/puzzle_pkg.vhd:443 · rtl/puzzle_top.vhd:617',
        active: [2],
        busyLinks: [1],
        holdMs: 1500,
        clock: '5 s',
        progress: 0.42,
      },
      {
        title: '散落：请求/应答握手（不是单拍脉冲）',
        detail:
          '进入对局时 req_go 置起并**保持**，直到引擎报告 o_busy；go_done 保证一局只请求一次（没有它会不断反复散落、按键全部失效）。散落用拒绝采样，候选锚点范围 ch = 9 − hh、cw = 9 − ww。',
        cite: 'rtl/game_fsm.vhd:404 · rtl/puzzle_ctrl.vhd:897',
        active: [3],
        busyLinks: [2],
        holdMs: 1400,
        clock: '数十微秒',
        progress: 0.54,
      },
      {
        title: '对局：限时 30 / 40 / 60 s',
        detail:
          'DISP4:DISP3 显示两位倒计时。第一关 30 s（B5 明文）、第二关 40 s（B10 明文）、第三关 60 s（A2 扩展关，自拟）。倒计时由 t_1hz 递减。',
        cite: 'rtl/puzzle_pkg.vhd:444 · rtl/puzzle_pkg.vhd:458',
        active: [3],
        holdMs: 1300,
        clock: '30 / 40 / 60 s',
        progress: 0.66,
      },
      {
        title: '告急幽灵：≤10 s 才出现（绿 + 2 Hz 闪）',
        detail:
          '倒计时 ≤10 s 时把目标图案里**还空着**的格子用绿列 2 Hz 闪出来（借 game_fsm 自由走的 gblink，不新增计数器，代价 0 LE）。为什么不是别的颜色：双色点阵每点只有 灭/红/绿/黄 四态，而对局中三种点亮态已经被零片占满。',
        cite: 'rtl/puzzle_top.vhd:646 · docs/06-硬件调试记录.md（ERR-056）',
        active: [3],
        holdMs: 1400,
        clock: 't ≤ 10 s',
        progress: 0.78,
      },
      {
        title: '判据只有两条',
        detail:
          'o_solved = frm_ok **且** alllock_r（并集 == 目标图案、且每块都已锁定）⇒ 过关/通关；o_all_lock = alllock_r **且** 帧有效 ⇒ 全锁但画面不对，判负。超时（t_1hz 数到 0）同样判负。',
        cite: 'rtl/puzzle_ctrl.vhd:360 · rtl/game_fsm.vhd:320',
        active: [3, 4, 5],
        busyLinks: [3, 4],
        holdMs: 1500,
        clock: '瞬时',
        progress: 0.9,
      },
      {
        title: '结算画面：先闪 1 s 再常亮',
        detail:
          '胜利 = 绿色粗对勾（只点绿列）、失败 = 红色叉（只点红列），交通灯配色；数码管 DISP7..4 显示 PASS / FAIL。闪烁数 t_4hz 的 4 个半周期 = 1 s 后转常亮 —— 一直闪不利于远距离判读。',
        cite: 'rtl/puzzle_top.vhd:664 · rtl/puzzle_top.vhd:742',
        active: [4, 5],
        holdMs: 1500,
        clock: '1 s 闪 + 常亮',
        progress: 1,
      },
    ],
  },

  /* ------------------------------------------------------------------ *
   * ④ 旋转的几何
   * ------------------------------------------------------------------ */
  {
    id: 'rotate',
    title: '旋转的几何',
    subtitle: '为什么锚点不动',
    blurb:
      'A4 的 90° 旋转看着简单，但"怎么算才对、又不花钱"是这个项目里最典型的面积与正确性之争：一种写法多 229 个 LE 直接装不下，于是换成"盒内转 + 补偏移"。',
    instrument: 'frame',
    nodes: [
      { name: '选中零片', sub: 'ori 2 位/块', kind: 'core' },
      { name: '固定 3×3 盒内转', sub: '每处只要 3 个 4:1 mux', kind: 'core' },
      { name: '补锚点偏移 dr/dc', sub: '在"算行掩码"的唯一一处', kind: 'core' },
      { name: '边界检查', sub: 'cr+hh ≤ 8 且 cc+ww ≤ 8', kind: 'core' },
      { name: '重叠检查', sub: '串行逐块比对', kind: 'core' },
      { name: '接受：只改 ori', sub: '锚点一个字节都不动', kind: 'out' },
      { name: '拒绝：什么都不变', sub: '而且没有提示音', kind: 'out' },
    ],
    links: [
      { label: 'ori_next' },
      { label: '盒内坐标' },
      { label: '紧包围盒锚点' },
      { label: '旋转后高宽' },
      { label: '与邻块比较' },
      { label: '合法' },
    ],
    steps: [
      {
        title: '一次按键 = ori + 1（顺时针 90°）',
        detail:
          '每块零片一个 2 位朝向，4 次回到原样。语义是**原地顺时针 90°**：只改朝向、不动锚点。',
        cite: 'rtl/puzzle_pkg.vhd:140 · docs/00-规范理解与需求.md §1.2 A4',
        active: [0],
        holdMs: 900,
        clock: 'ori: 0→1',
        progress: 0.12,
      },
      {
        title: '在固定 3×3 盒里转（为了省面积）',
        detail:
          '盒内坐标 (r,c)：00 → in(sr,c)；01 → in(2−c, sr)；10 → in(2−sr, 2−c)；11 → in(c, 2−sr)。每个调用点只有 3 个 4:1 mux。对照组：**直接在紧包围盒里转**要算 h−1−c / w−1−c 并加范围保护，实测 **+229 LE，直接装不下**。',
        cite: 'rtl/puzzle_pkg.vhd:100 · rtl/puzzle_pkg.vhd:116',
        active: [1],
        busyLinks: [0, 1],
        holdMs: 1500,
        clock: '+0 LE',
        progress: 0.3,
      },
      {
        title: '但盒内转会把锚点"甩偏"，必须补回来',
        detail:
          '3×3 盒内转完之后，紧包围盒不再锚在 (0,0)：例如 1×3 横条转 90° 会落到盒子的第 2 列。若不补，零片一旋转就凭空横移两格、而且再也够不到左边界 —— 第一版就是这个 bug，被"旋转后仍以紧包围盒左上角为锚点"这条不变量抓出来。补法只有一个地方：盒内行号 = 紧包围盒行号 + dr，列移位 = 锚点列 − dc。',
        cite: 'rtl/puzzle_pkg.vhd:104 · rtl/puzzle_pkg.vhd:122',
        active: [2],
        busyLinks: [1, 2],
        holdMs: 1700,
        clock: '+64 LE',
        progress: 0.5,
      },
      {
        title: '边界：用的是**旋转之后**的高宽',
        detail:
          '90°/270° 时高宽互换。判据 cr + hh ≤ 8 且 cc + ww ≤ 8 —— 转到一半会越出 8×8 的请求**直接不启动检查**，等效于拒绝。B7"不能移出点阵"对旋转同样成立。',
        cite: 'rtl/puzzle_ctrl.vhd:843 · rtl/puzzle_ctrl.vhd:850',
        active: [3],
        busyLinks: [3],
        holdMs: 1300,
        clock: '解析式判定',
        progress: 0.66,
      },
      {
        title: '重叠：复用移动那一套串行引擎',
        detail:
          '旋转与移动共用同一条校验流水（所以两者的拒绝语义天然一致）。引擎一拍只算一个 row_mask、比一个邻块，用资源换面积。',
        cite: 'rtl/puzzle_ctrl.vhd:195 · rtl/puzzle_ctrl.vhd:972',
        active: [4],
        busyLinks: [4],
        holdMs: 1300,
        clock: '数拍',
        progress: 0.8,
      },
      {
        title: '接受：只改 ori；拒绝：一律不变',
        detail:
          '通过则只改朝向、锚点不动（这就是单元测试里断言的那条）。不通过则朝向与锚点都不变 —— 硬件上也**没有提示音**（实测 +5 LE、LAB 128/127 装不下，已回退留档）。',
        cite: 'rtl/puzzle_ctrl.vhd:838 · docs/05-资源利用与编译报告.md',
        active: [5, 6],
        busyLinks: [5],
        holdMs: 1400,
        clock: '0 LE',
        progress: 0.92,
      },
      {
        title: '等价性由穷举证明，不靠眼力',
        detail:
          'scripts/check_geometry.py 用**独立定义**（在紧包围盒里直接转）与 RTL 的"盒内转 + 偏移"逐块 × 逐朝向 × 逐行比对：**7 块 × 4 朝向全等**。站点的单元测试又把这份结论在浏览器模型里重算了一遍。',
        cite: 'scripts/check_geometry.py · site/src/engine/engine.test.ts',
        active: [2, 5],
        holdMs: 1600,
        clock: 'ALL CHECKS PASSED',
        progress: 1,
      },
    ],
  },
];

/** 播放器默认从哪一场景开始（"一次按键"最能把跨模块关系讲清楚）。 */
export const DEFAULT_SCENARIO = 'keypress';
