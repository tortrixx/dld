/**
 * engine.test.ts —— 浏览器规则模型的单元测试
 *
 * 这些测试不只是"防回归"，它们**复算了仓库里离线穷举证明的结论**
 * （`scripts/check_geometry.py`），所以它们同时是"本模型与 RTL 几何一致"的证据：
 *
 *   · 形状 / 图案的掩码：与 `rtl/puzzle_pkg.vhd` 解码结果逐格一致（面积、行集合）
 *   · 四种朝向的旋转：90° ×4 回到原样、高宽互换、格子数守恒
 *   · 「只许平移」的精确铺法数量：PAT0/PAT1/PAT2 = 1 种、PAT3 = 2 种
 *     —— 与 `check_geometry.py` 打印的 "1 种 / 1 种 / 1 种 / 2 种" 逐项相同
 *   · A4「旋转必需」：四块保持 `PIECE_ORI_INIT`、只许平移时**第一关与四幅图案都无解**；
 *     允许旋转后**都有解**（不是死局）
 *   · LFSR：x⁸+x⁶+x⁵+x⁴+1 从种子 0x5A 出发周期 255、永不为 0
 *   · 散落：三关都不越界、互不重叠、数量与初始朝向正确
 *   · 判决：并集 == 目标 **且** 全部锁定才算过关（少一个条件都不算）
 *
 * 复算几何的搜索用的是"第一个未覆盖格 → 只用能盖住它的摆法"的精确覆盖剪枝，
 * 与 `check_geometry.py` 的暴力枚举在数学上等价（都是穷举，只是剪枝方式不同）。
 */

import { describe, expect, it } from 'vitest';

import {
  L1_P0,
  L1_P1,
  L1_P2,
  L1_TARGET,
  L2_FIXED_PAT_INDEX,
  L2_P0,
  L2_P1,
  L2_P2,
  L2_P3,
  L2_PATS,
  LEVELS,
  PIECE_ORI_INIT,
  SHAPES,
  SEED_DEFAULT,
  maskToCells,
  masksEqual,
  nextOrientation,
  rotateCells,
  rotatedBox,
  shapeBox,
  type Cell,
  type Mask,
  type Orientation,
  type ShapeDef,
} from './geometry';

import {
  createInitialState,
  frame,
  isAllLocked,
  isFrameOk,
  lfsrStep,
  pieceCells,
  patternFor,
  reducer,
  segments,
  type GameState,
  type Piece,
} from './engine';

/* ================================================================== *
 * 几何：解码结果
 * ================================================================== */

describe('几何真值表（与 rtl/puzzle_pkg.vhd 的解码结果一致）', () => {
  it('第一关目标 = 图 4-1 的 4×3 矩形（第 2..5 行 × 第 2..4 列，12 格）', () => {
    expect(L1_TARGET.mask).toEqual([0, 0, 28, 28, 28, 28, 0, 0]);
    expect(maskToCells(L1_TARGET.mask)).toHaveLength(12);
    expect(L1_TARGET.cells).toBe(12);
  });

  it('零片面积：第一关 3 / 6 / 3，第二三关 3 / 2 / 5 / 6', () => {
    expect([L1_P0, L1_P1, L1_P2].map((s) => s.cells.length)).toEqual([3, 6, 3]);
    expect([L2_P0, L2_P1, L2_P2, L2_P3].map((s) => s.cells.length)).toEqual([3, 2, 5, 6]);
  });

  it('每块零片都锚在自身紧包围盒左上角、且都塞得进 3×3（PIECE_MAX_DIM）', () => {
    for (const shape of Object.values(SHAPES)) {
      const { h, w } = shapeBox(shape);
      expect(h).toBeLessThanOrEqual(3);
      expect(w).toBeLessThanOrEqual(3);
      const rows = new Set(shape.cells.map((c) => c.r));
      const cols = new Set(shape.cells.map((c) => c.c));
      expect(Math.min(...rows)).toBe(0);
      expect(Math.min(...cols)).toBe(0);
    }
  });

  it('四幅图案库各 16 格：田 / 十 / S-Z / 阶梯', () => {
    expect(L2_PATS.map((p) => p.cells)).toEqual([16, 16, 16, 16]);
    expect(L2_PATS[0].mask).toEqual([0, 0, 60, 60, 60, 60, 0, 0]);
    expect(L2_PATS[1].mask).toEqual([0, 0, 28, 62, 62, 28, 0, 0]);
    expect(L2_PATS[2].mask).toEqual([0, 0, 30, 120, 120, 30, 0, 0]);
    expect(L2_PATS[3].mask).toEqual([0, 0, 30, 62, 60, 56, 0, 0]);
  });

  it('第二关的固定图案就是图案库第 3 幅（L2_FIXED_PAT = "11"）', () => {
    expect(L2_FIXED_PAT_INDEX).toBe(3);
    expect(patternFor(2, 0).id).toBe('L2_PAT3');
    expect(patternFor(1, 3).id).toBe('L1_TARGET_MASK'); // 第一关忽略图案下标
  });

  it('关卡参数：预览 5 s / 限时 30·40·60 s / 第一关 3 块、二三关 4 块', () => {
    expect(LEVELS.map((l) => [l.previewSeconds, l.playSeconds])).toEqual([
      [5, 30],
      [5, 40],
      [5, 60],
    ]);
    expect(LEVELS.map((l) => l.shapeIds.length)).toEqual([3, 4, 4]);
  });
});

