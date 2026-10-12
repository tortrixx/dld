/**
 * Keypad.tsx —— 4×4 矩阵键盘示意图（只画右下那个 3×3 功能区块）
 *
 * 布局来自**板子手册附图 26 + 上板实测**（`rtl/game_fsm.vhd` 的注释与 `key_of()`）：
 * 七个控制键集中在右下角同一个连续的 3×3 区块里，方向键按标准「十字」排列
 * （中心 = 确认，与数字小键盘一样）。键号 = 4×ROW + COL，ROW0 在最下、COL0 在最左。
 *
 * ⚠️ KEY13（键号 0）**不可用**：扫描器用 "0000" 表示"没有按键"，
 *    所以它和"没按"无法区分 —— 界面上把它画成灰的，就是这条硬件事实。
 */

import type { GameKey } from '../engine/engine';

export interface KeypadProps {
  readonly onPress?: (key: GameKey) => void;
  /** 最近按下的动作（用于 220 ms 的高亮反馈）。 */
  readonly activeKey?: GameKey | null;
  readonly disabled?: boolean;
  /** 只读模式：渲染成不可点的键帽（用于"玩法说明"里的键位图示）。 */
  readonly readonly?: boolean;
}

interface KeyCell {
  readonly key: GameKey | null;
  readonly silk: string;
  readonly code: number;
  readonly label: string;
  readonly dead?: boolean;
}

/**
 * 键位表按**板子手册附图 26 的真实位置**排：
 *   ROW2 / ROW1 只取 COL1..COL3（COL0 上是无功能的 KEY5/KEY9 一列，不画）；
 *   ROW0 取 COL0..COL3 —— 也就是最下面一整行 4 个键。
 *
 * ⚠️ 两个"不能按"的键性质不同，图注必须分开说（早先版本把 KEY6 标成"不可用"、
 *    图注却写 KEY13，图文互相矛盾）：
 *   · **KEY6**（键号 9）：扫描器能报出来，只是本游戏**没有给它分配功能**；
 *   · **KEY13**（键号 0）：**不可用** —— 扫描器用 "0000" 表示"没有按键"，
 *     所以它和"没按"无法区分（rtl/game_fsm.vhd:119-122 的注释）。
 */
interface KeyCell {
  readonly key: GameKey | null;
  readonly silk: string;
  readonly code: number;
  readonly label: string;
  readonly dead?: boolean;
}

/** 上面两行：ROW2 / ROW1 的 COL1..COL3（每行首格空出来，对齐到 4 列网格的第 2 列）。 */
const ROWS_UPPER: readonly (readonly (KeyCell | null)[])[] = [
  [
    null,
    { key: null, silk: 'KEY6', code: 9, label: '未分配', dead: true },
    { key: 'up', silk: 'KEY7', code: 10, label: '上' },
    { key: 'rotate', silk: 'KEY8', code: 11, label: '旋转' },
  ],
  [
    null,
    { key: 'left', silk: 'KEY10', code: 5, label: '左' },
    { key: 'confirm', silk: 'KEY11', code: 6, label: '确认' },
    { key: 'right', silk: 'KEY12', code: 7, label: '右' },
  ],
];

/** 最下面一整行：ROW0 的 COL0..COL3。 */
const ROW_BOTTOM: readonly KeyCell[] = [
  { key: null, silk: 'KEY13', code: 0, label: '不可用', dead: true },
  { key: 'start', silk: 'KEY14', code: 1, label: '开始' },
  { key: 'down', silk: 'KEY15', code: 2, label: '下' },
  { key: 'select', silk: 'KEY16', code: 3, label: '选择' },
];

function cellClass(cell: KeyCell, on: boolean, readonly: boolean): string {
  return `keypad__key${cell.dead ? ' keypad__key--dead' : ''}${on ? ' keypad__key--on' : ''}${
    readonly || !cell.key ? ' keypad__key--static' : ''
  }`;
}

function cellLabel(cell: KeyCell): string {
  if (cell.silk === 'KEY13') {
    return `${cell.silk}（键号 ${cell.code}）不可用：扫描器用键号 0 表示"没有按键"，与"没按"无法区分`;
  }
  if (cell.dead) return `${cell.silk}（键号 ${cell.code}）未分配游戏功能`;
  return `${cell.label}（${cell.silk}，键号 ${cell.code}）`;
}

export function Keypad({ onPress, activeKey = null, disabled = false, readonly = false }: KeypadProps): JSX.Element {
  const renderCell = (cell: KeyCell | null, pos: string): JSX.Element => {
    if (!cell) return <span key={pos} aria-hidden="true" />;
    const on = activeKey === cell.key;
    const cls = cellClass(cell, on, readonly);
    const label = cellLabel(cell);
    if (readonly || !cell.key) {
      return (
        <span key={cell.silk} className={cls} aria-label={label}>
          <b>{cell.label}</b>
          <span>
            {cell.silk} · {cell.code}
          </span>
        </span>
      );
    }
    return (
      <button
        key={cell.silk}
        type="button"
        className={cls}
        onClick={() => onPress?.(cell.key as GameKey)}
        disabled={disabled}
        aria-label={label}
      >
        <b>{cell.label}</b>
        <span>
          {cell.silk} · {cell.code}
        </span>
      </button>
    );
  };

  return (
    <div className="keypad" role="group" aria-label="4×4 矩阵键盘的右下角（ROW0 整行 + ROW1/ROW2 的 COL1..COL3）">
      {ROWS_UPPER.map((row, ri) => row.map((cell, ci) => renderCell(cell, `${ri}-${ci}`)))}
      {ROW_BOTTOM.map((cell, ci) => renderCell(cell, `3-${ci}`))}
    </div>
  );
}
