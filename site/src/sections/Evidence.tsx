/**
 * Evidence.tsx —— 数据与证据（这一版以**图表**为主，不再堆表格）
 *
 * 用户的原话是"表格数据太多"。所以这一节把四件事都画出来：
 *   ① 利用率细线条（LE / LAB / 引脚 / UFM）—— 一眼看出瓶颈是 LAB
 *   ② 时序预算尺：一根 20 ns 的尺子上摆"数据路径 18.428 ns + 余量 1.572 ns"
 *   ③ 逐模块断言数（12 根条，合计由 facts.ts 的 SIM_COVERAGE 求和得到）—— 验证覆盖一眼可见
 *   ④ 资源与时序的**演进**折线（历史读数，标清楚不是当前值）
 * 剩下的文字只保留"每个数字的出处"和"口径差异"这两件必须写清的事。
 */

import { BarChart, EvolutionChart, TimingBudget, UtilizationBars } from '../components/charts';
import { Figure, RichText, Section, Src, Tag } from '../components/ui';
import {
  BUILD_PROVENANCE,
  EXTRA_CHECKS,
  RESOURCE_EVOLUTION,
  SIM_COVERAGE,
  SIM_TOTAL_ASSERTIONS,
  blob,
  figure,
} from '../data/facts';

/** 逐模块断言数：直接由 SIM_COVERAGE 派生，避免出现第二份真值源。 */
const ASSERTION_BARS = SIM_COVERAGE.map((r) => ({
  label: r.module,
  value: r.assertions,
  note: `第 ${r.round} 轮 · ${r.note}`,
}));

