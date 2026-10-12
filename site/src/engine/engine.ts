/**
 * engine.ts —— 8×8 双色点阵拼图游戏的**浏览器端规则模型**
 *
 * ⚠️ 边界声明（本站的诚信纪律：不把模拟说成硬件）
 *   这一份是**用 TypeScript 重写的规则模型**，不是 RTL 的逐位移植，也不驱动任何硬件。
 *   它被刻意做到"**规则一致**"的那些点，每一条都能在 RTL 里指出出处（见下面各处的
 *   `依据:` 注释）。它**不**声称与 RTL 逐拍等价，尤其是：
 *     · 散落用的是同一个 LFSR 多项式与种子（结果可复现），但**取数的先后顺序与重试次数**
 *       是本站重写的，不是逐拍复刻；
 *     · 时间轴用 250 ms 的 `tick_4hz` 心跳驱动，与 RTL 的分频链口径一致，
 *       但"翻牌重入时的自由走相位"只对本站自己成立；
 *     · 声效完全不做（板子上的蜂鸣器时序本站不模拟）。
 *   把这些写清楚，比含糊地说"完全还原硬件"更重要。
 */

import {
  BOARD,
  BLINK_EVERY_TICKS,
  END_FLASH_HALF_CYCLES,
  HINT_THRESHOLD_SECONDS,
  KEY_MAP,
  L1_TARGET,
  L2_FIXED_PAT_INDEX,
  L2_PATS,
  LEVELS,
  PIECE_ORI_INIT,
  SECONDS_EVERY_TICKS,
  SEED_DEFAULT,
  SELFTEST_TICKS,
  SHAPES,
  TICK_MS,
  WIN_MASK,
  FAIL_MASK,
  emptyMask,
  hasBit,
  masksEqual,
  nextOrientation,
  rotateCells,
  rotatedBox,
  shapeBox,
  setBit,
  type Cell,
  type Orientation,
  type PatternDef,
} from './geometry';

export type Phase = 'selftest' | 'idle' | 'preview' | 'playing' | 'win' | 'fail';
export type GameKey = 'start' | 'select' | 'confirm' | 'up' | 'down' | 'left' | 'right' | 'rotate';
export type CellColor = 'off' | 'red' | 'green' | 'yellow';
export type RejectReason = 'locked' | 'out-of-bounds' | 'overlap' | 'no-piece';

export interface Piece {
  readonly shapeId: string;
  /** 原始朝向下的紧包围盒。 */
  readonly box: { readonly h: number; readonly w: number };
  /** 锚点 = 紧包围盒左上角（旋转**不改**锚点）。依据: rtl/puzzle_ctrl.vhd「旋转只改朝向」 */
  readonly r: number;
  readonly c: number;
  readonly ori: Orientation;
  readonly locked: boolean;
}

export interface GameState {
  readonly phase: Phase;
  readonly level: 1 | 2 | 3;
  /** 第三关在预览入口锁存的图案下标（`rtl/puzzle_top.vhd` 的 pat_sel）。 */
  readonly patSel: number;
  readonly pieces: readonly Piece[];
  readonly selected: number;
  readonly previewLeft: number;
  readonly timeLeft: number;
  /** 自由走的心跳计数（= RTL 的 `tick_4hz` 计数，**不随重开清零**）。 */
  readonly t4: number;
  readonly selfTick: number;
  readonly endFlash: number;
  readonly lfsr: number;
  readonly lastEvent: string;
  readonly log: readonly string[];
}

export interface Frame {
  /** [row][col] 的即时颜色（已经把 2 Hz 闪烁相位算进去）。 */
  readonly cells: readonly (readonly CellColor[])[];
  /** 幽灵提示当前是否处于点亮相位（用于图说）。 */
  readonly hintActive: boolean;
  readonly hintOn: boolean;
}

export interface SegDisplay {
  /** 8 位；下标 = DISP 编号（0 = 最右）。' ' = 消隐。 */
  readonly digits: readonly string[];
  /** 与 `digits` 同步的消隐标志（'1' = 消隐）。依据: rtl/disp_format.vhd 的 o_blank */
  readonly blank: readonly boolean[];
}

/* ================================================================== *
 * 小工具
 * ================================================================== */

const LEVEL_KEY_RE = /^[1-3]$/;

export function levelDef(level: 1 | 2 | 3) {
  return LEVELS[level - 1];
}