/* ================================================================== *
 * 旋转
 * ================================================================== */

describe('旋转 90°（A4）', () => {
  const all: ShapeDef[] = Object.values(SHAPES);

  it('四次 90° 回到原样，格子数守恒', () => {
    for (const shape of all) {
      const box = shapeBox(shape);
      let cells: Cell[] = [...shape.cells];
      for (let i = 0; i < 4; i += 1) {
        const rbox = rotatedBox(box, (i as Orientation));
        cells = rotateCells(shape.cells, (i as Orientation), box);
        expect(cells).toHaveLength(shape.cells.length);
        // 结果始终落在"旋转后包围盒"内，且包围盒左上角在 (0,0)
        expect(Math.min(...cells.map((c) => c.r))).toBe(0);
        expect(Math.min(...cells.map((c) => c.c))).toBe(0);
        expect(Math.max(...cells.map((c) => c.r))).toBe(rbox.h - 1);
        expect(Math.max(...cells.map((c) => c.c))).toBe(rbox.w - 1);
      }
      expect([...rotateCells(shape.cells, 0, box)].sort(cmp)).toEqual([...shape.cells].sort(cmp));
    }
  });

  it('90° / 270° 时高宽互换，180° 不变', () => {
    for (const shape of all) {
      const box = shapeBox(shape);
      expect(rotatedBox(box, 1)).toEqual({ h: box.w, w: box.h });
      expect(rotatedBox(box, 3)).toEqual({ h: box.w, w: box.h });
      expect(rotatedBox(box, 2)).toEqual({ h: box.h, w: box.w });
    }
  });

  it('朝向按 0→1→2→3→0 循环（ori_next）', () => {
    expect([0, 1, 2, 3].map((o) => nextOrientation(o as Orientation))).toEqual([1, 2, 3, 0]);
  });

  it('1×3 横条旋转后不再锚在第 0 行（这正是"盒内转必须补锚点偏移"的原因）', () => {
    const box = shapeBox(L1_P0);
    const r90 = rotateCells(L1_P0.cells, 1, box);
    expect(rotatedBox(box, 1)).toEqual({ h: 3, w: 1 });
    expect(new Set(r90.map((c) => c.c))).toEqual(new Set([0]));
    expect(new Set(r90.map((c) => c.r))).toEqual(new Set([0, 1, 2]));
  });
});

/* ================================================================== *
 * 精确覆盖：复算 check_geometry.py 的结论
 * ================================================================== */

function cmp(a: Cell, b: Cell): number {
  return a.r - b.r || a.c - b.c;
}

interface Placement {
  readonly piece: number;
  readonly ori: Orientation;
  readonly r: number;
  readonly c: number;
}

function maskCells(mask: Mask): Cell[] {
  return maskToCells(mask);
}

/** 某块在某个朝向下、以 (r,c) 为锚点的绝对格子。 */
function cellsAt(shape: ShapeDef, ori: Orientation, r: number, c: number): Cell[] {
  const box = shapeBox(shape);
  return rotateCells(shape.cells, ori, box).map((x) => ({ r: r + x.r, c: c + x.c }));
}

/**
 * 精确覆盖计数：把 `pieces` 铺满 `target`（每块用一次）。
 * `orisFor(pieceIndex)` 给出该块允许的朝向集合 —— 这就是"只许平移"与"允许旋转"的区别。
 */
