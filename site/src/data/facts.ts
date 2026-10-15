/**
 * facts.ts —— 本站引用的**全部**事实、数字与链接
 *
 * 纪律（与仓库 `README.md` §二 同一套）：
 *   · 每一个数字都要能指到仓库里一个**已入库**的文件。指向 `quartus/output_files/*.rpt`
 *     之类**未入库**的编译产物是无效链接（那些文件被 .gitignore 挡掉了，克隆下来不存在），
 *     所以本站一律指 `quartus/build_provenance.json`（入库的机读溯源）与 `docs/05`（入库的报告）。
 *   · 拿不到出处的说法一律不写。
 *   · 与硬件无关的推断（例如"为什么这样设计"）只写文档里明确记录过的理由。
 */

export const REPO = 'https://github.com/tortrixx/dld';
export const REPO_BRANCH = 'main';

/**
 * 生成 GitHub 上的文件链接。中文路径（比如 `docs/图/`）逐段编码，
 * 避免不同浏览器对未编码 UTF-8 路径的处理差异导致 404。
 */
export function blob(path: string, line?: number): string {
  const encoded = path
    .split('/')
    .map((seg) => encodeURIComponent(seg))
    .join('/');
  const base = `${REPO}/blob/${REPO_BRANCH}/${encoded}`;
  return line ? `${base}#L${line}` : base;
}

export function tree(path: string): string {
  const encoded = path
    .split('/')
    .map((seg) => encodeURIComponent(seg))
    .join('/');
  return `${REPO}/tree/${REPO_BRANCH}/${encoded}`;
}

/** 站点内引用的图素材：同步脚本会把它们放到 `public/figures/` 下。 */
export function figure(name: string): string {
  return `${import.meta.env.BASE_URL}figures/${name}`;
}

/* ================================================================== *
 * 项目标识
 * ================================================================== */

export const PROJECT = {
  title: '简易拼图游戏',
  subtitle: '8×8 双色 LED 点阵 · MAX II 上的纯 RTL 拼图',
  course: '数字电路与逻辑设计实验（下）· 题目 4',
  oneLiner:
    '在一块 8×8 双色点阵上玩拼图：先看 5 秒目标图案，零片随机散落，用 4×4 矩阵键盘选择、上下左右移动、必要时原地旋转 90°，把零片拼回目标形状后逐块按【确认】锁定。三关递增，第三关图案从四幅库中随机。',
  hardware: 'Altera MAX II EPM1270T144C5（144 脚 TQFP，1270 LE / 127 LAB）',
  hdl: 'VHDL-93',
  tool: 'Quartus II 9.1 Build 222（TimeQuest 时序分析）',
  board: 'MAX II 数字实验板（LCM12864 液晶版）',
  device: 'EPM1270T144C5',
} as const;

export const STACK: readonly { label: string; value: string }[] = [
  { label: '器件', value: 'MAX II EPM1270T144C5' },
  { label: 'RTL', value: 'VHDL-93 · 纯 RTL' },
  { label: '工具', value: 'Quartus II 9.1' },
  { label: '显示', value: '8×8 双色点阵（红 / 绿 / 黄）' },
  { label: '输入', value: '4×4 矩阵键盘（8 个功能键）' },
  { label: '音频', value: '蜂鸣器方波 · 8 音高 · 16 步乐句' },
];

/* ================================================================== *
 * 一、真实读数（当前固件：2026-10-15 15:13:21 清洁重编译；sha256 与 10-12 那份逐字节相同）
 * ================================================================== */

export interface Metric {
  readonly label: string;
  readonly value: string;
  readonly unit?: string;
  readonly note: string;
  readonly source: { readonly path: string; readonly line?: number; readonly note: string };
}

export const HEADLINE_METRICS: readonly Metric[] = [
  {
    label: '逻辑单元 LE',
    value: '1264',
    unit: '/ 1270',
    note: 'Fitter 报告打印 100%；项目文档按整数百分比记 99%（1264/1270 = 99.53%），余 6 个 LE —— 但"余 6 个 LE"在装箱层面约等于 0',
    source: { path: 'quartus/build_provenance.json', line: 48, note: 'fit.le' },
  },
  {
    label: 'LAB（逻辑阵列块）',
    value: '127',
    unit: '/ 127',
    note: '器件真正的瓶颈。MAX II 的 LE 只能按每个 LAB 10 个成组分配 ⇒ 余 6 LE 凑不出一个 LAB',
    source: { path: 'quartus/build_provenance.json', line: 49, note: 'fit.lab' },
  },
  {
    label: 'Fmax（TimeQuest）',
    value: '54.27',
    unit: 'MHz',
    note: '约束 50 MHz / 20 ns；0 条时序违例。Restricted Fmax 同为 54.27 MHz',
    source: { path: 'quartus/build_provenance.json', line: 53, note: 'sta.setup_slack 与 docs/05 的 Fmax 表' },
  },
  {
    label: 'Setup slack',
    value: '+1.572',
    unit: 'ns',
    note: '数据路径 18.428 ns = 约束 20 ns − 余量 1.572 ns（**反推值**：入库文件只记 slack，没记路径长度与节点名，所以这里不写路径名）',
    source: { path: 'quartus/build_provenance.json', line: 53, note: 'sta.setup_slack' },
  },
  {
    label: 'Hold slack',
    value: '+1.078',
    unit: 'ns',
    note: 'TNS 0.000；最小脉宽 slack +9.734 ns',
    source: { path: 'quartus/build_provenance.json', line: 54, note: 'sta.hold_slack' },
  },
  {
    label: '已锁定引脚',
    value: '52',
    unit: '/ 116',
    note: '52 个引脚全部显式锁定（含点阵绿列与 LD8~15 复用的取舍），未约束引脚 0',
    source: { path: 'quartus/build_provenance.json', line: 50, note: 'fit.pins' },
  },
  {
    label: '仿真断言',
    value: '184',
    unit: '条全过',
    note: '12 个模块/场景（整机两种场景各 28 条）；轮次与条数的所有者是 docs/03 §2。见下方断言分布表',
    source: { path: 'docs/03-仿真验证方案.md', note: '§2 覆盖情况总览（唯一所有者）' },
  },
  {
    label: 'Fitter seed',
    value: 'SEED 8',
    note: '第 9 次在 seed 1~16 里重扫，筛选条件是"装得进 127 LAB 且 ≥ 50 MHz"',
    source: { path: 'quartus/puzzle.qsf', line: 40, note: 'set_global_assignment -name SEED 8' },
  },
];

export const BUILD_PROVENANCE = {
  timestamp: '2026-10-15 16:59:42',
  gitHead: 'c6c5f6a7',
  quartus: 'Quartus II 9.1 Build 222 10/21/2009 SJ Full Version',
  pofBytes: 27312,
  pofMtime: '2026-10-15 15:13:21',
  pofSha256: 'cc3c69b3419f40a20eaf310eb3259d25ff342b56f3b0d52ab270a6ca7e41aea3',
  clockConstraint: 'create_clock -name clk -period 20.000 → 50 MHz / 20 ns',
  ioDelay: 'set_input_delay / set_output_delay 各 5.000 ns（外设全是慢速人机接口器件）',
} as const;