/** 某一关的图案。依据: rtl/pattern_rom.vhd（level='0' 时忽略 i_pat）+ puzzle_top 的 pat_sel 锁存 */
export function patternFor(level: 1 | 2 | 3, patSel: number): PatternDef {
  if (level === 1) return L1_TARGET;
  if (level === 2) return L2_PATS[L2_FIXED_PAT_INDEX];
  return L2_PATS[((patSel % L2_PATS.length) + L2_PATS.length) % L2_PATS.length];
}

/** 零片在**当前朝向**下、相对锚点的格子偏移。 */
export function orientedCells(piece: Piece): Cell[] {
  const shape = SHAPES[piece.shapeId];
  return rotateCells(shape.cells, piece.ori, piece.box);
}

/** 零片的绝对占用格子。 */
export function pieceCells(piece: Piece): Cell[] {
  return orientedCells(piece).map(({ r, c }) => ({ r: piece.r + r, c: piece.c + c }));
}

export function piecesMask(pieces: readonly Piece[], filter: (p: Piece) => boolean = () => true): number[] {
  const mask = emptyMask();
  for (const p of pieces) {
    if (!filter(p)) continue;
    for (const { r, c } of pieceCells(p)) setBit(mask, r, c);
  }
  return mask;
}

/** `cov` —— 所有零片的并集（不区分是否锁定）。依据: rtl/puzzle_ctrl.vhd 的 cov_a */
export function coverageMask(pieces: readonly Piece[]): number[] {
  return piecesMask(pieces);
}

/** `kc` —— 已锁定零片的并集。依据: rtl/puzzle_ctrl.vhd 的 kc_a */
export function lockedMask(pieces: readonly Piece[]): number[] {
  return piecesMask(pieces, (p) => p.locked);
}

/** `sl` —— 选中且未锁定的那一块。依据: rtl/puzzle_ctrl.vhd 的 sl_a */
function selectedPieceMask(pieces: readonly Piece[], selected: number): number[] {
  const mask = emptyMask();
  const p = pieces[selected];
  if (!p || p.locked) return mask;
  for (const { r, c } of pieceCells(p)) setBit(mask, r, c);
  return mask;
}

/** 全部零片是否都已锁定（第一关只看 3 块）。依据: rtl/puzzle_ctrl.vhd 的 alllock_r */
export function isAllLocked(state: GameState): boolean {
  if (state.pieces.length === 0) return false;
  return state.pieces.every((p) => p.locked);
}

/** `frm_ok` —— 并集是否**恰好**等于目标图案。依据: rtl/puzzle_ctrl.vhd o_solved <= frm_ok and alllock_r */
export function isFrameOk(state: GameState): boolean {
  const target = patternFor(state.level, state.patSel).mask;
  return masksEqual(coverageMask(state.pieces), target);
}

/* ================================================================== *
 * LFSR（与 rtl/rng_lfsr.vhd 同一个多项式与种子）
 * ================================================================== */

/**
 * 推进一步：`fb := sr(7) xor sr(5) xor sr(4) xor sr(3); sr <= sr(6 downto 0) & fb;`
 * 逐字对应 `rtl/rng_lfsr.vhd:43-48`，包括"绝不变全零"的防御分支。周期 255。
 */
export function lfsrStep(sr: number): number {
  const s = sr & 0xff;
  const fb = ((s >> 7) ^ (s >> 5) ^ (s >> 4) ^ (s >> 3)) & 1;
  let next = ((s << 1) & 0xfe) | fb;
  if (next === 0) next = SEED_DEFAULT;
  return next;
}

/* ================================================================== *
 * 散落（拒绝采样 + 确定性兜底）
 * ================================================================== */

/**
 * 散落：位置随机、互不重叠、不越界。
 *
 * 依据 `rtl/puzzle_ctrl.vhd`：
 *   · 候选锚点范围 `ch := 9 - hh` / `cw := 9 - ww`（ERR-037 修过：旧写 `8 - hh`
 *     会让最后一行/列抽不到、且锚点 0 概率翻倍）；
 *   · 取模在 x ∈ 0..7 且 ch ≥ 4 时等价于"一次条件相减"（ERR-032 的等价改写）；
 *   · 用**同一套**重叠引擎做合法性检查，拒绝采样并带确定性兜底 ⇒ 散落总能完成；
 *   · 初始朝向 = `PIECE_ORI_INIT`（1/1/2/2）—— 这是 A4「旋转必需」的实现手段。
 *
 * ⚠️ 诚实的边界：**同一次散落不会与板子逐格一致**。RTL 的取模发生在它自己的流水相位上、
 *    随机数在两级之间锁存，本站只是按同一套规则重写；一致的是一整套**约束**（候选范围、
 *    边界、互不重叠、初始朝向），以及"16 次失败后落到确定性兜底锚点"这条策略。
 */
