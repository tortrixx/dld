/**
 * ui.tsx —— 全站共用的结构件
 *
 * 抽出来的是**重复的结构**（章节头、图框、数据条、声明块），
 * 不是"为了抽象而抽象"：每一件都在页面上出现 3 次以上。
 * 视觉规则全部住在 `styles/app.css` 里，组件只负责语义与数据。
 */

import { Fragment, useState, type ReactNode } from 'react';

import { blob } from '../data/facts';

/* ---------------------------------------------------------------- 行内强调 */

/**
 * 极小的行内强调：把 `**这样**` 渲染成 `<strong>`。
 *
 * 为什么需要它：`src/data/facts.ts` 是纯数据（字符串），但里面的文案大量用了
 * `**强调**` 来标出关键约束。直接把字符串塞进 JSX 会把星号原样显示出来 ——
 * 这是真浏览器截图里抓到的内容 bug（卡片上明晃晃地写着 `**保证存在…**`）。
 *
 * 只处理这一种语法、只做一层，不引入 Markdown 解析器：数据保持可读，
 * 页面保持干净，也不用为此加依赖。
 */
export function RichText({ text }: { readonly text: string }): JSX.Element {
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  return (
    <>
      {parts.map((part, i) =>
        // split 带捕获组时，奇数下标就是被 `**` 包住的那一段
        i % 2 === 1 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>,
      )}
    </>
  );
}

/* ---------------------------------------------------------------- 章节 */

export interface SectionProps {
  /** 章节编号，如 "03"。 */
  readonly num: string;
  readonly title: string;
  readonly kicker: string;
  readonly lede?: ReactNode;
  readonly id: string;
  readonly children: ReactNode;
  /** 首屏下面的第一节不需要上边框。 */
  readonly flush?: boolean;
}

export function Section({ num, title, kicker, lede, id, children, flush = false }: SectionProps): JSX.Element {
  return (
    <section className={`sec${flush ? ' sec--flush' : ''}`} id={id} aria-labelledby={`${id}-h`}>
      <div className="shell">
        <header className="sec__head">
          <div className="sec__num" aria-hidden="true">
            {num}
          </div>
          <div>
            <h2 className="sec__title" id={`${id}-h`}>
              {title}
            </h2>
            <p className="sec__kicker">{kicker}</p>
            {lede ? <div className="sec__lede">{lede}</div> : null}
          </div>
        </header>
        {children}
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------- 图框 */

export interface FigureProps {
  readonly caption: string;
  /** 来源标注 —— 必填，因为"这张图哪来的"本身就是可信度的一部分。可以是节点，便于内嵌链接。 */
  readonly source: ReactNode;
  readonly src?: string;
  readonly alt?: string;
  readonly children?: ReactNode;
  /** true = 素材缺失，显示占位说明而不是空白（避免"看起来没问题"）。 */
  readonly missing?: boolean;
}

export function Figure({ caption, source, src, alt, children, missing = false }: FigureProps): JSX.Element {
  // 图加载失败（例如素材还没同步）时降级成"素材缺失"占位，
  // 而不是留一个破图标 —— 免得"图挂了"被当成"图没问题"。
  const [failed, setFailed] = useState(false);
  const unavailable = missing || failed;
  return (
    <figure className="figbox">
      {src && !unavailable ? (
        <img
          className="figbox__img"
          src={src}
          alt={alt ?? caption}
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : null}
      {children}
      {unavailable ? (
        <div className="figbox--missing">
          素材缺失：源文件不在 <code>docs/图/</code> 里
          <br />
          （页面按"缺失"显示，而不是留下空白当成没问题）
        </div>
      ) : null}
      <figcaption className="figbox__cap">
        <b>{caption}</b>
        <br />
        {source}
      </figcaption>
    </figure>
  );
}

/* ---------------------------------------------------------------- 表格容器 */

/**
 * 所有数据表的统一外壳：窄屏时**表自己滚动**，不让整页横向溢出。
 * （320px 下 5 列的技术表会把页面 scrollWidth 撑到 549px —— 这是真浏览器检查抓到的。）
 */
export function TableWrap({ children, label }: { readonly children: ReactNode; readonly label?: string }): JSX.Element {
  return (
    <div className="table-wrap" role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------- 数据条 */

export interface BarProps {
  readonly label: string;
  readonly used: number;
  readonly total: number;
  readonly unit: string;
  /** 满或接近满时用强调色 —— 这不是"好看"，是"这就是瓶颈"。 */
  readonly critical?: boolean;
}

export function Bar({ label, used, total, unit, critical = false }: BarProps): JSX.Element {
  const pct = Math.min(100, (used / total) * 100);
  return (
    <div className="bar" role="img" aria-label={`${label}：${used} / ${total} ${unit}（${pct.toFixed(1)}%）`}>
      <span>{label}</span>
      <span className="bar__track">
        <span className={`bar__fill${critical ? ' bar__fill--full' : ''}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="bar__v">
        {used} / {total} · {pct.toFixed(1)}%
      </span>
    </div>
  );
}

/* ---------------------------------------------------------------- 来源链接 */

/** 指向仓库里某个**已入库**文件的链接（路径由 facts.ts 统一生成，中文路径会被编码）。 */
export function Src({ path, line, children }: { readonly path: string; readonly line?: number; readonly children?: ReactNode }): JSX.Element {
  return (
    <a href={blob(path, line)} target="_blank" rel="noreferrer noopener">
      {children ?? path}
      {line ? `:${line}` : ''}
    </a>
  );
}

/* ---------------------------------------------------------------- 声明块 */

export function Caveat({ title, children }: { readonly title: string; readonly children: ReactNode }): JSX.Element {
  return (
    <div className="caveat" role="note">
      <span className="caveat__mark" aria-hidden="true">
        !
      </span>
      <div className="caveat__body">
        <b>{title}</b>
        <br />
        {children}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- 标签 */

export function Tag({ children, accent = false }: { readonly children: ReactNode; readonly accent?: boolean }): JSX.Element {
  return <span className={`tag${accent ? ' tag--acc' : ''}`}>{children}</span>;
}
