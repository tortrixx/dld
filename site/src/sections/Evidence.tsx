/**
 * Evidence.tsx —— 实验结果与工程证据
 *
 * 这一节的原则：**每个数字都带单位和出处**，而且要区分"当前读数"与"历史演进对照"。
 * 资源与时序的唯一真值源是入库的 `quartus/build_provenance.json` 与 `docs/05`；
 * 本站**不引用** `quartus/output_files/*.rpt` —— 那些文件被 .gitignore 挡掉了，
 * 克隆下来根本不存在，链过去就是死链。
 */

import { Figure, Bar, RichText, Section, Src, TableWrap, Tag } from '../components/ui';
import {
  BUILD_PROVENANCE,
  EXTRA_CHECKS,
  HEADLINE_METRICS,
  SIM_COVERAGE,
  SIM_TOTAL_ASSERTIONS,
  blob,
  figure,
} from '../data/facts';

export function Evidence(): JSX.Element {
  return (
    <Section
      id="evidence"
      num="04"
      kicker="Verified Data · 唯一真值源指向入库文件"
      title="实验结果与工程证据"
      lede={
        <>
          <p>
            下面每一个数字都能指到仓库里一个<strong>已入库</strong>的文件。
            资源与时序的真值源只有两处：机读的 <Src path="quartus/build_provenance.json" />{' '}
            与报告的 <Src path="docs/05-资源利用与编译报告.md" />。
            断言的分布由 <Src path="docs/03-仿真验证方案.md" /> 拥有。
          </p>
          <p className="note" style={{ marginTop: 'var(--s3)' }}>
            口径提示：Quartus 在 Fitter 报告里把 1264/1270 打成 <code>( 100 % )</code>，
            而项目文档按两位小数记 <strong>99%、余 6</strong> —— 同一个数的两种取整口径，
            两处都如实保留，本站不替它们统一。
          </p>
        </>
      }
    >
      {/* ---------------- 关键读数 ---------------- */}
      <div className="figures">
        {HEADLINE_METRICS.map((m) => (
          <div className="figure-cell" key={m.label}>
            <span className="figure-cell__k">{m.label}</span>
            <span className="figure-cell__v">
              {m.value}
              {m.unit ? <span>{m.unit}</span> : null}
            </span>
            <span className="figure-cell__n"><RichText text={m.note} /></span>
            <span className="figure-cell__src">
              来源：
              <a
                href={blob(m.source.path, m.source.line)}
                target="_blank"
                rel="noreferrer noopener"
                title={`仓库路径：${m.source.path}${m.source.line ? `:${m.source.line}` : ''}`}
              >
                {m.source.path.split('/').pop()}
                {m.source.line ? `:${m.source.line}` : ''}
              </a>
              <br />
              <RichText text={m.source.note} />
            </span>
          </div>
        ))}
      </div>

      {/* ---------------- 利用率 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-6">
          <h3 className="case__title" style={{ marginBottom: 'var(--s3)' }}>
            资源利用率：真正的瓶颈是 <Tag accent>LAB 127 / 127</Tag>
          </h3>
          <Bar label="LE" used={1264} total={1270} unit="LE" />
          <Bar label="LAB" used={127} total={127} unit="LAB" critical />
          <Bar label="引脚" used={52} total={116} unit="PIN" />
          <Bar label="UFM" used={0} total={1} unit="块" />
          <p className="note" style={{ marginTop: 'var(--s4)' }}>
            <strong>为什么"余 6 个 LE"约等于 0：</strong>
            MAX II 的 LE 只能按<strong>每个 LAB 10 个 LE 成组分配</strong>，
            所以剩下 3~6 个 LE 凑不出一个 LAB。这不是估算，是实测撞出来的：
            有一次真编译 <strong>1267 / 1270 LE（99.8%）却装不下</strong>，
            报错是"需要 128~129 个 LAB、器件只有 127"。所以判断"装不装得下"要看 LAB，不能只看 LE。
            出处：<Src path="docs/06-硬件调试记录.md" /> 的 ERR-046（§16.3）。
          </p>
        </div>
        <div className="col-6">
          <div className="frame">
            <TableWrap label="构建溯源">
            <table className="tbl">
              <caption>构建溯源（机读，入库）</caption>
              <tbody>
                <tr>
                  <th scope="row">编译时间</th>
                  <td>{BUILD_PROVENANCE.timestamp}</td>
                </tr>
                <tr>
                  <th scope="row">Quartus</th>
                  <td>{BUILD_PROVENANCE.quartus}</td>
                </tr>
                <tr>
                  <th scope="row">git HEAD</th>
                  <td>
                    {BUILD_PROVENANCE.gitHead}（编译时工作树有未提交改动，provenance 里如实记着）
                  </td>
                </tr>
                <tr>
                  <th scope="row">综合 LE（map）</th>
                  <td>{BUILD_PROVENANCE.syntheticLe} logic cells（fitter 装箱后 1264）</td>
                </tr>
                <tr>
                  <th scope="row">寄存器</th>
                  <td>{BUILD_PROVENANCE.registers}</td>
                </tr>
                <tr>
                  <th scope="row">时钟约束</th>
                  <td>{BUILD_PROVENANCE.clockConstraint}</td>
                </tr>
                <tr>
                  <th scope="row">I/O 延时</th>
                  <td>{BUILD_PROVENANCE.ioDelay}</td>
                </tr>
                <tr>
                  <th scope="row">固件</th>
                  <td>
                    puzzle.pof · {BUILD_PROVENANCE.pofBytes.toLocaleString('en-US')} B ·{' '}
                    {BUILD_PROVENANCE.pofMtime}
                    <br />
                    <span className="note" style={{ wordBreak: 'break-all' }}>
                      sha256 {BUILD_PROVENANCE.pofSha256}
                    </span>
                    <br />
                    已烧入板子并读回校验通过（Erase / Program / Verify 全过）
                  </td>
                </tr>
                <tr>
                  <th scope="row">RTL 指纹</th>
                  <td>
                    16 个源文件各带两种指纹（字节哈希 + <strong>逻辑指纹</strong>）：
                    后者对注释与行尾不敏感，所以"只改注释"不会被误判成功能变更。
                  </td>
                </tr>
              </tbody>
            </table>
            </TableWrap>
            <p className="figcap">
              本表全部来自 <Src path="quartus/build_provenance.json" />（由{' '}
              <Src path="scripts/record_build.py" /> 在编译后写入，属于入库交付物）。
              <code>.rpt</code> 一类编译产物被 <code>.gitignore</code> 挡掉、克隆后不存在，
              所以本站一律不链接它们。
            </p>
          </div>
        </div>
      </div>

      {/* ---------------- 仿真覆盖 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-12">
          <h3 className="case__title">
            仿真覆盖：12 个模块 / 场景、<Tag accent>{SIM_TOTAL_ASSERTIONS} 条断言全过</Tag>
          </h3>
          <p className="note" style={{ marginTop: 'var(--s2)' }}>
            测试台是 Python 写的（<code>sim/tb_*.py</code>），驱动 Quartus II 的内置仿真器：
            在 <code>.tmp/</code> 里建隔离工程，把功能网表跑一遍，再解析回写进 <code>.vwf</code> 的波形、
            与独立的参考模型逐点比对。每一轮的机读结论在{' '}
            <Src path="sim/rounds/" /> 下的 <code>rNN.json</code>。
            <strong>179 = 下表 12 行逐项相加</strong>（整机两种场景合计 56 条，但按"整机算一个模块"只计 28）。
          </p>
        </div>
        <div className="col-12">
          <TableWrap label="仿真覆盖">
          <table className="tbl" style={{ marginTop: 'var(--s4)' }}>
            <caption>
              当前全绿的轮次（第 25 工作阶段全量重跑）· 逐行都能在{' '}
              sim/rounds/&lt;模块&gt;/rNN.json 里核到
            </caption>
            <thead>
              <tr>
                <th>模块 / 场景</th>
                <th className="num">轮次</th>
                <th className="num">断言</th>
                <th>这一轮在验什么</th>
              </tr>
            </thead>
            <tbody>
              {SIM_COVERAGE.map((row) => (
                <tr key={row.module}>
                  <td>
                    <Src path={`sim/rounds/${row.module}/${row.round.split(' / ')[0]}.md`}>{row.module}</Src>
                  </td>
                  <td className="num">{row.round}</td>
                  <td className="num">{row.assertions}</td>
                  <td style={{ whiteSpace: 'normal' }}><RichText text={row.note} /></td>
                </tr>
              ))}
              <tr>
                <td colSpan={2}>
                  <strong>合计</strong>
                </td>
                <td className="num">
                  <strong>{SIM_TOTAL_ASSERTIONS}</strong>
                </td>
                <td>
                  <strong>全部通过</strong>
                </td>
              </tr>
            </tbody>
          </table>
          </TableWrap>
        </div>
      </div>

      {/* ---------------- 三项离线检查 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s7)' }}>
        <div className="col-12">
          <h3 className="case__title">除了仿真，还有三项离线检查</h3>
        </div>
        {EXTRA_CHECKS.map((c) => (
          <div className="col-4" key={c.name}>
            <div className="frame" style={{ height: '100%' }}>
              <p className="figcap" style={{ marginTop: 0 }}>
                <b>
                  <Src path={c.path}>{c.name}</Src>
                </b>
              </p>
              <p className="note" style={{ marginTop: 'var(--s2)' }}>
                <b>运行结论：</b>
                <RichText text={c.result} />
              </p>
              <p style={{ marginTop: 'var(--s3)', fontSize: '0.87rem', color: 'var(--ink-2)' }}><RichText text={c.what} /></p>
            </div>
          </div>
        ))}
      </div>

      {/* ---------------- 图素材 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-12">
          <h3 className="case__title">图素材：分清"Quartus 实测截图"与"脚本渲染的辅助波形"</h3>
          <p className="note" style={{ marginTop: 'var(--s2)' }}>
            这条区分来自 <Src path="docs/图/README.md" /> §0：
            <strong>只有 Quartus 图形界面里的截图才算"实测仿真图"</strong>
            （图里带着菜单栏、工程名、节点表与时间刻度，是软件本身渲染的，别人能核）；
            脚本画出来的矢量波形<strong>不能当实测截图用</strong>，只能当逐点对照的辅助证据。
            本站的图说严格照此标注。目前入库的实测截图只有 1 张，另外 11 张在清单里标着"待拍"——
            这一点在下面的局限一节也如实列着。
          </p>
        </div>
        <div className="col-12">
          <div className="figgrid" style={{ marginTop: 'var(--s4)' }}>
            <Figure
              src={figure('gui-clk_gen.png')}
              caption="Quartus GUI 实测仿真截图 · clk_gen 分频链"
              source={
                <>
                  来源：<code>docs/图/GUI-clk_gen.png</code>（在 Quartus II 波形编辑器里打开{' '}
                  <code>sim/clk_gen.vwf</code> 后截屏，标题栏已裁掉 —— 那条里含本机用户名）。
                  图里能看到 Project Navigator 的工程名、节点名列表与时间刻度。
                </>
              }
            />
            <Figure
              src={figure('sim-disp_format.svg')}
              caption="脚本渲染的辅助波形（不是 Quartus 界面截图）"
              source={
                <>
                  来源：<code>docs/图/SIM-disp_format.svg</code>，由 <code>scripts/sim.py</code>{' '}
                  解析 <code>sim/disp_format.vwf</code> 后自己画的。
                  <strong>不能当"实测仿真图"交</strong>，只能用于逐点比对 —— 本站按这个口径标注。
                </>
              }
            />
            <Figure
              src={figure('sim-clk_gen.svg')}
              caption="脚本渲染的辅助波形（不是 Quartus 界面截图）"
              source={
                <>
                  来源：<code>docs/图/SIM-clk_gen.svg</code>。
                  与上面那张 GUI 截图看的是同一份仿真，但渲染者不同 —— 这正好演示了为什么两者不能互换。
                </>
              }
            />
            <Figure
              src={figure('sim-dot_matrix_scan.svg')}
              caption="脚本渲染的辅助波形 · 点阵行扫描"
              source={
                <>
                  来源：<code>docs/图/SIM-dot_matrix_scan.svg</code>。
                  8 行 × 1 ms = 8 ms ⇒ 帧扫描 125 Hz、占空比 1/8。
                </>
              }
            />
          </div>
        </div>
      </div>
    </Section>
  );
}
