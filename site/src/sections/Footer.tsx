/**
 * Footer.tsx —— 页尾
 *
 * 只放能核实的四类信息：仓库入口、技术栈、文档入口、完成状态。
 * **不加**个人简介、奖项、团队成员、学校背书、合作方 —— 那些东西本站没有依据。
 */

import { Src } from '../components/ui';
import { BUILD_PROVENANCE, PROJECT, REPO, blob } from '../data/facts';

const DOC_LINKS: readonly { readonly label: string; readonly path: string }[] = [
  { label: 'README · 项目总览', path: 'README.md' },
  { label: '00 · 规范理解与需求', path: 'docs/00-规范理解与需求.md' },
  { label: '02 · 模块详细设计', path: 'docs/02-模块详细设计.md' },
  { label: '03 · 仿真验证方案', path: 'docs/03-仿真验证方案.md' },
  { label: '05 · 资源利用与编译报告', path: 'docs/05-资源利用与编译报告.md' },
  { label: '06 · 硬件调试记录（ERR-001~056）', path: 'docs/06-硬件调试记录.md' },
  { label: 'HANDOFF · 编译 / 仿真 / 烧录手册', path: 'HANDOFF.md' },
  { label: 'AI_LOG · AI 工具使用记录', path: 'AI_LOG.md' },
];

const SOURCE_LINKS: readonly { readonly label: string; readonly path: string }[] = [
  { label: 'rtl/ · 16 个 VHDL 源文件', path: 'rtl/' },
  { label: 'sim/ · 12 个测试台与轮次记录', path: 'sim/rounds/' },
  { label: 'scripts/ · 构建与审计工具', path: 'scripts/' },
  { label: 'quartus/ · 工程与构建溯源', path: 'quartus/' },
  { label: 'docs/图/ · 图清单与截图流程', path: 'docs/图/README.md' },
  { label: 'site/ · 本站源码', path: 'site/' },
];

export function Footer(): JSX.Element {
  return (
    <footer className="foot">
      <div className="shell">
        <div className="foot__grid">
          <div>
            <p className="foot__h">项目</p>
            <p style={{ fontSize: '1.05rem', fontWeight: 700, lineHeight: 1.4 }}>{PROJECT.title}</p>
            <p style={{ fontSize: '0.86rem', color: 'hsl(var(--muted-foreground))', marginTop: 'var(--s2)' }}>
              {PROJECT.subtitle}
              <br />
              {PROJECT.course}
            </p>
            <p style={{ marginTop: 'var(--s4)' }}>
              <a className="btn" href={REPO} target="_blank" rel="noreferrer noopener">
                源码仓库 →
              </a>
            </p>
          </div>

          <div>
            <p className="foot__h">文档入口</p>
            <div className="foot__list">
              {DOC_LINKS.map((d) => (
                <a key={d.path} href={blob(d.path)} target="_blank" rel="noreferrer noopener">
                  {d.label}
                </a>
              ))}
            </div>
          </div>

          <div>
            <p className="foot__h">源码与证据</p>
            <div className="foot__list">
              {SOURCE_LINKS.map((d) => (
                <a
                  key={d.path}
                  href={d.path.endsWith('/') ? `${REPO}/tree/main/${encodeURI(d.path)}` : blob(d.path)}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  {d.label}
                </a>
              ))}
            </div>
          </div>

          <div>
            <p className="foot__h">技术栈</p>
            <div className="foot__list">
              <span>{PROJECT.device}</span>
              <span>{PROJECT.hdl} · 纯 RTL（无 CPU / 无 IP 核）</span>
              <span>{PROJECT.tool}</span>
              <span>8×8 双色点阵 + 4×4 矩阵键盘 + 8 位数码管 + 蜂鸣器</span>
            </div>
            <p className="foot__h" style={{ marginTop: 'var(--s5)' }}>
              完成状态
            </p>
            <div className="foot__list">
              <span>功能全部完成 · 最后一条挂起口径已闭环</span>
              <span>已上板复测通过</span>
              <span>179 条仿真断言全过 · 固件已烧录并读回校验</span>
              <span>
                最后编译：{BUILD_PROVENANCE.timestamp}
                <br />
                <span style={{ color: 'hsl(var(--muted-foreground))' }}>git {BUILD_PROVENANCE.gitHead}</span>
              </span>
            </div>
          </div>
        </div>

        <div className="foot__base">
          <span>
            本站是 <Src path="site/">site/</Src> 下的静态站点，与 <code>rtl/</code> /
            <code>sim/</code> / <code>quartus/</code> 完全隔离，不参与也不影响硬件工程。
          </span>
          <span>
            页面上每个数字都带出处；未经核实的说法一律不写。
            <br />
            浏览器点阵模拟器用于演示玩法，<strong>不驱动 FPGA 硬件</strong>。
          </span>
        </div>
      </div>
    </footer>
  );
}