const SCATTER_RETRY_LIMIT = 16;
/** RTL 的确定性兜底锚点，顺序即优先级。依据: rtl/puzzle_ctrl.vhd 的 SH_DONE 分支 */
const SCATTER_FALLBACK_ANCHORS: readonly [number, number][] = [
  [0, 0],
  [0, 4],
  [4, 0],
  [4, 4],
];

function scatter(
  level: 1 | 2 | 3,
  lfsrIn: number,
): { pieces: Piece[]; lfsr: number } {
  const def = levelDef(level);
  const pieces: Piece[] = [];
  const occupied = emptyMask();
  let lfsr = lfsrIn;

  /** 一次推进给出 6 位：低 3 位作行候选、高 3 位作列候选（对应 RTL 那两个取模的输入）。 */
  const draw6 = (): number => {
    lfsr = lfsrStep(lfsr);
    return lfsr & 0x3f;
  };

  def.shapeIds.forEach((shapeId, index) => {
    const shape = SHAPES[shapeId];
    const box = shapeBox(shape);
    const ori = PIECE_ORI_INIT[index] ?? 0;
    const rbox = rotatedBox(box, ori);
    const ch = Math.max(1, 9 - rbox.h);
    const cw = Math.max(1, 9 - rbox.w);

    const fits = (r: number, c: number): boolean => {
      if (r + rbox.h > BOARD || c + rbox.w > BOARD) return false;
      const cand: Piece = { shapeId, box, r, c, ori, locked: false };
      for (const { r: pr, c: pc } of pieceCells(cand)) {
        if (hasBit(occupied, pr, pc)) return false;
      }
      return true;
    };

    const commit = (r: number, c: number): void => {
      pieces.push({ shapeId, box, r, c, ori, locked: false });
      const cand: Piece = pieces[pieces.length - 1];
      for (const { r: pr, c: pc } of pieceCells(cand)) setBit(occupied, pr, pc);
    };

    // 阶段 1：拒绝采样（一次取 6 位，行/列各取模一次）
    for (let attempt = 0; attempt < SCATTER_RETRY_LIMIT; attempt += 1) {
      const v = draw6();
      const r = (v & 0x07) % ch;
      const c = ((v >> 3) & 0x07) % cw;
      if (fits(r, c)) {
        commit(r, c);
        return;
      }
    }
    // 阶段 2：确定性兜底锚点（与 RTL 同一组坐标），保证散落一定会完成
    for (const [r, c] of SCATTER_FALLBACK_ANCHORS) {
      if (fits(r, c)) {
        commit(r, c);
        return;
      }
    }
    // 阶段 3：全盘扫描（本站补充的最后一层保险；RTL 走到这里说明 16 次 + 4 个兜底锚点全冲突）
    for (let r = 0; r + rbox.h <= BOARD; r += 1) {
      for (let c = 0; c + rbox.w <= BOARD; c += 1) {
        if (fits(r, c)) {
          commit(r, c);
          return;
        }
      }
    }
  });

  return { pieces, lfsr };
}

/* ================================================================== *
 * 初始状态 / 动作
 * ================================================================== */

export type Action =
  | { readonly type: 'tick' }
  | { readonly type: 'press'; readonly key: GameKey }
  /** 网站便利功能：直接点某一块来选中它。硬件上只有循环的【选择】键，
   *  所以这是**站点特有的交互**，不是硬件行为 —— 界面上的说明写明了这一点。 */
  | { readonly type: 'selectPiece'; readonly index: number }
  | { readonly type: 'reset' };

/** 找出某一格属于哪一块零片（找不到返回 -1）。 */
export function pieceAt(state: GameState, row: number, col: number): number {
  for (let i = 0; i < state.pieces.length; i += 1) {
    for (const cell of pieceCells(state.pieces[i])) {
      if (cell.r === row && cell.c === col) return i;
    }
  }
  return -1;
}

export function createInitialState(): GameState {
  return {
    phase: 'selftest', // 上电即自检（B1/B2）
    level: 1,
    patSel: 0,
    pieces: [],
    selected: 0,
    previewLeft: levelDef(1).previewSeconds,
    timeLeft: levelDef(1).playSeconds,
    t4: 0,
    selfTick: 0,
    endFlash: 0,
    lfsr: SEED_DEFAULT,
    lastEvent: '上电复位：进入开机自检',
    log: ['上电复位：进入开机自检（B1：整屏黄 + 2 Hz，数码管全 8）'],
  };
}

