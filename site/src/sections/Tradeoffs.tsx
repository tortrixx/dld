/**
 * Tradeoffs.tsx —— 工程设计与关键权衡
 *
 * 上一版把 7 个案例平铺成 7 × 6 个格子（42 个文字块），读起来是一堵墙。
 * 这一版改成**切换器**：左侧只列案例（编号 + 一句话标题），右侧只渲染当前选中的那一个，
 * 六步骨架做成竖向 stepper（问题 → 约束 → 方案 → 验证 → 结果 → 局限）。
 * 一次只看一个，反而更容易比较"每个案例都做了什么、剩了什么"。
 */

import { useState } from 'react';

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

export function Tradeoffs(): JSX.Element {
  const [slug, setSlug] = useState(CASES[0].slug);
  const current = CASES.find((c) => c.slug === slug) ?? CASES[0];

  return (
    <Section
      id="cases"
      num="05"
      kicker="Engineering Tradeoffs · ERR-001 ~ ERR-056"
      title="工程取舍：7 个案例"
      lede={
        <>
          <p>
            这个项目最花时间的不是"把功能写出来"，而是<strong>让每一句话都有可执行的证据</strong>。
            仓库里有一本 56 条的调试账本（<Src path="docs/06-硬件调试记录.md" />），
            每条都记着现象、根因、修法、验证与残余。下面是从中挑出的 7 条 ——
            挑的标准是：技术含量够、能从仓库核、能体现 FPGA 的真实约束
            （面积、时序、握手、几何正确性、验证方法学）。
          </p>
          <p className="note" style={{ marginTop: 'var(--s3)' }}>
            每条都保留了 <strong>"局限"</strong> 那一格。没有局限的工程案例，通常只是没找而已。
          </p>
        </>
      }
    >
      <div className="cases">
        {/* 左：案例列表 */}
        <div className="case-list" role="group" aria-label="工程案例列表">
          {CASES.map((c) => (
            <button
              key={c.slug}
              type="button"
              className="case-list__item"
              aria-pressed={c.slug === current.slug}
              onClick={() => setSlug(c.slug)}
            >
              <span className="case-list__err">{c.err}</span>
              <span className="case-list__t">{c.title}</span>
            </button>
          ))}
        </div>

        {/* 右：当前案例的六步 */}
        <div className="case-detail">
          <div className="case-detail__head">
            <span className="case-detail__err">{current.err}</span>
            <h3 className="case-detail__title">{current.title}</h3>
          </div>
          <div className="stepper">
            {STEPS.map((s) => (
              <div className={`step${s.key === 'limitation' ? ' step--limit' : ''}`} key={s.key}>
                <span className="step__k">{s.label}</span>
                <p className="step__v">
                  <RichText text={current[s.key] as string} />
                </p>
              </div>
            ))}
          </div>
          <p className="note" style={{ marginTop: 'var(--s5)' }}>
            完整条目（含更多验证细节与历史）：
            <Src path={current.doc.path}>{current.doc.path}</Src> · {current.doc.note}
          </p>
        </div>
      </div>

      {/* ---------------- 局限 ---------------- */}
      <div style={{ marginTop: 'var(--s9)' }}>
        <h3 className="sec__title" style={{ fontSize: 'var(--fs-h3)' }}>
          明确的局限与未做项
        </h3>
        <p className="note" style={{ marginTop: 'var(--s2)', marginBottom: 'var(--s5)' }}>
          "如实说明限制"不是一句态度，而是一份列表。下面每一条都能在仓库里找到出处；
          凡是已经关闭的历史局限（例如"Fmax 没达到 50 MHz"），本站<strong>不写</strong>。
        </p>
        <ul className="rows">
          {LIMITATIONS.map((l, i) => (
            <li className="limits-item" key={l.title}>
              <span className="limits-item__i">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <p className="limits-item__t">{l.title}</p>
                <p className="limits-item__d">
                  <RichText text={l.detail} />
                </p>
                <p className="limits-item__s">出处：{l.source}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  );
}
