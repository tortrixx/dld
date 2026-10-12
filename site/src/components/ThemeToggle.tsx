/**
 * ThemeToggle.tsx —— 深浅主题切换
 *
 * 与参照站同一套做法：
 *   · 默认**跟随系统**（`prefers-color-scheme`），不预设品牌色偏好；
 *   · 用户点过之后写 `localStorage`，用 `data-theme` 属性显式覆盖；
 *   · 首帧之前就把属性写进 `<html>`（见 index.html 里的内联脚本），
 *     否则深色模式下会先闪一下白屏（FOUC）。
 */

import { useEffect, useState } from 'react';

type Theme = 'system' | 'light' | 'dark';

const KEY = 'dld-theme';

function apply(theme: Theme): void {
  const root = document.documentElement;
  if (theme === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', theme);
}

export function ThemeToggle(): JSX.Element {
  const [theme, setTheme] = useState<Theme>(() => {
    // ⚠️ 只判 `typeof localStorage` 不够：在"屏蔽所有站点数据"的浏览器里，
    //    访问 window.localStorage **本身**就抛 SecurityError ⇒ 初始化器抛异常
    //    ⇒ 报头里的这个组件会让**整页白屏**。所以整段包 try/catch。
    try {
      const saved = localStorage.getItem(KEY);
      return saved === 'light' || saved === 'dark' ? saved : 'system';
    } catch {
      return 'system';
    }
  });

  useEffect(() => {
    apply(theme);
    try {
      if (theme === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, theme);
    } catch {
      /* 隐私模式下写不了，忽略即可 */
    }
  }, [theme]);

  /** 三态循环：跟随系统 → 浅色 → 深色 → 跟随系统 */
  const next = (): Theme => (theme === 'system' ? 'light' : theme === 'light' ? 'dark' : 'system');
  const label = theme === 'system' ? '跟随系统' : theme === 'light' ? '浅色' : '深色';

  return (
    <button
      type="button"
      className="icon-btn"
      onClick={() => setTheme(next())}
      aria-label={`主题：${label}（点击切换）`}
      title={`主题：${label}`}
    >
      {/* 三个图标都是纯装饰，可访问名由按钮的 aria-label 承担 */}
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        {theme === 'system' ? (
          <>
            <rect x="3" y="4" width="18" height="13" rx="2" />
            <path d="M8 20h8M12 17v3" />
          </>
        ) : theme === 'light' ? (
          <>
            <circle cx="12" cy="12" r="4.2" />
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
          </>
        ) : (
          <path d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.4 8.4 0 1 0 10.2 10.2z" />
        )}
      </svg>
    </button>
  );
}
