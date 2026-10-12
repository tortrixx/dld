/**
 * BlockDiagram.tsx —— 系统框图（分层带 + 编号连线）
 *
 * ⚠️ 这张图**不是示意图**：每个方框都是 `rtl/` 里真实存在的 entity，
 * 编号连线对应的信号名一律取自 `rtl/puzzle_top.vhd` 的端口关联（图注里给了行号）。
 * 模块名用源码里的名字，不自创。
 *
 * 【为什么是"分带 + 编号"而不是"一堆方框加箭头标注"】
 *   第一版按教科书那样把信号名直接写在连线上，结果在 1140×660 的画布里
 *   标签互相压字（`t_1hz/t_4hz` 压在 `state/gtime` 上、`o_sound` 压在 `puzzle_ctrl` 上），
 *   整张图读不了。现在改成：
 *     · 每一层是一条**通栏带**，带内方框等宽排列 ⇒ 不会挤；
 *     · 连线上只放一个**编号**（①…），信号名放在**图注的信号对照表**里。
 *   这样结构由图形负责、精确信号名由文字负责，两边都不将就。
 *
 * 只画主干：`puzzle_top` 里那些**没有读者**的悬空调试网
 * （`kp_raw` / `release` / `t_100` / `t_40` / `piece_n` / `sel_idx` / `pos_dbg` /
 * `lock_dbg` / `scanrow`，以及显式接 `open` 的 `o_ori`）一条都没画 ——
 * 画上去就等于声称它们在功能里有用。
 */

export interface SignalLink {
  /** 与图上的圆圈编号对应；`null` = 跨层或同层内部的连线（画成箭头会误导，所以只在表里）。 */
  readonly via: number | null;
  readonly from: string;
  readonly to: string;
  readonly signals: string;
  readonly note: string;
}

/** 连线的真值表：编号与图上的圆圈一一对应。信号名全部取自 rtl/puzzle_top.vhd。 */
export const SIGNAL_LINKS: readonly SignalLink[] = [
  {
    via: 1,
    from: '板级输入',
    to: 'clk_gen / keypad_scan',
    signals: 'clk（PIN_18）· btn（PIN_61）· sw7（PIN_125）· kp_row[3:0]（PIN_111..114）',
    note: '板级时钟、复位键、系统开关、键盘行线。sw7 同时是 seg_scan / dot_matrix_scan / buzzer_ctrl 的 i_en',
  },
  {
    via: 2,
    from: 'keypad_scan',
    to: 'game_fsm',
    signals: 'o_key[3:0] · o_press · o_release',
    note: '原始键号（4×行＋列）与单拍脉冲；键号→游戏键的译码在 game_fsm.key_of()，不在扫描器里',
  },
  {
    via: 2,
    from: 'clk_gen',
    to: 'game_fsm',
    signals: 't_1hz · t_4hz',
    note: '1 Hz 秒计数与 2 Hz 闪烁（自检整屏闪 / 告急幽灵 / 结算先闪后常亮）的来源',
  },
  {
    via: 3,
    from: 'game_fsm',
    to: 'piece_rom / pattern_rom',
    signals: 'o_level · o_lvl3 → i_level',
    note: '关卡位决定"取哪一套零片、是否从图案库里选"。同一个 o_level 也送给 puzzle_ctrl.i_level',
  },
  {
    via: 4,
    from: 'piece_rom / pattern_rom / rng_lfsr',
    to: 'puzzle_ctrl',
    signals: 'i_sh0..i_sh3 · i_h0..i_h3 · i_w0..i_w3 · i_target[63:0] · rnd_val[7:0]',
    note: '零片形状与包围盒、目标图案、随机数。这三个模块全是常量折叠 ⇒ 0 LE',
  },
  {
    via: 5,
    from: '驱动层',
    to: '板级输出',
    signals: 'dot_row[7:0] · dot_colr[7:0] · dot_colg[7:0] · seg[7:0] · cat[7:0] · buzz',
    note: '点阵行选（低有效）与红/绿列、数码管段选/位选、蜂鸣器方波',
  },
  {
    via: null,
    from: 'clk_gen',
    to: '跨层广播到各层',
    signals: 't_1k → puzzle_ctrl.i_tick / seg_scan.i_tick · t_4hz → buzzer_ctrl.i_t4',
    note: '分频链的 tick 是广播的、不是逐层传递的 —— 这正是"只有第一级面对 50 MHz"的含义',
  },
  {
    via: null,
    from: 'game_fsm',
    to: 'puzzle_ctrl（跨层）',
    signals: 'o_sel · o_move · o_conf · o_rot · o_go · o_up/o_down/o_left/o_right',
    note: '6 条命令脉冲 + 散落请求/应答握手（o_go 是电平，保持到引擎报告不忙为止）',
  },
  {
    via: null,
    from: 'puzzle_ctrl',
    to: 'rng_lfsr（跨层，双向）',
    signals: 'rnd_step（请求）→ · ← rnd_val[7:0]（返回）',
    note: 'LFSR 不接任何时钟节拍，只在被推进时走一步 —— 所以散落可复现',
  },
  {
    via: null,
    from: 'game_fsm',
    to: 'disp_format / buzzer_ctrl（跨层）',
    signals: 'o_state[2:0] · o_time[5:0] · o_blink · o_level · o_lvl3 · o_sound[3:0]',
    note: '状态、倒计时、关卡两位、2 Hz 闪烁、4 位音效码',
  },
  {
    via: null,
    from: '同层内部',
    to: '驱动层之间',
    signals: 'puzzle_ctrl.o_rowr/o_rowg[63:0] → dot_matrix_scan.i_colr/i_colg（顶层按 mrow 切行）· disp_format.o_data/o_blank → seg_scan',
    note: '引擎发布的是 64 位列平面；顶层按行号切片后交给点阵驱动，红绿两列同亮即黄',
  },
  {
    via: null,
    from: 'puzzle_ctrl',
    to: 'game_fsm（反向反馈）',
    signals: 'o_solved · o_all_lock · o_busy → i_solved / i_all_lock / i_shuf_busy',
    note: '决策侧唯一的"来自引擎的输入"：过关（并集 == 目标且全锁）、全锁但不对、以及散落忙',
  },
];