/**
 * 「还没选中任何一块」的哨兵。用 -1 而**不是 0**：0 是合法的块号，
 * 拿它当哨兵会让"第一次按【选择】"跳过第 1 块（本站早期版本真的踩过这个坑，
 * 被单元测试当场抓出来 —— 这正是给规则模型写测试的价值）。
 */
export const NOTHING_SELECTED = -1;

const LOG_LIMIT = 7;

/** 往事件日志里追加一条；`state` 只用来保证类型上"总是携带一份完整状态"。 */
function pushLog(state: GameState, event: string, extra: string[] = []): Pick<GameState, 'lastEvent' | 'log'> {
  void state;
  const log = [...extra, event].slice(-LOG_LIMIT);
  return { lastEvent: event, log };
}

function enterPreview(state: GameState): GameState {
  const level = state.level;
  const def = levelDef(level);
  // 第三关才锁存随机图案；第二关恒取 L2_FIXED_PAT。依据: rtl/puzzle_top.vhd 的 pat_sel 锁存
  let lfsr = state.lfsr;
  let patSel = state.patSel;
  if (def.pattern === 'random') {
    lfsr = lfsrStep(lfsr);
    patSel = lfsr & 0x03;
  }
  const pat = patternFor(level, patSel);
  return {
    ...state,
    phase: 'preview',
    patSel,
    lfsr,
    pieces: [],
    selected: 0,
    previewLeft: def.previewSeconds,
    timeLeft: def.playSeconds,
    endFlash: 0,
    ...pushLog(
      state,
      `第 ${level} 关预览：${pat.label}，${def.previewSeconds} s（DISP7 倒数）`,
      [`按【开始】开局（B4/B10：预览 ${def.previewSeconds} s）`],
    ),
  };
}

function enterPlaying(state: GameState): GameState {
  const def = levelDef(state.level);
  const { pieces, lfsr } = scatter(state.level, state.lfsr);
  return {
    ...state,
    phase: 'playing',
    pieces,
    selected: NOTHING_SELECTED, // 还没选任何一块：所有块都保持红色（未选中态）
    lfsr,
    timeLeft: def.playSeconds,
    ...pushLog(
      state,
      `散落完成：${pieces.length} 块，初始朝向 ${PIECE_ORI_INIT.slice(0, pieces.length).join('/')}（旋转是通关必需的）`,
      [`预览结束 → 对局（B5/B10：${pieces.length} 块随机散落、互不重叠）`],
    ),
  };
}

function resetToIdle(state: GameState): GameState {
  return {
    ...state,
    phase: 'idle',
    pieces: [],
    selected: NOTHING_SELECTED,
    previewLeft: levelDef(1).previewSeconds,
    timeLeft: levelDef(1).playSeconds,
    lastEvent: '自检结束 → 待机（B2：点阵全灭、DISP7=5、DISP0=1）',
    log: [...state.log, '自检结束 → 待机（B2）'].slice(-LOG_LIMIT),
  };
}

/** 【选择】：循环切换选中零片，**跳过已锁定的**（B6 + ERR-035）。 */
function doSelect(state: GameState): GameState {
  const n = state.pieces.length;
  if (n === 0) return feedback(state, '还没进入对局，【选择】暂不生效', 'no-piece');
  const cur = state.selected;
  for (let step = 1; step <= n; step += 1) {
    const idx = (((cur + step) % n) + n) % n;
    if (!state.pieces[idx].locked) {
      return {
        ...state,
        selected: idx,
        ...pushLog(state, `选中第 ${idx + 1} 块（变绿）；已锁定的零片会被跳过（B6/ERR-035）`),
      };
    }
  }
  return feedback(state, '所有零片都已锁定，无可选目标', 'locked');
}

function feedback(state: GameState, msg: string, _reason: RejectReason): GameState {
  return { ...state, ...pushLog(state, msg) };
}

/**
 * 候选落点是否合法：边界 + 重叠。
 * 依据 `rtl/puzzle_ctrl.vhd:850`：`if (cr + hh <= 8) and (cc + ww <= 8) and locked(sel) = '0'`，
 * 再跑**同一套**重叠检查引擎（旋转与移动共用这一条流水）。
 */
function candidateOk(pieces: readonly Piece[], index: number, r: number, c: number, ori: Orientation): boolean {
  const p = pieces[index];
  if (!p || p.locked) return false;
  const rbox = rotatedBox(p.box, ori);
  if (r + rbox.h > BOARD || c + rbox.w > BOARD) return false;
  const cand: Piece = { ...p, r, c, ori };
  for (const { r: pr, c: pc } of pieceCells(cand)) {
    for (let i = 0; i < pieces.length; i += 1) {
      if (i === index) continue;
      for (const { r: qr, c: qc } of pieceCells(pieces[i])) {
        if (qr === pr && qc === pc) return false;
      }
    }
  }
  return true;
}

