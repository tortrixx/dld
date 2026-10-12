/**
 * DotMatrix.tsx —— 8×8 双色点阵
 *
 * 这是全站唯一允许出现红/绿/黄的地方：这三种颜色是**硬件的物理事实**
 * （双色点阵每点只有 灭 / 红 / 绿 / 黄 四种状态），不是设计选择。
 * 所以点阵内部的配色不参与页面配色系统。
 *
 * 交互：
 *   · 点一下格子 = 选中那一格所在的零片（等价于按【选择】，但更直觉）
 *   · 在点阵上拖动 = 朝拖动的方向移动一格（触屏与鼠标都支持）
 *   · 拖动阈值 18px，避免"手一抖就动了零片"
 */

import { useRef } from 'react';

import type { CellColor } from '../engine/engine';

export interface DotMatrixProps {
  /** [row][col] 的即时颜色。 */
  readonly cells: readonly (readonly CellColor[])[];
  /** 是否处于"告急幽灵"的绿色闪烁相位（闪烁交给 CSS，这里只标注语义）。 */
  readonly hintActive: boolean;
  /** 选中零片占据的格子（用于加描边，使"选中"不只靠颜色表达）。 */
  readonly selectedCells?: ReadonlySet<string>;
  readonly onTapCell?: (row: number, col: number) => void;
  readonly onSwipe?: (dir: 'up' | 'down' | 'left' | 'right') => void;
  readonly disabled?: boolean;
  readonly label?: string;
}

const DRAG_THRESHOLD = 18;

export function DotMatrix({
  cells,
  hintActive,
  selectedCells,
  onTapCell,
  onSwipe,
  disabled = false,
  label = '8×8 双色点阵',
}: DotMatrixProps): JSX.Element {
  const start = useRef<{ x: number; y: number } | null>(null);
  const dragged = useRef(false);
  /**
   * pointerdown 命中的格子。**必须在按下时记住它**：
   * 一旦调用了 setPointerCapture，后续 pointerup 的 target 会被重定向到
   * 捕获元素（也就是点阵容器本身），那时再 `closest('[data-cell]')` 就找不到了。
   * —— 这是真浏览器检查抓出来的一个真 bug：点一下零片完全没反应。
   */
  const pressedCell = useRef<{ r: number; c: number } | null>(null);

  const cellOf = (target: EventTarget | null): { r: number; c: number } | null => {
    const el = (target as HTMLElement | null)?.closest?.<HTMLElement>('[data-cell]');
    if (!el) return null;
    const [r, c] = (el.dataset.cell ?? '').split(',').map(Number);
    return Number.isFinite(r) && Number.isFinite(c) ? { r, c } : null;
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>): void => {
    if (disabled) return;
    start.current = { x: e.clientX, y: e.clientY };
    dragged.current = false;
    pressedCell.current = cellOf(e.target);
    try {
      // 指针捕获能保证手指滑出点阵也还能收到 pointerup；
      // 但它在"指针已经抬起"等情况下会抛 NotFoundError —— 那不该让整个交互挂掉。
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* 捕获失败不影响点选与滑动 */
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>): void => {
    if (disabled || !start.current || dragged.current) return;
    const dx = e.clientX - start.current.x;
    const dy = e.clientY - start.current.y;
    if (Math.abs(dx) < DRAG_THRESHOLD && Math.abs(dy) < DRAG_THRESHOLD) return;
    dragged.current = true;
    start.current = null;
    if (Math.abs(dx) >= Math.abs(dy)) onSwipe?.(dx > 0 ? 'right' : 'left');
    else onSwipe?.(dy > 0 ? 'down' : 'up');
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>): void => {
    if (disabled) return;
    const wasDrag = dragged.current;
    const cell = pressedCell.current;
    start.current = null;
    dragged.current = false;
    pressedCell.current = null;
    if (wasDrag || !onTapCell || !cell) return;
    // 拖动过就不当点击；按下与抬起落在不同格子也不算点击
    const up = cellOf(e.target);
    if (up && (up.r !== cell.r || up.c !== cell.c)) return;
    onTapCell(cell.r, cell.c);
  };

  return (
    <div
      className="matrix"
      role="grid"
      aria-label={label}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
    >
      {cells.map((row, r) =>
        row.map((color, c) => {
          const key = `${r},${c}`;
          const isSel = selectedCells?.has(key) ?? false;
          const isGhost = color === 'green' && hintActive;
          const cls = [
            'matrix__cell',
            color === 'off' ? null : `matrix__cell--${color}`,
            isGhost ? 'matrix__cell--ghost' : null,
            isSel ? 'matrix__cell--selected' : null,
          ]
            .filter(Boolean)
            .join(' ');
          return (
            <div
              key={key}
              data-cell={key}
              className={cls}
              role="gridcell"
              aria-label={`第 ${r + 1} 行第 ${c + 1} 列 · ${
                { off: '灭', red: '红', green: '绿', yellow: '黄' }[color]
              }${isGhost ? '（告急幽灵，2 Hz 闪）' : ''}${isSel ? ' · 当前选中' : ''}`}
            />
          );
        }),
      )}
    </div>
  );
}
