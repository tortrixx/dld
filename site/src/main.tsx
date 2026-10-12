/**
 * main.tsx —— 入口
 *
 * 只做三件事：挂载、引入样式、把首个可聚焦元素以外的滚动行为交给浏览器。
 * 没有任何全局副作用（没有分析、没有字体加载、没有 polyfill）。
 */

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import './styles/tokens.css';
import './styles/app.css';

const host = document.getElementById('root');
if (!host) throw new Error('#root 不存在 —— index.html 与入口脚本不匹配');

createRoot(host).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