function doMove(state: GameState, dir: 'up' | 'down' | 'left' | 'right'): GameState {
  if (state.phase !== 'playing') {
    return feedback(state, '当前不在对局中，方向键不生效（B7 只在拼图阶段接受方向键）', 'no-piece');
  }
  const idx = state.selected;
  const p = state.pieces[idx];
  if (!p) return feedback(state, '还没有选中零片 —— 先按【选择】（或点一下零片）', 'no-piece');
  if (p.locked) return feedback(state, '这块已锁定（黄色），不能再移动（B8）', 'locked');

  // 夹紧：锚点先饱和到 0..7。依据: rtl/puzzle_ctrl.vhd:804-814
  let r = p.r;
  let c = p.c;
  if (dir === 'up' && r > 0) r -= 1;
  else if (dir === 'down' && r < 7) r += 1;
  else if (dir === 'left' && c > 0) c -= 1;
  else if (dir === 'right' && c < 7) c += 1;

  if (!candidateOk(state.pieces, idx, r, c, p.ori)) {
    return feedback(state, `移动被拒绝（越界或与别的零片重叠）—— 位置不变（B7/B5）`, 'out-of-bounds');
  }
  const pieces = state.pieces.map((q, i) => (i === idx ? { ...q, r, c } : q));
  return { ...state, pieces, ...pushLog(state, `移动：第 ${idx + 1} 块 → 锚点 (${r}, ${c})`) };
}

/** 【旋转】：原地顺时针 90°，锚点不动；越界或重叠一律拒绝（A4）。 */
function doRotate(state: GameState): GameState {
  if (state.phase !== 'playing') {
    return feedback(state, '当前不在对局中，【旋转】不生效', 'no-piece');
  }
  const idx = state.selected;
  const p = state.pieces[idx];
  if (!p) return feedback(state, '还没有选中零片 —— 先按【选择】或点一下零片', 'no-piece');
  if (p.locked) return feedback(state, '这块已锁定（黄色），不能再旋转（B8）', 'locked');

  const ori = nextOrientation(p.ori);
  if (!candidateOk(state.pieces, idx, p.r, p.c, ori)) {
    return feedback(
      state,
      `旋转被拒绝：转过去会越出 8×8 或压到别的零片 —— 锚点与朝向都不变（A4）`,
      'overlap',
    );
  }
  const pieces = state.pieces.map((q, i) => (i === idx ? { ...q, ori } : q));
  return { ...state, pieces, ...pushLog(state, `旋转 90°：第 ${idx + 1} 块朝向 ${p.ori} → ${ori}（锚点不动）`) };
}

/**
 * 【确认】：锁定选中零片（变黄）。**确认本身不判对错**（B8）。
 * 判决发生在"全部零片都已锁定"那一刻（B9/H9）：
 *   · 并集 == 目标 ⇒ 过关 / 通关（`o_solved`）
 *   · 并集 ≠ 目标 ⇒ 拼装错误、判负（`o_all_lock`）
 * 依据: rtl/puzzle_ctrl.vhd:360-364 与 rtl/game_fsm.vhd:320-335。
 */
function doConfirm(state: GameState): GameState {
  if (state.phase !== 'playing') {
    return feedback(state, '当前不在对局中，【确认】不生效', 'no-piece');
  }
  const idx = state.selected;
  const p = state.pieces[idx];
  if (!p) return feedback(state, '还没有选中零片 —— 先按【选择】或点一下零片', 'no-piece');
  if (p.locked) return feedback(state, '这块已经锁定过了（B8）', 'locked');

  const pieces = state.pieces.map((q, i) => (i === idx ? { ...q, locked: true } : q));
  let next: GameState = { ...state, pieces };

  const allLocked = pieces.every((q) => q.locked);
  if (allLocked) {
    const target = patternFor(next.level, next.patSel).mask;
    const ok = masksEqual(coverageMask(pieces), target);
    if (ok) {
      if (next.level === 3) {
        next = {
          ...next,
          phase: 'win',
          endFlash: 0,
          ...pushLog(next, '三关全部拼成 → 胜利画面（绿色粗对勾 + 数码管 PASS），游戏结束（B10）'),
        };
      } else {
        const nl = (next.level + 1) as 2 | 3;
        next = {
          ...next,
          level: nl,
          ...pushLog(
            next,
            `过关！并集 == 目标图案 ⇒ 进入第 ${nl} 关（B9 / A2 增加关数）`,
          ),
        };
        next = enterPreview(next);
      }
    } else {
      next = {
        ...next,
        phase: 'fail',
        endFlash: 0,
        ...pushLog(next, '全部锁定但并集 ≠ 目标图案 ⇒ 拼装错误、判负（B9/B10 的失败分支）'),
      };
    }
  } else {
    next = {
      ...next,
      selected: nextUnlocked(pieces, idx),
      ...pushLog(next, `已锁定第 ${idx + 1} 块（变黄、不可再选/移动）—— 确认不判对错（B8/H9）`),
    };
  }
  return next;
}

