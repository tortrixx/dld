/**
 * gen-demo-frames.ts —— 生成"演示一局"的帧序列（`site/.shots/demo-frames.json`）
 *
 * 这个脚本**不重写任何规则**：它只用 `site/src/engine/engine.ts` 的 `reducer` 推进状态，
 * 用 `frame()` / `segments()` 取画面，所以"演示"里出现的每一步都真的走过了那份规则模型
 * （而那份模型是被 45 条单元测试盯着的、逐条对着 RTL 核过的）。
 *
 * 它做的事：
 *   1. 真实时序：上电 → 自检（8 拍）→ 待机 → 按【开始】→ 预览 5 s（20 个 250 ms 心跳）→ 对局；
 *   2. 对局里**自动求解**：
 *        a. 精确覆盖搜索（同一套"第一个未覆盖格 → 只能用它盖住"的剪枝，与
 *           `engine.test.ts` 的 `countExactCovers` / `scripts/check_geometry.py` 等价）
 *           求出每块零片的目标 (锚点, 朝向)；
 *        b. 对 4!（第一关 3!）种"逐块处理顺序"各做一次**单块 BFS**（状态 = 锚点 × 朝向，
 *           动作 = 上/下/左/右/旋转，约束 = 不越界、不压到别的零片），取总按键数最少的方案；
 *        c. 用 `reducer` 逐动作重放，并**断言每一步都真的被受理**（某一步被拒绝就抛错 ——
 *           那说明 BFS 的合法性判定与 reducer 不一致，是 bug，绝不能忽略）；
 *        d. 每块摆好后按【确认】锁定，最后一块确认的那一刻状态机自己判过关 → 第 2 关预览。
 *   3. 抽帧压缩：自检/待机各留少量帧、预览 20 帧、对局**每个按键一帧**（纯等待的心跳不单独出帧），
 *      每帧带 `delayMs`（真实经过时间，夹在 60..600 ms）。
 *
 * 运行（`src/engine/*.ts` 用的是无扩展名相对导入，所以不能直接 node）：
 *
 *   cd site && node_modules/.bin/vite-node scripts/gen-demo-frames.ts
 *
 * 产物：`site/.shots/demo-frames.json`（顶层是**帧数组**，每帧字段见下方 `OutFrame`）。
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  BOARD,
  KEY_MAP,
  PIECE_ORI_INIT,
  SHAPES,
  TICK_MS,
  maskToCells,
  nextOrientation,
  rotateCells,
  rotatedBox,
  shapeBox,
  type Cell,
  type Mask,
  type Orientation,
  type ShapeDef,
} from '../src/engine/geometry';

import {
  createInitialState,
  frame,
  isAllLocked,
  isFrameOk,
  levelDef,
  patternFor,
  pieceCells,
  rawKeyCode,
  reducer,
  segments,
  type Action,
  type GameKey,
  type GameState,
} from '../src/engine/engine';

/* ================================================================== *
 * 输出帧的字段
 * ================================================================== */

interface OutFrame {
  /** 8 行 × 8 列，'off' | 'red' | 'green' | 'yellow'。 */
  readonly cells: readonly (readonly string[])[];
  /** 8 位数码管；**下标 = DISP 编号**（0 = 最右，7 = 最左），' ' = 消隐。 */
  readonly digits: readonly string[];
  /** 与 digits 同步的消隐标志。 */
  readonly blank: readonly boolean[];
  /** 'selftest' | 'idle' | 'preview' | 'playing' | 'win' | 'fail' */
  readonly phase: string;
  /** 底部说明（一行，中文）。 */
  readonly caption: string;
  /** 右侧细节（可多句，中文）。 */
  readonly detail: string;
  /** 这一帧在 GIF 里停留多久（真实经过时间，夹在 60..600 ms）。 */
  readonly delayMs: number;
}

/* ================================================================== *
 * 小工具
 * ================================================================== */

const MIN_DELAY_MS = 60;
const MAX_DELAY_MS = 600;

function clampDelay(ms: number): number {
  return Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, Math.round(ms)));
}

