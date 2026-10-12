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
  // 空数组 ⇒ Math.max() = -Infinity；全 0 ⇒ 0 ⇒ 0/0 = NaN ⇒ width="NaN"（图形静默消失）。
  const top = Math.max(1, max ?? Math.max(0, ...data.map((d) => d.value)));
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
              {d.note ? <title>{`${d.label}：${d.value}${unit}（${d.note}）`}</title> : null}
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
  const h = 92;
  const x0 = 92;
  // ⚠️ 右边必须留出**标签宽度**（原来只留 16px，"+1.572 ns" 的文本画到 x≈646、
  //    越过 620 的 viewBox 跑到绘图区外，还和"约束 20 ns"挤在一起 —— 读者会以为
  //    "余量落在约束线之外"，而事实正好相反）。
  const labelW = 104;
  const usable = width - x0 - labelW;
  const pxPerNs = usable / periodNs;
  const dataW = dataPathNs * pxPerNs;
  const slackW = slackNs * pxPerNs;
  const ticks = [0, periodNs / 2, periodNs];

  return (
    <div className="chart">
      <div className="chart__head">
        <p className="chart__title">{title}</p>
      </div>
      <svg
        className="chart__svg"
        viewBox={`0 0 ${width} ${h}`}
        role="img"
        aria-label={`时序预算：时钟周期 ${periodNs} ns，最差数据路径 ${dataPathNs} ns，余量 +${slackNs} ns`}
      >
        {/* 数据路径 */}
        <text x={0} y={22}>
          数据路径
        </text>
        <rect className="chart__bar" x={x0} y={10} width={dataW} height={16} />
        <text className="cv" x={x0 + dataW / 2} y={22} textAnchor="middle" style={{ fill: 'hsl(var(--background))' }}>
          {dataPathNs} ns
        </text>

        {/* 余量 */}
        <text x={0} y={50}>
          余量 slack
        </text>
        <rect className="chart__bar chart__bar--acc" x={x0 + dataW} y={38} width={slackW} height={16} />
        {/* 值右对齐到约束线左侧（画在条形以外会溢出画布） */}
        <text className="cv" x={x0 + usable - 4} y={50} textAnchor="end" style={{ fill: 'var(--acc-ink)' }}>
          +{slackNs} ns
        </text>

        {/* 基线 + 0 / 半周期 / 约束 三个刻度 */}
        <line className="chart__axis" x1={x0} y1={h - 22} x2={x0 + usable} y2={h - 22} />
        {ticks.map((tv) => (
          <g key={tv}>
            <line className="chart__grid" x1={x0 + tv * pxPerNs} y1={h - 26} x2={x0 + tv * pxPerNs} y2={h - 18} />
            <text x={x0 + tv * pxPerNs} y={h - 8} textAnchor={tv === 0 ? 'start' : tv === periodNs ? 'end' : 'middle'}>
              {tv} ns
            </text>
          </g>
        ))}
        {/* 20 ns 约束线（只画在绘图区内） */}
        <line className="chart__limit" x1={x0 + usable} y1={2} x2={x0 + usable} y2={h - 22} />
        <text x={x0 + usable} y={72} textAnchor="end" style={{ fill: 'var(--acc-ink)' }}>
          约束 {periodNs} ns（{Math.round(1000 / periodNs)} MHz）
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
  // viewBox 与"实际渲染宽度"要接近 1:1：这张图原放在半栏（约 430px）里，
  // 640 宽的 viewBox 被缩到 0.67×，9.5px 的刻度字实际只剩约 6.4px —— 读不了。
  // 现在它固定整宽显示，并且字号统一抬到 11px。
  const width = 660;
  const height = 260;
  const padL = 62;
  const padR = 66;
  const padT = 26;
  const padB = 62;
  const maxLe = 1300;
  const minF = 34;
  const maxF = 58;

  const x = (i: number): number => padL + (i * (width - padL - padR)) / Math.max(1, points.length - 1);
  const yLe = (le: number): number => padT + (1 - le / maxLe) * (height - padT - padB);
  const yF = (f: number): number => padT + (1 - (f - minF) / (maxF - minF)) * (height - padT - padB);

  const lePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${yLe(p.le).toFixed(1)}`).join(' ');
  const fPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i).toFixed(1)} ${yF(p.fmax).toFixed(1)}`).join(' ');
  const last = points[points.length - 1];
  const lastX = x(points.length - 1);

  return (
    <div className="chart">
      <div className="chart__head">
        <p className="chart__title">{title}</p>
        <p className="chart__cap" style={{ marginTop: 0 }}>
          <span style={{ color: 'hsl(var(--foreground))' }}>— LE（左轴）</span> ·{' '}
          <span style={{ color: 'var(--acc)' }}>— Fmax（右轴）</span>
        </p>
      </div>
      <svg
        className="chart__svg"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`资源与时序演进：${points.map((p) => `${p.label} ${p.le} LE / ${p.fmax} MHz`).join('，')}`}
      >
        {/* 左轴（LE）三条刻度 */}
        {[0, 650, 1300].map((v) => (
          <g key={`le${v}`}>
            <line className="chart__grid" x1={padL} y1={yLe(v)} x2={width - padR} y2={yLe(v)} />
            <text x={padL - 8} y={yLe(v) + 3.5} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {/* 右轴（MHz）三条刻度 */}
        {[34, 46, 58].map((v) => (
          <g key={`f${v}`}>
            <text className="cv" x={width - padR + 8} y={yF(v) + 3.5} style={{ fill: 'var(--acc-ink)' }}>
              {v}
            </text>
          </g>
        ))}

        {/* 器件上限与 50 MHz 约束：文字画在线**下方**，不再压在折线上 */}
        <line className="chart__limit" x1={padL} y1={yLe(1270)} x2={width - padR} y2={yLe(1270)} />
        <text x={padL + 2} y={yLe(1270) + 12} style={{ fill: 'var(--acc-ink)' }}>
          1270 LE 器件上限
        </text>
        <line className="chart__grid" x1={padL} y1={yF(50)} x2={width - padR} y2={yF(50)} />
        <text x={padL + 2} y={yF(50) - 5}>
          50 MHz 约束
        </text>

        <path className="chart__line" d={lePath} style={{ stroke: 'hsl(var(--foreground))' }} />
        <path className="chart__line" d={fPath} />

        {/* 末点（当前值）单独强调：竖虚线 + 空心大字重圆点 + 直接标注，
            免得"最后一点与历史点同形"被读成同一类读数。 */}
        <line className="chart__limit" x1={lastX} y1={padT} x2={lastX} y2={height - padB} />
        <text x={lastX - 4} y={padT - 8} textAnchor="end" className="cv">
          当前 {last.le} LE / {last.fmax.toFixed(2)} MHz
        </text>

        {points.map((p, i) => {
          const isLast = i === points.length - 1;
          return (
            <g key={p.label}>
              <circle
                className="chart__dot"
                cx={x(i)}
                cy={yLe(p.le)}
                r={isLast ? 5 : 3.2}
                style={{ fill: isLast ? 'hsl(var(--background))' : 'hsl(var(--foreground))', stroke: isLast ? 'hsl(var(--foreground))' : 'none', strokeWidth: 2, animationDelay: `${i * 0.06}s` }}
              />
              <circle
                className="chart__dot"
                cx={x(i)}
                cy={yF(p.fmax)}
                r={isLast ? 5 : 3.2}
                style={{ animationDelay: `${i * 0.06}s` }}
              />
              <text x={x(i)} y={height - padB + 16} textAnchor="middle">
                {p.label}
              </text>
              <text className="cv" x={x(i)} y={height - padB + 30} textAnchor="middle">
                {p.le} LE / {p.fmax.toFixed(1)} MHz
              </text>
              {p.note ? <title>{`${p.label}：${p.le} LE，Fmax ${p.fmax} MHz。${p.note}`}</title> : null}
            </g>
          );
        })}

        <line className="chart__axis" x1={padL} y1={height - padB} x2={width - padR} y2={height - padB} />
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