export function Evidence(): JSX.Element {
  return (
    <Section
      id="evidence"
      num="04"
      kicker="Verified Data · 每个数字都带出处"
      title="数据与证据"
      lede={
        <>
          <p>
            下面每个数字都能指到仓库里一个<strong>已入库</strong>的文件。
            资源与时序的真值源只有两处：机读的 <Src path="quartus/build_provenance.json" /> 与报告的{' '}
            <Src path="docs/05-资源利用与编译报告.md" />；断言的分布由{' '}
            <Src path="docs/03-仿真验证方案.md" /> 拥有。
          </p>
          <p className="note" style={{ marginTop: 'var(--s3)' }}>
            口径提示：Fitter 报告把 1264/1270 打成 <code>( 100 % )</code>，
            而项目文档按<strong>整数</strong>百分比记 <strong>99%（余 6）</strong> ——
            1264/1270 实际是 99.53%，两种取整口径都如实保留，本站不替它们统一。
          </p>
        </>
      }
    >
      {/* ---------------- 利用率 + 时序预算 ---------------- */}
      <div className="grid12">
        <div className="col-5">
          <div className="chart" style={{ height: '100%' }}>
            <div className="chart__head">
              <p className="chart__title">
                资源利用率：瓶颈是 <Tag accent>LAB 127 / 127</Tag>
              </p>
            </div>
            <UtilizationBars
              data={[
                { label: 'LE', used: 1264, total: 1270, unit: 'LE' },
                { label: 'LAB', used: 127, total: 127, unit: 'LAB', critical: true },
                { label: '引脚', used: 52, total: 116, unit: 'PIN' },
                { label: 'UFM', used: 0, total: 1, unit: '块' },
              ]}
            />
            <p className="chart__cap">
              <strong>为什么"余 6 个 LE"约等于 0：</strong>
              MAX II 的 LE 只能按<strong>每个 LAB 10 个 LE 成组分配</strong>，所以剩下 3~6 个 LE 凑不出一个
              LAB。这不是估算，是实测撞出来的：有一次真编译 <strong>1267 / 1270 LE（99.8%）却装不下</strong>，
              报错是"需要 128~129 个 LAB、器件只有 127"。判断"装不装得下"要看 LAB，不能只看 LE。
              出处：<Src path="docs/06-硬件调试记录.md">docs/06 · ERR-046</Src>。
            </p>
          </div>
        </div>
        <div className="col-7">
          <TimingBudget
            periodNs={20}
            dataPathNs={18.428}
            slackNs={1.572}
            title="时序预算：20 ns 周期 = 18.428 ns 数据路径 + 1.572 ns 余量"
            caption={
              <>
                时钟约束 <code>create_clock -name clk -period 20.000</code>（50 MHz）。
                余量 <strong>+1.572 ns</strong>（入库的 <code>sta.setup_slack</code>）、
                <strong>0 条时序违例</strong>；数据路径 <strong>18.428 ns = 20 − 1.572</strong>，
                是<strong>反推值</strong> —— 入库文件只记 slack，不记路径长度与节点名，
                所以这里不写路径名（宁可少说，也不写无法核对的数字）；
                hold 余量 +1.078 ns、最小脉宽 +9.734 ns。Fmax 54.27 MHz。
                <br />
                出处：<Src path="quartus/build_provenance.json" line={52}>build_provenance.json（sta 段）</Src>
                {' · '}
                <Src path="docs/05-资源利用与编译报告.md" />。
              </>
            }
          />
        </div>
      </div>

      {/* ---------------- 断言分布 + 演进（都整宽：图的 viewBox 需要 1:1 渲染才读得清） ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s6)' }}>
        <div className="col-12">
          <BarChart
            title={`仿真覆盖：12 个模块/场景，${SIM_TOTAL_ASSERTIONS} 条断言全过`}
            data={ASSERTION_BARS}
            unit=" 条"
            right={
              <Tag accent>
                {SIM_TOTAL_ASSERTIONS} / {SIM_TOTAL_ASSERTIONS}
              </Tag>
            }
            caption={
              <>
                测试台是 Python 写的（<code>sim/tb_*.py</code>），驱动 Quartus II 的<strong>内置</strong>仿真器：
                在 <code>.tmp/</code> 里建隔离工程，跑功能网表，再把波形回写进 <code>.vwf</code>，与独立参考模型逐点比对。
                每一轮的机读结论在 <Src path="sim/rounds/" /> 的 <code>rNN.json</code>。
                <strong>{SIM_TOTAL_ASSERTIONS} = 这 12 行逐项相加</strong>
                （整机两种场景各 28 条，按"整机算一个模块"只计一次）。
              </>
            }
          />
        </div>
      </div>
      <div className="grid12" style={{ marginTop: 'var(--s6)' }}>
        <div className="col-12">
          <EvolutionChart
            points={RESOURCE_EVOLUTION}
            title="资源与时序的演进（历史读数 → 当前）"
            caption={
              <>
                <strong>注意：这张图是演进对照，不是当前值</strong> —— 最后一点才是当前固件
                （图中已用竖虚线与实心圆单独标出）。7 个点每个都能在{' '}
                <Src path="docs/05-资源利用与编译报告.md" /> 里查到（行号见每点悬停说明）。
                想说明的是：面积是反复撞上限撞出来的 —— 中间 Fmax 掉到 36.68 MHz 又爬回 51.44，
                LE 从 958 一路加到 1268 再回落到 1264。
              </>
            }
          />
        </div>
      </div>

      {/* ---------------- 构建溯源（精简成键值行，不用表格） ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-6">
          <div className="frame" style={{ height: '100%' }}>
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s3)' }}>
              <b>构建溯源</b>（机读，入库）
            </p>
            <div className="rows">
              {(
                [
                  ['编译时间', BUILD_PROVENANCE.timestamp],
                  ['Quartus', BUILD_PROVENANCE.quartus],
                  ['git HEAD', `${BUILD_PROVENANCE.gitHead}（编译时工作树有未提交改动，provenance 里如实记着）`],
                  ['时钟约束', BUILD_PROVENANCE.clockConstraint],
                  ['I/O 延时', BUILD_PROVENANCE.ioDelay],
                  [
                    '固件',
                    `puzzle.pof · ${BUILD_PROVENANCE.pofBytes.toLocaleString('en-US')} B · ${BUILD_PROVENANCE.pofMtime} · 已烧录并读回校验通过`,
                  ],
                ] as const
              ).map(([k, v]) => (
                <div className="spec__row" key={k} style={{ borderBottom: 'none' }}>
                  <span className="spec__k">{k}</span>
                  <span className="spec__v" style={{ fontSize: '0.86rem' }}>
                    {v}
                  </span>
                </div>
              ))}
            </div>
            <p className="figcap" style={{ marginTop: 'var(--s3)', wordBreak: 'break-all' }}>
              POF sha256：<code>{BUILD_PROVENANCE.pofSha256}</code>
              <br />
              RTL 指纹：16 个源文件各带两种指纹（字节哈希 + <strong>逻辑指纹</strong>）——
              后者对注释与行尾不敏感，所以"只改注释"不会被误判成功能变更。
              <br />
              来源：<Src path="quartus/build_provenance.json" />（由 <Src path="scripts/record_build.py" />{' '}
              在编译后写入，属于入库交付物）。<code>.rpt</code> 一类编译产物被 <code>.gitignore</code>{' '}
              挡掉、克隆后不存在，所以本站一律不链接它们。
            </p>
          </div>
        </div>
        <div className="col-6">
          <div className="frame" style={{ height: '100%' }}>
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s3)' }}>
              <b>除了仿真，还有三项离线检查</b>
            </p>
            <div className="rows">
              {EXTRA_CHECKS.map((c) => (
                <div key={c.name} style={{ paddingBlock: 'var(--s3)' }}>
                  <p className="figcap" style={{ marginTop: 0 }}>
                    <b>
                      <Src path={c.path}>{c.name}</Src>
                    </b>
                  </p>
                  <p className="note" style={{ marginTop: 'var(--s2)' }}>
                    运行结论：{c.result}
                  </p>
                  <p style={{ marginTop: 'var(--s2)', fontSize: '0.85rem', color: 'hsl(var(--muted-foreground))' }}><RichText text={c.what} /></p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ---------------- 图素材 ---------------- */}
      <div style={{ marginTop: 'var(--s8)' }}>
        <h3 className="sec__title" style={{ fontSize: 'var(--fs-h3)' }}>
          图素材：分清"Quartus 实测截图"与"脚本渲染的辅助波形"
        </h3>
        <p className="note" style={{ marginTop: 'var(--s2)', marginBottom: 'var(--s5)' }}>
          这条区分来自 <Src path="docs/图/README.md" /> §0：
          <strong>只有 Quartus 图形界面里的截图才算"实测仿真图"</strong>
          （图里带着菜单栏、工程名、节点表与时间刻度，是软件本身渲染的，别人能核）；
          脚本画出来的矢量波形<strong>不能当实测截图用</strong>，只能当逐点对照的辅助证据。
          目前入库的实测截图只有 1 张（见上一节），另外 11 张在清单里标着"待拍"——
          这一点在「工程取舍」的局限里也如实列着。
        </p>
        <div className="figgrid">
          <Figure
            src={figure('sim-clk_gen.svg')}
            caption="脚本渲染的辅助波形 · clk_gen（与上一节那张 GUI 截图看的是同一份仿真）"
            source={
              <>
                <code>docs/图/SIM-clk_gen.svg</code>，由 <code>scripts/sim.py</code> 解析{' '}
                <code>sim/clk_gen.vwf</code> 后自己画的。<strong>它不是 Quartus 界面截图</strong> ——
                两张图讲的是同一次仿真，差别只在"谁画的"，这正好说明为什么两者不能互相替代。
              </>
            }
          />
          <Figure
            src={figure('sim-disp_format.svg')}
            caption="脚本渲染的辅助波形（不是 Quartus 界面截图）"
            source={
              <>
                <code>docs/图/SIM-disp_format.svg</code>，由 <code>scripts/sim.py</code> 解析{' '}
                <code>sim/disp_format.vwf</code> 后自己画的。只能用于逐点比对 —— 本站按这个口径标注。
              </>
            }
          />
          <Figure
            src={figure('sim-dot_matrix_scan.svg')}
            caption="脚本渲染的辅助波形 · 点阵行扫描"
            source={
              <>
                <code>docs/图/SIM-dot_matrix_scan.svg</code>。8 行 × 1 ms = 8 ms ⇒ 帧扫描 125 Hz、占空比 1/8
                （推导见「节拍链」场景）。
              </>
            }
          />
          <Figure
            src={figure('sim-keypad_scan.svg')}
            caption="脚本渲染的辅助波形 · 键盘四相扫描与消抖"
            source={
              <>
                <code>docs/图/SIM-keypad_scan.svg</code>。一轮扫描 = 2 个 t_200 = 10 ms；
                4 轮消抖 = 40 ms（见「一次按键」场景）。
              </>
            }
          />
          <Figure
            src={figure('sim-seg_scan.svg')}
            caption="脚本渲染的辅助波形 · 数码管位选"
            source={
              <>
                <code>docs/图/SIM-seg_scan.svg</code>。8 位轮一遍 = 8 ms ⇒ 每位 125 Hz。
              </>
            }
          />
        </div>
      </div>

      <p className="note" style={{ marginTop: 'var(--s6)' }}>
        完整报告入口：
        <a href={blob('docs/05-资源利用与编译报告.md')} target="_blank" rel="noreferrer noopener">
          docs/05 · 资源利用与编译报告
        </a>
        {' · '}
        <a href={blob('docs/03-仿真验证方案.md')} target="_blank" rel="noreferrer noopener">
          docs/03 · 仿真验证方案
        </a>
        {' · '}
        <a href={blob('quartus/build_provenance.json')} target="_blank" rel="noreferrer noopener">
          quartus/build_provenance.json
        </a>
      </p>
    </Section>
  );
}
