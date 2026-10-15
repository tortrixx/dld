/**
 * App.tsx —— 页面骨架
 *
 * 阅读顺序（也是本站的主张）：
 *   30 秒看懂 → 看一遍玩法（GIF）→ 看懂数据怎么随时间流 →
 *   看懂模块分工 → 核对数据 → 读工程取舍 → 找到文档。
 *
 * 报头是唯一固定定位的元素、只有 56px，不遮挡内容；
 * 右上角是主题切换（参照站同款：默认跟随系统、可显式覆盖）。
 */

import { ThemeToggle } from './components/ThemeToggle';
import { Hero } from './sections/Hero';
import { Demo } from './sections/Demo';
import { Flow } from './sections/Flow';
import { Architecture } from './sections/Architecture';
import { Evidence } from './sections/Evidence';
import { Tradeoffs } from './sections/Tradeoffs';
import { DocsNav } from './sections/DocsNav';
import { Footer } from './sections/Footer';
import { DOCS_SITE_URL } from './data/facts';

const NAV: readonly { readonly href: string; readonly label: string }[] = [
  { href: '#demo', label: '01 玩法' },
  { href: '#flow', label: '02 时序' },
  { href: '#arch', label: '03 架构' },
  { href: '#evidence', label: '04 数据' },
  { href: '#cases', label: '05 取舍' },
  { href: '#docs', label: '06 文档' },
];

/** 背景虚线网格：纯装饰（aria-hidden），fixed 铺满 + 中心径向遮罩。 */
function BackgroundGrid(): JSX.Element {
  return (
    <svg className="bg-grid" aria-hidden="true">
      <defs>
        <pattern id="dld-grid" width="24" height="24" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="24" y2="0" />
          <line x1="0" y1="0" x2="0" y2="24" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#dld-grid)" />
    </svg>
  );
}

export function App(): JSX.Element {
  return (
    <>
      <a className="sr" href="#demo">
        跳到玩法演示
      </a>
      <BackgroundGrid />

      <div className="masthead">
        <div className="shell masthead__in">
          <a className="masthead__id" href="#top" style={{ borderBottom: 0 }}>
            <b>DLD</b>
            <span>8×8 点阵拼图 / MAX II EPM1270</span>
          </a>
          <nav className="masthead__nav" aria-label="章节导航">
            {NAV.map((n) => (
              <a key={n.href} href={n.href}>
                {n.label}
              </a>
            ))}
            {/* 技术文档站是**另一个站点**（同一套工程事实），用绝对地址跳转 */}
            <a href={DOCS_SITE_URL} className="masthead__docs">
              技术文档 ↗
            </a>
            <ThemeToggle />
          </nav>
        </div>
      </div>

      <main>
        <Hero />
        <Demo />
        <Flow />
        <Architecture />
        <Evidence />
        <Tradeoffs />
        <DocsNav />
      </main>

      <Footer />
    </>
  );
}
