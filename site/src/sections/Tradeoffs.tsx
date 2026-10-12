/**
 * Tradeoffs.tsx —— 工程设计与关键权衡
 *
 * 每条案例都按同一个骨架写：问题 → 约束 → 方案 → 验证 → 结果 → 局限。
 * 骨架本身就是这一节的主张：**只讲"最后写成什么样"是没用的，
 * 要讲清"当时被什么卡住、怎么证明改对了、还剩什么问题"。**
 *
 * 案例只取自 `docs/06-硬件调试记录.md` 里已经记录的 ERR 条目，
 * 没有把"可能遇到的问题"编成一节。
 */

import { RichText, Section, Src } from '../components/ui';
import { CASES, LIMITATIONS, type Case as CaseData } from '../data/facts';

const STEPS: readonly { readonly key: keyof CaseData; readonly label: string }[] = [
  { key: 'problem', label: '问题' },
  { key: 'constraint', label: '约束' },
  { key: 'solution', label: '方案' },
  { key: 'verification', label: '验证' },
  { key: 'result', label: '结果' },
  { key: 'limitation', label: '局限' },
];

function CaseBlock({ c }: { readonly c: CaseData }): JSX.Element {
  return (
    <article className="case">
      <header className="case__head">
        <div className="case__err">{c.err}</div>
        <h3 className="case__title">{c.title}</h3>
      </header>
      <dl className="case__steps">
        {STEPS.map((s) => (
          <div className={`case__step${s.key === 'limitation' ? ' case__step--limit' : ''}`} key={s.key}>
            <dt>{s.label}</dt>
            <dd>
              <RichText text={c[s.key] as string} />
            </dd>
          </div>
        ))}
      </dl>
      <p className="case__src">
        完整条目（含更多验证细节与历史）：<Src path={c.doc.path}>{c.doc.path}</Src> · {c.doc.note}
      </p>
    </article>
  );
}

export function Tradeoffs(): JSX.Element {
  return (
    <Section
      id="cases"
      num="05"
      kicker="Engineering Tradeoffs · ERR-001 ~ ERR-056"
      title="工程设计与关键权衡"
      lede={
        <>
          <p>
            这个项目最花时间的不是"把功能写出来"，而是<strong>让每一句话都有可执行的证据</strong>。
            仓库里有一本 56 条的调试账本（<Src path="docs/06-硬件调试记录.md" />），
            每条都记着现象、根因、修法、验证与残余。
            下面是从中挑出的 7 条 —— 挑的标准是：技术含量够、能从仓库核、能体现 FPGA 的真实约束
            （面积、时序、握手、几何正确性、验证方法学）。
          </p>
          <p className="note" style={{ marginTop: 'var(--s3)' }}>
            每条都保留了 <strong>"局限"</strong> 那一格。没有局限的工程案例，
            通常只是没找而已。
          </p>
        </>
      }
    >
      <div className="cases">
        {CASES.map((c) => (
          <CaseBlock c={c} key={c.slug} />
        ))}
      </div>

      {/* ---------------- 局限 ---------------- */}
      <div style={{ marginTop: 'var(--s9)' }}>
        <h3 className="case__title" style={{ marginBottom: 'var(--s2)' }}>
          明确的局限与未做项
        </h3>
        <p className="note" style={{ marginBottom: 'var(--s5)' }}>
          "如实说明限制"不是一句态度，而是一份列表。下面每一条都能在仓库里找到出处；
          凡是已经关闭的历史局限（例如"Fmax 没达到 50 MHz"），本站<strong>不写</strong>。
        </p>
        <ul className="limits">
          {LIMITATIONS.map((l, i) => (
            <li className="limits__item" key={l.title}>
              <span className="limits__i">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <p className="limits__t">{l.title}</p>
                <p className="limits__d">
                  <RichText text={l.detail} />
                </p>
                <p className="limits__s">出处：{l.source}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}
