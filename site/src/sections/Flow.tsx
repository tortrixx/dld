/**
 * Flow.tsx —— 「时序与数据流」一节（本次改版的核心新增）
 *
 * 用户的诉求是："用动态图表、draw.io 动态流程图解释数据流随时间传播、
 * 每个模块之间的数据传输通道和时序过程"。落实成三件东西：
 *   ① 可播放的**时序播放器**（`DataFlow` 组件）：每个场景一条线性流水线，
 *      一步步走，每一步高亮"这一拍在动的模块与通道"，配真实时间刻度与出处；
 *   ② 左边那块**仪表**显示的确实是"这一拍"的画面（规则模型实算，不是示意图）；
 *   ③ 一份可编辑的 **draw.io 源文件**（`docs/图/dld-架构.drawio`）与 Quartus GUI
 *      实测截图，供答辩时改图/放大看细节。
 */

import { DataFlow } from '../components/DataFlow';
import { Figure, Section, Src } from '../components/ui';
import { blob, figure } from '../data/facts';

const READ_ORDER: readonly { readonly k: string; readonly v: string }[] = [
  {
    k: '① 节拍链',
    v: '50 MHz 怎么变成 125 Hz 帧扫描与 25/21 Hz 内容刷新 —— 先看清"时间从哪来"。',
  },
  {
    k: '② 一次按键',
    v: '手指按下到被接受约 45 ms（扫描 + 4 轮消抖），之后还要等一帧才在画面上看到（≤40/48 ms）⇒ 端到端约 85–93 ms。这条最能把"跨模块"讲明白。',
  },
  {
    k: '③ 一局流程',
    v: '6 个状态、每一步的时长与判据打哪来（题目要求 vs 自拟取舍）。',
  },
  {
    k: '④ 旋转的几何',
    v: '为什么"盒内转 + 补锚点偏移"和"在紧包围盒里转"等价，而且能省 229 个 LE。',
  },
];

export function Flow(): JSX.Element {
  return (
    <Section
      id="flow"
      num="02"
      kicker="Timing & Dataflow · 可播放"
      title="时序播放器：数据是怎么随时间走的"
      lede={
        <>
          <p>
            静态框图能说明"谁连着谁"，但说明不了"什么时候发生、经过了多少毫秒、
            哪一拍在做校验"。这一节把四个最难看懂的过程做成了<strong>可以逐步播放的时间线</strong>：
            点【播放】，看脉冲沿着流水线一节一节走，右边那块点阵与数码管显示的就是这一拍的画面。
          </p>
        </>
      }
    >
      <div className="grid12" style={{ marginBottom: 'var(--s6)' }}>
        {READ_ORDER.map((r, i) => (
          <div className="col-6" key={r.k}>
            <div className="frame fade" style={{ ['--i' as string]: i } as React.CSSProperties}>
              <p className="figcap" style={{ marginTop: 0 }}>
                <b>{r.k}</b>
              </p>
              <p style={{ marginTop: 'var(--s2)', fontSize: '0.88rem', color: 'hsl(var(--muted-foreground))' }}>{r.v}</p>
            </div>
          </div>
        ))}
      </div>

      <DataFlow />

      <p className="note" style={{ marginTop: 'var(--s6)' }}>
        时间刻度与信号名全部核实自源码与文档：<Src path="rtl/puzzle_pkg.vhd" /> 的常量表、
        <Src path="rtl/clk_gen.vhd" /> 的分频链、<Src path="rtl/puzzle_ctrl.vhd" /> 的渲染与校验流水、
        <Src path="rtl/game_fsm.vhd" /> 的状态机，以及 <Src path="docs/02-模块详细设计.md" /> 里
        "一行 npc+2 拍 ⇒ 一帧 40/48 拍"的推导。
        <strong>本页不写没有出处的时序数字</strong> —— 这也是为什么这里能放心把它当"说明"看。
      </p>

      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-7">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s4)' }}>
              <b>图 02 · 完整互联关系（可编辑源文件）</b>
              <br />
              上面那个播放器为了可读性只画"当前场景"的一条线；要看全貌就用 draw.io 打开——
              每个方框都是 <code>rtl/</code> 里真实的 entity，连线上的信号名取自{' '}
              <Src path="rtl/puzzle_top.vhd" line={251} /> 的端口关联。
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--s3)' }}>
              <a className="btn btn--ghost" href={blob('docs/图/dld-架构.drawio')} target="_blank" rel="noreferrer noopener">
                打开 draw.io 源文件
              </a>
              <a className="btn btn--ghost" href={blob('rtl/puzzle_top.vhd')} target="_blank" rel="noreferrer noopener">
                看顶层源码
              </a>
            </div>
            <p className="figcap">
              <code>docs/图/dld-架构.drawio</code> 是纯文本 XML，可以直接在{' '}
              <a href="https://app.diagrams.net/" target="_blank" rel="noreferrer noopener">
                app.diagrams.net
              </a>{' '}
              或 VS Code 的 draw.io 插件里改，改完存回仓库即生效（网页里的框图是它的一份精简重绘）。
            </p>
          </div>
        </div>
        <div className="col-5">
          <Figure
            src={figure('gui-clk_gen.png')}
            caption="Quartus GUI 实测仿真截图 · clk_gen 分频链"
            source={
              <>
                <code>docs/图/GUI-clk_gen.png</code>：在 Quartus II 波形编辑器里打开{' '}
                <code>sim/clk_gen.vwf</code> 后截屏（标题栏已裁掉，那条里含本机用户名）。
                图里能看到工程名、节点名列表与时间刻度 —— 这是<strong>实测</strong>图；
                脚本画的矢量波形只能当辅助对照，不能当实测图用（见{' '}
                <code>docs/图/README.md</code> §0）。
              </>
            }
          />
        </div>
      </div>
    </Section>
  );
}