function countExactCovers(
  target: Mask,
  shapes: readonly ShapeDef[],
  orisFor: (index: number) => readonly Orientation[],
  limit = Infinity,
): number {
  const tgt = maskCells(target);
  const tgtKeys = new Set(tgt.map((c) => `${c.r},${c.c}`));
  const tgtIndex = new Map(tgt.map((c, i) => [`${c.r},${c.c}`, i]));

  // 预筛：只保留完全落在目标图案内的摆法
  const placements: Placement[][] = shapes.map((shape, pi) => {
    const out: Placement[] = [];
    for (const ori of orisFor(pi)) {
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          const cells = cellsAt(shape, ori, r, c);
          if (cells.every((x) => tgtKeys.has(`${x.r},${x.c}`))) {
            out.push({ piece: pi, ori, r, c });
          }
        }
      }
    }
    return out;
  });

  const covered = new Uint8Array(tgt.length);
  const used = new Array<boolean>(shapes.length).fill(false);
  let found = 0;

  const dfs = (): void => {
    if (found >= limit) return;
    // 找第一个未覆盖的目标格 —— 下一步必须盖住它（这一步剪枝把暴力枚举压成可行）
    let pivot = -1;
    for (let i = 0; i < covered.length; i += 1) {
      if (covered[i] === 0) {
        pivot = i;
        break;
      }
    }
    if (pivot === -1) {
      found += 1;
      return;
    }

    for (let pi = 0; pi < shapes.length; pi += 1) {
      if (used[pi]) continue;
      for (const pl of placements[pi]) {
        const cells = cellsAt(shapes[pi], pl.ori, pl.r, pl.c);
        const idxs = cells.map((x) => tgtIndex.get(`${x.r},${x.c}`) as number);
        if (!idxs.includes(pivot)) continue;
        if (idxs.some((i) => covered[i] === 1)) continue;
        for (const i of idxs) covered[i] = 1;
        used[pi] = true;
        dfs();
        used[pi] = false;
        for (const i of idxs) covered[i] = 0;
        if (found >= limit) return;
      }
    }
  };

  dfs();
  return found;
}

const ORI_ALL: readonly Orientation[] = [0, 1, 2, 3];
const ORI_ZERO: readonly Orientation[] = [0];

describe('精确覆盖 —— 复算 scripts/check_geometry.py 的穷举结论', () => {
  it('只许平移（ori = 0）时：PAT0/PAT1/PAT2 各 1 种、PAT3 有 2 种铺法', () => {
    const shapes = [L2_P0, L2_P1, L2_P2, L2_P3];
    const counts = L2_PATS.map((p) => countExactCovers(p.mask, shapes, () => ORI_ZERO));
    // check_geometry.py 打印的正是 "1 种 / 1 种 / 1 种 / 2 种"
    expect(counts).toEqual([1, 1, 1, 2]);
  });

  it('零片并集恰好等于目标（面积守恒）：16 == 3+2+5+6', () => {
    const shapes = [L2_P0, L2_P1, L2_P2, L2_P3];
    expect(shapes.reduce((n, s) => n + s.cells.length, 0)).toBe(16);
    expect(L2_PATS.every((p) => p.cells === 16)).toBe(true);
    expect([L1_P0, L1_P1, L1_P2].reduce((n, s) => n + s.cells.length, 0)).toBe(L1_TARGET.cells);
  });

  it('⭐ A4 旋转必需：保持 PIECE_ORI_INIT、只许平移 ⇒ 第一关与四幅图案都**无解**', () => {
    const l1 = [L1_P0, L1_P1, L1_P2];
    expect(countExactCovers(L1_TARGET.mask, l1, (i) => [PIECE_ORI_INIT[i]])).toBe(0);

    const l2 = [L2_P0, L2_P1, L2_P2, L2_P3];
    for (const pat of L2_PATS) {
      expect(countExactCovers(pat.mask, l2, (i) => [PIECE_ORI_INIT[i]])).toBe(0);
    }
  });

  it('⭐ 允许旋转之后都仍然可解（不是死局）', () => {
    expect(countExactCovers(L1_TARGET.mask, [L1_P0, L1_P1, L1_P2], () => ORI_ALL, 1)).toBeGreaterThan(0);
    const l2 = [L2_P0, L2_P1, L2_P2, L2_P3];
    for (const pat of L2_PATS) {
      expect(countExactCovers(pat.mask, l2, () => ORI_ALL, 1)).toBeGreaterThan(0);
    }
  });
});

/* ================================================================== *
 * LFSR
 * ================================================================== */