/* ------------------------------------------------------------------ *
 * 仿真覆盖（docs/03 §2 是这张表的"所有者"）
 * ------------------------------------------------------------------ */

export interface SimRow {
  readonly module: string;
  readonly round: string;
  readonly assertions: number;
  readonly note: string;
}

export const SIM_COVERAGE: readonly SimRow[] = [
  { module: 'puzzle_top', round: 'r56 / r57', assertions: 28, note: '整机模式 A / B 各 28 条（三关流程、胜负画面、幽灵、音效链路；① 已加强为"每位槽段码集合同时含 0x7F 与 0x00"）' },
  { module: 'game_fsm', round: 'r36', assertions: 30, note: '主状态机与倒计时、关卡切换、命令译码' },
  { module: 'puzzle_ctrl', round: 'r37', assertions: 28, note: '引擎：重叠判定、选中/锁定、旋转、整帧判据（含 ⑳ 主路径竞态；该轮"RTL 补丁：无"）' },
  { module: 'buzzer_ctrl', round: 'r37', assertions: 16, note: '音高表、方波计数、16 步乐句' },
  { module: 'disp_format', round: 'r27', assertions: 16, note: '状态 → 数码管内容；含口径 C 的 DISP2 全局熄灭钉子与 ⑦b（t=0..63 全表逐项）' },
  { module: 'seg_scan', round: 'r31', assertions: 12, note: '位选扫描与 7 段译码（含 A/P/S/F/L 字母、⑧b en 压过 raw_en）' },
  { module: 'clk_gen', round: 'r25', assertions: 10, note: '分频链与复位计数' },
  { module: 'piece_rom', round: 'r23', assertions: 10, note: '形状库与包围盒、每关零片数' },
  { module: 'keypad_scan', round: 'r27', assertions: 9, note: '四相扫描 + 消抖 40 ms' },
  { module: 'rng_lfsr', round: 'r23', assertions: 10, note: 'x⁸+x⁶+x⁵+x⁴+1，周期 255；⑩ 跑开后复位回 SEED_DEFAULT' },
  { module: 'pattern_rom', round: 'r21', assertions: 8, note: '图案库按 i_pat 查表' },
  { module: 'dot_matrix_scan', round: 'r23', assertions: 7, note: '8 行扫描与行序；⑤b 早采样点（+20 ns）无混合态' },
];

export const SIM_TOTAL_ASSERTIONS = 184;

export const EXTRA_CHECKS: readonly { name: string; result: string; what: string; path: string }[] = [
  {
    name: 'check_geometry.py',
    result: 'ALL CHECKS PASSED',
    what: '把四幅图案 + 第一关矩形 + 7 块零片做**穷举**：目标 == 零片并集、四块精确铺法的数量、旋转必需性（删掉旋转就拼不出来）、RTL 的"盒内转 + 偏移"与独立参考模型逐格全等、胜负画面方向不镜像',
    path: 'scripts/check_geometry.py',
  },
  {
    name: 'check_plans.py',
    result: 'ALL PLAN CHECKS PASSED',
    what: '用带旋转的 A* 从零重解四份走法计划（19 / 34 / 24 / 30 条按键），并验证删掉全部 rot 命令后无解',
    path: 'scripts/check_plans.py',
  },
  {
    name: 'audit_evidence.py',
    result: '0 FAIL / 1 WARN / 31 OK（git 干净树下；脏树时 30 OK）',
    what: '证据链审计：文档里的每个数字是否都能在入库文件里找到。唯一那条 WARN 是"LAB 已满 127/127"——这是事实，不是缺陷',
    path: 'scripts/audit_evidence.py',
  },
];

/* ================================================================== *
 * 二、系统架构：真实模块（名字全部取自 rtl/，未自创）
 * ================================================================== */

export interface ModuleRow {
  readonly file: string;
  readonly entity: string;
  readonly role: '设计模块' | '整机顶层' | '包' | '诊断顶层';
  readonly job: string;
  /** 输入（人话）。 */
  readonly consumes: string;
  /** 输出（人话）。 */
  readonly produces: string;
  /** 关键机制（带真实常量/数值）。 */
  readonly mechanism: string;
  readonly tier: 'io' | 'core' | 'store' | 'top';
}

