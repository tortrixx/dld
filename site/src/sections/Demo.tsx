/**
 * Demo.tsx —— 玩法演示（替代原来的交互式模拟器）
 *
 * 用户的原话是"网页上模拟游戏没那个必要，但可以贴一副演示图上去"。
 * 所以这里只做三件事：把那一局讲清楚（4 步）、把键位画出来（不用表格）、
 * 把三关的参数摆开。想"动手"的需求由上面首屏的 GIF 满足。
 */

import { Keypad } from '../components/Keypad';
import { Section, Src, Tag, TableWrap } from '../components/ui';
import { KEY_MAP } from '../engine/geometry';
import { LEVELS } from '../engine/geometry';

const PLAY_STEPS: readonly { readonly t: string; readonly d: string }[] = [
  {
    t: '开机自检 → 待机',
    d: '整屏黄 + 2 Hz 闪、8 位数码管全显 "8"，持续 2 秒；随后点阵全灭、DISP7 显示 5、DISP0 显示 1。',
  },
  {
    t: '按【开始】→ 预览 5 秒',
    d: '点阵显示完整目标图案（第一关是图 4-1 的 4×3 矩形），DISP7 从 5 倒数到 1 —— 记形状的时间。',
  },
  {
    t: '零片散落 → 拼',
    d: '三块零片随机落在互不重叠的位置，初始朝向是 1/1/2（**所以不旋转就拼不出来**）。用【选择】切块、方向键移动、【旋转】原地转 90°。',
  },
  {
    t: '逐块【确认】锁定 → 判胜负',
    d: '拼对了位置按【确认】，该块变黄并不再能动。全部锁定后比较"零片并集 == 目标图案"：相等就过关/通关，不等就判负；超时也判负。',
  },
];

export function Demo(): JSX.Element {
  return (
    <Section
      id="demo"
      num="01"
      kicker="How it plays · 一局怎么玩"
      title="玩法：四步，三关"
      lede={
        <>
          <p>
            一句话讲完规则：<strong>看 5 秒目标图案 → 零片被打散 → 用矩阵键盘把零片拼回原样 →
            逐块确认锁定 → 判对错</strong>。没有实时压力之外的机制：不旋转就拼不出来，是设计上刻意
            保证的（见「工程取舍」里的 ERR-043）。
          </p>
        </>
      }
    >
      <div className="grid12">
        <div className="col-7">
          <ol className="demo__steps rows">
            {PLAY_STEPS.map((s, i) => (
              <li className="demo__step" key={s.t}>
                <span className="demo__step-i">{String(i + 1).padStart(2, '0')}</span>
                <div>
                  <p className="demo__step-t">{s.t}</p>
                  {/* 这里单独渲染 strong：文案里的 **重点** 是给人看的强调 */}
                  <p className="demo__step-d">
                    {s.d.split('**').map((part, k) =>
                      k % 2 === 1 ? <strong key={k}>{part}</strong> : <span key={k}>{part}</span>,
                    )}
                  </p>
                </div>
              </li>
            ))}
          </ol>
          <p className="note" style={{ marginTop: 'var(--s4)' }}>
            时限：第一关 30 s（题目 B5 明文）、第二关 40 s（B10 明文）、第三关 60 s（A2 扩展关，自拟）。
            倒计时 ≤10 s 时，点阵会把你<strong>还没拼上的目标格子</strong>用绿色 2 Hz 闪出来当提示。
          </p>
        </div>

        <div className="col-5">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s3)' }}>
              <b>键位</b> · 4×4 矩阵键盘的右下 3×3 区块（与板子手册附图 26 一致）
            </p>
            <Keypad readonly />
            <p className="figcap">
              键号 = 4×ROW + COL（ROW0 在最下、COL0 在最左）。布局与译码在{' '}
              <Src path="rtl/game_fsm.vhd" line={139} /> 的一个函数里，改键位只改那一处。
              灰色那个 <b>KEY13</b> 键号是 0，而扫描器用键号 0 表示"没有按键"，
              所以它<strong>不可用</strong> —— 这是硬件事实，不是疏忽。
            </p>
          </div>

          <div className="panel" style={{ marginTop: 'var(--s5)' }}>
            <div className="panel__label">
              <span>三关参数</span>
              <span>零片 · 预览 · 限时 · 图案</span>
            </div>
            <div className="rows">
              {LEVELS.map((l) => (
                <div className="spec__row" key={l.level} style={{ borderBottom: 'none' }}>
                  <span className="spec__k">第 {l.level} 关</span>
                  <span className="spec__v">
                    {l.shapeIds.length} 块 · 预览 {l.previewSeconds} s · 限时 {l.playSeconds} s
                    <br />
                    <span className="note">
                      {l.pattern === 'fixed-l1' && '图 4-1（题目指定，固定）'}
                      {l.pattern === 'fixed-l2' && '阶梯形（自拟但固定，B10 字面）'}
                      {l.pattern === 'random' && '四幅库随机：田 / 十 / S·Z / 阶梯'}
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <details style={{ marginTop: 'var(--s7)' }}>
        <summary className="mono-label" style={{ cursor: 'pointer', color: 'var(--acc)' }}>
          展开：完整的键位映射表（9 行）
        </summary>
        <TableWrap label="键位映射表">
          <table className="tbl" style={{ marginTop: 'var(--s4)' }}>
            <caption>
              键位映射 = <Src path="rtl/game_fsm.vhd" line={139} /> 的 key_of() 逐条对应
            </caption>
            <thead>
              <tr>
                <th>丝印</th>
                <th className="num">键号</th>
                <th>功能</th>
              </tr>
            </thead>
            <tbody>
              {KEY_MAP.map((k) => (
                <tr key={k.silk} style={k.code === 0 ? { opacity: 0.55 } : undefined}>
                  <td>{k.silk}</td>
                  <td className="num">{k.code}</td>
                  <td style={{ whiteSpace: 'normal' }}>{k.fn}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </details>

      <p className="note" style={{ marginTop: 'var(--s5)' }}>
        <Tag accent>与硬件的关系</Tag>{' '}
        这一节讲的是板子上的玩法；上面首屏那张 GIF 由站点的规则模型渲染，用于说明规则，<strong>不驱动硬件</strong>。
      </p>
    </Section>
  );
}
