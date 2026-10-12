/**
 * App.tsx —— 页面骨架
 *
 * 阅读顺序（也是本站的主张）：30 秒看懂 → 动手玩 → 看懂架构 →
 * 核数据 → 读工程取舍 → 找到文档 → 页尾。
 * 报头是唯一固定定位的元素，且只占 52px，不遮挡内容。
 */

import { Hero } from './sections/Hero';
import { Simulator } from './sections/Simulator';
import { Architecture } from './sections/Architecture';
import { Evidence } from './sections/Evidence';
import { Tradeoffs } from './sections/Tradeoffs';
import { DocsNav } from './sections/DocsNav';
import { Footer } from './sections/Footer';

const NAV: readonly { readonly href: string; readonly label: string }[] = [
  { href: '#sim', label: '01 模拟器' },
  { href: '#arch', label: '02 架构' },
  { href: '#evidence', label: '03 数据' },
  { href: '#cases', label: '04 工程取舍' },
  { href: '#docs', label: '05 文档' },
];

export function App(): JSX.Element {
  return (
    <>
      <a className="sr" href="#sim">
        跳到点阵模拟器
      </a>

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
          </nav>
        </div>
      </div>

      <main>
        <Hero />
        <Simulator />
        <Architecture />
        <Evidence />
        <Tradeoffs />
        <DocsNav />
      </main>

      <Footer />
    </>
  );
}