export const MODULES: readonly ModuleRow[] = [
  /**
   * ⚠️ 顶层也要算在里面：仓库 README 的口径是
   * "16 个 VHDL 源文件（**12 个设计模块** + 3 个诊断顶层 + 1 个包）"，
   * 这 12 个**包含 puzzle_top 自己**。早先这张表只列了 11 个子模块、
   * 还写着"整机顶层不在这 12 个里"，与全站"12 个设计模块"的说法自相矛盾 ——
   * 被 `smoke.test.ts` 的"12 张卡"断言抓出来（11 ≠ 12）。
   */
  {
    file: 'rtl/puzzle_top.vhd',
    entity: 'puzzle_top',
    role: '整机顶层',
    job: '唯一做引脚绑定的层级；把 11 个子模块连成整机',
    consumes: '板级时钟 / SW7 / 复位键 / 矩阵键盘行线',
    produces: '键盘列驱动、点阵行与红绿列、数码管段选与位选、蜂鸣器',
    mechanism:
      '按状态决定点阵画什么（自检整屏黄 2 Hz、待机全灭、预览画目标图案、对局画引擎帧 + 告急幽灵、结算画绿对勾/红叉），并在**进入预览那一拍**锁存第三关的随机图案下标、按 mrow 把引擎的 64 位列平面切成一行',
    tier: 'top',
  },
  {
    file: 'rtl/clk_gen.vhd',
    entity: 'clk_gen',
    role: '设计模块',
    job: '时钟分频链、上电复位与按键复位',
    consumes: '板级 50 MHz（PIN_18）、复位按键 BTN0',
    produces: '7 路 tick（1k / 200 / 100 / 2 / 4 / 1 / 40 Hz）与高有效复位 o_rst',
    mechanism:
      '级联分频链，只有第 1 级面对 50 MHz：CNT_1K = 49999 → 1 kHz；÷5 → 200 Hz；二分频 → 100 Hz；÷25 → 4 Hz（2 Hz / 1 Hz 由它派生）；40 Hz 供诊断顶层。上电复位实测约 9 ms，按键复位消抖 20 ms',
    tier: 'io',
  },
  {
    file: 'rtl/keypad_scan.vhd',
    entity: 'keypad_scan',
    role: '设计模块',
    job: '4×4 矩阵键盘扫描 + 消抖',
    consumes: '4 条行线（低有效为按下）、200 Hz 节拍',
    produces: '列驱动、原始键号（4×行＋列）、单拍 o_press / o_release',
    mechanism:
      '四相扫描 FSM（ALL_HIGH → ALL_LOW → SETTLE → RELEASE）；一轮扫描 = 2 个 tick_200 = 10 ms；DEBOUNCE_MAX = 3 ⇒ 4 轮 = 40 ms。必须恰好一行被拉低才报键，否则报"无键"（避免合成鬼键）',
    tier: 'io',
  },
  {
    file: 'rtl/dot_matrix_scan.vhd',
    entity: 'dot_matrix_scan',
    role: '设计模块',
    job: '8×8 双色点阵的行扫描译码与输出寄存',
    consumes: '逻辑行号、该行的红/绿两个位平面',
    produces: '行选（低有效）、红列与绿列驱动',
    mechanism:
      '模块内部没有计数器：扫描率完全由调用方的 i_row 节拍决定。整机里 8 行 = 8 ms ⇒ 帧扫描 125 Hz、占空比 1/8。红绿两平面直通、不强制互斥 ⇒ 同亮即黄（双色点阵每点只有 灭/红/绿/黄 4 态）',
    tier: 'io',
  },
  {
    file: 'rtl/seg_scan.vhd',
    entity: 'seg_scan',
    role: '设计模块',
    job: '8 位数码管动态扫描与 7 段译码',
    consumes: '8×4 位 BCD 数据包、逐位消隐掩码、1 kHz 位选节拍',
    produces: '段线（高有效）与 8 条共阴极位选（低有效）',
    mechanism:
      '每拍推一位（1 ms/位）⇒ 8 位一轮 = 8 ms ⇒ 每位刷新 125 Hz；译码用完整字面量查表，含 A / P / S / F / L 五个字母（S 与 5 同形、I 用 1 的形状，7 段管固有局限）',
    tier: 'io',
  },
  {
    file: 'rtl/game_fsm.vhd',
    entity: 'game_fsm',
    role: '设计模块',
    job: '主状态机：流程、倒计时、关卡切换、键号译码、音效选择',
    consumes: 'SW7、按键单拍脉冲与键号、1 Hz / 4 Hz 节拍、引擎的 solved / all_lock / shuf_busy',
    produces: '6 条命令脉冲 + o_go 电平握手、状态码、倒计时、关卡两位、2 Hz 闪烁、4 位音效码',
    mechanism:
      '3 位状态编码（SELF_TEST / IDLE / PREVIEW / PLAYING / WIN / FAIL）。自检窗口数 8 个 tick_4hz（倒计数，修掉"SW7 重入只有 1 s"的 ERR-051）；预览 5 s；限时 30 / 40 / 60 s；过关链 一关→二关→三关→胜利；散落用请求/应答握手，go_done 保证每局只请求一次',
    tier: 'core',
  },
  {
    file: 'rtl/puzzle_ctrl.vhd',
    entity: 'puzzle_ctrl',
    role: '设计模块',
    job: '拼图引擎：落位、移动、旋转、边界、精确重叠、锁定与着色',
    consumes: '散落/选择/移动/确认/旋转命令、零片形状与包围盒、目标图案、随机数、行渲染节拍',
    produces: '64 位红/绿帧、锚点、朝向、锁定标志、solved / all_lock / busy',
    mechanism:
      '**行扫描渲染器**：不存 64 位占位，每拍只算一行，把组合路径压到 8 位（ph 相位机 + srl8 移位）。配色 redrow := cov and (not sl)、grnrow := kc or sl。重叠检查串行化（一拍比一个邻块）。⭐ **面积 861 LC 是"全设计最大的一块"这一层级的当轮快照**（来源：本机 `quartus/output_files/puzzle.map.rpt` 的层次面积表 —— **构建产物，未入库**，克隆下来不存在，故不作为可点的出处；当前整机读数见 `quartus/build_provenance.json` / `docs/05`，逐模块层次面积在 `docs/05` §1.1/§1.3 里只有部分模块的部分阶段）',
    tier: 'core',
  },
  {
    file: 'rtl/pattern_rom.vhd',
    entity: 'pattern_rom',
    role: '设计模块',
    job: '完整图案查找表',
    consumes: '关卡位、图案库下标',
    produces: '64 位目标图案掩码',
    mechanism:
      '纯组合。level = 0 时恒为第一关图 4-1（忽略下标）；否则从四幅库 L2_PATS[0..3] 中选。常量被综合器完全折叠 ⇒ 0 LE',
    tier: 'store',
  },
  {
    file: 'rtl/piece_rom.vhd',
    entity: 'piece_rom',
    role: '设计模块',
    job: '零片形状查找表',
    consumes: '关卡位',
    produces: '一次给出全部 4 块的形状掩码、包围盒高/宽、本关零片数',
    mechanism:
      '第一关 3 块（3 / 6 / 3 格，共 12 格）、第二三关 4 块异形（3 / 2 / 5 / 6 格，共 16 格）；所有形状都装进 3×3（PIECE_MAX_DIM）——这是"只扫 3×3 邻域"能成立的前提。0 LE',
    tier: 'store',
  },
  {
    file: 'rtl/rng_lfsr.vhd',
    entity: 'rng_lfsr',
    role: '设计模块',
    job: '8 位伪随机源',
    consumes: 'i_step（推进一步）',
    produces: '8 位伪随机值',
    mechanism:
      '最大长度 LFSR：x⁸+x⁶+x⁵+x⁴+1，fb := sr(7) xor sr(5) xor sr(4) xor sr(3)，周期 255。**不接任何时钟节拍**，只在被推进时走一步 ⇒ 散落可复现；种子 0x5A，含防全零兜底',
    tier: 'store',
  },
  {
    file: 'rtl/disp_format.vhd',
    entity: 'disp_format',
    role: '设计模块',
    job: '把游戏状态翻译成数码管内容',
    consumes: '状态码、关卡两位、倒计时秒数、2 Hz 闪烁标志',
    produces: '8×4 位 BCD 数据包与逐位消隐掩码',
    mechanism:
      '纯组合、不存状态。自检全 8；待机 DISP7=5 / DISP0=1；预览 DISP7=倒计时；对局 DISP4:DISP3=两位倒计时；结算 DISP7..4 = PASS / FAIL。两位拆分用 64 项查表**刻意避开 /10 与 mod 10 的除法器**。DISP2 全程不赋值（口径 C）',
    tier: 'io',
  },
  {
    file: 'rtl/buzzer_ctrl.vhd',
    entity: 'buzzer_ctrl',
    role: '设计模块',
    job: '提示音效与背景音乐',
    consumes: '4 位音效码、4 Hz 节拍、使能',
    produces: '蜂鸣器方波（PIN_60）',
    mechanism:
      '÷256 预分频 ⇒ 195.3125 kHz 时间基准；8 个音高查表（E5…G6，半周期 148…62 拍）；16 步、每步 250 ms 的乐句（4 s 循环）；对局期间默认播背景曲，按键一律静音（用户明确要求）',
    tier: 'io',
  },
];