function nextUnlocked(pieces: readonly Piece[], from: number): number {
  const n = pieces.length;
  for (let step = 1; step <= n; step += 1) {
    const idx = (from + step) % n;
    if (!pieces[idx].locked) return idx;
  }
  return from;
}

/* ================================================================== *
 * reducer
 * ================================================================== */

export function reducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case 'reset':
      return createInitialState();

    case 'tick': {
      const t4 = state.t4 + 1;
      const atSecond = t4 % SECONDS_EVERY_TICKS === 0;
      const next: GameState = { ...state, t4 };

      if (next.phase === 'selftest') {
        const selfTick = next.selfTick + 1;
        if (selfTick >= SELFTEST_TICKS) return resetToIdle({ ...next, selfTick });
        return { ...next, selfTick };
      }
      if (next.phase === 'preview') {
        if (!atSecond) return next;
        if (next.previewLeft <= 1) return enterPlaying(next);
        return { ...next, previewLeft: next.previewLeft - 1 };
      }
      if (next.phase === 'playing') {
        if (!atSecond) return next;
        if (next.timeLeft <= 1) {
          return {
            ...next,
            phase: 'fail',
            timeLeft: 0,
            endFlash: 0,
            ...pushLog(next, '倒计时到 0 仍未拼成 ⇒ 超时判负、显示失败图案（B9/B10）'),
          };
        }
        return { ...next, timeLeft: next.timeLeft - 1 };
      }
      if (next.phase === 'win' || next.phase === 'fail') {
        if (next.endFlash >= END_FLASH_HALF_CYCLES) return next;
        return { ...next, endFlash: next.endFlash + 1 };
      }
      return next;
    }

    case 'selectPiece': {
      if (state.phase !== 'playing') return state;
      const p = state.pieces[action.index];
      if (!p) return state;
      if (p.locked) return feedback(state, '这块已锁定（黄色），不能再选中（B8）', 'locked');
      return {
        ...state,
        selected: action.index,
        ...pushLog(state, `点选第 ${action.index + 1} 块（站点便利交互；硬件上用循环的【选择】键）`),
      };
    }

    case 'press': {
      const key = action.key;
      // 【开始】的受理状态：待机 / 预览 / 对局 / 结算；自检期间不受理。
      // 依据: rtl/game_fsm.vhd 各状态的 K_START 分支（S_SELF_TEST 里没有）
      if (key === 'start') {
        if (state.phase === 'selftest') {
          return feedback(state, '自检进行中（B1）—— 自检结束进入待机后才受理【开始】', 'no-piece');
        }
        const restarted = state.phase === 'win' || state.phase === 'fail' || state.phase === 'playing' || state.phase === 'preview';
        const base: GameState = { ...state, level: 1, patSel: 0 };
        const p = enterPreview(base);
        return {
          ...p,
          ...pushLog(
            state,
            restarted
              ? '【开始】→ 重开一局（B11：游戏中或游戏结束后都能重新开始）'
              : '【开始】→ 第 1 关预览（B4）',
          ),
        };
      }
      switch (key) {
        case 'select':
          return doSelect(state);
        case 'confirm':
          return doConfirm(state);
        case 'rotate':
          return doRotate(state);
        case 'up':
        case 'down':
        case 'left':
        case 'right':
          return doMove(state, key);
        default:
          return state;
      }
    }

    default:
      return state;
  }
}

/* ================================================================== *
 * 渲染
 * ================================================================== */

function blinkOn(t4: number): boolean {
  // 每 BLINK_EVERY_TICKS 个 250 ms 心跳翻转一次 ⇒ 50% 占空的 2 Hz 方波。
  // 依据: rtl/game_fsm.vhd 的 gblink（在 tick_4hz 上翻转）
  return Math.floor(t4 / (BLINK_EVERY_TICKS * 2)) % 2 === 0;
}