/** 游戏内的动作键 → 板子上那个键的丝印名（板子上没有键盘快捷键，演示里按的是硬件键）。 */
function silkOf(key: GameKey): string {
  const code = rawKeyCode(key);
  return KEY_MAP.find((k) => k.code === code)?.silk ?? '?';
}

const DIR_CN: Record<string, string> = { up: '上', down: '下', left: '左', right: '右' };

function pieceLabel(state: GameState, index: number): string {
  const p = state.pieces[index];
  const shape = SHAPES[p.shapeId];
  return `第 ${index + 1} 块（${p.shapeId}，${shape.cells.length} 格）`;
}

/* ================================================================== *
 * 精确覆盖：求出每块零片的目标 (锚点, 朝向)
 *   与 engine.test.ts 的 findOneSolution / 前者的 countExactCovers 同一套剪枝
 * ================================================================== */

interface Placement {
  readonly piece: number;
  readonly ori: Orientation;
  readonly r: number;
  readonly c: number;
}

function cellsAt(shape: ShapeDef, ori: Orientation, r: number, c: number): Cell[] {
  const box = shapeBox(shape);
  return rotateCells(shape.cells, ori, box).map((x) => ({ r: r + x.r, c: c + x.c }));
}

/** 枚举所有"每块用一次、恰好铺满目标"的摆法（按块号升序），最多 `limit` 组。 */
function allExactCovers(target: Mask, shapes: readonly ShapeDef[], limit: number): Placement[][] {
  const tgt = maskToCells(target);
  const tgtKeys = new Set(tgt.map((c) => `${c.r},${c.c}`));
  const tgtIndex = new Map(tgt.map((c, i) => [`${c.r},${c.c}`, i]));

  // 预筛：只保留完全落在目标图案内的摆法
  const placements: Placement[][] = shapes.map((shape, pi) => {
    const out: Placement[] = [];
    for (const ori of [0, 1, 2, 3] as const) {
      for (let r = 0; r < BOARD; r += 1) {
        for (let c = 0; c < BOARD; c += 1) {
          if (cellsAt(shape, ori, r, c).every((x) => tgtKeys.has(`${x.r},${x.c}`))) {
            out.push({ piece: pi, ori, r, c });
          }
        }
      }
    }
    return out;
  });

  const covered = new Uint8Array(tgt.length);
  const used = new Array<boolean>(shapes.length).fill(false);
  const chosen: Placement[] = [];
  const out: Placement[][] = [];

  const dfs = (): void => {
    if (out.length >= limit) return;
    // 第一个未覆盖的目标格：下一步必须盖住它（这条剪枝把暴力枚举压成可行）
    let pivot = -1;
    for (let i = 0; i < covered.length; i += 1) {
      if (covered[i] === 0) {
        pivot = i;
        break;
      }
    }
    if (pivot === -1) {
      out.push([...chosen].sort((a, b) => a.piece - b.piece));
      return;
    }
    for (let pi = 0; pi < shapes.length; pi += 1) {
      if (used[pi]) continue;
      for (const pl of placements[pi]) {
        const idxs = cellsAt(shapes[pi], pl.ori, pl.r, pl.c).map(
          (x) => tgtIndex.get(`${x.r},${x.c}`) as number,
        );
        if (!idxs.includes(pivot)) continue;
        if (idxs.some((i) => covered[i] === 1)) continue;
        for (const i of idxs) covered[i] = 1;
        used[pi] = true;
        chosen.push(pl);
        dfs();
        chosen.pop();
        used[pi] = false;
        for (const i of idxs) covered[i] = 0;
        if (out.length >= limit) return;
      }
    }
  };

  dfs();
  return out;
}

/* ================================================================== *
 * 单块 BFS：从当前 (锚点, 朝向) 走到目标 (锚点, 朝向)
 *   合法性与 reducer 的 candidateOk **同一口径**：越界 / 压到别的零片一律不许。
 *   （已锁定与还没处理的零片，都按"固定障碍"处理 —— 这也正是 reducer 的做法。）
 * ================================================================== */

type MoveKey = 'up' | 'down' | 'left' | 'right' | 'rotate';

