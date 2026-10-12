/**
 * Simulator.tsx —— 交互式 8×8 点阵拼图模拟器（本站最重要的组件）
 *
 * 这一节要同时做到三件事：
 *   1. **真的能玩**：规则来自 RTL（越界/重叠拒绝、旋转只改朝向、全部锁定才判、
 *      三关图案与限时、告急幽灵），不是"会变色的假演示"。
 *   2. **诚实**：醒目声明浏览器模拟不驱动 FPGA、不声称与硬件时序等价，
 *      并逐条列出"哪些一致、哪些是重写"。
 *   3. **可操作**：鼠标、触屏（点选 + 拖动）、键盘（面板聚焦后）三种方式，
 *      触控目标 ≥44px，焦点态可见。
 */

import { useCallback, useMemo } from 'react';

import { DotMatrix } from '../components/DotMatrix';
import { Keypad } from '../components/Keypad';
import { SegDisplay, readOut } from '../components/SegDisplay';
import { Caveat, RichText, Section, Src, TableWrap, Tag } from '../components/ui';
import { useGame } from '../state/useGame';
import {
  NOTHING_SELECTED,
  isFrameOk,
  patternFor,
  phaseLabel,
  pieceAt,
  pieceCells,
} from '../engine/engine';
import { HINT_THRESHOLD_SECONDS, KEY_MAP, LEVELS, TICK_MS } from '../engine/geometry';
import { blob } from '../data/facts';

const PHASE_TEXT: Record<string, string> = {
  selftest: '开机自检（B1/B2）',
  idle: '待机（B2）',
  preview: '预览目标图案（B4/B10）',
  playing: '对局中（B5/B7/B8）',
  win: '通关胜利（B10）',
  fail: '失败（B9/B10）',
};