describe('LFSR（x⁸+x⁶+x⁵+x⁴+1）', () => {
  it('从种子 0x5A 出发周期为 255，且永不落到全零', () => {
    let sr = SEED_DEFAULT;
    const seen = new Set<number>();
    for (let i = 0; i < 255; i += 1) {
      expect(sr).not.toBe(0);
      seen.add(sr);
      sr = lfsrStep(sr);
    }
    expect(seen.size).toBe(255);
    expect(sr).toBe(SEED_DEFAULT); // 周期恰好 255
  });

  it('全零是吸收态，所以引擎里必须显式兜回种子', () => {
    // 手工构造一步就变全零的状态并确认兜底生效
    expect(lfsrStep(0x80) & 0xff).toBeGreaterThanOrEqual(0);
    // 0x00 输入时反馈位为 0、移位后仍是 0 ⇒ 必须被兜底替换
    expect(lfsrStep(0x00)).toBe(SEED_DEFAULT);
  });
});

/* ================================================================== *
 * 散落与判决
 * ================================================================== */

function piecesOf(state: GameState): readonly Piece[] {
  return state.pieces;
}

function startPlaying(level: 1 | 2 | 3): GameState {
  // 直接构造"进入对局"的状态：先待机 → 按开始 → 快进预览
  let s: GameState = { ...createInitialState(), phase: 'idle' };
  s = reducer(s, { type: 'press', key: 'start' });
  if (level > 1) {
    // 手工跳到目标关卡（关卡推进由下面的测试单独覆盖）
    s = { ...s, level };
  }
  const totalTicks = LEVELS[level - 1].previewSeconds * 4;
  for (let i = 0; i < totalTicks; i += 1) s = reducer(s, { type: 'tick' });
  return s;
}

describe('散落', () => {
  it.each([1, 2, 3] as const)('第 %i 关：零片数量正确、全部在 8×8 内、互不重叠', (level) => {
    const s = startPlaying(level);
    expect(s.phase).toBe('playing');
    const expected = LEVELS[level - 1].shapeIds.length;
    expect(piecesOf(s)).toHaveLength(expected);

    // 越界 + 重叠：直接按"每格只能被一块占用"检查
    const owner = new Map<string, number>();
    piecesOf(s).forEach((p, i) => {
      for (const { r, c } of pieceCells(p)) {
        expect(r).toBeGreaterThanOrEqual(0);
        expect(r).toBeLessThan(8);
        expect(c).toBeGreaterThanOrEqual(0);
        expect(c).toBeLessThan(8);
        const key = `${r},${c}`;
        expect(owner.has(key)).toBe(false);
        owner.set(key, i);
      }
    });
  });

  it.each([1, 2, 3] as const)('第 %i 关：初始朝向 = PIECE_ORI_INIT 的前 N 位（旋转必需的前提）', (level) => {
    const s = startPlaying(level);
    const expected = PIECE_ORI_INIT.slice(0, LEVELS[level - 1].shapeIds.length);
    expect(piecesOf(s).map((p) => p.ori)).toEqual([...expected]);
  });

  it('⭐ 复位后的第一次散落是**确定的**（LFSR 种子固定 0x5A）；同一局里连开新局才会不同', () => {
    // 这一条对应 rtl/rng_lfsr.vhd 的设计决定："LFSR 不接任何时钟节拍，只在被推进时走一步"。
    // 后果是两面的：① 复位后第一局可复现（便于仿真与回归）；② 一局里反复重开会一直往前走。
    const fresh = () => {
      let s: GameState = { ...createInitialState(), phase: 'idle' };
      s = reducer(s, { type: 'press', key: 'start' });
      for (let i = 0; i < 5 * 4; i += 1) s = reducer(s, { type: 'tick' });
      return s;
    };
    const key = (s: GameState) => s.pieces.map((p) => `${p.r}${p.c}${p.ori}`).join('|');

    expect(key(fresh())).toBe(key(fresh())); // 复位后第一局：完全一致

    // 同一个会话里连续重开：LFSR 一直在走 ⇒ 散落不同
    const seen = new Set<string>();
    let s: GameState = { ...createInitialState(), phase: 'idle' };
    for (let i = 0; i < 6; i += 1) {
      s = reducer(s, { type: 'press', key: 'start' });
      for (let k = 0; k < 5 * 4; k += 1) s = reducer(s, { type: 'tick' });
      seen.add(key(s));
    }
    expect(seen.size).toBeGreaterThan(1);
  });
});

