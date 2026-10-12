/**
 * charts.tsx —— 手写 SVG 图表（零依赖，入场即动画）
 *
 * 为什么自己画而不用图表库：本站要的东西很窄（横向条形、时序预算、逐模块断言数、
 * 演进折线），而一个图表库动辄 100 KB+ 且带来自己的配色与排版，会和设计系统打架。
 * 这里每个图都是纯函数 + CSS 动画，产物只有几 KB，而且**数据与出处写在同一个组件里**。
 *
 * 诚实性要求（本项目纪律）：所有数字都来自入库的真值源，不能现编。
 * 每个图都带 `caption` 说明口径与出处。
 */

import { type ReactNode } from 'react';

/* ================================================================== *
 * 横向条形图（用于"逐模块断言数"这类一维量）
 * ================================================================== */

export interface BarDatum {
  readonly label: string;
  readonly value: number;
  /** 强调色（例如"整机"那一根、或接近上限的那些）。 */
  readonly accent?: boolean;
  readonly note?: string;
}

export function BarChart({
  data,
  unit,
  max,
  caption,
  title,
  right,
}: {
  readonly data: readonly BarDatum[];
  readonly unit: string;
  readonly max?: number;
  readonly caption: ReactNode;
  readonly title: string;
  readonly right?: ReactNode;
}): JSX.Element {
  const top = max ?? Math.max(...data.map((d) => d.value));
  const rowH = 22;
  const gap = 6;
  const labelW = 108;
  const valueW = 46;
  const width = 620;
  const barW = width - labelW - valueW;
  const height = data.length * (rowH + gap) + 8;

  return (
    <div className="chart">
      <div className="chart__head">
        <p className="chart__title">{title}</p>
        {right}
      </div>
      <svg className="chart__svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}：${data.map((d) => `${d.label} ${d.value}${unit}`).join('，')}`}>
        {/* 竖向参考网格 */}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <line
            key={t}
            className="chart__grid"
            x1={labelW + barW * t}
            y1={0}
            x2={labelW + barW * t}
            y2={height - 4}
          />
        ))}
        {data.map((d, i) => {
          const y = i * (rowH + gap) + 4;
          const w = Math.max(1, (d.value / top) * barW);
          return (
            <g key={d.label}>
              <text x={0} y={y + rowH / 2 + 3.5}>
                {d.label}
              </text>
              <rect
                className={`chart__bar${d.accent ? ' chart__bar--acc' : ''}`}
                x={labelW}
                y={y + 3}
                width={w}
                height={rowH - 8}
                style={{ animationDelay: `${i * 0.035}s` }}
              />
              <text className="cv" x={labelW + barW + valueW - 4} y={y + rowH / 2 + 3.5} textAnchor="end">
                {d.value}
              </text>
              {d.note ? (
                <title>
                  {d.label}：{d.value}
                  {unit}（{d.note}）
                </title>
              ) : null}
            </g>
          );
        })}
      </svg>
      <p className="chart__cap">{caption}</p>
    </div>
  );
}

/* ================================================================== *
 * 时序预算（一根 20 ns 的尺子：数据路径 + slack = 周期）
 * ================================================================== */

export function TimingBudget({
  periodNs,
  dataPathNs,
  slackNs,
  caption,
  title,
}: {
  readonly periodNs: number;
  readonly dataPathNs: number;
  readonly slackNs: number;
  readonly caption: ReactNode;
  readonly title: string;
}): JSX.Element {
  const width = 620;
  const h = 74;
  const x0 = 92;
  const usable = width - x0 - 16;
  const pxPerNs = usable / periodNs;
  const dataW = dataPathNs * pxPerNs;
  const slackW = slackNs * pxPerNs;

  return (
    <div className="chart">
      <div className="chart__head">
        <p className="chart__title">{title}</p>
      </div>
      <svg
        className="chart__svg"
        viewBox={`0 0 ${width} ${h}`}
        role="img"
        aria-label={`时序预算：时钟周期 ${periodNs} ns，最差数据路径 ${dataPathNs} ns，余量 ${slackNs} ns`}
      >
        <text x={0} y={26}>
          数据路径
        </text>
        <rect className="chart__bar" x={x0} y={14} width={dataW} height={16} />
        <text className="cv" x={x0 + dataW + 6} y={26}>
          {dataPathNs} ns
        </text>

        <text x={0} y={54}>
          余量 slack
        </text>
        <rect className="chart__bar chart__bar--acc" x={x0 + dataW} y={42} width={slackW} height={16} />
        <text className="cv" x={x0 + dataW + slackW + 6} y={54}>
          +{slackNs} ns
        </text>

        {/* 20 ns 约束线 */}
        <line className="chart__limit" x1={x0 + usable} y1={4} x2={x0 + usable} y2={h - 6} />
        <text x={x0 + usable} y={h - 8} textAnchor="end" style={{ fill: 'var(--acc)' }}>
          约束 {periodNs} ns（50 MHz）
        </text>
        <text x={x0} y={h - 8}>
          0
        </text>
      </svg>
      <p className="chart__cap">{caption}</p>
    </div>
  );
}