/** 编号圆圈的坐标：**只放在相邻两层之间的空隙正中**。 */
const NODES: readonly { readonly n: number; readonly x: number; readonly y: number }[] = [
  { n: 1, x: 540, y: 102 },
  { n: 2, x: 300, y: 186 },
  { n: 3, x: 780, y: 284 },
  { n: 4, x: 400, y: 380 },
  { n: 5, x: 540, y: 492 },
];

type Tone = 'io' | 'core' | 'store';

interface BoxDef {
  readonly title: string;
  readonly sub?: string;
  readonly tone?: Tone;
}

interface Band {
  readonly y: number;
  readonly h: number;
  readonly label: string;
  readonly boxes: readonly BoxDef[];
}

const ROW = { x: 24, w: 1032, gap: 12 };

/** 把 n 个方框等宽铺在通栏里（通栏宽 1032，间距 12）。 */
function span(count: number): { x: number; w: number }[] {
  const w = (ROW.w - ROW.gap * (count - 1)) / count;
  return Array.from({ length: count }, (_, i) => ({ x: ROW.x + i * (w + ROW.gap), w }));
}

const BANDS: readonly Band[] = [
  {
    y: 46,
    h: 44,
    label: '板级输入',
    boxes: [
      { title: 'clk 50 MHz', sub: 'PIN_18', tone: 'io' },
      { title: 'sw7 系统开关', sub: 'PIN_125', tone: 'io' },
      { title: 'btn 复位键', sub: 'PIN_61', tone: 'io' },
      { title: '4×4 矩阵键盘', sub: 'kp_row[3:0] · PIN_111..114', tone: 'io' },
    ],
  },
  {
    y: 124,
    h: 62,
    label: '时钟与输入',
    boxes: [
      { title: 'clk_gen', sub: '级联分频链 + 上电 / 按键复位', tone: 'io' },
      { title: 'keypad_scan', sub: '四相扫描 + 消抖（4 轮 = 40 ms）', tone: 'io' },
    ],
  },
  {
    y: 220,
    h: 62,
    label: '时间与决策',
    boxes: [{ title: 'game_fsm', sub: '流程 · 倒计时 · 关卡切换 · 键号译码 · 音效选择（3 位状态 / 6 个状态）', tone: 'core' }],
  },
  {
    y: 316,
    h: 62,
    label: '常量与随机',
    boxes: [
      { title: 'piece_rom', sub: '形状库（常量折叠 ⇒ 0 LE）', tone: 'store' },
      { title: 'pattern_rom', sub: '图案库（level = 0 时忽略下标）', tone: 'store' },
      { title: 'rng_lfsr', sub: 'x⁸+x⁶+x⁵+x⁴+1 · 周期 255', tone: 'store' },
    ],
  },
  {
    y: 412,
    h: 76,
    label: '空间引擎与输出驱动',
    boxes: [
      { title: 'puzzle_ctrl', sub: '落位 · 移动 · 旋转 · 边界 · 重叠 · 着色', tone: 'core' },
      { title: 'disp_format', sub: '状态 → 数码管内容', tone: 'io' },
      { title: 'seg_scan', sub: '8 位扫描 + 7 段译码', tone: 'io' },
      { title: 'dot_matrix_scan', sub: '8 行扫描 · 125 Hz', tone: 'io' },
      { title: 'buzzer_ctrl', sub: '8 音高 · 16 步乐句', tone: 'io' },
    ],
  },
  {
    y: 522,
    h: 56,
    label: '板级输出',
    boxes: [
      { title: 'dot_row / dot_colr / dot_colg', sub: '点阵行选（低有效）· 红列 · 绿列', tone: 'io' },
      { title: 'seg / cat', sub: '数码管段选 / 位选', tone: 'io' },
      { title: 'buzz', sub: '蜂鸣器方波 · PIN_60', tone: 'io' },
    ],
  },
];