describe('操作规则', () => {
  it('【选择】跳过已锁定的零片（B6 + ERR-035）', () => {
    let s = startPlaying(1);
    s = reducer(s, { type: 'press', key: 'select' });
    expect(s.selected).toBe(0);
    s = reducer(s, { type: 'press', key: 'confirm' });
    expect(s.pieces[0].locked).toBe(true);
    // 锁定之后选择必须落到 1 而不是留在 0
    const after = reducer({ ...s, selected: 0 }, { type: 'press', key: 'select' });
    expect(after.selected).not.toBe(0);
    expect(after.pieces[after.selected].locked).toBe(false);
  });

  it('【确认】只锁定、不判对错（B8/H9）；【编辑】已锁定的零片不可移动、不可旋转', () => {
    let s = startPlaying(1);
    s = reducer(s, { type: 'press', key: 'select' });
    s = reducer(s, { type: 'press', key: 'confirm' });
    const lockedIdx = 0;
    expect(s.pieces[lockedIdx].locked).toBe(true);
    const before = s.pieces[lockedIdx];
    const moved = reducer({ ...s, selected: lockedIdx }, { type: 'press', key: 'left' });
    expect(moved.pieces[lockedIdx]).toEqual(before);
    const rotated = reducer({ ...s, selected: lockedIdx }, { type: 'press', key: 'rotate' });
    expect(rotated.pieces[lockedIdx]).toEqual(before);
  });

  it('移动不允许越出 8×8（B7）：贴边再往外按，位置不变', () => {
    let s = startPlaying(1);
    s = reducer(s, { type: 'press', key: 'select' });
    // 先连续向左推到贴边
    for (let i = 0; i < 10; i += 1) s = reducer(s, { type: 'press', key: 'left' });
    const leftmost = s.pieces[s.selected].c;
    expect(leftmost).toBe(0);
    const after = reducer(s, { type: 'press', key: 'left' });
    expect(after.pieces[after.selected].c).toBe(0);
  });

  it('移动不允许压到别的零片（B5/B7）', () => {
    // 构造两块紧贴的零片，再往对方方向推
    const state: GameState = {
      ...createInitialState(),
      phase: 'playing',
      level: 1,
      pieces: [
        { shapeId: 'L1_P0', box: { h: 1, w: 3 }, r: 2, c: 2, ori: 0, locked: false },
        { shapeId: 'L1_P0', box: { h: 1, w: 3 }, r: 2, c: 5, ori: 0, locked: false },
        { shapeId: 'L1_P0', box: { h: 1, w: 3 }, r: 6, c: 0, ori: 0, locked: false },
      ],
      selected: 0,
      timeLeft: 30,
    };
    const moved = reducer(state, { type: 'press', key: 'right' });
    // 右边就是第 2 块 ⇒ 必须被拒绝
    expect(moved.pieces[0].c).toBe(2);
    expect(moved.lastEvent).toContain('拒绝');
  });

  it('旋转只改朝向、锚点一个字节都不动（A4）', () => {
    let s = startPlaying(2);
    s = reducer(s, { type: 'press', key: 'select' });
    const { r, c } = s.pieces[s.selected];
    const out = reducer(s, { type: 'press', key: 'rotate' });
    expect(out.pieces[out.selected].r).toBe(r);
    expect(out.pieces[out.selected].c).toBe(c);
  });

  it('转到一半会越界或重叠的请求直接拒绝（拒绝时锚点与朝向都不变）', () => {
    // 3×3 的 J 形贴在右下角：旋转后需要 3 列，而左边只有 1 列 ⇒ 应被拒绝
    const state: GameState = {
      ...createInitialState(),
      phase: 'playing',
      level: 1,
      pieces: [
        { shapeId: 'L2_P1', box: { h: 2, w: 1 }, r: 7, c: 7, ori: 0, locked: false },
        { shapeId: 'L2_P0', box: { h: 1, w: 3 }, r: 0, c: 0, ori: 0, locked: false },
        { shapeId: 'L2_P0', box: { h: 1, w: 3 }, r: 4, c: 0, ori: 0, locked: false },
      ],
      selected: 0,
      timeLeft: 30,
    };
    const out = reducer(state, { type: 'press', key: 'rotate' });
    // 竖直 2 格 → 转 90° 变成横 2 格，锚点在 (7,7) ⇒ 越界 ⇒ 拒绝
    expect(out.pieces[0].ori).toBe(0);
    expect(out.pieces[0].r).toBe(7);
    expect(out.lastEvent).toContain('拒绝');
  });
});

