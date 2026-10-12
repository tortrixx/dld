/**
 * geometry.ts —— 拼图几何真值表
 *
 * 这里每一个数都**不是手抄的**，而是由仓库自身的解码器从 RTL 常量里抽出来的：
 *
 *   · 形状 / 图案 / 胜负画面：`rtl/puzzle_pkg.vhd` 的 64 位常量，按该文件
 *     自己的约定 `bit = 8*row + col`（行 0 在最低 8 位）逐位解码；
 *     解码方式与 `scripts/check_geometry.py` 的 `cells_xy()` 完全一致
 *     （那份脚本是独立实现，还被 `docs/02` §9.2 用作穷举证明的基础）。
 *   · 初始朝向：`PIECE_ORI_INIT := "10" & "10" & "01" & "01"`
 *     ⇒ 块 0/1/2/3 = 1 / 1 / 2 / 2。
 *   · 每行一个字节，bit c = 第 c 列（列 0 在最左），行 0 在最上。
 *
 * ⚠️ 不要手改这里的数字。改 RTL 之后请重新解码（`site/README.md` 有解码命令），
 *    否则网页上的图案就会和板子上跑的对不上 —— 那正是本项目最忌讳的一类错误。
 */

/** 8 行掩码，每行一个字节；bit c = 第 c 列，行 0 在最上。 */
export type Mask = readonly number[];

export interface Cell {
  readonly r: number;
  readonly c: number;
}

export type Orientation = 0 | 1 | 2 | 3;

export interface ShapeDef {
  /** RTL 里那个常量的名字（用作本站的稳定 id，不另起名字）。 */
  readonly id: string;
  /** 归一化到自身紧包围盒左上角 = (0,0) 的格子集合。 */
  readonly cells: readonly Cell[];
}

/* ------------------------------------------------------------------ *
 * 零片形状（相对掩码；原点在紧包围盒左上角）
 * ------------------------------------------------------------------ */

/** 第一关 P1：1×3 横条，3 格。（`rtl/puzzle_pkg.vhd` L1_P0） */
export const L1_P0: ShapeDef = {
  id: 'L1_P0',
  cells: [
    { r: 0, c: 0 },
    { r: 0, c: 1 },
    { r: 0, c: 2 },
  ],
};

/** 第一关 P2：3-2-1 阶梯形，6 格。（L1_P1） */
export const L1_P1: ShapeDef = {
  id: 'L1_P1',
  cells: [
    { r: 0, c: 0 },
    { r: 0, c: 1 },
    { r: 0, c: 2 },
    { r: 1, c: 0 },
    { r: 1, c: 1 },
    { r: 2, c: 0 },
  ],
};

/** 第一关 P3：L 形三格块，占其 2×2 包围盒的 (0,1)(1,0)(1,1)。（L1_P2） */
export const L1_P2: ShapeDef = {
  id: 'L1_P2',
  cells: [
    { r: 0, c: 1 },
    { r: 1, c: 0 },
    { r: 1, c: 1 },
  ],
};

/** 第二/三关 Q0：1×3 横条，3 格。（L2_P0） */
export const L2_P0: ShapeDef = {
  id: 'L2_P0',
  cells: [
    { r: 0, c: 0 },
    { r: 0, c: 1 },
    { r: 0, c: 2 },
  ],
};

/** 第二/三关 Q1：1×2 竖条，2 格。（L2_P1） */
export const L2_P1: ShapeDef = {
  id: 'L2_P1',
  cells: [
    { r: 0, c: 0 },
    { r: 1, c: 0 },
  ],
};

/** 第二/三关 Q2：J 形，5 格。（L2_P2） */
export const L2_P2: ShapeDef = {
  id: 'L2_P2',
  cells: [
    { r: 0, c: 0 },
    { r: 0, c: 1 },
    { r: 0, c: 2 },
    { r: 1, c: 2 },
    { r: 2, c: 2 },
  ],
};

/** 第二/三关 Q3：六格块，6 格。（L2_P3） */
export const L2_P3: ShapeDef = {
  id: 'L2_P3',
  cells: [
    { r: 0, c: 0 },
    { r: 1, c: 0 },
    { r: 1, c: 1 },
    { r: 1, c: 2 },
    { r: 2, c: 1 },
    { r: 2, c: 2 },
  ],
};

export const SHAPES: Record<string, ShapeDef> = { L1_P0, L1_P1, L1_P2, L2_P0, L2_P1, L2_P2, L2_P3 };

/* ------------------------------------------------------------------ *
 * 目标图案
 * ------------------------------------------------------------------ */

export interface PatternDef {
  /** 常量名（稳定 id）。 */
  readonly id: string;
  /** 站内展示用的短名 —— 只用于标题，几何一律以掩码为准。 */
  readonly label: string;
  readonly mask: Mask;
  readonly cells: number;
}

/** 第一关 = 图 4-1：4 行 × 3 列实心矩形，占第 2..5 行 / 第 2..4 列，12 格。（L1_TARGET_MASK） */
export const L1_TARGET: PatternDef = {
  id: 'L1_TARGET_MASK',
  label: '图 4-1 · 4×3 实心矩形',
  mask: [0, 0, 28, 28, 28, 28, 0, 0],
  cells: 12,
};

