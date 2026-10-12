/**
 * useGame.ts —— 把规则模型接到 React 上
 *
 * 三件事，别多做：
 *   1. 用 **250 ms 的心跳**驱动 `reducer` —— 与 RTL 的 `tick_4hz` 同周期。
 *      所以自检窗口、2 Hz 闪烁、1 Hz 倒计时都由同一支心跳派生，
 *      和板子上"一条 4 Hz 节拍派生出闪烁与秒计数"的结构一致。
 *   2. 把 SW7（系统开关）建模成一个真实开关：关掉时**所有显示器件不显示**（B1），
 *      重新打开会走一次上电自检（与 RTL 里 `i_sw='0'` 把 FSM 按在自检起点一致）。
 *   3. 把键盘快捷键挂在**面板自己**的 keydown 上（面板可聚焦），
 *      而不是挂在 window 上 —— 否则会和页面滚动、Tab 导航抢按键。
 */

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';

import {
  ACTION_KEYS,
  createInitialState,
  frame,
  rawKeyCode,
  reducer,
  segments,
  type GameKey,
  type GameState,
} from '../engine/engine';
import { TICK_MS } from '../engine/geometry';

/** 键盘映射：刻意避开 Tab（浏览器焦点导航）与 Space（页面滚动）。 */
const KEY_BINDINGS: readonly { readonly keys: readonly string[]; readonly key: GameKey }[] = [
  { keys: ['n', 'N'], key: 'start' },
  { keys: ['q', 'Q'], key: 'select' },
  { keys: ['Enter'], key: 'confirm' },
  { keys: ['e', 'E'], key: 'rotate' },
  { keys: ['ArrowUp'], key: 'up' },
  { keys: ['ArrowDown'], key: 'down' },
  { keys: ['ArrowLeft'], key: 'left' },
  { keys: ['ArrowRight'], key: 'right' },
];

export interface GameApi {
  readonly state: GameState;
  readonly display: ReturnType<typeof frame>;
  readonly seg: ReturnType<typeof segments>;
  /** SW7：false 时点阵与数码管一律不显示（B1 "所有显示器件不显示"）。 */
  readonly sw7: boolean;
  readonly setSw7: (on: boolean) => void;
  readonly press: (key: GameKey) => void;
  /** 网站便利交互：点某一块直接选中（硬件上只有循环的【选择】键）。 */
  readonly selectPiece: (index: number) => void;
  readonly reset: () => void;
  /** 面板自己的 keydown 处理器（挂到可聚焦容器上，不挂 window）。 */
  readonly onKeyDown: (e: KeyboardEventLike) => void;
  /** 最近一次实际送进引擎的动作（用于高亮键盘示意图上的按键）。 */
  readonly lastKey: GameKey | null;
  readonly lastCode: number | null;
  readonly keys: typeof ACTION_KEYS;
}

/** 只用到这几个字段，所以不依赖 React 的事件类型，便于单测。 */
export interface KeyboardEventLike {
  readonly key: string;
  readonly ctrlKey: boolean;
  readonly metaKey: boolean;
  readonly altKey: boolean;
  preventDefault: () => void;
}

export function useGame(): GameApi {
  const [state, dispatch] = useReducer(reducer, undefined, createInitialState);
  const [sw7, setSw7Raw] = useState(true);
  const [lastKey, setLastKey] = useState<GameKey | null>(null);
  const lastKeyTimer = useRef<number | null>(null);

  /** 心跳：只在 SW7 打开、并且页面可见时走（切到后台不该继续推进倒计时）。 */
  useEffect(() => {
    if (!sw7) return undefined;
    let timer = window.setInterval(() => dispatch({ type: 'tick' }), TICK_MS);
    const onVisibility = (): void => {
      window.clearInterval(timer);
      if (!document.hidden) timer = window.setInterval(() => dispatch({ type: 'tick' }), TICK_MS);
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [sw7]);

  const press = useCallback((key: GameKey) => {
    dispatch({ type: 'press', key });
    setLastKey(key);
    if (lastKeyTimer.current !== null) window.clearTimeout(lastKeyTimer.current);
    lastKeyTimer.current = window.setTimeout(() => setLastKey(null), 220);
  }, []);

  const selectPiece = useCallback((index: number) => {
    dispatch({ type: 'selectPiece', index });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: 'reset' });
    setLastKey(null);
  }, []);

  const setSw7 = useCallback((on: boolean) => {
    setSw7Raw(on);
    // 重新合上开关 = 重新上电：走一次自检（B1 → B2）。
    if (on) dispatch({ type: 'reset' });
  }, []);

  /** 面板自己的 keydown 处理（由 Simulator 挂到可聚焦容器上）。 */
  const onKeyDown = useCallback(
    (e: KeyboardEventLike) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const hit = KEY_BINDINGS.find((b) => b.keys.includes(e.key));
      if (!hit) return;
      e.preventDefault();
      press(hit.key);
    },
    [press],
  );

  const display = useMemo(() => frame(state), [state]);
  const seg = useMemo(() => segments(state), [state]);

  return {
    state,
    display,
    seg,
    sw7,
    setSw7,
    press,
    selectPiece,
    reset,
    onKeyDown,
    lastKey,
    lastCode: lastKey === null ? null : rawKeyCode(lastKey),
    keys: ACTION_KEYS,
  };
}
