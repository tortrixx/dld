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
  readonly onPress: (key: GameKey) => void;
  /** 最近按下的动作（用于 220 ms 的高亮反馈）。 */
  readonly activeKey: GameKey | null;
  readonly disabled?: boolean;
}

interface KeyCell {
  readonly key: GameKey | null;
  readonly silk: string;
  readonly code: number;
  readonly label: string;
  readonly dead?: boolean;
}

/** 按视觉顺序排的 3×3：ROW2 / ROW1 / ROW0，每行 COL1..COL3。 */
const GRID: readonly (readonly KeyCell[])[] = [
  [
    { key: null, silk: 'KEY6', code: 9, label: '—', dead: true },
    { key: 'up', silk: 'KEY7', code: 10, label: '上' },
    { key: 'rotate', silk: 'KEY8', code: 11, label: '旋转' },
  ],
  [
    { key: 'left', silk: 'KEY10', code: 5, label: '左' },
    { key: 'confirm', silk: 'KEY11', code: 6, label: '确认' },
    { key: 'right', silk: 'KEY12', code: 7, label: '右' },
  ],
  [
    { key: 'start', silk: 'KEY14', code: 1, label: '开始' },
    { key: 'down', silk: 'KEY15', code: 2, label: '下' },
    { key: 'select', silk: 'KEY16', code: 3, label: '选择' },
  ],
];

export function Keypad({ onPress, activeKey, disabled = false }: KeypadProps): JSX.Element {
  return (
    <div className="keypad" role="group" aria-label="4×4 矩阵键盘的右下 3×3 功能区块">
      {GRID.flat().map((cell) => {
        if (!cell.key) {
          return (
            <span
              key={cell.silk}
              className="keypad__key keypad__key--dead"
              aria-label={`${cell.silk}（键号 ${cell.code}）不可用：扫描器用键号 0 表示没有按键`}
            >
              <b>{cell.silk}</b>
              <span>{cell.label} · 键号 {cell.code}</span>
            </span>
          );
        }
        const on = activeKey === cell.key;
        return (
          <button
            key={cell.silk}
            type="button"
            className={`keypad__key${on ? ' keypad__key--on' : ''}`}
            onClick={() => onPress(cell.key as GameKey)}
            disabled={disabled}
            aria-label={`${cell.label}（${cell.silk}，键号 ${cell.code}）`}
          >
            <b>{cell.label}</b>
            <span>{cell.silk} · {cell.code}</span>
          </button>
        );
      })}
    </div>
  );
}
