/**
 * Hero.tsx —— 首屏
 *
 * 首屏要回答四个问题（30 秒内）：这是什么、跑在什么硬件上、解决了什么任务、
 * 源码与文档在哪。
 *
 * 右侧那张点阵**不是装饰画**：它是规则模型在"复位后第一局"跑出来的真实散落帧
 * （`PIECE_ORI_INIT` = 1/1/2，见下方图注）。用真图而不是示意图，
 * 是因为本站的纪律是"不把合成图伪装成实验结果"—— 反过来也成立：能拿真数据就不用画的。
 */

import { createInitialState, frame, reducer, type GameState } from '../engine/engine';
import { DotMatrix } from '../components/DotMatrix';
import { RichText, Src, Tag } from '../components/ui';
import { PROJECT, REPO, blob } from '../data/facts';
import { LEVELS } from '../engine/geometry';

/** 复位后第一局的散落帧：LFSR 种子固定，所以这一帧**是可复现的**。 */
function heroFrame(): GameState {
  let s: GameState = { ...createInitialState(), phase: 'idle' };
  s = reducer(s, { type: 'press', key: 'start' });
  for (let i = 0; i < LEVELS[0].previewSeconds * 4; i += 1) s = reducer(s, { type: 'tick' });
  return s;
}

const HERO_SPEC: readonly { readonly k: string; readonly v: string }[] = [
  { k: '器件', v: PROJECT.device },
  { k: '资源', v: '1264 / 1270 LE · LAB 127 / 127（已满）' },
  { k: '时序', v: 'Fmax 54.27 MHz · setup +1.572 ns · 0 违例' },
  { k: 'RTL', v: 'VHDL-93 · 12 个设计模块 + 1 个包 · 纯 RTL（无 CPU / 无 IP 核）' },
  { k: '输入', v: '4×4 矩阵键盘（8 个功能键，右下 3×3 标准十字）' },
  { k: '显示', v: '8×8 双色点阵（灭 / 红 / 绿 / 黄）+ 8 位数码管' },
  { k: '音频', v: '蜂鸣器方波 · 8 音高 · 16 步乐句（三关各一首背景曲）' },
  { k: '验证', v: '12 个模块/场景 · 179 条仿真断言全过 · 已上板复测通过' },
];

export function Hero(): JSX.Element {
  const s = heroFrame();
  const f = frame(s);

  return (
    <header className="hero" id="top">
      <div className="shell">
        <div className="hero__grid">
          <div>
            <p className="hero__eyebrow">
              <span>FPGA / CPLD 课程设计</span>
              <span>{PROJECT.course}</span>
              <span>tortrixx/dld</span>
            </p>

            <h1 className="hero__title">
              {PROJECT.title}
              <em>{PROJECT.subtitle}</em>
            </h1>

            <p className="hero__lede">{PROJECT.oneLiner}</p>

            <div className="hero__cta">
              <a className="btn" href={REPO} target="_blank" rel="noreferrer noopener">
                源码仓库 GitHub →
              </a>
              <a className="btn btn--ghost" href="#sim">
                直接玩点阵模拟器
              </a>
              <a className="btn btn--ghost" href={blob('docs/03-仿真验证方案.md')} target="_blank" rel="noreferrer noopener">
                仿真验证方案
              </a>
              <a className="btn btn--ghost" href={blob('docs/05-资源利用与编译报告.md')} target="_blank" rel="noreferrer noopener">
                资源与时序报告
              </a>
            </div>

            <div style={{ marginTop: 'var(--s6)', display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap' }}>
              <Tag accent>纯 RTL · 无 CPU</Tag>
              <Tag>VHDL-93</Tag>
              <Tag>Quartus II 9.1</Tag>
              <Tag>MAX II EPM1270T144C5</Tag>
              <Tag>179 条断言全过</Tag>
            </div>

            {/* 硬件与实测规格：放在左栏而不是右栏，是为了让两栏高度接近 ——
                首版把这张表放在右侧，左栏下面留了一大片空白（版式上很难看）。 */}
            <table className="spec" style={{ marginTop: 'var(--s7)' }}>
              <caption className="sr">项目硬件与实测规格</caption>
              <tbody>
                {HERO_SPEC.map((row) => (
                  <tr className="spec__row" key={row.k}>
                    <th className="spec__k" scope="row">
                      {row.k}
                    </th>
                    <td className="spec__v"><RichText text={row.v} /></td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="note" style={{ marginTop: 'var(--s4)' }}>
              上面每个数字都指得到仓库里一个<strong>已入库</strong>的文件：
              资源与时序的真值源是 <Src path="quartus/build_provenance.json" /> 与{' '}
              <Src path="docs/05-资源利用与编译报告.md" />；断言的分布见{' '}
              <Src path="docs/03-仿真验证方案.md" />。本站不复述没有出处的数字。
            </p>
          </div>

          <div>
            <div className="panel">
              <div className="panel__label">
                <span>
                  <b>第 1 关散落帧</b> · 规则模型实跑
                </span>
                <span>复位后第一局 · 可复现</span>
              </div>
              <DotMatrix
                cells={f.cells}
                hintActive={false}
                disabled
                label="第 1 关散落后的点阵画面（未锁定的零片为红色）"
              />
              <p className="figcap" style={{ color: 'var(--panel-ink-2)' }}>
                <b style={{ color: 'var(--panel-ink)' }}>图 00 · 第 1 关散落帧</b>
                <br />
                三块零片（1×3 横条 3 格 / 3-2-1 阶梯 6 格 / L 形 3 格，共 12 格），
                初始朝向 <b style={{ color: 'var(--panel-ink)' }}>1 / 1 / 2</b>
                （<code style={{ color: 'var(--led-yellow)' }}>PIECE_ORI_INIT</code> 的前三位）。
                正因为这个初始朝向，<b style={{ color: 'var(--panel-ink)' }}>不旋转就拼不出来</b>
                —— 该性质由 <Src path="scripts/check_geometry.py" /> 穷举证明，
                并在本站的单元测试里复算。
              </p>
            </div>

            <div className="note" style={{ marginTop: 'var(--s5)' }}>
              <p>
                <strong>这一帧是真的跑出来的</strong>，不是画出来的示意图：
                它与页面里那个可操作模拟器共用同一份规则模型
                （<code>site/src/engine/</code>），而模型的几何与判定又逐条对应{' '}
                <Src path="rtl/puzzle_ctrl.vhd" />、<Src path="rtl/puzzle_pkg.vhd" />。
                复位后 LFSR 种子固定为 <code>0x5A</code>，所以这一局是<strong>可复现</strong>的。
              </p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
