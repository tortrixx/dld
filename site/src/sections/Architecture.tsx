/**
 * Architecture.tsx —— 系统架构
 *
 * 全部模块名来自 `rtl/`，没有自创名字。框图与源码一致；
 * 拿不准的连接**不补全**，而是明说"顶层里这个网没有读者"。
 */

import { BlockDiagram, SIGNAL_LINKS } from '../components/BlockDiagram';
import { RichText, Section, Src, TableWrap } from '../components/ui';
import { CLOCK_TICKS, DIAG_TOPS, MODULES, TOP_LEVEL } from '../data/facts';

const TIER_LABEL: Record<string, string> = {
  io: '输入输出 / 驱动',
  core: '时序与决策',
  store: '常量查找表',
  top: '整机顶层',
};

export function Architecture(): JSX.Element {
  return (
    <Section
      id="arch"
      num="03"
      kicker="RTL Architecture · 12 modules + 1 package"
      title="系统架构：谁负责时间，谁负责空间"
      lede={
        <>
          <p>
            整机只有一个顶层 <code>puzzle_top</code>（唯一做引脚绑定的文件），
            它实例化 11 个子模块（见 <Src path="rtl/puzzle_top.vhd" /> 的 component 声明区与端口关联）。
            设计的骨架是一条<strong>职责切分</strong>：<code>game_fsm</code> 只管"时间与决策"（流程、倒计时、关卡切换、
            键号译码、音效选择），<code>puzzle_ctrl</code> 只管"空间"（落位、移动、旋转、边界、精确重叠、
            锁定与着色），两者之间只有命令脉冲与三个判决位。这样切开之后，两边都能单独仿真。
          </p>
        </>
      }
    >
      <div className="frame">
        <BlockDiagram />
        <p className="figcap">
          <b>图 03 · puzzle_top 整机框图</b>（方框 = 真实 entity；实时信号名见下表）
          <br />
          连线依据：<Src path="rtl/puzzle_top.vhd" line={419} />（实例化区）与{' '}
          <Src path="rtl/puzzle_top.vhd" line={251} />（顶层内部信号声明）。
          图上只放编号、信号名放在下面的对照表里 —— 因为把信号名直接写在连线上会互相压字，
          第一版就是这么糊掉的。只画主干；顶层里那些<strong>没有读者</strong>的悬空调试网
          （<code>kp_raw</code> / <code>release</code> / <code>t_100</code> / <code>t_40</code> /{' '}
          <code>piece_n</code> / <code>sel_idx</code> / <code>pos_dbg</code> / <code>lock_dbg</code> /{' '}
          <code>scanrow</code>，以及显式接 <code>open</code> 的 <code>o_ori</code>）一条都没画 ——
          画上去就等于声称它们在功能里有用。
        </p>
        <TableWrap label="图 03 的连线与信号对照表">
          <table className="tbl" style={{ marginTop: 'var(--s4)' }}>
            <thead>
              <tr>
                <th className="num">#</th>
                <th>从</th>
                <th>到</th>
                <th>信号（真实端名）</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={5} className="note" style={{ whiteSpace: 'normal' }}>
                  编号只标<strong>相邻两层之间</strong>的主干流向；<code>—</code> 表示跨层或同层内部的连线。
                  为什么不给跨层连线也画箭头：一张"每层一根竖箭头"的图天生只能表达相邻层关系，
                  硬画就会把"<code>clk_gen</code> 的 <code>t_4hz</code> 送给 <code>buzzer_ctrl</code>"
                  画成"送给 <code>game_fsm</code>"—— 那是错的。所以跨层连线只进这张表。
                </td>
              </tr>
              {SIGNAL_LINKS.map((l) => (
                <tr key={`${l.via}-${l.from}-${l.signals}`}>
                  <td className="num">{l.via ?? '—'}</td>
                  <td style={{ whiteSpace: 'normal' }}>{l.from}</td>
                  <td style={{ whiteSpace: 'normal' }}>{l.to}</td>
                  <td style={{ whiteSpace: 'normal' }}>
                    <code>{l.signals}</code>
                  </td>
                  <td style={{ whiteSpace: 'normal' }}><RichText text={l.note} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </div>

      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-12">
          <h3 className="case__title">12 个设计模块逐个交代：吃什么、吐什么、凭什么</h3>
          <p className="note" style={{ marginTop: 'var(--s2)' }}>
            每一行的"关键机制"都带真实常量或实测数值，不是形容词。
          </p>
        </div>
      </div>

      <TableWrap label="12 个设计模块清单">
      <table className="tbl" style={{ marginTop: 'var(--s5)' }}>
        <caption>
          设计模块清单 · 名字全部取自 <Src path="rtl/" /> · 面积读数来自聚合报告
        </caption>
        <thead>
          <tr>
            <th>文件 / entity</th>
            <th>职责</th>
            <th>输入（吃什么）</th>
            <th>输出（吐什么）</th>
            <th>关键机制与实测数</th>
          </tr>
        </thead>
        <tbody>
          {MODULES.map((m) => (
            <tr key={m.entity}>
              <td style={{ whiteSpace: 'normal', minWidth: '13ch' }}>
                <Src path={m.file}>{m.entity}</Src>
                <br />
                <span className="note">{TIER_LABEL[m.tier]}</span>
              </td>
              <td style={{ whiteSpace: 'normal' }}><RichText text={m.job} /></td>
              <td style={{ whiteSpace: 'normal' }}><RichText text={m.consumes} /></td>
              <td style={{ whiteSpace: 'normal' }}><RichText text={m.produces} /></td>
              <td style={{ whiteSpace: 'normal' }}><RichText text={m.mechanism} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      </TableWrap>

      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-12">
          <h3 className="case__title">整机顶层：它自己做了什么</h3>
        </div>
        <div className="col-5">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0 }}>
              <b>{TOP_LEVEL.entity}</b>（<Src path={TOP_LEVEL.file} />）
              <br />
              {TOP_LEVEL.job}
            </p>
            <p style={{ marginTop: 'var(--s3)', fontSize: '0.9rem', color: 'var(--ink-2)' }}>
              <RichText text={TOP_LEVEL.detail} />
            </p>
            <p className="figcap" style={{ marginTop: 'var(--s3)' }}>
              引脚真值源：<Src path="quartus/puzzle.qsf" />（由{' '}
              <Src path="scripts/gen_project.py" /> 生成，<strong>不手工改引脚</strong>）；
              时序约束：<Src path="quartus/puzzle.sdc" />。
            </p>
          </div>
        </div>
        <div className="col-7">
          <TableWrap label="时钟拓扑">
          <table className="tbl">
            <caption>时钟拓扑：一条级联分频链，只有第一级面对 50 MHz</caption>
            <thead>
              <tr>
                <th>tick</th>
                <th className="num">频率</th>
                <th className="num">周期</th>
                <th>谁在用</th>
              </tr>
            </thead>
            <tbody>
              {CLOCK_TICKS.map((t) => (
                <tr key={t.name}>
                  <td>{t.name}</td>
                  <td className="num">{t.freq}</td>
                  <td className="num">{t.period}</td>
                  <td style={{ whiteSpace: 'normal' }}><RichText text={t.used} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          </TableWrap>
          <p className="note" style={{ marginTop: 'var(--s3)' }}>
            <Src path="rtl/clk_gen.vhd" /> 把 50 MHz 逐级往下分，后面每一级只数上一级来的脉冲 ——
            这也是"谁能在 50 MHz 上跑"这个问题的答案：只有第一级。
            复位来自上电计数器（实测约 9 ms）与按键消抖（20 ms）的<strong>或</strong>，高有效。
          </p>
        </div>
      </div>

      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-12">
          <h3 className="case__title">
            三个诊断顶层：上板第一步用的"仪表"，不属于主数据通路
          </h3>
          <p className="note" style={{ marginTop: 'var(--s2)' }}>
            <strong>没有任何诊断顶层被 <code>puzzle_top</code> 实例化</strong> ——
            它们是并列的备用顶层，同一份源文件列表里可选其一作为综合顶层。
            这正是这套工程"先证明引脚假设、再写功能"的证据。
          </p>
        </div>
        <div className="col-12">
          <div className="case__steps" style={{ marginTop: 'var(--s4)' }}>
            {DIAG_TOPS.map((d) => (
              <dl className="case__step" key={d.entity}>
                <dt>{d.entity}</dt>
                <dd>
                  <Src path={d.file} />
                  <br />
                  <strong>什么时候用：</strong>
                  <RichText text={d.when} />
                  <br />
                  <strong>里面是什么：</strong>
                  <RichText text={d.what} />
                </dd>
              </dl>
            ))}
          </div>
        </div>
      </div>
    </Section>
  );
}