export const TOP_LEVEL = {
  entity: 'puzzle_top',
  file: 'rtl/puzzle_top.vhd',
  job: '唯一做引脚绑定的层级；把 11 个子模块连成整机',
  detail:
    '按状态决定点阵内容（自检整屏黄 2 Hz、待机全灭、预览画目标、对局画引擎帧 + 告急幽灵、结算画绿对勾/红叉），并在**进入预览那一拍**锁存第三关的随机图案下标。',
} as const;

export const DIAG_TOPS: readonly { entity: string; file: string; when: string; what: string }[] = [
  {
    entity: 'board_test_top',
    file: 'rtl/board_test_top.vhd',
    when: '上板第一步：烧进去先确认引脚级假设（位序 / 极性 / 键盘 / 时钟档位）',
    what: '只实例化 clk_gen / keypad_scan / dot_matrix_scan / seg_scan；自带 500 Hz 蜂鸣器方波（`rtl/board_test_top.vhd` 第 700~701 行在 `t_1k` 的**单拍脉冲**上翻转 `buzz_r`，`rtl/clk_gen.vhd` 每 1 ms 给一个该脉冲 ⇒ 半周期 1 ms ⇒ **500 Hz** 方波；与 ERR-038 同类的"2 倍算错"）；测试序号每 3 s 自动前进、BTN0 短按冻结（RTL 的 `test_idx` 是 **4 位：15→0 回绕，共 16 槽**；其中 **0~10 有定义** —— 第 26 工作阶段新增测试 10「CAT」：8 位数码管各显示自己的位号，读出位选顺序）',
  },
  {
    entity: 'keypad_diag_top',
    file: 'rtl/keypad_diag_top.vhd',
    when: '需要把"原始键号 ↔ 游戏键"一一对照时',
    what: '数码管显示原始键号、按下计数、已见键数、译码后的游戏键，以及实时行线状态。键位表就是靠它 + 手册附图 26 重排到右下 3×3 标准十字的',
  },
  {
    entity: 'keypad_raw_top',
    file: 'rtl/keypad_raw_top.vhd',
    when: '键盘电气验证',
    what: '把四列全部拉低，四条行线实时直显 ⇒ 不依赖扫描时序，只验电气连接',
  },
];

/* ------------------------------------------------------------------ *
 * 时钟拓扑
 * ------------------------------------------------------------------ */

export interface TickRow {
  readonly name: string;
  readonly freq: string;
  readonly period: string;
  readonly used: string;
}

export const CLOCK_TICKS: readonly TickRow[] = [
  { name: 't_1k', freq: '1 kHz', period: '1 ms', used: '点阵行推进（8 行 = 8 ms ⇒ 125 Hz）、puzzle_ctrl 行渲染、seg_scan 位选' },
  { name: 't_200', freq: '200 Hz', period: '5 ms', used: '矩阵键盘扫描（一轮 = 2 个 tick = 10 ms）' },
  { name: 't_100', freq: '100 Hz', period: '10 ms', used: '中间级（整机顶层无读者，保留在分频链里）' },
  { name: 't_2hz', freq: '2 Hz', period: '500 ms', used: '整机顶层接 open（无读者）；board_test_top 的自检画面用它' },
  { name: 't_4hz', freq: '4 Hz', period: '250 ms', used: '2 Hz 方波（自检整屏闪 / 告急幽灵 / 结算先闪后常亮）、自检窗口 8 拍、蜂鸣器换步' },
  { name: 't_1hz', freq: '1 Hz', period: '1 s', used: '倒计时秒递减（预览 5 s、对局 30/40/60 s）' },
  { name: 't_40', freq: '40 Hz', period: '25 ms', used: '仅供诊断顶层逐行推进点阵' },
];

/* ================================================================== *
 * 三、工程案例（问题 → 约束 → 方案 → 验证 → 结果 → 局限）
 * ================================================================== */

export interface Case {
  readonly slug: string;
  readonly err: string;
  readonly title: string;
  readonly problem: string;
  readonly constraint: string;
  readonly solution: string;
  readonly verification: string;
  readonly result: string;
  readonly limitation: string;
  readonly doc: { readonly path: string; readonly note: string };
}