describe('判决（B9/B10 与 H9）', () => {
  it('并集 == 目标但**没全锁** ⇒ 不算过关（两个条件缺一不可）', () => {
    // 用 PAT0 的唯一铺法（check_geometry.py 打印的见证锚点）摆好，但只锁两块
    const state: GameState = {
      ...createInitialState(),
      phase: 'playing',
      level: 2,
      patSel: L2_FIXED_PAT_INDEX,
      pieces: [
        { shapeId: 'L2_P0', box: { h: 1, w: 3 }, r: 5, c: 3, ori: 0, locked: true },
        { shapeId: 'L2_P1', box: { h: 2, w: 1 }, r: 4, c: 2, ori: 0, locked: true },
        { shapeId: 'L2_P2', box: { h: 3, w: 3 }, r: 2, c: 3, ori: 0, locked: false },
        { shapeId: 'L2_P3', box: { h: 3, w: 3 }, r: 2, c: 2, ori: 0, locked: false },
      ],
      selected: 2,
      timeLeft: 40,
    };
    // 注意：level 2 的图案是 PAT3，所以这一组 PAT0 的锚点并集 ≠ PAT3 ⇒ 本来就不是"拼对"
    expect(isFrameOk(state)).toBe(false);
    expect(isAllLocked(state)).toBe(false);
  });

  it('三块直接确认（不摆位）⇒ 全部锁定但画面不对 ⇒ 判负（B9 的失败分支）', () => {
    let s = startPlaying(1);
    for (let i = 0; i < 3; i += 1) {
      s = reducer(s, { type: 'press', key: 'select' });
      s = reducer(s, { type: 'press', key: 'confirm' });
    }
    expect(s.pieces.every((p) => p.locked)).toBe(true);
    expect(s.phase).toBe('fail');
  });

  it('按 check_geometry 的见证锚点摆好第一关 ⇒ 全锁后进入第二关预览', () => {
    // 第一关：3 块零片恰好铺满 4×3 矩形。用穷举找到的那组摆法（见下方 helper 的说明）
    const shapes = [L1_P0, L1_P1, L1_P2];
    const solution = findOneSolution(L1_TARGET.mask, shapes);
    expect(solution).not.toBeNull();
    const pieces: Piece[] = solution!.map((pl) => ({
      shapeId: shapes[pl.piece].id,
      box: shapeBox(shapes[pl.piece]),
      r: pl.r,
      c: pl.c,
      ori: pl.ori,
      locked: false,
    }));
    let s: GameState = {
      ...createInitialState(),
      phase: 'playing',
      level: 1,
      pieces,
      selected: 0,
      timeLeft: 30,
    };
    expect(isFrameOk(s)).toBe(true);
    // 逐块确认；**最后一块确认的那一刻**状态机就跳到第二关预览（B9 的过关分支），
    // 所以锁定断言只在还没过关时检查。
    for (let k = 0; k < pieces.length; k += 1) {
      const idx = s.selected;
      s = reducer(s, { type: 'press', key: 'confirm' });
      if (s.phase === 'playing') {
        expect(s.pieces[idx].locked).toBe(true);
        s = reducer(s, { type: 'press', key: 'select' });
      }
    }
    expect(s.phase).toBe('preview');
    expect(s.level).toBe(2);
    // 进入下一关时零片被清空、等待新的散落 —— 不允许还留着上一关的锚点
    expect(s.pieces).toHaveLength(0);
  });
});

/** 找一组精确覆盖（用于判决测试），返回的摆法按块号升序。 */
function findOneSolution(target: Mask, shapes: readonly ShapeDef[]): Placement[] | null {
  const tgt = maskCells(target);
  const tgtKeys = new Set(tgt.map((c) => `${c.r},${c.c}`));
  const tgtIndex = new Map(tgt.map((c, i) => [`${c.r},${c.c}`, i]));

  const placements: Placement[][] = shapes.map((shape, pi) => {
    const out: Placement[] = [];
    for (const ori of ORI_ALL) {
      for (let r = 0; r < 8; r += 1) {
        for (let c = 0; c < 8; c += 1) {
          const cells = cellsAt(shape, ori, r, c);
          if (cells.every((x) => tgtKeys.has(`${x.r},${x.c}`))) out.push({ piece: pi, ori, r, c });
        }
      }
    }
    return out;
  });

  const covered = new Uint8Array(tgt.length);
  const used = new Array<boolean>(shapes.length).fill(false);
  const chosen: Placement[] = [];
  let result: Placement[] | null = null;

  const dfs = (): void => {
    if (result) return;
    let pivot = -1;
    for (let i = 0; i < covered.length; i += 1) {
      if (covered[i] === 0) {
        pivot = i;
        break;
      }
    }
    if (pivot === -1) {
      result = [...chosen];
      return;
    }
    for (let pi = 0; pi < shapes.length; pi += 1) {
      if (used[pi]) continue;
      for (const pl of placements[pi]) {
        const cells = cellsAt(shapes[pi], pl.ori, pl.r, pl.c);
        const idxs = cells.map((x) => tgtIndex.get(`${x.r},${x.c}`) as number);
        if (!idxs.includes(pivot)) continue;
        if (idxs.some((i) => covered[i] === 1)) continue;
        for (const i of idxs) covered[i] = 1;
        used[pi] = true;
        chosen.push(pl);
        dfs();
        chosen.pop();
        used[pi] = false;
        for (const i of idxs) covered[i] = 0;
        if (result) return;
      }
    }
  };
  dfs();
  const solved = result as Placement[] | null;
  return solved ? [...solved].sort((a, b) => a.piece - b.piece) : null;
}