/** 目标与 reducer 的 candidateOk 等价：边界 + 与其他零片不重叠。 */
function legal(state: GameState, index: number, r: number, c: number, ori: Orientation): boolean {
  if (r < 0 || c < 0) return false;
  const p = state.pieces[index];
  const rbox = rotatedBox(p.box, ori);
  if (r + rbox.h > BOARD || c + rbox.w > BOARD) return false;
  const mine = rotateCells(SHAPES[p.shapeId].cells, ori, p.box).map((x) => ({
    r: r + x.r,
    c: c + x.c,
  }));
  for (const cell of mine) {
    for (let i = 0; i < state.pieces.length; i += 1) {
      if (i === index) continue;
      for (const q of pieceCells(state.pieces[i])) {
        if (q.r === cell.r && q.c === cell.c) return false;
      }
    }
  }
  return true;
}

/** 最短动作序列（BFS：状态 = 锚点 × 朝向，动作 = 上下左右 + 顺时针旋转）。 */
function bfsMoves(state: GameState, index: number, goal: Placement): MoveKey[] | null {
  const p = state.pieces[index];
  const key = (r: number, c: number, o: Orientation): string => `${r},${c},${o}`;
  const startKey = key(p.r, p.c, p.ori);
  const goalKey = key(goal.r, goal.c, goal.ori);
  if (startKey === goalKey) return [];

  const prev = new Map<string, { from: string; move: MoveKey }>();
  const seen = new Set<string>([startKey]);
  const queue: { r: number; c: number; o: Orientation }[] = [{ r: p.r, c: p.c, o: p.ori }];

  while (queue.length > 0) {
    const cur = queue.shift() as { r: number; c: number; o: Orientation };
    const curKey = key(cur.r, cur.c, cur.o);
    const nexts: [MoveKey, number, number, Orientation][] = [
      ['up', cur.r - 1, cur.c, cur.o],
      ['down', cur.r + 1, cur.c, cur.o],
      ['left', cur.r, cur.c - 1, cur.o],
      ['right', cur.r, cur.c + 1, cur.o],
      // 顺时针 90°，锚点不动（A4）
      ['rotate', cur.r, cur.c, nextOrientation(cur.o)],
    ];
    for (const [move, r, c, o] of nexts) {
      const k = key(r, c, o);
      if (seen.has(k)) continue;
      if (!legal(state, index, r, c, o)) continue;
      seen.add(k);
      prev.set(k, { from: curKey, move });
      if (k === goalKey) {
        const path: MoveKey[] = [];
        let at = goalKey;
        while (at !== startKey) {
          const step = prev.get(at) as { from: string; move: MoveKey };
          path.push(step.move);
          at = step.from;
        }
        return path.reverse();
      }
      queue.push({ r, c, o });
    }
  }
  return null;
}

/* ================================================================== *
 * 计划：对一组精确覆盖 + 一个"逐块处理顺序"，生成按键序列
 *   全程用 reducer 推进，任何一步被拒绝就返回 null（而不是忽略）
 * ================================================================== */

interface PlannedStep {
  readonly action: Action;
  readonly kind: 'select' | 'move' | 'rotate' | 'confirm';
}

function planWith(
  start: GameState,
  cover: readonly Placement[],
  order: readonly number[],
): PlannedStep[] | null {
  let s = start;
  const steps: PlannedStep[] = [];
  const goalOf = new Map<number, Placement>();
  for (const pl of cover) goalOf.set(pl.piece, pl);

  for (const idx of order) {
    const goal = goalOf.get(idx);
    if (!goal) return null;
    if (s.phase !== 'playing') return null;

    // ① 选中：只用硬件上的【选择】键循环（跳过已锁定的），不用站点便利交互
    let guard = 0;
    while (s.selected !== idx) {
      if (s.phase !== 'playing') return null;
      const before = s.selected;
      s = reducer(s, { type: 'press', key: 'select' });
      steps.push({ action: { type: 'press', key: 'select' }, kind: 'select' });
      if (s.selected === before) return null;
      guard += 1;
      if (guard > 8) return null;
    }

    // ② 单块 BFS 得到的动作序列
    const moves = bfsMoves(s, idx, goal);
    if (moves === null) return null;
    for (const mv of moves) {
      const p0 = s.pieces[idx];
      const before = `${p0.r},${p0.c},${p0.ori}`;
      s = reducer(s, { type: 'press', key: mv });
      const p1 = s.pieces[idx];
      if (`${p1.r},${p1.c},${p1.ori}` === before) {
        // reducer 拒绝了这一步 ⇒ BFS 的合法性判定与 reducer 不一致，是 bug
        return null;
      }
      steps.push({ action: { type: 'press', key: mv }, kind: mv === 'rotate' ? 'rotate' : 'move' });
    }

    // ③ 确认锁定；最后一块确认的那一刻状态机自己判过关
    const remaining = s.pieces.filter((q) => !q.locked).length;
    s = reducer(s, { type: 'press', key: 'confirm' });
    steps.push({ action: { type: 'press', key: 'confirm' }, kind: 'confirm' });
    if (remaining > 1) {
      if (!s.pieces[idx].locked) return null;
    } else if (s.phase !== 'preview') {
      return null; // 并集 == 目标且全锁 ⇒ 必须已经进入下一关预览
    }
  }
  return steps;
}