/**
 * 点阵的即时画面。
 *
 * 颜色语义**逐条对应 `rtl/puzzle_ctrl.vhd:480-483` 与 `rtl/puzzle_top.vhd:796-797`**：
 *   `redrow := cov and (not sl)`   → 未锁定、未选中的零片 = 红
 *   `grnrow := kc or sl`           → 选中的零片 = 绿；已锁定的零片 = 红 + 绿 = **黄**
 *   `mat_g  <= gw or (prev and not rw and hint_blink)` → 告急幽灵 = 绿 + 2 Hz 闪
 * 双色点阵每点只有 **4 种状态：灭 / 红 / 绿 / 黄**，这是硬件事实、不是设计选择。
 */
export function frame(state: GameState): Frame {
  const cells: CellColor[][] = Array.from({ length: BOARD }, () => new Array<CellColor>(BOARD).fill('off'));
  const lv = blinkOn(state.t4);

  const paint = (r: number, c: number, color: CellColor): void => {
    cells[r][c] = color;
  };

  if (state.phase === 'selftest') {
    // B1：整屏黄，2 Hz 闪
    for (let r = 0; r < BOARD; r += 1) {
      for (let c = 0; c < BOARD; c += 1) paint(r, c, lv ? 'yellow' : 'off');
    }
    return { cells, hintActive: false, hintOn: false };
  }

  if (state.phase === 'idle') {
    return { cells, hintActive: false, hintOn: false }; // B2：待机全灭
  }

  if (state.phase === 'preview') {
    const target = patternFor(state.level, state.patSel).mask;
    for (let r = 0; r < BOARD; r += 1) {
      for (let c = 0; c < BOARD; c += 1) if (hasBit(target, r, c)) paint(r, c, 'red');
    }
    return { cells, hintActive: false, hintOn: false };
  }

  // ⚠️ 用显式枚举而不是"漏到最后就当对局"：非法 phase 若落到 S_PLAYING 分支，
  //    会画出一幅"看起来正常但语义错误"的画面（例如整片绿色幽灵），比报错更难发现。
  if (state.phase === 'win' || state.phase === 'fail') {
    const mask = state.phase === 'win' ? WIN_MASK : FAIL_MASK;
    // S5：先按 2 Hz 闪 4 个半周期（1 s）再常亮 —— 远距离可读
    const ev = lv || state.endFlash >= END_FLASH_HALF_CYCLES;
    const color: CellColor = state.phase === 'win' ? 'green' : 'red';
    for (let r = 0; r < BOARD; r += 1) {
      for (let c = 0; c < BOARD; c += 1) if (hasBit(mask, r, c)) paint(r, c, ev ? color : 'off');
    }
    return { cells, hintActive: false, hintOn: false };
  }

  if (state.phase !== 'playing') {
    // 六个已知状态都在上面处理完了；走到这里说明传入了一个非法 phase。
    // 返回全灭（而不是"当成对局画"）——宁可什么都不显示，也不显示错的东西。
    return { cells, hintActive: false, hintOn: false };
  }

  // S_PLAYING
  const cov = coverageMask(state.pieces);
  const kc = lockedMask(state.pieces);
  const sl = selectedPieceMask(state.pieces, state.selected);
  const target = patternFor(state.level, state.patSel).mask;
  const hintOn = state.timeLeft <= HINT_THRESHOLD_SECONDS;
  const hintBlink = hintOn && lv;

  for (let r = 0; r < BOARD; r += 1) {
    for (let c = 0; c < BOARD; c += 1) {
      const inCov = hasBit(cov, r, c);
      const inSel = hasBit(sl, r, c);
      const red = inCov && !inSel;
      const green = hasBit(kc, r, c) || inSel || (hintBlink && hasBit(target, r, c) && !inCov);
      const color: CellColor = red && green ? 'yellow' : red ? 'red' : green ? 'green' : 'off';
      paint(r, c, color);
    }
  }

  return { cells, hintActive: hintBlink, hintOn };
}

/* ------------------------------------------------------------------ *
 * 数码管（8 位；口径 C：DISP2 全程熄灭）
 * ------------------------------------------------------------------ */

/** 段码（低 7 位 = a..g）。字母码来自 `rtl/puzzle_pkg.vhd` 的 `DIG_*`。 */
export const SEG_FONT: Record<string, string> = {
  '0': '0',
  '1': '1',
  '2': '2',
  '3': '3',
  '4': '4',
  '5': '5',
  '6': '6',
  '7': '7',
  '8': '8',
  '9': '9',
  P: 'P',
  A: 'A',
  S: 'S',
  F: 'F',
  I: 'I',
  L: 'L',
  ' ': ' ',
};

