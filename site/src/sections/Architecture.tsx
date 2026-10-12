/**
 * Architecture.tsx —— 系统架构
 *
 * 这一版把原来那张"5 列 × 12 行"的宽表换成了**可点的模块地图**：
 * 鼠标点一个模块，右侧只显示它的四件事（职责 / 吃什么 / 吐什么 / 关键机制）。
 * 一次看一个反而更容易横向比较，因为位置固定、扫视成本低；
 * 而完整互联关系仍由整机框图承担（框图只画相邻层主干，跨层连线进下面的对照表）。
 */

import { BlockDiagram, SIGNAL_LINKS } from '../components/BlockDiagram';
import { ModuleMap } from '../components/ModuleMap';
import { Section, Src, TableWrap, Tag } from '../components/ui';
import { CLOCK_TICKS, DIAG_TOPS, TOP_LEVEL } from '../data/facts';

export function Architecture(): JSX.Element {
  return (
    <Section
      id="arch"
      num="03"
      kicker="RTL Architecture · 12 modules + 1 package"
      title="架构：谁负责时间，谁负责空间"
      lede={
        <>
          <p>
            整机只有一个顶层 <code>puzzle_top</code>（唯一做引脚绑定的文件），它实例化 11 个子模块。
            骨架是一条<strong>职责切分</strong>：<code>game_fsm</code> 只管"时间与决策"
            （流程、倒计时、关卡切换、键号译码、音效选择），<code>puzzle_ctrl</code> 只管"空间"
            （落位、移动、旋转、边界、精确重叠、锁定与着色），两者之间只有命令脉冲与三个判决位。
            这样切开之后，两边都能单独仿真。
          </p>
        </>
      }
    >
      {/* ---------------- 整机框图 ---------------- */}
      <div className="frame">
        <BlockDiagram />
        <p className="figcap">
          <b>图 03 · puzzle_top 整机框图</b>（方框 = 真实 entity；编号只标<strong>相邻两层之间</strong>的主干流向）
          <br />
          连线依据：<Src path="rtl/puzzle_top.vhd" line={419} />（实例化区）与{' '}
          <Src path="rtl/puzzle_top.vhd" line={251} />（顶层内部信号声明）。
          跨层的连线（最典型的是 <code>clk_gen</code> 把 tick 广播给每一层、以及{' '}
          <code>game_fsm</code> 直接命令 <code>puzzle_ctrl</code>）在图上<strong>不画箭头</strong> ——
          一张"每层一根竖箭头"的图天生只能表达相邻层关系，硬画就会把
          "clk_gen 把 t_4hz 送给 buzzer_ctrl"画成"送给 game_fsm"，那是错的。所以它们只进下表。
          想看完整互联（含跨层连线）就走 <code>docs/图/dld-架构.drawio</code>。
        </p>
        <TableWrap label="图 03 的连线与信号对照表">
          <table className="tbl" style={{ marginTop: 'var(--s4)' }}>
            <thead>
              <tr>
                <th className="num">层</th>
                <th>从</th>
                <th>到</th>
                <th>信号（真实端名）</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={5} className="note" style={{ whiteSpace: 'normal' }}>
                  编号只标相邻两层之间的主干流向；<code>—</code> 表示跨层或同层内部的连线。
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
                  <td style={{ whiteSpace: 'normal' }}>{l.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </div>

      {/* ---------------- 模块地图 ---------------- */}
      <div style={{ marginTop: 'var(--s8)' }}>
        <h3 className="sec__title" style={{ fontSize: 'var(--fs-h3)' }}>
          12 个设计模块：点一个，只看它
        </h3>
        <p className="note" style={{ marginTop: 'var(--s2)', marginBottom: 'var(--s5)' }}>
          每一栏的"关键机制"都带真实常量或实测数值，不是形容词。
        </p>
        <ModuleMap />
      </div>

      {/* ---------------- 顶层引脚与时序约束 ---------------- */}
      {/* 顶层实体自身的职责已经在上面的模块地图里（它现在也是 12 张卡之一），
          这里只留它**独有的**东西：物理接口的真值源。两处重复讲同一件事是本项目要避免的。 */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-5">
          <div className="frame" style={{ height: '100%' }}>
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s3)' }}>
              <b>顶层只做两件别处做不了的事</b>
            </p>
            <p style={{ fontSize: '0.9rem' }}>
              ① <strong>引脚绑定</strong>：真值源是 <Src path="quartus/puzzle.qsf" /> ——
              它由 <Src path="scripts/gen_project.py" />{' '}
              <strong>生成</strong>，引脚号取自实验板手册、<strong>不手工改</strong>。
              <br />
              ② <strong>时序约束</strong>：<Src path="quartus/puzzle.sdc" />{' '}
              把板上 50 MHz 时钟写成 20 ns 的约束，`Fmax` 只能从 TimeQuest（`quartus_sta`）读 ——
              经典时序分析器（`quartus_tan`）<strong>不读</strong> <code>.sdc</code>，跑它只会得到空的 Fmax 列。
            </p>
            <p className="figcap" style={{ marginTop: 'var(--s3)' }}>
              顶层实体 <code>{TOP_LEVEL.entity}</code> 自身的职责见上面模块地图里的那一张卡。
            </p>
          </div>
        </div>
        <div className="col-7">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s4)' }}>
              <b>时钟拓扑</b> · 一条级联分频链，只有第一级面对 50 MHz
              （这条链的逐步推导见上一节「节拍链」播放器）
            </p>
            <TableWrap label="时钟拓扑表">
              <table className="tbl">
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
                      <td style={{ whiteSpace: 'normal' }}>{t.used}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </div>
        </div>
      </div>

      {/* ---------------- 诊断顶层 ---------------- */}
      <div style={{ marginTop: 'var(--s8)' }}>
        <h3 className="sec__title" style={{ fontSize: 'var(--fs-h3)' }}>
          三个诊断顶层：上板第一步用的"仪表"
        </h3>
        <p className="note" style={{ marginTop: 'var(--s2)', marginBottom: 'var(--s5)' }}>
          <strong>
            没有任何诊断顶层被 <code>puzzle_top</code> 实例化
          </strong>{' '}
          —— 它们是并列的备用顶层，同一份源文件列表里可选其一作为综合顶层。
          这正是这套工程"先证明引脚假设、再写功能"的证据。
        </p>
        <div className="grid12">
          {DIAG_TOPS.map((d) => (
            <div className="col-4" key={d.entity}>
              <div className="frame" style={{ height: '100%' }}>
                <p className="figcap" style={{ marginTop: 0 }}>
                  <b>{d.entity}</b>{' '}
                  <Tag>
                    <Src path={d.file}>源码</Src>
                  </Tag>
                </p>
                <p style={{ marginTop: 'var(--s3)', fontSize: '0.86rem' }}>
                  <b>什么时候用：</b>
                  {d.when}
                </p>
                <p style={{ marginTop: 'var(--s3)', fontSize: '0.86rem', color: 'hsl(var(--muted-foreground))' }}>
                  <b>里面是什么：</b>
                  {d.what}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}
