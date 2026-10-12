/**
 * DataFlow.tsx —— 「时序播放器」：把数据流随时间的传播演出来
 *
 * 设计取舍（为什么不做一张大 SVG 布线图）：
 *   一开始我想画一张"所有模块 + 所有连线"的总图，然后把脉冲跑在连线上。
 *   但那张图必然有 20 条交叉连线，**而且会误导** —— 一张"每层一根竖箭头"的图天生只能
 *   表达相邻层关系，硬画就会把 "clk_gen 把 t_4hz 送给 buzzer_ctrl" 画成"送给 game_fsm"。
 *   所以改成：**每个场景一条线性流水线**。线性图没有交叉、窄屏自动换行、
 *   而且每一步只高亮"这一拍真正在动的节点与通道"，读的人不用在图里找路。
 *   想看完整互联关系时，去「系统架构」那一节的带图，或直接开 `docs/图/dld-架构.drawio`
 *   （那份 draw.io 把跨层连线也画全了，因为它可以缩放、拖拽、折叠）。
 *
 * 动画靠 CSS + 定时器，不引任何图形库；`prefers-reduced-motion` 下自动退化为静态高亮。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { DotMatrix } from './DotMatrix';
import { RichText, Src } from './ui';
import { SegDisplay, readOut } from './SegDisplay';
import { DEFAULT_SCENARIO, FLOW_SCENARIOS, type FlowScenario } from '../data/timeline';
import { createInitialState, frame, reducer, segments, type GameState } from '../engine/engine';
import { LEVELS } from '../engine/geometry';

/** 仪表要显示的东西：一份真实状态 + 可选的"已发布到第几行"覆盖。 */
interface Instrument {
  readonly state: GameState;
  /** `row` 模式下，覆盖成"只发布到第 N 行"的帧（模拟逐行扫描）。 */
  readonly rowOverride: number | null;
  readonly cells: ReturnType<typeof frame>['cells'];
}

/**
 * 用规则模型算一帧"真实画面"，供 instrument 面板显示。
 * 刻意**不改动**引擎：行推进只是把已发布行之后的行抹掉，
 * 用来演示"每 1 ms 发布一行"这件事，不冒充另一种游戏状态。
 */
function useInstrument(scenario: FlowScenario, stepIndex: number): Instrument | null {
  return useMemo(() => {
    if (scenario.instrument === 'none') return null;
    let s: GameState = { ...createInitialState(), phase: 'idle' };
    s = reducer(s, { type: 'press', key: 'start' });
    for (let i = 0; i < LEVELS[0].previewSeconds * 4; i += 1) s = reducer(s, { type: 'tick' });
    const full = frame(s).cells;
    if (scenario.instrument === 'row') {
      const row = Math.min(7, stepIndex % 8);
      const cells = full.map((r, ri) => r.map((c) => (ri <= row ? c : 'off')));
      return { state: s, rowOverride: row, cells };
    }
    return { state: s, rowOverride: null, cells: full };
  }, [scenario, stepIndex]);
}