export const CASES: readonly Case[] = [
  {
    slug: 'rotation-necessity',
    err: 'ERR-043',
    title: '把"旋转"从可选功能变成通关必需的一步（代价 0 LE）',
    problem:
      '功能做完了、仿真也全绿，但用户上板后问："旋转 90 度效果倒是有，但是旋转好像对游戏并没有什么影响，不旋转也能成功通关。"',
    constraint:
      '四块零片开局朝向全是 0°，而四幅图案本来就是用"只许平移"的铺法搜索解出来的 ⇒ **保证存在一条一次都不转的通关路线**。器件当时已经 1268 / 1270 LE，任何修法都必须接近 0 LE。',
    solution:
      '在 puzzle_pkg 里新增 PIECE_ORI_INIT = "10" & "10" & "01" & "01"（四块开局朝向 1 / 1 / 2 / 2），puzzle_ctrl 在复位与散落时装载它（原来是全 0）。同一个向量对一、二、三关都成立，不需要按关卡选 mux。',
    verification:
      '① check_geometry.py 新增"旋转必需性"一节：保持初始朝向、只许平移 ⇒ 对第一关矩形与四幅图案**无一有精确覆盖**；允许旋转 ⇒ 都仍可解（不是死局）。② check_plans.py 用带旋转的 A* 从零重解四份走法计划（19 / 34 / 24 / 30 条按键），删掉全部 rot 命令就无解。③ 整机仿真按真实键盘按下 KEY8，朝向单调 +1、锚点不动。',
    result: '代价 0 LE（常量换常量）。三关都变成"不转就拼不出来"。',
    limitation:
      '穷举证明的是"**至少有一块**必须被转过"，不能说成"每一块都必须被玩家转过一次"——对 (1,1,2,2) 逐块复核过，PAT0/PAT1/PAT3 都存在"某一块保持初始朝向、其余三块自由旋转"的铺法，只有 PAT2 是四块都得转。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '§15.2（ERR-043）' },
  },
  {
    slug: 'srl8-shift-direction',
    err: 'ERR-019',
    title: '移位方向反了：几何正确性 vs 243 个逻辑单元',
    problem:
      '仿真断言（64 格逐格着色比对）实测"选中的零片一格都没画出来"（红 0 绿 0）。上板完全看不出来 —— 预览画面是直接把图案常量画出来的，根本不经过这条移位。',
    constraint:
      '器件只有 1270 LE，起点 958 / 1270。错误的左移会把低列格子推出边界，锚点列 ≥ 3 的整片逻辑被综合器常量折叠剪掉 —— 也就是说"面积小"本身是 bug 的副产品。',
    solution:
      'srl8 由 v := \'0\' & r(7 downto 1)（左移）改成 r(6 downto 0) & \'0\'（右移）。还试过"位序反转 + 左移 + 再反转"的等价写法，实测同样 1201 LE ⇒ 代价来自方向正确本身，不是写法问题。',
    verification:
      'puzzle_ctrl 断言 ⑧：整帧 64 格与**独立**的参考模型一致（选中零片 6 格纯绿、已锁定 3 格黄）。该轮记录"断言 ⑧ 全部 64 格一致"。',
    result: '958 → 1201 LE（95%），Fmax 42.24 → 41.39 MHz。把方向改回错误写法立刻回到 967 LE。',
    limitation:
      '文档明确写着"绝不能为了面积好看而保留这个 bug"。这 243 LE 的差不能反过来当成"修坏了"——它本来就是被折叠掉的假面积。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '第 2 阶段（ERR-019）' },
  },
  {
    slug: 'one-cycle-pulse-contract',
    err: 'ERR-020',
    title: '1 拍脉冲跨了流水线：四个方向键全部失效',
    problem:
      '上板验收时 B1/B2/B4/B5/B6 全部正常，但四个方向键按下去零片一动不动 —— 而且连"被拒绝"的表现都没有。',
    constraint:
      'game_fsm 的方向脉冲与移动请求是**同拍、各一个时钟**（约 20 ns）的脉冲；而 puzzle_ctrl 把方向锁存放到了移动请求流水的第二级，第 T+1 拍才采方向时，脉冲已经撤销 ⇒ mv_dir 恒为 0，移动退化成"原地重算"。',
    solution:
      '把方向与移动请求改成**同一拍锁存**（mv_dir <= i_up & i_down & i_left & i_right 搬进 i_move = \'1\' 那一拍），流水线只保留锚点的寄存 —— 面积与时序收益一点都不损失。',
    verification:
      '先加了一条**与键位映射无关**的协议判据：只要 FSM 发出方向脉冲，引擎必须在同拍或其后 2 拍内锁进非 0 方向。整机仿真断言 ⑧（方向协议不变量，4 次脉冲全部满足）与断言 ⑨（候选锚点确实出现过与当前不同的值，说明"夹紧 + 边界/重叠判定"真的参与了）。',
    result: '+1 LE（1202 LE），Fmax 保持 41.39 MHz；重烧后四个方向键与确认键现场验收全部正常。',
    limitation:
      '当时 puzzle_ctrl 的测试台把方向电平多保持 10 拍，**掩盖了**这个缺陷 —— 只有走真实时序的整机测试台才能覆盖"跨模块握手假设"。这条教训后来成了"整机 tb 必须存在"的理由。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '§3（ERR-020）' },
  },
  {
    slug: 'debounce-timing',
    err: 'ERR-031',
    title: '消抖时长被注释少算一倍：160 ms → 40 ms',
    problem:
      '用户上板反馈"按键的防抖时间有点长了…是否可以缩短一点时间使其更灵敏"。而注释与两份文档都写"16 轮 = 80 ms"。',
    constraint:
      '一轮扫描 = ALL_HIGH（等 1 个 tick_200）→ ALL_LOW（**再等 1 个**）→ SETTLE(64 拍) → RELEASE(相 0 一拍 + 相 1/2/3 各 64 拍 = 193 拍) ⇒ 一轮 = **2 × 5 ms = 10 ms**，不是 5 ms。所以 16 轮真实是 160 ms：按下要 160 ms 才被接受、松开也要 160 ms，连按最快约 3 次/秒。改这个常量会平移整机测试台的**全部**按键计划窗口。',
    solution:
      'DEBOUNCE_MAX 由 15 改成 3（4 轮 = 40 ms），注释改成实测结论；整机测试台引入 DB_ROUNDS = 4 / DB_SHIFT = 16 − 4 = 12，把每个按键按下起点整体后移 12 轮 ⇒ **接受时刻与改前逐轮一致**，其余时间常量一个都不用改；键盘测试台新增一条断言把时长本身钉死。',
    verification:
      '键盘断言 ⑦（短按 3 轮 < 消抖 4 轮，不产生 o_press）与断言 ⑨（消抖 = 4 个连续相同采样 = 40 ms 板上；实测 o_press 在 11T、o_release 在 63T，T = 8 µs 仿真 = 5 ms 板上）；整机测试台同步保持全绿。',
    result: '40 ms（按下 → 接受实测约 45 ms，原来约 165 ms）；连按上限提高到约 12 次/秒。',
    limitation:
      '改之前只有"短按被丢弃"这类相对判据，所以 80 / 160 ms 的矛盾**一直没触发任何红灯** —— 这类"注释与实现差一倍"的错误只有把时长本身写成断言才防得住。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '§9.2（ERR-031）' },
  },
  {
    slug: 'divider-and-pipeline',
    err: 'ERR-032 / ERR-033',
    title: '一个变除数除法器把 Fmax 从 44.77 打到 36.68 MHz',
    problem:
      '第二关零片从"四块一模一样的 2×2 方块"换成三种大小、四种形状之后，整机 Fmax 从 44.77 掉到 **36.68 MHz**（最差 slack −7.265 ns、TNS −926 ns），而综合出来的单元只多了 4 个。',
    constraint:
      '原来四块都是 2×2，散落用的 ch = 8 − hh 是**常量** 6，被综合器折叠成 LUT；异形让 ch / cw 随零片变化（5/6/7，由块号选择）⇒ Quartus 真的实例化了两个**变除数 lpm_divide**（各 38 个单元 + 长进位链）。而且这是**逻辑深度**问题，不是布局运气，重跑 seed 救不回来。',
    solution:
      '两步：① 用"x ∈ 0..7 且 ch ≥ 4 ⟹ x mod ch ≡ (x ≥ ch ? x − ch : x)"的**比较 + 条件相减**替掉取模 —— 候选序列逐拍完全相同，是等价改写；② 先把渲染切成两拍流水切断最长路径，再打开 AUTO_RESOURCE_SHARING ON，让渲染器和重叠检查引擎共用同一套 row_mask / srl8。',
    verification:
      '6 个配置**全部真编译量过**（map → fit → sta，一次约 10 秒）：1242 LE / 44.77 MHz；1246 / 36.68；1254 / 50.06（slack +0.023 ns）；1199 / 44.97（×2）；1200 / 51.44 MHz。反向对照：**直接**打开资源复用会让最差路径从 +0.023 变成 −2.714 ns、Fmax 掉到 44.03 ⇒ 证明"先流水再复用"的顺序是必需的，不是巧合。',
    result: '36.68 → 50.06 → 51.44 MHz（slack +0.561 ns，**首次满足 50 MHz 约束**），同时净省 54 LE。',
    limitation:
      '负结果也留档：对**旧的** 2×2 版本做同样的条件相减是 −1.7 MHz / +12 LE（取模本来就被折叠了，优化只在除数真的变化时才有意义）。另外讲义推荐的 Optimization Technique = Area 在 Quartus II 9.1 上**对本器件无效**（map 报告仍为 Balanced）。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '§10.3–§10.4（ERR-032 / ERR-033）' },
  },
  {
    slug: 'lab-not-le',
    err: 'ERR-046',
    title: '真正的瓶颈是 127 个 LAB，不是 1270 个 LE',
    problem:
      '音效内容升级后真编译：**1267 / 1270 LE（99.8%）却"装不下"**。报错说的不是逻辑单元不够，而是 LAB 需要 128~129 个、器件只有 127 个。',
    constraint:
      'MAX II 的 LE **只能按每个 LAB 10 个 LE 成组分配** ⇒ "剩下 3 个 LE"凑不出一个 LAB，**在装箱层面等于 0**。这条约束解释了后面所有取舍：为什么移动/旋转的拒绝音效（+5 LE）装不下、为什么"红/绿交替"幽灵（+10 LE）装不下。',
    solution:
      '① 删掉**自加的**"最后 5 秒提醒"分支（常量与乐句都保留，只是不再产生该音效码）；② 对 fitter seed 做 1~16 的重扫，发现**只有 3 / 5 / 7 / 8 能装进 127 LAB**，其中 seed 7 时序最好；③ 把 seed 固定写进工程生成脚本，从此 qsf 的这一行由脚本产出，不手工改。',
    verification:
      '清洁重编译对照：复用上一次 quartus/db 直接编译会读到 +0.108 ns（旧库残留、不可信）；删掉 db / output_files / incremental_db 重建之后才是 +1.261 ns ≈ 53.4 MHz 的真实读数。这条"必须清洁重编译"的纪律就是这一步定下来的。',
    result: '1263 / 1270 LE、LAB 127/127、setup +1.261 ns、hold +1.078 ns、0 errors。',
    limitation:
      '4 条装箱负结果留档（换写法对调 → 需 128 LAB；AND-NOT 编码 → 能装但 Fmax 48.41 MHz；寄存"当前曲目"→ 1272 LE；16 个音高 → +3 LE）。而且**旧 seed 的结论只对那一版 RTL 成立**：现在 seed 8 才是当前值。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '§16.3（ERR-046）' },
  },
  {
    slug: 'four-states-only',
    err: 'ERR-056',
    title: '双色点阵只有 4 种状态：于是"换颜色"改成"加时间维度"',
    problem:
      '用户第二次上板复测："≤10 秒的『目标幽灵』…未拼好部分显示出的『幽灵』显示为**与拼好零片一样的红色**，这种效果非常不好。"',
    constraint:
      '点阵驱动只有红列 / 绿列两组（i_colr / i_colg）⇒ 每个点只有 **灭 / 红 / 绿 / 黄** 4 种可能。而对局中这三种点亮状态**已经全部被零片占满**：未锁定 = 红、选中的 = 绿、已锁定的 = 黄 ⇒ 用户要求的"排除红绿黄之后换一种颜色"在硬件上只剩"灭"，等于看不见。面积侧同时被 1268 / 1270 LE、LAB 127/127 挤住。',
    solution:
      '幽灵改成**绿列 + 2 Hz 闪烁**：mat_r <= rw；mat_g <= gw or (prev_row and (not rw) and hint_mask)。hint_mask = hint_on and gblink，直接借用 game_fsm 已有的 2 Hz 方波、**不新增计数器**。并且**减掉 rw**：否则被未锁定零片盖住的格子会红 + 绿 ⇒ 变成"黄闪"，那是假提示。',
    verification:
      '方案选型用**真编译**否掉了两条更花哨的做法："红/绿交替"实测 +10 LE（fit 1268 → 1278，Quartus 原文："Design contains 1278 blocks of type logic cell, device contains only 1270"）。判据侧把单点采样改成**跨相位窗口取并集**（窗口 0.480 ms ≥ 2 Hz 半周期 0.400 ms）：① 确实在闪 ② 会变的格子**全部**落在目标图案里（实测 12 个）③ 每个会变的格子遇到过的状态集合**恰好**是 {(0,0) 灭, (0,1) 绿} —— 不是红、也不是黄 ④ 跳变 1~3 次。另有一条阈值钉子：倒计时 = 11 时目标格必须全灭。',
    result: '改法**实测 0 额外 LE**（一进一出正好打平，多出来的 1 个 LUT4 被 fitter 吸收），整机仍 1268 / 1270、LAB 127/127。',
    limitation:
      '断言只能证"在闪 + 只闪绿 + 只出现在目标格 + 频率量级对"，**证不了亮/灭各占 50%**（那需要更长窗口；50% 由 gblink 的定义保证，另一支测试台有断言）。',
    doc: { path: 'docs/06-硬件调试记录.md', note: '§22（ERR-056）' },
  },
];