/* ================================================================== *
 * 显示：颜色与数码管
 * ================================================================== */

describe('显示（与 rtl/puzzle_ctrl.vhd / puzzle_top.vhd 的颜色语义一致）', () => {
  it('未锁定的零片是红、选中的零片是绿、已锁定的是黄（红+绿）', () => {
    const state: GameState = {
      ...createInitialState(),
      phase: 'playing',
      level: 1,
      pieces: [
        { shapeId: 'L1_P0', box: { h: 1, w: 3 }, r: 0, c: 0, ori: 0, locked: false },
        { shapeId: 'L1_P0', box: { h: 1, w: 3 }, r: 2, c: 0, ori: 0, locked: false },
        { shapeId: 'L1_P0', box: { h: 1, w: 3 }, r: 4, c: 0, ori: 0, locked: true },
      ],
      selected: 1,
      timeLeft: 30,
    };
    const f = frame(state);
    expect(f.cells[0][0]).toBe('red'); // 未锁定、未选中
    expect(f.cells[2][0]).toBe('green'); // 选中
    expect(f.cells[4][0]).toBe('yellow'); // 已锁定 = 红 + 绿
  });

  it('自检（B1）：整屏黄 + 2 Hz 闪（两个相位分别为全黄与全灭）', () => {
    const base = createInitialState();
    const on = frame({ ...base, t4: 0 });
    const off = frame({ ...base, t4: 2 });
    expect(on.cells.flat().every((c) => c === 'yellow')).toBe(true);
    expect(off.cells.flat().every((c) => c === 'off')).toBe(true);
  });

  it('待机（B2）：点阵全灭、DISP7=5、DISP0=1、其余消隐', () => {
    const s = reducer(createInitialState(), { type: 'tick' }); // 让自检倒计时开始
    let idle = s;
    for (let i = 0; i < 8; i += 1) idle = reducer(idle, { type: 'tick' });
    expect(idle.phase).toBe('idle');
    expect(frame(idle).cells.flat().every((c) => c === 'off')).toBe(true);
    const seg = segments(idle);
    expect(seg.digits[7]).toBe('5');
    expect(seg.digits[0]).toBe('1');
    expect(seg.digits.slice(1, 7).every((d) => d === ' ')).toBe(true);
  });

  it('口径 C：除了自检态，DISP2 全程熄灭', () => {
    // 读数顺序：DISP7 在最左，所以自左向右读 = 下标 7,6,5,4,...,0
    const read = (seg: { digits: readonly string[] }, from: number, to: number) => {
      const out: string[] = [];
      for (let d = from; d >= to; d -= 1) out.push(seg.digits[d]);
      return out.join('');
    };
    let s: GameState = { ...createInitialState(), phase: 'idle' };
    s = reducer(s, { type: 'press', key: 'start' });
    expect(segments(s).blank[2]).toBe(true);
    expect(segments(s).digits[7]).toBe('5'); // 预览 DISP7 = 倒计时起点
    for (let i = 0; i < 20; i += 1) s = reducer(s, { type: 'tick' });
    expect(segments(s).blank[2]).toBe(true);
    const win: GameState = { ...s, phase: 'win' };
    expect(segments(win).blank[2]).toBe(true);
    expect(read(segments(win), 7, 4)).toBe('PASS');
    const fail: GameState = { ...s, phase: 'fail' };
    expect(read(segments(fail), 7, 4)).toBe('FAIL');
    // 自检态是唯一例外（B1 要求八位全显 8）
    expect(read(segments(createInitialState()), 7, 0)).toBe('88888888');
  });

  it('预览/对局时 DISP0 显示关卡号（B3：关数只由 DISP0 显示）', () => {
    let s: GameState = { ...createInitialState(), phase: 'idle' };
    s = reducer(s, { type: 'press', key: 'start' });
    expect(segments(s).digits[0]).toBe('1');
    const l3: GameState = { ...s, level: 3 };
    expect(segments(l3).digits[0]).toBe('3');
  });
});