function permutations(n: number): number[][] {
  const out: number[][] = [];
  const walk = (prefix: number[], rest: number[]): void => {
    if (rest.length === 0) {
      out.push(prefix);
      return;
    }
    for (let i = 0; i < rest.length; i += 1) {
      walk([...prefix, rest[i]], [...rest.slice(0, i), ...rest.slice(i + 1)]);
    }
  };
  walk([], Array.from({ length: n }, (_, i) => i));
  return out;
}

/** 在"所有精确覆盖 × 所有处理顺序"里挑按键数最少的一版（按键少 = GIF 短）。 */
function bestPlan(start: GameState): PlannedStep[] {
  const shapes = levelDef(start.level).shapeIds.map((id) => SHAPES[id]);
  const target = patternFor(start.level, start.patSel).mask;
  const covers = allExactCovers(target, shapes, 200);
  if (covers.length === 0) throw new Error('精确覆盖搜索没找到任何解 —— 规则或几何有问题');
  const orders = permutations(shapes.length);
  let best: PlannedStep[] | null = null;
  for (const cover of covers) {
    for (const order of orders) {
      const plan = planWith(start, cover, order);
      if (plan === null) continue;
      if (best === null || plan.length < best.length) best = plan;
    }
  }
  if (best === null) {
    throw new Error(
      `有 ${covers.length} 组精确覆盖，但没有一组能被"逐块单块 BFS"走到 —— 需要放宽求解策略`,
    );
  }
  return best;
}

/* ================================================================== *
 * 主流程
 * ================================================================== */