/* ================================================================== *
 * 四、诚实的局限
 * ================================================================== */

export interface Limitation {
  readonly title: string;
  readonly detail: string;
  readonly source: string;
}

export const LIMITATIONS: readonly Limitation[] = [
  {
    title: 'LAB 已满 127 / 127',
    detail:
      'LE 只剩 6 个，而 MAX II 的 LE 只能按每 LAB 10 个成组分配 ⇒ 余量在装箱层面约等于 0。再加任何功能都必须先腾出 LAB。证据审计脚本唯一的一条 WARN 就是这一条 —— 它是事实，不是缺陷。',
    source: 'quartus/build_provenance.json · docs/05 §1.5',
  },
  {
    title: 'A3「方向随机」有意只做一半',
    detail:
      '零片位置随机做了；**开局朝向随机不做**。理由：A4 的旋转已经实现，玩家可以自己把零片转成任意朝向，"方向"在玩法上已经完备；而且开局朝向现在承担着"旋转必需"的职责（PIECE_ORI_INIT）。若改成随机，四份走法计划会全部失效，需要按随机朝向用带旋转的 A* 重解一遍，收益不抵工作量。',
    source: 'docs/00 §1.2 A3',
  },
  {
    title: '引擎内容更新率是 25 / 21 Hz（扫描是 125 Hz）',
    detail:
      '显示**扫描**已经是 125 Hz（点阵 8 行 = 8 ms；数码管每拍一位、1 ms/位，8 位一轮 = 8 ms ⇒ 125 Hz/位）。引擎 `puzzle_ctrl.i_tick` 接 **t_1k（1 kHz）**，但一行要渲染 `npc+2` 拍（第一关 5 拍、二三关 6 拍）⇒ 一帧 40 / 48 拍 = **40 / 48 ms**，即内容刷新 25 / 21 Hz。所以移动零片后，画面逐行重建、最多约 40 / 48 ms 后完全更新（观感上是轻微"滚过"）。**把这 40/48 ms 再压下去要再加流水线，而收益只是"更快一点点"、面积却已到顶** —— 这是面积与观感的取舍，不是缺陷。（⚠️ 早先这里写过"消除要 +76 LE"：那是第 11 工作阶段的受控实验数字，`docs/02` 已明确标注**结论已被取代**，不应当作现状引用。）',
    source: 'docs/02-模块详细设计.md:237-248 · rtl/puzzle_top.vhd:526',
  },
  {
    title: '没有重叠检查的极端散落分支（ERR-018b，未修）',
    detail:
      '拒绝采样连续 16 次冲突后会启用硬编码的兜底锚点，而那几个锚点**不做重叠检查**，理论上可能与别的零片的随机落位重叠。触发条件是连续 16 次随机冲突（概率约 1e-7 量级），且需要用户明确拒绝为角例改硬件；测试台已用极端激励（随机数恒 12）复现并留档。',
    source: 'docs/06（ERR-018b） · sim/rounds/puzzle_ctrl/r34.md 断言 ⑯',
  },
  {
    title: '被拒绝的移动 / 旋转没有声音反馈',
    detail:
      '这个功能**做完了**，实测 +5 LE：整机 1268 → 1273 LE、LAB 需求 128/127 ⇒ 装不下，于是回退。⚠️ **但音效码与乐句并没有"原样保留、将来一键接回"**：`puzzle_pkg` 里**没有 `SND_NAK`**（旧码位 `1101` 已改作 `SND_SEL`），`buzzer_ctrl` 里也**没有 `1101` 的查表臂**（落入 `when others` ⇒ 整句静音）⇒ 将来腾出面积要接回，得**重新加常量 + 乐句 + 查表臂**。另外"对局中按键一律静音、只留背景音乐"是**用户明确要求**，不是遗漏。',
    source: 'docs/05 · docs/06（ERR-055 相关） · rtl/game_fsm.vhd:485-490 · rtl/puzzle_pkg.vhd:577 · rtl/buzzer_ctrl.vhd:435-467',
  },
  {
    title: '音效"好不好听"离线验不了',
    detail:
      '仿真只能证明"发的是哪个音效码、这一步响不响、三关的背景曲确实是三首不同的曲子、音区与换音次数确实不同"。真正的区分度只能上板听 —— 而且真的出过事：有一轮提示音在测试台 16 / 16 全绿的情况下被耳朵判负，后来按"音区 × 轮廓方向 × 长度"三元相反重做。当前状态：用户上板复测结论为"现在的提示音效果非常好"。',
    source: 'docs/06 §21（ERR-055）· §22',
  },
  {
    title: '12 张 Quartus GUI 实测波形图已入库',
    detail:
      '报告用的"实测仿真截图"必须以 Quartus 界面截图为准（带工程名、节点表、时间刻度），脚本画的矢量波形只能当辅助对照。**12 张 `docs/图/GUI-*.png` 已全部入库**（2026-10-15 拍摄，逐张对应关系与用途由 `docs/图/README.md` 拥有）；`docs/图/SIM-*.svg` 是脚本渲染的辅助图，不是实测截图。',
    source: 'docs/图/README.md §2',
  },
  {
    title: '诊断顶层 BTN0 的松手抖动未做消抖',
    detail:
      '`board_test_top` 的"短按 BTN0 冻结 / 长按复位"靠 `clk_gen` 的 20 ms 复位滤波分开，但**没有对 BTN0 的松手抖动做消抖**（只保留两级同步器）⇒ 一次松手抖动可能被当成多次"松手沿"、把冻结状态来回切。彻底修需在该顶层加 4~8 个寄存器的消抖，当时判定超出范围、未加 —— 这只影响诊断顶层的手感，不影响主固件与游戏逻辑。',
    source: 'HANDOFF.md · docs/06 §11（ERR-039 相关）',
  },
  {
    title: '两条已知但未补的测试台覆盖缺口',
    detail:
      '深审列出、当时未动：(a) `tb_game_fsm` 的自检窗口判据对**相位**仍有依赖（只覆盖了与 1 Hz 网格错开 700 ns 的一种相位）；(b) `tb_keypad_scan` 的扫描相窗口只在有限几个相位上取样。两条都不影响已有结论，但"没覆盖到的相位"不等于"没问题"。',
    source: 'HANDOFF.md · .tmp 深审结论（2026-10-15）',
  },
];