export function Simulator(): JSX.Element {
  const game = useGame();
  const { state, display, seg } = game;

  /** 选中零片的格子集合 —— 用于给"选中"加一层描边，不只靠颜色。 */
  const selectedCells = useMemo(() => {
    const set = new Set<string>();
    if (state.phase !== 'playing' || state.selected === NOTHING_SELECTED) return set;
    const p = state.pieces[state.selected];
    if (!p || p.locked) return set;
    for (const { r, c } of pieceCells(p)) set.add(`${r},${c}`);
    return set;
  }, [state]);

  const pattern = patternFor(state.level, state.patSel);

  const onTapCell = useCallback(
    (r: number, c: number) => {
      const idx = pieceAt(state, r, c);
      if (idx < 0) {
        game.press('select');
        return;
      }
      game.selectPiece(idx);
    },
    [game, state],
  );

  const onSwipe = useCallback((dir: 'up' | 'down' | 'left' | 'right') => game.press(dir), [game]);

  const timerTotal = state.phase === 'preview' ? LEVELS[state.level - 1].previewSeconds : LEVELS[state.level - 1].playSeconds;
  const timerLeft = state.phase === 'preview' ? state.previewLeft : state.timeLeft;
  const timerPct = Math.max(0, Math.min(100, (timerLeft / timerTotal) * 100));

  return (
    <Section
      id="sim"
      num="02"
      kicker="Interactive Demo · 不是静态截图"
      title="可操作的 8×8 点阵模拟器"
      lede={
        <>
          <p>
            规则是从 <Src path="rtl/puzzle_ctrl.vhd" /> 与 <Src path="rtl/game_fsm.vhd" />{' '}
            里核实出来的：越界与重叠一律拒绝、旋转只改朝向而<strong>锚点不动</strong>、
            三关的图案与限时、倒计时 ≤ {HINT_THRESHOLD_SECONDS} s 才出现的告急幽灵。
            先看自检 → 待机，再按【开始】走一次完整的三关流程。
          </p>
        </>
      }
    >
      <div style={{ marginBottom: 'var(--s5)' }}>
        <Caveat title="浏览器交互模拟 ≠ FPGA 实机">
          本模拟器用于演示<strong>游戏规则与操作流程</strong>，
          <strong>不驱动任何 FPGA 硬件</strong>，也不声称与 RTL 逐拍等价。
          板子上的时序、扫描刷新率与音效在这里都没有复现（见本节末尾的"一致与不一致"清单）。
          它<strong>不能</strong>远程操作开发板，也没有任何遥测或后端。
        </Caveat>
      </div>

      <div className="sim">
        {/* ---------------- 左：仪器面板 ---------------- */}
        <div
          className="panel"
          tabIndex={0}
          role="application"
          aria-label="拼图模拟器控制面板：点阵、数码管与键盘操作区。点一下本面板后可用键盘快捷键。"
          onKeyDown={game.onKeyDown}
          onPointerDown={(e) => e.currentTarget.focus({ preventScroll: true })}
        >
          <div className="panel__label">
            <span>
              <b>8×8 双色点阵</b> · 浏览器模拟
            </span>
            <span>{game.sw7 ? '点一下面板后可用键盘快捷键' : 'SW7 = 0：显示器件全部不显示'}</span>
          </div>

          {game.sw7 ? (
            <DotMatrix
              cells={display.cells}
              hintActive={display.hintActive}
              selectedCells={selectedCells}
              onTapCell={onTapCell}
              onSwipe={onSwipe}
              disabled={state.phase !== 'playing'}
              label={`8×8 点阵，当前 ${phaseLabel(state.phase)}`}
            />
          ) : (
            <div className="matrix matrix--empty" aria-label="SW7 关闭：所有显示器件不显示">
              {Array.from({ length: 8 }, (_, r) => (
                <div key={r} style={{ display: 'contents' }}>
                  {Array.from({ length: 8 }, (_, c) => (
                    <div key={`${r}-${c}`} className="matrix__cell" />
                  ))}
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 'var(--s5)' }}>
            {game.sw7 ? (
              <SegDisplay
                digits={seg.digits}
                blank={seg.blank}
                blink={state.phase === 'selftest'}
                label="8 位数码管"
              />
            ) : (
              <SegDisplay digits={Array(8).fill(' ')} blank={Array(8).fill(true)} label="6 位熄灭" />
            )}
          </div>

          <div className="panel__label" style={{ marginTop: 'var(--s5)', marginBottom: 'var(--s3)' }}>
            <span>状态</span>
            <span>
              心跳 {TICK_MS} ms · 与 RTL 的 tick_4hz 同周期
            </span>
          </div>

          <div className="sim__status" aria-live="polite">
            <div className="sim__status-line">
              <span className="sim__status-k">主状态机</span>
              <span className="sim__status-v">{phaseLabel(state.phase)}</span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">阶段</span>
              <span className="sim__status-v">{PHASE_TEXT[state.phase]}</span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">关卡 / 图案</span>
              <span className="sim__status-v">
                第 {state.level} 关 · {pattern.label}
              </span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">倒计时</span>
              <span className={`sim__status-v${timerLeft <= HINT_THRESHOLD_SECONDS && state.phase === 'playing' ? ' sim__status-v--hot' : ''}`}>
                {timerLeft} s / {timerTotal} s
              </span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">选中的零片</span>
              <span className="sim__status-v">
                {state.phase !== 'playing'
                  ? '—'
                  : state.selected === NOTHING_SELECTED
                    ? '还没选（按【选择】/点零片）'
                    : `第 ${state.selected + 1} 块 · ${state.pieces[state.selected].locked ? '已锁定（黄）' : '未锁定（绿）'}`}
              </span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">拼装进度</span>
              <span className="sim__status-v">
                {state.phase === 'playing'
                  ? `并集 == 目标？${isFrameOk(state) ? '是' : '否'} · 已锁定 ${state.pieces.filter((p) => p.locked).length} / ${state.pieces.length}`
                  : '—'}
              </span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">告急幽灵</span>
              <span className="sim__status-v">
                {state.phase === 'playing'
                  ? display.hintOn
                    ? `已显示（≤${HINT_THRESHOLD_SECONDS} s，绿 + 2 Hz 闪）`
                    : `未显示（> ${HINT_THRESHOLD_SECONDS} s）`
                  : '—'}
              </span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">数码管读数</span>
              <span className="sim__status-v">{game.sw7 ? readOut(seg.digits, seg.blank) : '全灭（SW7=0）'}</span>
            </div>
            <div className="sim__status-line">
              <span className="sim__status-k">最近按键</span>
              <span className="sim__status-v">
                {game.lastKey ? `${game.lastKey}（原始键号 ${game.lastCode}）` : '—'}
              </span>
            </div>
          </div>

          <div style={{ marginTop: 'var(--s4)' }}>
            <div className="bar" role="img" aria-label={`倒计时剩余 ${timerLeft} / ${timerTotal} 秒`}>
              <span>倒计时</span>
              <span className="bar__track">
                <span
                  className={`bar__fill${state.phase === 'playing' && timerLeft <= HINT_THRESHOLD_SECONDS ? ' bar__fill--full' : ''}`}
                  style={{ width: `${timerPct}%` }}
                />
              </span>
              <span className="bar__v">
                {timerLeft} / {timerTotal}
              </span>
            </div>
          </div>
        </div>

        {/* ---------------- 右：控制区 ---------------- */}
        <div className="sim__control">
          <div className="panel" style={{ padding: 'var(--s4)' }}>
            <div className="panel__label" style={{ marginBottom: 'var(--s3)' }}>
              <span>控制</span>
              <label className="toggle">
                <input type="checkbox" checked={game.sw7} onChange={(e) => game.setSw7(e.target.checked)} />
                SW7 系统开关
              </label>
            </div>

            <div className="dpad" style={{ marginBottom: 'var(--s3)' }}>
              <span />
              <button type="button" className="dpad__btn" onClick={() => game.press('up')} aria-label="上（KEY7，快捷键 ↑）">
                上 <small>↑ KEY7</small>
              </button>
              <span />
              <button type="button" className="dpad__btn" onClick={() => game.press('left')} aria-label="左（KEY10，快捷键 ←）">
                左 <small>← KEY10</small>
              </button>
              <button type="button" className="dpad__btn" onClick={() => game.press('confirm')} aria-label="确认（KEY11，快捷键 Enter）">
                确认 <small>Enter KEY11</small>
              </button>
              <button type="button" className="dpad__btn" onClick={() => game.press('right')} aria-label="右（KEY12，快捷键 →）">
                右 <small>→ KEY12</small>
              </button>
              <span />
              <button type="button" className="dpad__btn" onClick={() => game.press('down')} aria-label="下（KEY15，快捷键 ↓）">
                下 <small>↓ KEY15</small>
              </button>
              <span />
            </div>

            <div className="sim__actions">
              <button type="button" className="btn" onClick={() => game.press('start')} style={{ justifyContent: 'center' }}>
                开始 / 重开
              </button>
              <button type="button" className="btn btn--ghost" onClick={() => game.press('select')} style={{ justifyContent: 'center', borderColor: 'var(--panel-rule)', color: 'var(--panel-ink)' }}>
                选择
              </button>
              <button type="button" className="btn btn--ghost" onClick={() => game.press('rotate')} style={{ justifyContent: 'center', borderColor: 'var(--panel-rule)', color: 'var(--panel-ink)' }}>
                旋转 90°
              </button>
              <button type="button" className="btn btn--ghost" onClick={game.reset} style={{ justifyContent: 'center', borderColor: 'var(--panel-rule)', color: 'var(--panel-ink)' }}>
                复位
              </button>
            </div>

            <div className="sim__feedback" style={{ marginTop: 'var(--s4)' }} aria-live="polite">
              {game.sw7 ? state.lastEvent : 'SW7 = 0：所有显示器件不显示（B1）'}
            </div>
          </div>

          <div className="panel" style={{ padding: 'var(--s4)' }}>
            <div className="panel__label" style={{ marginBottom: 'var(--s3)' }}>
              <span>4×4 矩阵键盘 · 右下 3×3 功能区块</span>
            </div>
            <Keypad onPress={game.press} activeKey={game.lastKey} disabled={!game.sw7} />
            <p className="figcap" style={{ color: 'var(--panel-ink-2)', marginTop: 'var(--s3)' }}>
              键号 = 4×ROW + COL（ROW0 在最下、COL0 在最左）。布局来自板子手册附图 26 与上板实测
              （<a href={blob('rtl/game_fsm.vhd', 139)} target="_blank" rel="noreferrer noopener" style={{ color: 'var(--panel-ink)' }}>
                rtl/game_fsm.vhd:139
              </a>
              ）。灰色那个 <b>KEY13</b> 键号是 0，而扫描器用键号 0 表示"没有按键"，
              所以它<strong>不可用</strong> —— 这是硬件事实，不是疏忽。
            </p>
          </div>

          <div className="panel" style={{ padding: 'var(--s4)' }}>
            <div className="panel__label" style={{ marginBottom: 'var(--s3)' }}>
              <span>事件日志（最新在下）</span>
            </div>
            <ul className="log" aria-live="polite">
              {state.log.map((line, i) => (
                <li key={`${i}-${line}`}>{line}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* ---------------- 规则速查 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-6">
          <TableWrap label="关卡与计时">
          <table className="tbl">
            <caption>关卡与计时（题目明文 + 一处自拟）</caption>
            <thead>
              <tr>
                <th>关</th>
                <th className="num">零片</th>
                <th className="num">预览</th>
                <th className="num">限时</th>
                <th>图案</th>
              </tr>
            </thead>
            <tbody>
              {LEVELS.map((l) => (
                <tr key={l.level}>
                  <td>第 {l.level} 关</td>
                  <td className="num">{l.shapeIds.length}</td>
                  <td className="num">{l.previewSeconds} s</td>
                  <td className="num">{l.playSeconds} s</td>
                  <td style={{ whiteSpace: 'normal' }}>
                    {l.pattern === 'fixed-l1' && '图 4-1（固定）'}
                    {l.pattern === 'fixed-l2' && '阶梯形（固定）'}
                    {l.pattern === 'random' && '四幅库随机（田 / 十 / S·Z / 阶梯）'}
                    <br />
                    <span className="note">{l.basis}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </TableWrap>
        </div>
        <div className="col-6">
          <TableWrap label="键位映射">
          <table className="tbl">
            <caption>键位映射（= game_fsm.key_of 的逐条对应）</caption>
            <thead>
              <tr>
                <th>丝印</th>
                <th className="num">键号</th>
                <th>功能</th>
                <th>本站快捷键</th>
              </tr>
            </thead>
            <tbody>
              {KEY_MAP.map((k) => (
                <tr key={k.silk} style={k.code === 0 ? { opacity: 0.55 } : undefined}>
                  <td>{k.silk}</td>
                  <td className="num">{k.code}</td>
                  <td style={{ whiteSpace: 'normal' }}>{k.fn}</td>
                  <td>{k.shortcut}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </TableWrap>
          <p className="note" style={{ marginTop: 'var(--s3)' }}>
            快捷键是<strong>网站的便利功能</strong>，硬件上没有 —— 挂在面板自己的 keydown 上
            （不挂 <code>window</code>），所以不会和 Tab 焦点导航或页面滚动抢按键。点一下面板即可用键盘。
          </p>
        </div>
      </div>

      {/* ---------------- 一致与不一致 ---------------- */}
      <div className="grid12" style={{ marginTop: 'var(--s8)' }}>
        <div className="col-12">
          <h3 className="case__title" style={{ marginBottom: 'var(--s4)' }}>
            这个模拟器"像"到什么程度 —— 逐条交代
          </h3>
        </div>
        <div className="col-6">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s3)' }}>
              <b>与硬件一致（每条都能在 RTL 里指出出处）</b>
            </p>
            <ul className="limits" style={{ borderTop: 0 }}>
              {[
                '零片形状、目标图案、胜负画面：逐位来自 puzzle_pkg.vhd 的 64 位常量，不是照着截图画的',
                '旋转语义：顺时针 90°、锚点不动、四次回原位；越界或重叠一律拒绝',
                '移动语义：先夹紧到 0..7，再查"包围盒装得下 + 不压到别的零片"',
                '判决：并集 == 目标图案 **且** 全部零片已锁定，才判过关（o_solved <= frm_ok and alllock_r）',
                '颜色：未锁定=红、选中=绿、已锁定=黄（红+绿）、告急幽灵=绿 + 2 Hz 闪 —— 与 puzzle_ctrl/puzzle_top 的赋值逐行对应',
                '数码管：DISP7 预览倒计时 / DISP4:DISP3 对局倒计时 / DISP0 关卡号 / DISP2 全程熄灭（口径 C）',
                '时序：4 Hz 心跳（250 ms）派生出 2 Hz 闪烁与 1 Hz 秒计数；自检 8 拍；预览 5 s；30/40/60 s',
                '初始朝向 1/1/2/2（PIECE_ORI_INIT）—— 所以不旋转就拼不出来',
              ].map((t, i) => (
                <li className="limits__item" key={t} style={{ paddingBlock: 'var(--s3)' }}>
                  <span className="limits__i">{String(i + 1).padStart(2, '0')}</span>
                  <span style={{ fontSize: '0.85rem', lineHeight: 1.65, color: 'var(--ink-2)' }}>
                    <RichText text={t} />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="col-6">
          <div className="frame">
            <p className="figcap" style={{ marginTop: 0, marginBottom: 'var(--s3)' }}>
              <b>与硬件不一致（如实列出）</b>
            </p>
            <ul className="limits" style={{ borderTop: 0 }}>
              {[
                '散落是重写的：同一个 LFSR 多项式与种子（0x5A、周期 255），但取数的先后顺序与重试次数不是逐拍复刻 ⇒ 同一局不会与板子逐格一致',
                '时间轴按复位路径的相位建模；板子上 tick_4hz 是自由走的，SW7 重新进入时自检窗口落在 1.75~2.0 s（本站按 2.0 s）',
                '完全不做音效：蜂鸣器的音高、乐句与量化时序一概不模拟',
                '不做扫描：板子上点阵是 125 Hz 行扫描、引擎内容更新率 25/21 Hz；网页是整帧直画，没有占空比与涂抹现象',
                '点选零片、拖动移动、键盘快捷键都是**网站便利交互**，硬件上只有循环的【选择】键与八个按键',
                '被拒绝的移动/旋转在硬件上**没有声音**（+5 LE 装不下，已回退）；本站只在状态行给文字反馈',
                '自检的 POST 短鸣相位残余、被拒按键无音效等 RTL 已知残余，这里没有对应物',
              ].map((t, i) => (
                <li className="limits__item" key={t} style={{ paddingBlock: 'var(--s3)' }}>
                  <span className="limits__i">{String(i + 1).padStart(2, '0')}</span>
                  <span style={{ fontSize: '0.85rem', lineHeight: 1.65, color: 'var(--ink-2)' }}>
                    <RichText text={t} />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div className="col-12" style={{ marginTop: 'var(--s4)' }}>
          <p className="note">
            这套规则模型的几何部分<strong>在单元测试里复算了仓库自己的穷举证明</strong>（<Src path="scripts/check_geometry.py" />）：
            ①「只许平移」时 PAT0/PAT1/PAT2 各 1 种铺法、PAT3 有 2 种；
            ② 保持初始朝向、只许平移时第一关与四幅图案<strong>都无解</strong>（旋转必需）；
            ③ 允许旋转后<strong>都仍可解</strong>（不是死局）。
            跑 <code>cd site &amp;&amp; npm test</code> 可以看到这些断言逐条通过。{' '}
            <Tag accent>45 条单元测试</Tag>
          </p>
        </div>
      </div>
    </Section>
  );
}