function main(): void {
  const frames: OutFrame[] = [];
  let s = createInitialState();

  const counters = { press: 0, select: 0, move: 0, rotate: 0, confirm: 0, tick: 0 };

  const snap = (caption: string, detail: string, delayMs: number): void => {
    const f = frame(s);
    const seg = segments(s);
    frames.push({
      cells: f.cells.map((row) => [...row]),
      digits: [...seg.digits],
      blank: [...seg.blank],
      phase: s.phase,
      caption,
      detail,
      delayMs: clampDelay(delayMs),
    });
  };

  const tick = (): void => {
    s = reducer(s, { type: 'tick' });
    counters.tick += 1;
  };

  /* ---- 1. 上电自检（B1）：整屏黄 + 2 Hz 闪，8 个心跳 = 2 s ---- */
  snap(
    '上电复位 → 开机自检（B1）：整屏黄 + 2 Hz 闪烁',
    '自检窗口 = 8 个 250 ms 心跳 = 2.0 s（RTL: T_SELFTEST_T4 = 7）。数码管 8 位全显 "8"。自检期间按【开始】不受理。',
    500,
  );
  tick();
  tick(); // t4 = 2 ⇒ 闪烁的"灭"相位（blinkOn = floor(t4/2) % 2）
  snap(
    '自检 2 Hz 闪烁的"灭"相位（同一屏的另一半周期）',
    '黄色 = 红 + 绿同时点亮（双色点阵的硬件事实）；这里只是整屏在闪烁。',
    500,
  );
  for (let i = 0; i < 6; i += 1) tick(); // 第 8 拍结束 ⇒ 自动进待机
  if (s.phase !== 'idle') throw new Error(`自检没有按时结束，phase = ${s.phase}`);
  snap(
    '自检结束 → 待机（B2）：点阵全灭、DISP7=5、DISP0=1',
    '待机画面等的是【开始】（KEY14）。DISP0 显示关卡号 1。',
    600,
  );

  /* ---- 2. 按【开始】→ 第 1 关预览（B4）：5 s 倒数 ---- */
  s = reducer(s, { type: 'press', key: 'start' });
  counters.press += 1;
  if (s.phase !== 'preview' || s.level !== 1) throw new Error('按【开始】没有进入第 1 关预览');
  const pat1 = patternFor(1, 0);
  snap(
    `按【开始】(${silkOf('start')}) → 第 1 关预览：${pat1.label}`,
    '预览 5 s：点阵把目标图案整幅点亮（全红），DISP7 从 5 倒数；预览结束自动进入对局。',
    500,
  );

  for (let i = 1; i <= 20; i += 1) {
    tick();
    if (s.phase === 'preview') {
      snap(
        `第 1 关 · 预览 目标图案（${pat1.label}）`,
        `预览剩 ${s.previewLeft} s（心跳 ${i}/20，1 拍 = 250 ms）。认准这 12 格：第 2..5 行 × 第 2..4 列。`,
        TICK_MS,
      );
    } else {
      snap(
        '预览结束 → 对局开始：3 块零片随机散落',
        `散落：互不重叠、不越界，初始朝向 ${PIECE_ORI_INIT.slice(0, s.pieces.length).join('/')}（PIECE_ORI_INIT）—— ` +
          '⚠️ 这个初始朝向**不是**终点朝向，所以不旋转就拼不出来（A4）。',
        TICK_MS,
      );
    }
  }
  if (s.phase !== 'playing') throw new Error(`预览 20 拍后没有进入对局，phase = ${s.phase}`);

  const scatterDesc = s.pieces
    .map((p, i) => `第${i + 1}块 (${p.r},${p.c}) 朝向 ${p.ori}`)
    .join('；');
  snap(
    '对局开始：先看清散落位置，再按【选择】选块',
    `散落实况：${scatterDesc}。红色 = 未选中、绿色 = 选中、黄色 = 已锁定（红+绿）。`,
    TICK_MS,
  );

  /* ---- 3. 对局：自动求解（精确覆盖 → 单块 BFS → 逐动作重放） ---- */
  const plan = bestPlan(s);
  const target1 = patternFor(1, 0).mask;
  for (const step of plan) {
    const before = s;
    s = reducer(s, step.action);
    counters.press += 1;
    if (s.phase !== 'playing' && s.phase !== 'preview') {
      throw new Error(`执行计划时状态机跑到了 ${s.phase}（倒计时 ${s.timeLeft} s）`);
    }
    const idx = before.selected;

    if (step.kind === 'select') {
      counters.select += 1;
      snap(
        `按【选择】(${silkOf('select')}) → 选中第 ${s.selected + 1} 块（变绿）`,
        '【选择】循环切换、**跳过已锁定的零片**（B6/ERR-035）。选中的那块变绿，其余保持红色。',
        TICK_MS,
      );
    } else if (step.kind === 'confirm') {
      counters.confirm += 1;
      const remaining = before.pieces.filter((q) => !q.locked).length;
      if (remaining === 1) {
        // 最后一块：【确认】之前必须"并集 == 目标、但还没全锁"，之后才可能判过关 —— 两个条件缺一不可
        if (!isFrameOk(before) || isAllLocked(before)) {
          throw new Error('最后一块确认前的状态不满足"并集 == 目标 且 尚未全锁"');
        }
      }
      if (s.phase === 'preview') {
        // 最后一块确认 ⇒ 并集 == 目标 且 全部锁定 ⇒ 过关
        const lastPiece = before.pieces[idx];
        snap(
          '按【确认】锁定最后一块 → 并集 == 目标 且 全部零片已锁定 ⇒ 过关！',
          `第 ${idx + 1} 块（${lastPiece.shapeId}）散落时恰好就停在目标位上（锚点 (${lastPiece.r}, ${lastPiece.c})、朝向 ${lastPiece.ori}），` +
            '所以它只需要【确认】。并集 = 3+6+3 = 12 格，恰好等于目标图案 ⇒ frm_ok and alllock ⇒ 状态机立刻跳到第 2 关预览（B9）。',
          TICK_MS,
        );
      } else {
        snap(
          `按【确认】(${silkOf('confirm')}) → 第 ${idx + 1} 块锁定（变黄、不可再动）`,
          '【确认】本身**不判对错**（B8/H9）：判决发生在"全部零片都已锁定"那一刻。',
          TICK_MS,
        );
      }
    } else if (step.kind === 'rotate') {
      counters.rotate += 1;
      const p = s.pieces[idx];
      snap(
        `按【旋转】(${silkOf('rotate')}) → 第 ${idx + 1} 块 顺时针 90°，朝向 ${before.pieces[idx].ori} → ${p.ori}（锚点不动）`,
        `旋转在原地做：锚点仍是 (${p.r}, ${p.c})，只换朝向（A4）。转到越界或压到别的零片会被拒绝、什么都不改。`,
        TICK_MS,
      );
    } else {
      counters.move += 1;
      const key = (step.action as { type: 'press'; key: GameKey }).key;
      const p = s.pieces[idx];
      snap(
        `按【${DIR_CN[key]}】(${silkOf(key)}) → ${pieceLabel(s, idx)} 锚点 (${before.pieces[idx].r}, ${before.pieces[idx].c}) → (${p.r}, ${p.c})`,
        '每次按键只走一格；越界或压到别的零片会被整条拒绝（位置不变，B5/B7）。',
        TICK_MS,
      );
    }

    // 一帧 250 ms：按一次键 = 一个 tick_4hz 心跳，倒计时也照真实节拍往下走
    if (s.phase === 'playing') tick();
  }

  /* ---- 4. 第 2 关预览收尾 ---- */
  if (s.phase !== 'preview' || s.level !== 2) {
    throw new Error(`第一关没有过关，phase = ${s.phase}, level = ${s.level}`);
  }
  const pat2 = patternFor(2, s.patSel);
  for (let i = 1; i <= 6; i += 1) {
    tick();
    snap(
      `第 2 关 · 预览（${pat2.label}）`,
      `过关后自动进入第 2 关预览：4 块零片（3/2/5/6 格）、限时 40 s。预览剩 ${s.previewLeft} s（预览心跳 ${i}/6）。`,
      300,
    );
  }
  const last = frames[frames.length - 1];
  frames.push({
    ...last,
    detail: `${last.detail} 演示到此为止 —— 第 2 关的对局与第 1 关同理（四块、限时 40 s）。`,
    delayMs: 600,
  });
  frames.push({
    ...last,
    detail: `${last.detail} 演示到此为止 —— GIF 到此循环回放。`,
    delayMs: 600,
  });

  /* ---- 5. 写盘 ---- */
  const here = dirname(fileURLToPath(import.meta.url));
  const outPath = resolve(here, '..', '.shots', 'demo-frames.json');
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, `${JSON.stringify(frames, null, 0)}\n`, 'utf8');

  const totalMs = frames.reduce((n, f) => n + f.delayMs, 0);
  const rotations = plan.filter((p) => p.kind === 'rotate').length;
  const targetCells = maskToCells(target1).length;
  process.stdout.write(
    [
      `写出 ${outPath}`,
      `帧数 = ${frames.length}（其中预览 ${frames.filter((f) => f.phase === 'preview').length}）`,
      `总时长 = ${totalMs} ms（按 delayMs 求和）`,
      `按键总数 = ${counters.press}（选择 ${counters.select} / 移动 ${counters.move} / 旋转 ${counters.rotate} / 确认 ${counters.confirm}）`,
      `心跳 tick = ${counters.tick}（对局外 + 按键间隔）`,
      `第一关目标 ${targetCells} 格；散落 = ${scatterDesc}`,
      `旋转步数 = ${rotations} ⇒ ${rotations > 0 ? '✅ 确实用到了旋转（"不旋转拼不出来"的正面证据）' : '❌ 没用到旋转'}`,
      `过关：level 1 → ${s.level}（phase = ${s.phase}，剩余 ${s.timeLeft} s）`,
    ].join('\n') + '\n',
  );
}

main();