/* ================================================================== *
 * 五、文档与源码导航
 * ================================================================== */

export interface DocEntry {
  readonly path: string;
  readonly title: string;
  readonly summary: string;
  readonly tag: string;
}

export const DOC_ENTRIES: readonly DocEntry[] = [
  {
    path: 'docs/00-规范理解与需求.md',
    title: '00 · 规范理解与需求',
    summary:
      '从三份课程 PDF 逐条摘取的规范理解稿，是所有设计与代码的上位依据：基本要求 B1~B11、提高要求 A1~A5、隐藏约束 H1~H9、待确认问题的裁定记录。',
    tag: '需求',
  },
  {
    path: 'docs/02-模块详细设计.md',
    title: '02 · 模块详细设计',
    summary: '每个模块的设计说明，框图与代码逐条对账；含状态机编码、数据通路、面积取舍的推导过程。',
    tag: '设计',
  },
  {
    path: 'docs/03-仿真验证方案.md',
    title: '03 · 仿真验证方案',
    summary:
      '验证方案与覆盖总览的**所有者**（12 个模块/场景、184 条断言）：每条断言在验什么、怎么激励、边界条件怎么造、波形图在哪。',
    tag: '验证',
  },
  {
    path: 'docs/05-资源利用与编译报告.md',
    title: '05 · 资源利用与编译报告',
    summary:
      '资源利用率、时序、引脚与打包过程的完整记录，含 seed 重扫对照表与"为什么瓶颈是 LAB 而不是 LE"。当前读数：1264 / 1270 LE、127 / 127 LAB、54.27 MHz、setup +1.572 ns。',
    tag: '证据',
  },
  {
    path: 'docs/06-硬件调试记录.md',
    title: '06 · 硬件调试记录',
    summary:
      'ERR-001 ~ ERR-056 的完整账本：每一条都有现象、根因、修法、验证与残余。本站"工程案例"一节的原始出处。',
    tag: '调试',
  },
  {
    path: 'docs/图/README.md',
    title: 'docs/图 · 图目录索引与截图流程',
    summary:
      '图清单的所有者。明确区分"Quartus GUI 实测截图"（GUI-*.png，报告里只能用这一组）与"脚本渲染的辅助波形"（SIM-*.svg），并写清拍图流程与"必须裁掉带用户名的标题栏"这条纪律。',
    tag: '图',
  },
  {
    path: 'AI_LOG.md',
    title: 'AI_LOG · AI 工具使用记录',
    summary: 'AI 工具在哪些环节被使用、哪些结论被人纠正过 —— 课程评分表里专门有一项是这一条。',
    tag: '过程',
  },
  {
    path: 'HANDOFF.md',
    title: 'HANDOFF · 交接与操作手册',
    summary: '怎么编译 / 仿真 / 烧录、开工清单、逐项上板验收清单、已知残余与历次复核记录。',
    tag: '操作',
  },
  {
    path: 'PROGRESS.md',
    title: 'PROGRESS · 进度账本',
    summary: '逐工作阶段的进度、口径变更与验收矩阵，用来回答"这一条到底是什么时候、为什么这么定的"。',
    tag: '过程',
  },
];

