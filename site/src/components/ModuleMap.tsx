/**
 * ModuleMap.tsx —— 模块地图（替代原来那张 5 列 12 行的宽表）
 *
 * 为什么换掉表格：原表把"职责 / 输入 / 输出 / 关键机制"四段散文塞进一行，
 * 12 行 = 一屏半的文字墙，读者根本读不下去（用户的原话："表格数据太多、
 * 系统架构太杂，不够直观"）。改成：**点一个模块，右侧只显示这一个模块的四件事**。
 * 一次只看一个，反而更容易横向比较——因为位置固定、扫视成本低。
 */

import { useState } from 'react';

import { RichText, Src } from './ui';
import { MODULES, TOP_LEVEL, type ModuleRow } from '../data/facts';

const TIER_LABEL: Record<ModuleRow['tier'], string> = {
  io: '输入 / 驱动',
  core: '时序与决策',
  store: '常量查找表',
  top: '整机顶层',
};

function Detail({ m }: { readonly m: ModuleRow }): JSX.Element {
  const fields: readonly { readonly k: string; readonly v: string }[] = [
    { k: '职责', v: m.job },
    { k: '输入（吃什么）', v: m.consumes },
    { k: '输出（吐什么）', v: m.produces },
    { k: '关键机制与实测数', v: m.mechanism },
  ];
  return (
    <div className="mod-detail">
      <div className="chart__head">
        <p className="chart__title">
          <code>{m.entity}</code>{' '}
          <span className="tag" style={{ marginLeft: 'var(--s2)' }}>
            {TIER_LABEL[m.tier]}
          </span>
        </p>
        <p className="note" style={{ marginTop: 0 }}>
          <Src path={m.file} />
        </p>
      </div>
      <div className="mod-detail__grid">
        {fields.map((f) => (
          <div key={f.k}>
            <p className="mod-detail__k">{f.k}</p>
            <p className="mod-detail__v"><RichText text={f.v} /></p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ModuleMap(): JSX.Element {
  const [selected, setSelected] = useState<string>(MODULES.find((m) => m.entity === 'puzzle_ctrl')?.entity ?? MODULES[0].entity);
  const current = MODULES.find((m) => m.entity === selected) ?? MODULES[0];

  return (
    <div>
      <div className="mods" role="group" aria-label="12 个设计模块（点击查看职责与接口）">
        {MODULES.map((m, i) => (
          <button
            key={m.entity}
            type="button"
            className="mod fade"
            aria-pressed={m.entity === current.entity}
            onClick={() => setSelected(m.entity)}
            style={{ ['--i' as string]: i } as React.CSSProperties}
          >
            <span className="mod__name">{m.entity}</span>
            <span className="mod__job">{m.job}</span>
            <span className={`mod__tier${m.tier === 'core' ? ' mod__tier--core' : ''}`}>{TIER_LABEL[m.tier]}</span>
          </button>
        ))}
      </div>

      <Detail m={current} />

      <p className="note" style={{ marginTop: 'var(--s4)' }}>
        这张表按仓库 README 的口径数：<strong>16 个 VHDL 源文件 = 12 个设计模块 + 3 个诊断顶层 + 1 个包</strong>
        （<code>docs/图/dld-架构.drawio</code> 是完整互联关系）。
        其中 <code>puzzle_top</code> 是整机顶层 —— 唯一做引脚绑定的那个，也是唯一会碰到点阵/数码管/蜂鸣器的层级。
        它把 {TOP_LEVEL.job.replace('唯一做引脚绑定的层级；', '')}
      </p>
    </div>
  );
}
