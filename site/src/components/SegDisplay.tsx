/**
 * SegDisplay.tsx —— 8 位数码管（DISP7 在最左，DISP0 在最右）
 *
 * 段码取自 `rtl/puzzle_pkg.vhd` 的 `DIG_*` 常量（a..g 低 7 位，高有效），
 * 所以字母 P / A / S / F / L 的形状是**照着硬件画的**，不是随便找的字体。
 * 其中 'S' 与 '5' 同形、'I' 用 '1' 的形状 —— 这是 7 段管的固有局限，题注里写明。
 */

import { SEGMENTS } from '../engine/engine';

export interface SegDisplayProps {
  /** 下标 = DISP 编号（0 = 最右）。 */
  readonly digits: readonly string[];
  readonly blank: readonly boolean[];
  /** 自检态要求整屏 2 Hz 闪烁（B1）；其余态这里是 false。 */
  readonly blink?: boolean;
  readonly label?: string;
}

const W = 30;
const H = 48;
const T = 5; // 段厚

/** 七个段的几何（a 上、b 右上、c 右下、d 下、e 左下、f 左上、g 中）。 */
const SEGMENTS_PATH: readonly { readonly bit: number; readonly points: string }[] = [
  { bit: 0, points: `${T},0 ${W - T},0 ${W - T - T / 2},${T} ${T + T / 2},${T}` },
  { bit: 1, points: `${W},${T} ${W},${H / 2 - T / 2} ${W - T},${H / 2 - T / 2 - T / 2} ${W - T},${T + T / 2}` },
  { bit: 2, points: `${W},${H / 2 + T / 2} ${W},${H - T} ${W - T},${H - T - T / 2} ${W - T},${H / 2 + T}` },
  { bit: 3, points: `${T},${H} ${W - T},${H} ${W - T - T / 2},${H - T} ${T + T / 2},${H - T}` },
  { bit: 4, points: `0,${H / 2 + T / 2} 0,${H - T} ${T},${H - T - T / 2} ${T},${H / 2 + T}` },
  { bit: 5, points: `0,${T} 0,${H / 2 - T / 2} ${T},${H / 2 - T / 2 - T / 2} ${T},${T + T / 2}` },
  {
    bit: 6,
    points: `${T + T / 2},${H / 2 - T / 2} ${W - T - T / 2},${H / 2 - T / 2} ${W - T},${H / 2} ${W - T - T / 2},${H / 2 + T / 2} ${T + T / 2},${H / 2 + T / 2} ${T},${H / 2}`,
  },
];

function Digit({ char, off, blink }: { readonly char: string; readonly off: boolean; readonly blink: boolean }): JSX.Element {
  const code = SEGMENTS[char] ?? SEGMENTS[' '];
  return (
    <svg viewBox={`-1 -1 ${W + 2} ${H + 2}`} aria-hidden="true" focusable="false">
      {SEGMENTS_PATH.map((seg) => {
        const on = !off && (code & (1 << seg.bit)) !== 0;
        return (
          <polygon
            key={seg.bit}
            points={seg.points}
            fill={on ? (blink ? 'var(--led-yellow)' : 'var(--led-red)') : '#1c1c20'}
            opacity={on ? 1 : 0.85}
          />
        );
      })}
    </svg>
  );
}

export function SegDisplay({ digits, blank, blink = false, label = '8 位数码管' }: SegDisplayProps): JSX.Element {
  return (
    <div className="seg-row" role="img" aria-label={`${label}：${readOut(digits, blank)}`}>
      {[7, 6, 5, 4, 3, 2, 1, 0].map((d) => (
        <div key={d} className={`seg${blank[d] ? ' seg--off' : ''}`}>
          <Digit char={digits[d] ?? ' '} off={Boolean(blank[d])} blink={blink} />
          <span className="seg__cat">DISP{d}</span>
        </div>
      ))}
    </div>
  );
}

/** 自左向右读出（DISP7 → DISP0），消隐位读作空格。 */
export function readOut(digits: readonly string[], blank: readonly boolean[]): string {
  const out: string[] = [];
  for (let d = 7; d >= 0; d -= 1) out.push(blank[d] ? ' ' : (digits[d] ?? ' '));
  return out.join('') || '全灭';
}