export interface SourceEntry {
  readonly path: string;
  readonly title: string;
  readonly summary: string;
}

export const SOURCE_ENTRIES: readonly SourceEntry[] = [
  { path: 'rtl/', title: 'rtl/ · 16 个 VHDL 源文件', summary: '12 个设计模块 + 3 个诊断顶层 + 1 个包（puzzle_pkg）。整机顶层 puzzle_top 是唯一做引脚绑定的文件。' },
  { path: 'sim/tb_puzzle_top.py', title: 'sim/tb_puzzle_top.py', summary: '整机测试台：三关完整流程、真实矩阵键号、胜负画面、幽灵提示与音效链路（28 条断言）。' },
  { path: 'sim/tb_puzzle_ctrl.py', title: 'sim/tb_puzzle_ctrl.py', summary: '引擎测试台：重叠判定、选中/锁定、旋转、整帧判据（28 条断言，含 ⑳ 主路径竞态）。' },
  { path: 'sim/rounds/', title: 'sim/rounds/ · 仿真轮次记录', summary: '每一轮的机读 JSON + 人读 Markdown：断言明细、实测值、RTL 指纹、波形指纹。当前全绿的那一轮就是"当前证据"。' },
  { path: 'sim/puzzle_top.vwf', title: 'sim/*.vwf · 12 份波形文件', summary: 'Quartus 内置仿真器会把结果**回写进激励文件本身** ⇒ 这些 .vwf 既是激励也是结果，是入库的交付物。' },
  { path: 'scripts/check_geometry.py', title: 'scripts/check_geometry.py', summary: '几何穷举证明：图案 == 零片并集、精确铺法数量、旋转必需性、旋转实现与独立参考模型逐格全等。' },
  { path: 'scripts/audit_evidence.py', title: 'scripts/audit_evidence.py', summary: '证据链审计：文档里的每个数字是否都能在入库文件里找到。当前 0 FAIL / 1 WARN / 31 OK（git 干净树下；脏树时 30 OK，差的正是 F 段"工作树干净"那一条）。' },
  { path: 'quartus/build_provenance.json', title: 'quartus/build_provenance.json', summary: '入库的机读溯源：RTL 逐文件哈希 + 逻辑指纹、固件 sha256、LE / LAB / 引脚、setup / hold slack。这是所有资源与时序数字的**唯一真值源**。' },
];

/* ------------------------------------------------------------------ *
 * 五、图表用的数据（全部来自入库文件，页面只负责画）
 * ------------------------------------------------------------------ */

/**
 * 资源与时序的**演进**（历史读数，**不是当前值**）。
 *
 * ⚠️ 图上必须标"历史演进"，否则会被读成"现在是这样"。每个点都在
 * `docs/05-资源利用与编译报告.md` 里能查到（行号见 point.note）。
 * 这条线想说明的是：**面积是反复撞上限撞出来的** —— 中间 Fmax 掉到 36.68 MHz
 * 又爬回 51.44，LE 从 958 一路加到 1268 再回落到 1264。
 */
export const RESOURCE_EVOLUTION = [
  {
    label: 'v1 初始',
    le: 958,
    fmax: 42.24,
    note: '早期版本：四块 2x2 方块的阶段（docs/05:604-607）',
  },
  {
    label: '修正移位方向',
    le: 1201,
    fmax: 41.39,
    note: 'ERR-019：把 srl8 的方向改对之后 958 → 1201 LE；Fmax 42.24 → 41.39 MHz（docs/05:542/607）',
  },
  {
    label: '异形零片',
    le: 1246,
    fmax: 36.68,
    note: 'ERR-032 之前：换成异形零片后真的实例化了两个变除数除法器，Fmax 掉到 36.68 MHz（docs/05:474）',
  },
  {
    label: '条件相减',
    le: 1254,
    fmax: 50.06,
    note: 'ERR-032：用"比较 + 条件相减"替掉取模 ⇒ 50.06 MHz，但余量只剩 +0.023 ns（docs/05:475）',
  },
  {
    label: '两拍流水 + 资源复用',
    le: 1200,
    fmax: 51.44,
    note: 'ERR-033：先切两拍流水再打开 AUTO_RESOURCE_SHARING ⇒ 1200 LE / 51.44 MHz，净省 54 LE（docs/05:477）',
  },
  {
    label: '功能补齐',
    le: 1268,
    fmax: 54.34,
    note: '第 22 工作阶段：幽灵改绿 + 2 Hz 闪等改动后的读数（docs/05:21/278）',
  },
  {
    label: '当前',
    le: 1264,
    fmax: 54.27,
    note: '2026-10-15 清洁重编译（逐字节复现 10-12 那份固件）：1264 / 1270 LE、LAB 127/127、setup +1.572 ns（build_provenance.json / docs/05:11-12）',
  },
] as const;

/* ================================================================== *
 * 六、部署与本地运行
 * ================================================================== */

/** 线上地址（已部署并通过实测，见 DEPLOY.status）。 */
export const SITE_URL = 'https://tortrixx.github.io/dld/';

export const DEPLOY = {
  local: [
    'cd site',
    'npm install',
    'npm run dev        # http://localhost:5173/dld/',
    'npm run test       # 规则模型的单元测试',
    'npm run build      # 产物在 site/dist/',
    'npm run preview    # 本地预览构建产物',
  ],
  pages: [
    '# 仓库 Settings → Pages → Source 选 "GitHub Actions"',
    '# 推送到 main 后 .github/workflows/pages.yml 自动构建并发布 site/',
    '# 线上地址：https://tortrixx.github.io/dld/',
  ],
  baseNote:
    '项目级 Pages 的站点挂在 /dld/ 子路径下，所以 vite.config.ts 里 build 的 base 默认就是 /dld/，源码里所有资源引用都走 import.meta.env.BASE_URL，**不写死 / ** ⇒ 刷新子路径也不会 404。换成用户级 Pages 或别的仓库名时不用改代码：VITE_BASE=/ npm run build。',
  status:
    '2026-10-12 首次部署成功：workflow 每一步（安装依赖 → 单元测试 → **事实对账** → 构建 → 上传 → 发布）全部 success；线上 index.html 的标题与资源路径均为 /dld/ 前缀，CSS / JS / 图素材逐个抓到 200 且内容类型正确；**并用 browser-check 对线上地址跑过一遍完整检查**（交互生效、无控制台报错、无横向溢出、锚点全命中、对比度达标）。线上的 JS/CSS 文件名哈希与本地验证过的构建**逐字节同源**，即"线上跑的就是测过的那一版"。',
} as const;