export const L2_PATS: readonly PatternDef[] = [
  { id: 'L2_PAT0', label: '田 · 4×4 实心方块', mask: [0, 0, 60, 60, 60, 60, 0, 0], cells: 16 },
  { id: 'L2_PAT1', label: '十 · 胖十字', mask: [0, 0, 28, 62, 62, 28, 0, 0], cells: 16 },
  { id: 'L2_PAT2', label: 'S/Z · 锯齿', mask: [0, 0, 30, 120, 120, 30, 0, 0], cells: 16 },
  { id: 'L2_PAT3', label: '阶梯形', mask: [0, 0, 30, 62, 60, 56, 0, 0], cells: 16 },
];

/** 第二关的固定图案 = 图案库第 3 幅（`L2_FIXED_PAT = "11"`）。 */
export const L2_FIXED_PAT_INDEX = 3;

/** 结算画面（S5 自拟）：胜利 = 绿色粗对勾，失败 = 红色叉（互为反色的交通灯配色）。 */
export const WIN_MASK: Mask = [128, 192, 224, 112, 49, 27, 31, 14];
export const FAIL_MASK: Mask = [0, 195, 102, 60, 60, 102, 195, 0];

/* ------------------------------------------------------------------ *
 * 关卡与时序（`rtl/puzzle_pkg.vhd` 第 5 节）
 * ------------------------------------------------------------------ */

export interface LevelDef {
  readonly level: 1 | 2 | 3;
  /** 预览持续秒数（B4/B10：三关都是 5 s）。 */
  readonly previewSeconds: number;
  /** 对局限时秒数。 */
  readonly playSeconds: number;
  /** 零片形状 id（顺序 = 块号）。 */
  readonly shapeIds: readonly string[];
  /** 该关图案是从固定表取还是从图案库随机取。 */
  readonly pattern: 'fixed-l1' | 'fixed-l2' | 'random';
  /** 题目依据 / 设计依据（站内脚注用）。 */
  readonly basis: string;
}

export const LEVELS: readonly LevelDef[] = [
  {
    level: 1,
    previewSeconds: 5,
    playSeconds: 30,
    shapeIds: ['L1_P0', 'L1_P1', 'L1_P2'],
    pattern: 'fixed-l1',
    basis: 'B4/B5 明文：预览 5 s、第一关 30 s、三块零片',
  },
  {
    level: 2,
    previewSeconds: 5,
    playSeconds: 40,
    shapeIds: ['L2_P0', 'L2_P1', 'L2_P2', 'L2_P3'],
    pattern: 'fixed-l2',
    basis: 'B10 明文：四块零片、40 s；图案自拟 = 固定取 L2_PAT3',
  },
  {
    level: 3,
    previewSeconds: 5,
    playSeconds: 60,
    shapeIds: ['L2_P0', 'L2_P1', 'L2_P2', 'L2_P3'],
    pattern: 'random',
    basis: 'A2 扩展关（自拟）：四块零片，图案从四幅库随机选；60 s 为自拟值',
  },
];

/**
 * 零片初始朝向（`PIECE_ORI_INIT`）。
 *
 * 这是 A4「旋转是通关必需的一步」的实现手段：四块从 1/1/2/2 开始散落，
 * 而 `scripts/check_geometry.py` 对第一关矩形 + 四幅图案**穷举证明**过
 * "四块都保持初始朝向时无解" ⇒ 不旋转就拼不出来（ERR-043）。
 * 代价 0 LE —— 常量换常量。
 */
export const PIECE_ORI_INIT: readonly Orientation[] = [1, 1, 2, 2];

/* ------------------------------------------------------------------ *
 * 时序常量（本站模拟器用 4 Hz 心跳，与 RTL 的 tick_4hz 对齐）
 * ------------------------------------------------------------------ */

/** 模拟器心跳周期：250 ms（= RTL 的 `tick_4hz`）。 */
export const TICK_MS = 250;
/** 2 Hz 方波 = 每 250 ms 翻转一次（RTL：`game_fsm` 在 tick_4hz 上翻转 `gblink`）。 */
export const BLINK_EVERY_TICKS = 1;
/** 1 Hz 秒计数 = 每 4 个 250 ms 心跳一次（RTL：`tick_1hz`）。 */
export const SECONDS_EVERY_TICKS = 4;
/** 自检窗口 = 8 个 250 ms 心跳（RTL：`T_SELFTEST_T4 := 7`，倒计数 8 拍）。 */
export const SELFTEST_TICKS = 8;
/** 结算画面：先闪 4 个 250 ms 半周期（= 1 s）再常亮（S5）。 */
export const END_FLASH_HALF_CYCLES = 4;
/** 告急幽灵阈值：倒计时 ≤ 10 s 时画目标幽灵（RTL：`hint_on <= gtime <= 10`）。 */
export const HINT_THRESHOLD_SECONDS = 10;

/** LFSR 种子（`SEED_DEFAULT := x"5A"`；全零是吸收态，绝不允许）。 */
export const SEED_DEFAULT = 0x5a;

