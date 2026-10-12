/**
 * Hero.tsx —— 首屏
 *
 * 30 秒内回答四个问题：这是什么、跑在什么硬件上、解决了什么任务、源码与文档在哪。
 * 右侧是**演示 GIF**（规则模型跑出来的一局，标注清楚不是板子实录）——
 * 用户明确要"贴一副演示图上去"，比让人在网页上自己点更直观，也少一大堆控件。
 */

import { Src, Tag } from '../components/ui';
import { PROJECT, REPO, SITE_URL, blob, figure } from '../data/facts';

const HERO_SPEC: readonly { readonly k: string; readonly v: string }[] = [
  { k: '器件', v: 'MAX II EPM1270T144C5 (1270 LE / 127 LAB / 144 脚 TQFP)' },
  { k: '资源', v: '1264 / 1270 LE · LAB 127 / 127（已满，真正的瓶颈）' },
  { k: '时序', v: 'Fmax 54.27 MHz · setup +1.572 ns · hold +1.078 ns · 0 条违例' },
  { k: 'RTL', v: 'VHDL-93 · 12 个设计模块 + 1 个包 · 纯 RTL（无 CPU、无 IP 核、无软核）' },
  { k: '输入', v: '4×4 矩阵键盘（8 个功能键，右下 3×3 标准十字）' },
  { k: '显示', v: '8×8 双色点阵（灭 / 红 / 绿 / 黄）+ 8 位数码管 + 蜂鸣器' },
  { k: '验证', v: '12 个模块/场景 · 179 条仿真断言全过 · 固件已烧录并读回校验 · 已上板复测' },
];

export function Hero(): JSX.Element {
  return (
    <header className="hero" id="top">
      <div className="shell">
        <div className="hero__grid">
          <div>
            <p className="hero__eyebrow fade">
              <span>FPGA / CPLD 课程设计</span>
              <span>{PROJECT.course}</span>
              <span>tortrixx/dld</span>
            </p>

            <h1 className="hero__title fade" style={{ ['--i' as string]: 1 } as React.CSSProperties}>
              {PROJECT.title}
              <em>{PROJECT.subtitle}</em>
            </h1>

            <p className="hero__lede fade" style={{ ['--i' as string]: 2 } as React.CSSProperties}>
              {PROJECT.oneLiner}
            </p>

            <div className="hero__cta fade" style={{ ['--i' as string]: 3 } as React.CSSProperties}>
              <a className="btn" href={REPO} target="_blank" rel="noreferrer noopener">
                源码仓库 GitHub →
              </a>
              <a className="btn btn--ghost" href="#flow">
                看数据怎么流
              </a>
              <a className="btn btn--ghost" href={blob('docs/03-仿真验证方案.md')} target="_blank" rel="noreferrer noopener">
                仿真验证方案
              </a>
              <a className="btn btn--ghost" href={blob('docs/05-资源利用与编译报告.md')} target="_blank" rel="noreferrer noopener">
                资源与时序报告
              </a>
            </div>

            <div
              className="fade"
              style={{ marginTop: 'var(--s6)', display: 'flex', gap: 'var(--s2)', flexWrap: 'wrap', ['--i' as string]: 4 } as React.CSSProperties}
            >
              <Tag accent>纯 RTL · 无 CPU</Tag>
              <Tag>VHDL-93</Tag>
              <Tag>Quartus II 9.1</Tag>
              <Tag>179 条断言全过</Tag>
              <Tag>已上板复测</Tag>
            </div>

            <div className="spec fade" style={{ ['--i' as string]: 5 } as React.CSSProperties}>
              {HERO_SPEC.map((row) => (
                <div className="spec__row" key={row.k}>
                  <span className="spec__k">{row.k}</span>
                  <span className="spec__v">{row.v}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="fade" style={{ ['--i' as string]: 2 } as React.CSSProperties}>
            <div className="panel">
              <div className="panel__label">
                <span>
                  <b>跑一局</b> · 规则模型自动演示
                </span>
                <span>非板子实录</span>
              </div>
              <img
                className="demo__gif"
                src={figure('demo-playthrough.gif')}
                alt="规则模型自动走完第一关的动画：自检 → 待机 → 预览目标图案 → 零片散落 → 旋转与移动 → 确认锁定 → 过关"
                width={640}
                height={420}
              />
              <p className="figcap">
                这是<strong>规则模型按 RTL 的规则自动走完的一局</strong>（自检 → 待机 → 预览 →
                散落 → 旋转/移动/确认 → 过关），每一帧都由站点同一份引擎算出。
                <strong>它不是开发板的录屏</strong>：网页不驱动硬件，板上的时序与音效这里没有复现。
                <br />
                规格：640 × 420 · 48 帧 · 14.1 s · 290 KiB · 循环播放（帧间差分，48 帧只占 290 KiB）。
                生成方式见 <Src path="site/scripts/gen-demo-frames.ts">gen-demo-frames.ts</Src> 与{' '}
                <Src path="site/scripts/render-demo-gif.py">render-demo-gif.py</Src>
                （后者是本站唯一需要 Pillow 的脚本，产物已入库，构建站点时<strong>不必</strong>重跑）。
              </p>
            </div>

            <div className="caveat caveat--ok" role="note" style={{ marginTop: 'var(--s5)' }}>
              <span className="caveat__mark" aria-hidden="true">
                ✓
              </span>
              <div className="caveat__body">
                <b>本站是工程展示，不是可玩游戏</b>，也不驱动任何 FPGA 硬件。
                想看每一拍到底发生了什么，去下一节的<strong>时序播放器</strong>；
                想核对数据，去「数据与证据」一节 —— 每个数字都带出处。
                <br />
                线上地址：
                <a href={SITE_URL} target="_blank" rel="noreferrer noopener">
                  {SITE_URL}
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
