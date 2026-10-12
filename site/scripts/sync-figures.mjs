#!/usr/bin/env node
/**
 * sync-figures.mjs —— 把仓库里的**真实**图素材同步进 `site/public/figures/`。
 *
 * 为什么要有这一步（而不是把图直接复制进 `site/` 并入库）：
 *   · 同一张图只允许有一份真值源。图的主人仍然是 `docs/图/`（其清单所有者为
 *     `docs/图/README.md`）；本站只是**引用方**。
 *   · 复制来的副本不入库（见 `site/.gitignore`），每次 `dev` / `build` 前重跑，
 *     所以上游换了图，本站自动跟上，不会出现"网页上是旧波形"这种静默漂移。
 *
 * 本项目**不生成、不美化、不合成**任何实验图：
 *   下面每一行都指向 `docs/图/` 里一个已经入库的真实文件。
 *   其中 `GUI-*.png` 是 Quartus II 图形界面的实测截图，
 *   `SIM-*.svg` 是 `scripts/sim.py` 解析 `.vwf` 后**自己画**的辅助波形
 *   （`docs/图/README.md` §0 明确区分这两类，本站的图说也照此标注）。
 */
import { existsSync, mkdirSync, copyFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, '..');
const repoRoot = resolve(siteRoot, '..');
const srcDir = join(repoRoot, 'docs', '图');
const dstDir = join(siteRoot, 'public', 'figures');

/** 本站引用的图素材：目标文件名 -> docs/图 下的源文件名。 */
const FIGURES = {
  // Quartus GUI 实测仿真截图（12 张清单里的第 1 张；其余见 docs/图/README.md §2）
  'gui-clk_gen.png': 'GUI-clk_gen.png',
  // 脚本渲染的辅助波形（不是 Quartus 界面截图 —— 图说里必须如实标注）
  'sim-clk_gen.svg': 'SIM-clk_gen.svg',
  'sim-disp_format.svg': 'SIM-disp_format.svg',
  'sim-dot_matrix_scan.svg': 'SIM-dot_matrix_scan.svg',
  'sim-keypad_scan.svg': 'SIM-keypad_scan.svg',
  'sim-seg_scan.svg': 'SIM-seg_scan.svg',
};

mkdirSync(dstDir, { recursive: true });

const missing = [];
let copied = 0;

for (const [dst, src] of Object.entries(FIGURES)) {
  const from = join(srcDir, src);
  if (!existsSync(from)) {
    missing.push(`docs/图/${src}`);
    continue;
  }
  const to = join(dstDir, dst);
  copyFileSync(from, to);
  copied += 1;
  const kb = (statSync(to).size / 1024).toFixed(1);
  console.log(`  figures  ${dst.padEnd(26)} <- docs/图/${src}  (${kb} KB)`);
}

if (missing.length > 0) {
  // 缺图不算致命：站点里对应的图框会自己降级成"素材缺失"占位说明，
  // 但要在日志里说清楚，避免"图没同步"被当成"图没问题"。
  console.warn(`  figures  ⚠ 缺少 ${missing.length} 个源文件：${missing.join(', ')}`);
  console.warn('  figures    （这些图在 docs/图/ 里不存在时，页面会显示"素材缺失"而不是空白）');
}

console.log(`  figures  已同步 ${copied} 个 -> site/public/figures/`);