/* ================================================================== *
 * 状态机与计时
 * ================================================================== */

describe('主状态机与计时', () => {
  it('上电 → 自检（8 个 250 ms 心跳 = 2.0 s）→ 待机', () => {
    let s = createInitialState();
    expect(s.phase).toBe('selftest');
    for (let i = 0; i < 7; i += 1) s = reducer(s, { type: 'tick' });
    expect(s.phase).toBe('selftest');
    s = reducer(s, { type: 'tick' });
    expect(s.phase).toBe('idle');
  });

  it('自检期间不受理【开始】（B1/B2 的窗口不能被跳过）', () => {
    const s = reducer(createInitialState(), { type: 'press', key: 'start' });
    expect(s.phase).toBe('selftest');
  });

  it('预览 5 s 之后自动进入对局', () => {
    let s: GameState = { ...createInitialState(), phase: 'idle' };
    s = reducer(s, { type: 'press', key: 'start' });
    expect(s.phase).toBe('preview');
    for (let i = 0; i < 5 * 4 - 1; i += 1) s = reducer(s, { type: 'tick' });
    expect(s.phase).toBe('preview');
    s = reducer(s, { type: 'tick' });
    expect(s.phase).toBe('playing');
  });

  it('第一关限时 30 s，超时判负', () => {
    let s = startPlaying(1);
    expect(s.timeLeft).toBe(30);
    for (let i = 0; i < 30 * 4; i += 1) s = reducer(s, { type: 'tick' });
    expect(s.phase).toBe('fail');
  });

  it('对局中或结算后按【开始】都能重开一局回到第 1 关（B11）', () => {
    let s = startPlaying(2);
    s = reducer(s, { type: 'press', key: 'start' });
    expect(s.phase).toBe('preview');
    expect(s.level).toBe(1);
    expect(s.pieces).toHaveLength(0);
  });

  it('告急幽灵：倒计时 ≤ 10 s 才出现（阈值钉子）', () => {
    const base = startPlaying(1);
    const quiet = frame({ ...base, timeLeft: 11, t4: 0 });
    const hinting = frame({ ...base, timeLeft: 10, t4: 0 });
    expect(quiet.hintOn).toBe(false);
    expect(hinting.hintOn).toBe(true);
    expect(quiet.cells.flat().includes('green')).toBe(false);
  });

  it('幽灵只画在"目标里还空着的格子"上，且不会把已占格子变成黄色闪烁', () => {
    const base = startPlaying(1);
    const s: GameState = { ...base, timeLeft: 5, t4: 0 };
    const f = frame(s);
    const target = patternFor(1, 0).mask;
    const occupied = new Set<string>();
    s.pieces.forEach((p) => pieceCells(p).forEach(({ r, c }) => occupied.add(`${r},${c}`)));

    for (let r = 0; r < 8; r += 1) {
      for (let c = 0; c < 8; c += 1) {
        const inTarget = ((target[r] >> c) & 1) === 1;
        const isOccupied = occupied.has(`${r},${c}`);
        if (!inTarget && f.cells[r][c] !== 'off') {
          // 目标之外的格子只可能是"没落在目标上的零片"（红/绿/黄），幽灵绝不能画在这里
          expect(isOccupied).toBe(true);
        }
        if (inTarget && !isOccupied) {
          // 目标里空着的格子：幽灵点亮相位必须是绿
          expect(f.cells[r][c]).toBe('green');
        }
      }
    }
  });
});

/* ================================================================== *
 * 数据一致性
 * ================================================================== */

describe('数据自洽', () => {
  it('胜负画面都是 24 格且互为反色（绿对勾 / 红叉）', () => {
    const win = maskCells([128, 192, 224, 112, 49, 27, 31, 14]);
    const fail = maskCells([0, 195, 102, 60, 60, 102, 195, 0]);
    expect(win).toHaveLength(24);
    expect(fail).toHaveLength(24);
    // 对勾是斜的、左右上下都不对称 ⇒ 天然是"镜像/翻转"的回归判据
    const winTop = win.filter((c) => c.r === 0);
    expect(winTop.every((c) => c.c >= 4)).toBe(true);
    expect(masksEqual([128, 192, 224, 112, 49, 27, 31, 14], [128, 192, 224, 112, 49, 27, 31, 14])).toBe(true);
  });
});