/* ================================================================== *
 * 演进折线（资源/时序随工作阶段变化）
 * ================================================================== */

export interface Point {
  readonly label: string;
  readonly le: number;
  readonly fmax: number;
  readonly note?: string;
}

export function EvolutionChart({
  points,
  caption,
  title,
}: {
  readonly points: readonly Point[];
  readonly caption: ReactNode;
  readonly title: string;
}): JSX.Element {
  const width = 640;
  const height = 220;
  const padL = 46;
  const padR = 52;
  const padT = 18;
  const padB = 42;
  const maxLe = 1300;
  const minF = 34;
  const maxF = 58;

  const x = (i: number): number => padL + (i * (width - padL - padR)) / Math.max(1, points.length - 1);
  const yLe = (le: number): number => padT + (1 - le / maxLe) * (height - padT - padB);
  const yF = (f: number): number => padT + (1 - (f - minF) / (maxF - minF)) * (height - padT - padB);

  const lePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${yLe(p.le).toFixed(1)}`).join(' ');
  const fPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${yF(p.fmax).toFixed(1)}`).join(' ');

  return (
    <div className="chart">
      <div className="chart__head">
        <p className="chart__title">{title}</p>
        <p className="chart__cap" style={{ marginTop: 0 }}>
          <span style={{ color: 'hsl(var(--foreground))' }}>— LE</span> ·{' '}
          <span style={{ color: 'var(--acc)' }}>— Fmax</span>
        </p>
      </div>
      <svg
        className="chart__svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`资源与时序演进：${points.map((p) => `${p.label} ${p.le} LE / ${p.fmax} MHz`).join('，')}`}
      >
        {/* 上限线：1270 LE 与 50 MHz 约束 */}
        <line className="chart__limit" x1={padL} y1={yLe(1270)} x2={width - padR} y2={yLe(1270)} />
        <text x={padL + 2} y={yLe(1270) - 4} style={{ fill: 'var(--acc)' }}>
          1270 LE（器件上限）
        </text>
        <line className="chart__grid" x1={padL} y1={yF(50)} x2={width - padR} y2={yF(50)} />
        <text x={padL + 2} y={yF(50) - 4}>
          50 MHz 约束
        </text>

        <path className="chart__line" d={lePath} style={{ stroke: 'hsl(var(--foreground))' }} />
        <path className="chart__line" d={fPath} />

        {points.map((p, i) => (
          <g key={p.label}>
            <circle className="chart__dot" cx={x(i)} cy={yLe(p.le)} r={3.2} style={{ fill: 'hsl(var(--foreground))', animationDelay: `${i * 0.06}s` }} />
            <circle className="chart__dot" cx={x(i)} cy={yF(p.fmax)} r={3.2} style={{ animationDelay: `${i * 0.06}s` }} />
            <text x={x(i)} y={height - padB + 16} textAnchor="middle">
              {p.label}
            </text>
            <text className="cv" x={x(i)} y={height - padB + 30} textAnchor="middle">
              {p.le} / {p.fmax.toFixed(1)}
            </text>
            {p.note ? (
              <title>
                {p.label}：{p.le} LE，Fmax {p.fmax} MHz。{p.note}
              </title>
            ) : null}
          </g>
        ))}

        <line className="chart__axis" x1={padL} y1={height - padB} x2={width - padR} y2={height - padB} />
        <text x={0} y={padT + 6}>
          LE
        </text>
        <text x={width - padR + 6} y={padT + 6} style={{ fill: 'var(--acc)' }}>
          MHz
        </text>
      </svg>
      <p className="chart__cap">{caption}</p>
    </div>
  );
}

/* ================================================================== *
 * 利用率细线条（保留"细线 + 数字右对齐"的老语法，加了入场动效）
 * ================================================================== */

export interface UtilDatum {
  readonly label: string;
  readonly used: number;
  readonly total: number;
  readonly unit: string;
  readonly critical?: boolean;
}

export function UtilizationBars({ data }: { readonly data: readonly UtilDatum[] }): JSX.Element {
  return (
    <div className="bars rows">
      {data.map((d) => {
        const pct = Math.min(100, (d.used / d.total) * 100);
        return (
          <div className="bar-row" key={d.label}>
            <span className="mono-label">{d.label}</span>
            <span
              className="bar-row__track"
              role="img"
              aria-label={`${d.label}：${d.used} / ${d.total} ${d.unit}（${pct.toFixed(1)}%）`}
            >
              <span
                className={`bar-row__fill${d.critical ? ' bar-row__fill--critical' : ''}`}
                style={{ width: `${pct}%` }}
              />
            </span>
            <span className="bar-row__v">
              {d.used} / {d.total} · {pct.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