/* ------------------------------------------------------------------ *
 * 键位（板子手册附图 26 + 上板实测；`game_fsm.key_of`）
 * ------------------------------------------------------------------ */

export interface KeyDef {
  /** 矩阵键盘上的丝印名。 */
  readonly silk: string;
  /** 原始键号 = 4 × ROW + COL。 */
  readonly code: number;
  /** 游戏内功能。 */
  readonly fn: string;
  /** 键盘快捷键：**当前站点没有实现**（交互模拟器已下线）。
   *  保留字段是为了记录"板子上没有快捷键"这件事；`Demo.tsx` 不渲染它。 */
  readonly shortcut: string;
}

export const KEY_MAP: readonly KeyDef[] = [
  { silk: 'KEY14', code: 1, fn: '开始 / 重开一局', shortcut: 'S' },
  { silk: 'KEY16', code: 3, fn: '选择零片（循环，跳过已锁定）', shortcut: 'Tab' },
  { silk: 'KEY11', code: 6, fn: '确认锁定（变黄，不可再动）', shortcut: 'Enter' },
  { silk: 'KEY7', code: 10, fn: '上', shortcut: '↑ / W' },
  { silk: 'KEY15', code: 2, fn: '下', shortcut: '↓' },
  { silk: 'KEY10', code: 5, fn: '左', shortcut: '← / A' },
  { silk: 'KEY12', code: 7, fn: '右', shortcut: '→ / D' },
  { silk: 'KEY8', code: 11, fn: '原地顺时针旋转 90°', shortcut: 'R' },
  { silk: 'KEY13', code: 0, fn: '不可用（扫描器用键号 0 表示"无键"）', shortcut: '—' },
];

/* ------------------------------------------------------------------ *
 * 几何工具
 * ------------------------------------------------------------------ */

export const BOARD = 8;

export function maskToCells(mask: Mask): Cell[] {
  const out: Cell[] = [];
  for (let r = 0; r < BOARD; r += 1) {
    for (let c = 0; c < BOARD; c += 1) {
      if (((mask[r] ?? 0) >> c) & 1) out.push({ r, c });
    }
  }
  return out;
}

export function emptyMask(): number[] {
  return new Array(BOARD).fill(0);
}

export function setBit(mask: number[], r: number, c: number): void {
  mask[r] |= 1 << c;
}

export function hasBit(mask: Mask, r: number, c: number): boolean {
  return (((mask[r] ?? 0) >> c) & 1) === 1;
}

export function masksEqual(a: Mask, b: Mask): boolean {
  for (let r = 0; r < BOARD; r += 1) if ((a[r] ?? 0) !== (b[r] ?? 0)) return false;
  return true;
}

/** 形状在**原始朝向**（ori = 0）下的紧包围盒。 */
export function shapeBox(shape: ShapeDef): { h: number; w: number } {
  let h = 0;
  let w = 0;
  for (const { r, c } of shape.cells) {
    if (r + 1 > h) h = r + 1;
    if (c + 1 > w) w = c + 1;
  }
  return { h, w };
}

/**
 * 旋转参考模型 —— 与 `scripts/check_geometry.py` 的 `rot_ref()` **逐格一致**。
 *
 * 语义：旋转在零片**自己的紧包围盒**里做，结果仍然锚在包围盒左上角
 * （这正是"锚点不动、只改朝向"的实现口径）。传入的 `cells` 必须是 ori=0 的原始形状：
 * 朝向是**绝对**的（不是累积矩阵），所以每次都从原始形状算起。
 *
 *   "01" 顺时针 90°  -> new(r',c') = old(c',  h-1-r')   ⇒ 尺寸变为 w × h
 *   "10" 180°        -> new(r',c') = old(h-1-r', w-1-c')
 *   "11" 顺时针 270° -> new(r',c') = old(w-1-c', r')
 *
 * 附：RTL 并不是这么算的（它在固定 3×3 盒里转、再补回锚点偏移，见
 * `rtl/puzzle_pkg.vhd` 的【锚点语义】，因为直接这么算实测要 +229 LE、装不下）。
 * `scripts/check_geometry.py` 已证明两种写法**7 块 × 4 朝向全等**，
 * 所以本站用这个更好读的等价模型。
 */
export function rotateCells(cells: readonly Cell[], ori: Orientation, box: { h: number; w: number }): Cell[] {
  const { h, w } = box;
  return cells.map(({ r, c }) => {
    switch (ori) {
      case 0:
        return { r, c };
      case 1:
        return { r: c, c: h - 1 - r };
      case 2:
        return { r: h - 1 - r, c: w - 1 - c };
      default:
        return { r: w - 1 - c, c: r };
    }
  });
}

/** 旋转后的紧包围盒尺寸（90°/270° 时高宽互换）。 */
export function rotatedBox(box: { h: number; w: number }, ori: Orientation): { h: number; w: number } {
  return ori === 1 || ori === 3 ? { h: box.w, w: box.h } : { h: box.h, w: box.w };
}

export function nextOrientation(ori: Orientation): Orientation {
  return (((ori + 1) % 4) as Orientation);
}
