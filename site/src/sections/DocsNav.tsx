/**
 * DocsNav.tsx —— 文档与源码导航 + 部署说明
 *
 * 所有链接都由 `facts.ts` 的 `blob()` 生成，指向仓库里**已入库**的文件；
 * 中文路径逐段编码，避免不同浏览器对未编码 UTF-8 路径的处理差异。
 *
 * 本页最上面那一块是**跨站**入口：本站负责"一眼看懂"，
 * 技术文档站（`book/`，Material for MkDocs）负责"逐条查证"。
 * 两者共用同一套工程事实，所以这里只做摘要 + 深链，不复制文档站的实现。
 */

import { RichText, Section, Src, Tag } from '../components/ui';
import {
  DEPLOY,
  DOCS_ENTRIES,
  DOCS_SITE_URL,
  DOC_ENTRIES,
  REPO,
  SITE_URL,
  SOURCE_ENTRIES,
  blob,
  tree,
} from '../data/facts';

export function DocsNav(): JSX.Element {
  return (
    <Section
      id="docs"
      num="06"
      kicker="Docs & Source · 每条链接都指向入库文件"
      title="文档与源码导航"
      lede={
        <>
          <p>
            这一节只做一件事：把<strong>真正有用的入口</strong>按"想了解什么"排好，
            并且每一条都指向仓库里实际存在、且已入库的文件。
            编译产物（<code>.rpt</code> / <code>.pof</code> / <code>.pin</code>）被{' '}
            <code>.gitignore</code> 挡掉了、克隆后不存在，所以<strong>一条都不链</strong>。
          </p>
        </>
      }
    >
      {/* ---------------- 跨站入口：技术文档站 ---------------- */}
      <div className="docscard">
        <div className="docscard__head">
          <p className="docscard__title">技术文档站 · Material for MkDocs</p>
          <Tag>同一个仓库 · 同一套事实</Tag>
        </div>
        <p className="docscard__lede">
          本站（<code>site/</code>）的定位是<strong>一眼看懂</strong>：首屏、交互点阵、时序播放器、演示动画。
          要做<strong>逐条查证</strong>就换到文档站（<code>book/</code>）：那里有 11 个模块的接口契约、
          跨模块连接总表、数据字典与位序约定、时序契约、184 条断言的逐条判据、资源/时序报告和答辩稿。
          两边读的是<strong>同一份</strong> <code>facts/facts.json</code>，所以数字不会互相打架。
          <br />
          <a href={DOCS_SITE_URL} target="_blank" rel="noreferrer noopener">
            {DOCS_SITE_URL}
          </a>
        </p>
        <div className="navlist">
          {DOCS_ENTRIES.map((d) => (
            <a
              className="navlist__item"
              key={d.href}
              href={DOCS_SITE_URL + d.href}
              target="_blank"
              rel="noreferrer noopener"
            >
              <span className="navlist__title">
                {d.title}
                <br />
                <Tag>{d.tag}</Tag>
              </span>
              <span className="navlist__sum"><RichText text={d.summary} /></span>
              <span className="navlist__path">book/docs/{d.href}</span>
            </a>
          ))}
        </div>
      </div>

      <div className="navlist">
        {DOC_ENTRIES.map((d) => (
          <a className="navlist__item" key={d.path} href={blob(d.path)} target="_blank" rel="noreferrer noopener">
            <span className="navlist__title">
              {d.title}
              <br />
              <Tag>{d.tag}</Tag>
            </span>
            <span className="navlist__sum"><RichText text={d.summary} /></span>
            <span className="navlist__path">{d.path}</span>
          </a>
        ))}
      </div>

      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-12">
          <h3 className="case__title">源码、测试台与工具</h3>
          <p className="note" style={{ marginTop: 'var(--s2)' }}>
            想直接读代码就从这里进。仓库结构（<Src path="README.md" /> §三）：
            <code>rtl/</code> 16 个 VHDL、<code>sim/</code> 12 个 Python 测试台 + 12 份{' '}
            <code>.vwf</code>、<code>scripts/</code> 构建与审计工具、<code>quartus/</code> 工程与溯源、
            <code>docs/</code> 交付文档、<code>refs/</code> 课程原始资料。
          </p>
        </div>
        <div className="col-12">
          <div className="navlist" style={{ marginTop: 'var(--s4)' }}>
            {SOURCE_ENTRIES.map((s) => {
              const isDir = s.path.endsWith('/');
              return (
                <a
                  className="navlist__item"
                  key={s.path}
                  href={isDir ? tree(s.path) : blob(s.path)}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  <span className="navlist__title">{s.title}</span>
                  <span className="navlist__sum"><RichText text={s.summary} /></span>
                  <span className="navlist__path">{s.path}</span>
                </a>
              );
            })}
          </div>
        </div>
      </div>

      {/* ---------------- 部署 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-12">
          <h3 className="case__title">本地运行与部署到 GitHub Pages</h3>
        </div>
        <div className="col-6">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0 }}>
              <b>本地运行</b>
            </p>
            <pre className="note" style={{ margin: 0, overflowX: 'auto' }}>
              {DEPLOY.local.join('\n')}
            </pre>
            <p className="figcap" style={{ marginTop: 'var(--s3)' }}>
              站点是纯静态的：没有后端、没有遥测、没有外部字体或 CDN 请求
              （字体走系统字体栈），所以离线也能打开。
            </p>
          </div>
        </div>
        <div className="col-6">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0 }}>
              <b>部署到 GitHub Pages</b>
            </p>
            <pre className="note" style={{ margin: 0, overflowX: 'auto' }}>
              {DEPLOY.pages.join('\n')}
            </pre>
            <p className="figcap" style={{ marginTop: 'var(--s3)' }}>
              <RichText text={DEPLOY.baseNote} />
            </p>
          </div>
        </div>
        <div className="col-12" style={{ marginTop: 'var(--s4)' }}>
          <div className="caveat" role="note">
            <span className="caveat__mark" aria-hidden="true">
              ✓
            </span>
            <div className="caveat__body">
              <b>
                部署状态：已上线 ——{' '}
                <a href={SITE_URL} target="_blank" rel="noreferrer noopener">
                  {SITE_URL}
                </a>
              </b>
              <br />
              <RichText text={DEPLOY.status} />
              仓库里此前<strong>没有任何</strong> CI / Pages 配置（无 <code>.github/</code>、无 <code>.yml</code>、
              无 <code>gh-pages</code> 分支），本次新增的工作流是
              <code>.github/workflows/pages.yml</code>，它与原有硬件工程完全隔离：
              只构建 <code>site/</code>、不动 <code>rtl/</code> / <code>sim/</code> /{' '}
              <code>quartus/</code>，也不会覆盖任何既有流程（因为原本就没有流程）。
            </div>
          </div>
        </div>
      </div>

      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-12">
          <p className="note">
            仓库地址：<a href={REPO} target="_blank" rel="noreferrer noopener">{REPO}</a>
            {' · '}
            站点目录：<Src path="site/README.md">site/README.md</Src>
            {' · '}
            本站引用的图素材由 <Src path="site/scripts/sync-figures.mjs">sync-figures.mjs</Src>{' '}
            在每次 dev / build 前从 <code>docs/图/</code> 同步进 <code>public/figures/</code>
            （副本不入库，避免同一张图有两份真值源）。
          </p>
        </div>
      </div>
    </Section>
  );
}
