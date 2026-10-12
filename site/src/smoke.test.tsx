/**
 * smoke.test.ts —— 整站渲染 smoke test（不需要浏览器）
 *
 * 为什么值得写：`DataFlow` / `ModuleMap` / `charts` / `Evidence` 这些组件里有大量
 * "按下标取数组元素、按字段拼字符串"的代码，一旦某个数据表被编辑坏（少一个字段、
 * 空数组、undefined 传给 `.map`），**TypeScript 不一定报错**，而页面会在运行时白屏 ——
 * 白屏只有在真实浏览器里才看得到。
 *
 * `react-dom/server` 的 `renderToString` 在纯 Node 环境里就能把整棵树渲染一遍
 * （副作用不执行、`useEffect` 不跑），所以它是"最低成本的崩溃哨兵"：
 *   · 任何一个组件里抛异常 ⇒ 这个测试立刻红；
 *   · 关键内容是否真的渲染出来了（标题、各章节、图表元素数）也能顺手断言。
 *
 * ⚠️ 它**不**替代 `scripts/browser-check.mjs`（那个跑真实浏览器、验交互与布局），
 *    两者是"快速哨兵 + 端到端实测"的关系。
 */

import type { ReactElement } from 'react';
import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { App } from './App';
import { DataFlow } from './components/DataFlow';
import { ModuleMap } from './components/ModuleMap';
import { Tradeoffs } from './sections/Tradeoffs';
import { Evidence } from './sections/Evidence';
import { Architecture } from './sections/Architecture';
import { Demo } from './sections/Demo';
import { Hero } from './sections/Hero';

/** 渲染一个组件并返回 HTML（抛异常就让测试失败）。 */
function html(node: ReactElement): string {
  return renderToString(node);
}

describe('整站渲染 smoke test', () => {
  it('App 能完整渲染（任何组件崩溃都会在这里暴露）', () => {
    const out = html(<App />);
    expect(out.length).toBeGreaterThan(20_000);
    // 骨架必须在
    expect(out).toContain('masthead__id'); // 报头标识
    expect(out).toContain('简易拼图游戏');
    expect(out).toContain('bg-grid'); // 背景网格（装饰但不可少）
    expect(out).toContain('icon-btn'); // 主题切换
  });

  it('六个章节的锚点都在（导航不会指向空气）', () => {
    const out = html(<App />);
    for (const id of ['top', 'demo', 'flow', 'arch', 'evidence', 'cases', 'docs']) {
      expect(out, `缺少 id="${id}"`).toContain(`id="${id}"`);
    }
  });

  it.each([
    ['Hero', <Hero key="hero" />],
    ['Demo', <Demo key="demo" />],
    ['DataFlow', <DataFlow key="flow" />],
    ['Architecture', <Architecture key="arch" />],
    ['Evidence', <Evidence key="evidence" />],
    ['Tradeoffs', <Tradeoffs key="cases" />],
  ])('%s 单独渲染不抛异常且内容非空', (_name, node) => {
    const out = html(node);
    expect(out.length).toBeGreaterThan(500);
  });

  it('时序播放器：4 个场景按钮 + 流水线 + 播放控件都渲染出来了', () => {
    const out = html(<DataFlow />);
    expect(out.match(/class="flow__scenario"/g)?.length).toBe(4);
    expect(out).toContain('pipe__node');
    expect(out).toContain('flow__play');
    expect(out).toContain('type="range"');
    // 每段连线都要有信号名标签（少了说明 links 与 nodes 数量不匹配）
    expect(out).toContain('pipe__arrow-label');
  });

  it('模块地图：12 个模块卡都在，且默认选中一个（详情不为空）', () => {
    const out = html(<ModuleMap />);
    expect(out.match(/class="mod fade"/g)?.length).toBe(12);
    expect(out).toContain('mod-detail');
    expect(out).toContain('puzzle_ctrl');
  });

  it('图表：条形 / 折线 / 利用率行都渲染出来（且没有 NaN 坐标）', () => {
    const out = html(<Evidence />);
    expect(out.match(/chart__bar/g)?.length).toBeGreaterThan(10);
    expect(out.match(/chart__line/g)?.length).toBeGreaterThanOrEqual(2);
    expect(out.match(/class="bar-row"/g)?.length).toBe(4); // 数行而不是数 fill（后者会被 --critical 前缀重复匹配）
    // NaN/Infinity 进 SVG 属性会让图形静默消失 —— 这是最典型的"数据坏了但页面不报错"
    expect(out).not.toMatch(/[xy]="NaN"|width="NaN"|height="NaN"|"Infinity"/);
  });

  it('工程取舍：7 个案例都列出来了，且默认渲染了六步骨架', () => {
    const out = html(<Tradeoffs />);
    expect(out.match(/case-list__item/g)?.length).toBe(7);
    for (const label of ['问题', '约束', '方案', '验证', '结果', '局限']) {
      expect(out, `六步里缺"${label}"`).toContain(label);
    }
    // "#" 很关键：局限必须被写出来
    expect(out).toContain('明确的局限与未做项');
  });

  it('架构：框图（SVG）+ 模块地图 + 时钟表都在', () => {
    const out = html(<Architecture />);
    expect(out).toContain('blockdiagram');
    expect(out).toContain('bd-box');
    expect(out).toMatch(/puzzle_top/);
    expect(out).toContain('keypad_scan');
  });

  it('首屏：演示 GIF 有 alt（可访问性），且没有裸露的 ** 记号', () => {
    const out = html(<Hero />);
    expect(out).toContain('demo__gif');
    expect(out).toContain('alt="');
    expect(out).not.toMatch(/\*\*[^*]+\*\*/);
  });
});
