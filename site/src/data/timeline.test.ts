/**
 * timeline.test.ts —— 时序播放器数据的**结构不变量**测试
 *
 * 为什么要给"数据文件"写测试：`src/data/timeline.ts` 是一张手写的表，
 * 而 `DataFlow.tsx` 会按下标去索引它（`nodes[i]`、`links[i-1]`、`steps[step]`）。
 * 一旦谁在编辑时删了一个节点却忘了删对应的连线，或者写了一个越界的 `active` 下标，
 * **TypeScript 不会报错**（都是 number），页面上只会静默少一个标签或高亮错位 ——
 * 这类"看不见的错"正是本项目的纪律要拦的东西。
 */

import { describe, expect, it } from 'vitest';

import { FLOW_SCENARIOS, DEFAULT_SCENARIO } from '../data/timeline';

describe('时序播放器数据（timeline.ts）', () => {
  it('默认场景存在', () => {
    expect(FLOW_SCENARIOS.some((s) => s.id === DEFAULT_SCENARIO)).toBe(true);
  });

  it('场景 id 唯一（切换器用 id 做 key 与查找）', () => {
    const ids = FLOW_SCENARIOS.map((s) => s.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it.each(FLOW_SCENARIOS.map((s) => [s.id, s] as const))('场景 %s：连线数 = 节点数 − 1', (_id, s) => {
    // 线性流水线的核心不变量：n 个节点之间正好 n-1 段连线。
    // 少了会让某段箭头没有信号名；多了说明数据写重了。
    expect(s.links.length).toBe(s.nodes.length - 1);
  });

  it.each(FLOW_SCENARIOS.map((s) => [s.id, s] as const))('场景 %s：每一拍的下标都在范围内', (_id, s) => {
    expect(s.steps.length).toBeGreaterThanOrEqual(4);
    for (const [i, step] of s.steps.entries()) {
      // active 指向节点
      for (const a of step.active) {
        expect(Number.isInteger(a), `steps[${i}].active 含非整数 ${a}`).toBe(true);
        expect(a, `steps[${i}].active 越界（节点只有 ${s.nodes.length} 个）`).toBeGreaterThanOrEqual(0);
        expect(a).toBeLessThan(s.nodes.length);
      }
      // busyLinks 指向连线
      for (const b of step.busyLinks ?? []) {
        expect(b, `steps[${i}].busyLinks 越界（连线只有 ${s.links.length} 段）`).toBeGreaterThanOrEqual(0);
        expect(b).toBeLessThan(s.links.length);
      }
      // 每一拍必须真的高亮到东西，否则点【播放】会觉得"没反应"
      expect(step.active.length, `steps[${i}] 没有高亮任何节点`).toBeGreaterThan(0);
      // 播放节奏必须为正，否则定时器退化成 0ms 死循环
      expect(step.holdMs, `steps[${i}].holdMs 必须 > 0`).toBeGreaterThan(0);
    }
  });

  it.each(FLOW_SCENARIOS.map((s) => [s.id, s] as const))('场景 %s：文案非空且没有漏渲染的 Markdown 记号', (_id, s) => {
    expect(s.title.trim().length).toBeGreaterThan(0);
    expect(s.subtitle.trim().length).toBeGreaterThan(0);
    expect(s.blurb.trim().length).toBeGreaterThan(0);
    for (const [i, step] of s.steps.entries()) {
      expect(step.title.trim().length, `steps[${i}].title 为空`).toBeGreaterThan(0);
      expect(step.detail.trim().length, `steps[${i}].detail 为空`).toBeGreaterThan(0);
      // `**强调**` 是给 RichText 解析的；星号必须成对，否则页面上会露出半截星号
      for (const text of [step.title, step.detail, s.blurb]) {
        const stars = (text.match(/\*\*/g) ?? []).length;
        expect(stars % 2, `强调星号不成对：${text.slice(0, 40)}`).toBe(0);
      }
    }
  });

  it('"旋转必需"这条结论在数据里有正面证据（旋转场景至少有一拍在讲旋转的接受/拒绝）', () => {
    const rotate = FLOW_SCENARIOS.find((s) => s.id === 'rotate');
    expect(rotate).toBeDefined();
    const text = rotate!.steps.map((s) => s.title + s.detail).join('');
    expect(text).toMatch(/锚点/);
    expect(text).toMatch(/拒绝|越界|重叠/);
  });
});