/** 每一层的左侧竖标签。 */
function BandLabel({ y, label }: { readonly y: number; readonly label: string }): JSX.Element {
  return (
    <text className="bd-bandlabel" x={ROW.x} y={y - 6} dominantBaseline="middle">
      {label}
    </text>
  );
}

export function BlockDiagram(): JSX.Element {
  return (
    <svg
      className="blockdiagram"
      viewBox="0 0 1080 620"
      role="img"
      aria-label="puzzle_top 整机框图，按六层分带：板级输入 → 时钟与输入（clk_gen、keypad_scan）→ 时间与决策（game_fsm）→ 常量与随机（piece_rom、pattern_rom、rng_lfsr）→ 空间引擎与输出驱动（puzzle_ctrl、disp_format、seg_scan、dot_matrix_scan、buzzer_ctrl）→ 板级输出。带与带之间的编号连线对应的真实信号名见下方信号对照表。"
    >
      <defs>
        <marker id="bd-arrow" viewBox="0 0 8 8" refX="6.5" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 8 4 L 0 8 z" style={{ fill: "hsl(var(--border-strong))" }} />
        </marker>
      </defs>

      {/* 顶层边界（只描边，不填色 —— 填色会把整张图压成一块黑板） */}
      <rect className="bd-frame" x="4" y="4" width="1072" height="612" rx={0} />
      <text className="bd-frame-label" x="20" y="26">
        puzzle_top
      </text>
      <text className="bd-frame-sub" x="118" y="26">
        rtl/puzzle_top.vhd — 唯一做引脚绑定的层级
      </text>

      {/* 分层带 */}
      {BANDS.map((band) => {
        const slots = span(band.boxes.length);
        return (
          <g key={band.label}>
            <BandLabel y={band.y} label={band.label} />
            {band.boxes.map((b, i) => {
              const slot = band.boxes.length === 1 ? { x: ROW.x, w: ROW.w } : slots[i];
              const cls = b.tone === 'store' ? 'bd-box bd-box--store' : b.tone === 'core' ? 'bd-box bd-box--core' : 'bd-box';
              return (
                <g key={`${band.label}-${b.title}`}>
                  <rect className={cls} x={slot.x} y={band.y} width={slot.w} height={band.h} rx={0} />
                  <text className="bd-t" x={slot.x + 10} y={band.y + 20}>
                    {b.title}
                  </text>
                  {b.sub ? (
                    <text className="bd-port" x={slot.x + 10} y={band.y + 36}>
                      {b.sub}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </g>
        );
      })}

      {/* 编号连线：每条只是一根竖线 + 一个圆圈，信号名在图注的对照表里 */}
      {NODES.map((node) => {
        const prev = [...BANDS].reverse().find((b) => b.y < node.y);
        const next = BANDS.find((b) => b.y > node.y);
        if (!prev || !next) return null;
        const y1 = prev.y + prev.h;
        const y2 = next.y;
        return (
          <g key={node.n}>
            <line className="bd-wire" x1={node.x} y1={y1} x2={node.x} y2={y2 - 10} markerEnd="url(#bd-arrow)" />
            <circle className="bd-num-bg" cx={node.x} cy={node.y} r={9} />
            <text className="bd-num" x={node.x} y={node.y + 3.5} textAnchor="middle">
              {node.n}
            </text>
          </g>
        );
      })}

      <text className="bd-foot" x={ROW.x} y={602}>
        只画主干：顶层里未画出的调试线（kp_raw / release / t_100 / t_40 / piece_n / sel_idx / pos_dbg / lock_dbg / scanrow）与接 open 的 o_ori 一并省略。
      </text>
    </svg>
  );
}