export function DataFlow(): JSX.Element {
  const [scenarioId, setScenarioId] = useState(DEFAULT_SCENARIO);
  const scenario = useMemo(
    () => FLOW_SCENARIOS.find((s) => s.id === scenarioId) ?? FLOW_SCENARIOS[0],
    [scenarioId],
  );
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);

  const steps = scenario.steps;
  const current = steps[Math.min(step, steps.length - 1)];

  /** 切换场景时回到第一步并停下（否则会带着上一条时间线的进度跑）。 */
  useEffect(() => {
    setStep(0);
    setPlaying(false);
  }, [scenarioId]);

  const stop = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  /** 播放：每一步按它自己的 holdMs 停留，最后一步停住。 */
  useEffect(() => {
    stop();
    if (!playing) return undefined;
    if (step >= steps.length - 1) {
      setPlaying(false);
      return undefined;
    }
    timer.current = window.setTimeout(() => setStep((s) => Math.min(s + 1, steps.length - 1)), current.holdMs);
    return stop;
  }, [playing, step, steps.length, current.holdMs, stop]);

  const instrument = useInstrument(scenario, step);
  const seg = instrument ? segments(instrument.state) : null;

  return (
    <div className="flow">
      {/* ---------------- 场景切换 ---------------- */}
      <div className="flow__scenarios" role="group" aria-label="时序场景">
        {FLOW_SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            className="flow__scenario"
            aria-pressed={s.id === scenario.id}
            onClick={() => setScenarioId(s.id)}
          >
            <span className="flow__scenario-t">{s.title}</span>
            <span className="flow__scenario-d">{s.subtitle}</span>
          </button>
        ))}
      </div>

      <p className="flow__blurb">
        <RichText text={scenario.blurb} />
      </p>

      {/* ---------------- 流水线（通栏：8 节需要整幅宽度，塞进半栏会折成三行） ---------------- */}
      <div className="flow__stage">
        <div className="pipe" role="list" aria-label={`${scenario.title} 的流水线`}>
          {scenario.nodes.map((n, i) => {
            const isActive = current.active.includes(i);
            return (
              <div className="pipe__item" role="listitem" key={n.name}>
                {i > 0 ? (
                  <span
                    className={`pipe__arrow${(current.busyLinks ?? []).includes(i - 1) ? ' pipe__arrow--busy' : ''}`}
                    aria-hidden="true"
                  >
                    <span className="pipe__arrow-label">{scenario.links[i - 1]?.label}</span>
                    <span className="pipe__arrow-line">
                      {(current.busyLinks ?? []).includes(i - 1) ? <span className="pipe__pulse" /> : null}
                    </span>
                  </span>
                ) : null}
                <span
                  className={`pipe__node pipe__node--${n.kind ?? 'core'}${isActive ? ' pipe__node--active' : ''}`}
                >
                  <span className="pipe__name">{n.name}</span>
                  <span className="pipe__sub">{n.sub}</span>
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---------------- 播放控制 ---------------- */}
      <div className="flow__controls">
        <button
          type="button"
          className={`flow__play${playing ? '' : ' flow__play--primary'}`}
          onClick={() => {
            if (step >= steps.length - 1) setStep(0);
            setPlaying((p) => !p);
          }}
        >
          {playing ? '⏸ 暂停' : step >= steps.length - 1 ? '↺ 重播' : '▶ 播放'}
        </button>
        <button
          type="button"
          className="flow__play"
          onClick={() => {
            setPlaying(false);
            setStep((s) => Math.max(0, s - 1));
          }}
          disabled={step === 0}
          aria-label="上一步"
        >
          ‹ 上一步
        </button>
        <button
          type="button"
          className="flow__play"
          onClick={() => {
            setPlaying(false);
            setStep((s) => Math.min(steps.length - 1, s + 1));
          }}
          disabled={step >= steps.length - 1}
          aria-label="下一步"
        >
          下一步 ›
        </button>
        <div className="flow__scrub">
          <input
            type="range"
            min={0}
            max={steps.length - 1}
            value={step}
            onChange={(e) => {
              setPlaying(false);
              setStep(Number(e.target.value));
            }}
            aria-label={`时间轴：第 ${step + 1} / ${steps.length} 步`}
          />
        </div>
        <span className="flow__time">
          {String(step + 1).padStart(2, '0')} / {String(steps.length).padStart(2, '0')}
          {current.clock ? ` · ${current.clock}` : ''}
        </span>
      </div>

      {/* ---------------- 叙述 + 仪表 ---------------- */}
      <div className="flow__side">
        <div className="flow__step" aria-live="polite">
          <p className="flow__step-t">
            <RichText text={current.title} />
          </p>
          <p className="flow__step-d">
            <RichText text={current.detail} />
          </p>
          <div className="flow__chips">
            {current.active.map((i) => (
              <span className="flow__chip flow__chip--acc" key={`a${i}`}>
                {scenario.nodes[i].name}
              </span>
            ))}
            {(current.busyLinks ?? []).map((i) => (
              <span className="flow__chip" key={`l${i}`}>
                → {scenario.links[i].label}
              </span>
            ))}
            {current.cite ? (
              <span className="flow__chip">
                出处：<Src path={current.cite.split(' · ')[0].split(':')[0]}>{current.cite}</Src>
              </span>
            ) : null}
          </div>
        </div>

        {/* ---------------- 仪表：用规则模型实算 ---------------- */}
        {instrument && seg ? (
          <div className="panel">
            <div className="panel__label">
              <span>
                <b>仪表</b> · 规则模型实算
              </span>
              <span>
                {instrument.rowOverride === null ? '当前画面' : `已发布到第 ${instrument.rowOverride + 1} 行`}
              </span>
            </div>
            <DotMatrix cells={instrument.cells} hintActive={false} disabled label="规则模型算出的点阵画面" />
            <div style={{ marginTop: 'var(--s5)' }}>
              <SegDisplay digits={seg.digits} blank={seg.blank} label="8 位数码管" />
            </div>
            <p className="figcap" style={{ marginTop: 'var(--s4)' }}>
              这两块显示的是<strong>规则模型按同一条时序跑出来的真实画面</strong>（不是示意图）：
              点阵内容来自 <code>frame()</code>，数码管来自 <code>segments()</code>。 数码管读数：
              <code>{readOut(seg.digits, seg.blank)}</code>
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