/** 每个字符的 a..g 段位（bit0 = a）。' ' = 全灭。 */
export const SEGMENTS: Record<string, number> = {
  '0': 0b0111111,
  '1': 0b0000110,
  '2': 0b1011011,
  '3': 0b1001111,
  '4': 0b1100110,
  '5': 0b1101101,
  '6': 0b1111101,
  '7': 0b0000111,
  '8': 0b1111111,
  '9': 0b1101111,
  // 下面 5 个字母的段形逐位对应 puzzle_pkg 的 DIG_A/P/S/F/L/I 注释
  P: 0b1110011, // a b e f g
  A: 0b1110111, // a b c e f g
  S: 0b1101101, // a c d f g（= '5' 同形，7 段管固有的限制）
  F: 0b1110001, // a e f g
  I: 0b0000110, // 用 '1' 的形状
  L: 0b0111000, // d e f
  ' ': 0b0000000,
};

/**
 * 8 位数码管内容。
 * 依据 `rtl/disp_format.vhd`：DISP7 = 预览倒计时 / 结算里的 'P'·'F'；
 * DISP4:DISP3 = 对局倒计时两位；DISP0 = 关卡号；**DISP2 全程熄灭**（口径 C）。
 */
export function segments(state: GameState): SegDisplay {
  const digits = new Array<string>(8).fill(' ');
  const blank = new Array<boolean>(8).fill(true);
  const set = (disp: number, ch: string): void => {
    digits[disp] = ch;
    blank[disp] = ch === ' ';
  };

  switch (state.phase) {
    case 'selftest':
      // B1：8 个全显 "8" 并 2 Hz 闪烁（本站把闪烁交给 CSS 的 .blink 类）
      for (let d = 0; d < 8; d += 1) set(d, '8');
      break;
    case 'idle':
      // B2：DISP7='5'、DISP0='1'，其余全灭
      set(7, '5');
      set(0, '1');
      break;
    case 'preview':
      set(7, String(Math.max(1, state.previewLeft)));
      set(0, String(state.level));
      break;
    case 'playing': {
      const t = Math.max(0, state.timeLeft);
      set(4, String(Math.floor(t / 10)));
      set(3, String(t % 10));
      set(0, String(state.level));
      break;
    }
    case 'win':
      set(7, 'P');
      set(6, 'A');
      set(5, 'S');
      set(4, 'S');
      break;
    case 'fail':
      set(7, 'F');
      set(6, 'A');
      set(5, 'I');
      set(4, 'L');
      break;
    default:
      break;
  }
  // 口径 C：DISP2 全程熄灭（自检态例外，B1 要求八位全显）
  if (state.phase !== 'selftest') set(2, ' ');
  return { digits, blank };
}

/* ------------------------------------------------------------------ *
 * 给 UI 用的派生信息
 * ------------------------------------------------------------------ */

export function phaseLabel(phase: Phase): string {
  switch (phase) {
    case 'selftest':
      return 'S_SELF_TEST 开机自检';
    case 'idle':
      return 'S_IDLE 待机';
    case 'preview':
      return 'S_PREVIEW 预览';
    case 'playing':
      return 'S_PLAYING 对局';
    case 'win':
      return 'S_WIN 胜利';
    default:
      return 'S_FAIL 失败';
  }
}

/* ------------------------------------------------------------------ *
 * 动作键 ↔ 板子键号
 * ------------------------------------------------------------------ */

/**
 * 游戏动作键 → 板子上那个键的丝印名。
 *
 * ⚠️ 这里**必须**保留 `rawKeyCode`：它曾被当成死代码删掉过一次，
 *    但 `scripts/gen-demo-frames.ts` 的 `silkOf()` 在用它 ——
 *    演示 GIF 的图层要写"按【旋转】(KEY8)"，靠的就是这条映射。
 *    教训：删"没人用"的导出之前要连 `scripts/` 一起 grep（当时只扫了 `src/`）。
 * 映射与 `rtl/game_fsm.vhd` 的 `key_of()` 一致（8 个功能键）。
 */
const ACTION_KEY_SILK: Record<GameKey, string> = {
  start: 'KEY14',
  select: 'KEY16',
  confirm: 'KEY11',
  up: 'KEY7',
  down: 'KEY15',
  left: 'KEY10',
  right: 'KEY12',
  rotate: 'KEY8',
};

/** 游戏动作键 → 键号（= 4×ROW + COL）。 */
export function rawKeyCode(key: GameKey): number {
  return KEY_MAP.find((k) => k.silk === ACTION_KEY_SILK[key])?.code ?? 0;
}

export { LEVEL_KEY_RE, TICK_MS };
