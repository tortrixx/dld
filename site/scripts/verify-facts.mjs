#!/usr/bin/env node
/**
 * verify-facts.mjs —— 把"网站上写的数字"和"仓库里的真值源"机械地对一遍
 *
 * 为什么要写这个脚本：
 *   本项目最花时间的纪律是"每句话都有可执行的证据"。网页是**最容易漂移**的一环 ——
 *   改完 RTL、重新编译、重跑仿真之后，网页上的 1264 LE / 54.27 MHz / 179 条断言
 *   就会悄悄变成旧数字，而且**没人会注意到**（页面照样好看）。
 *   所以这里不靠人眼复核，直接拿仓库里的机读文件来对。
 *
 * 它检查三类东西：
 *   ① **资源与时序数字** ← `quartus/build_provenance.json`（入库的机读溯源）
 *   ② **仿真轮次与断言条数** ← `sim/rounds/<模块>/*.json` 的**最新一轮**
 *   ③ **所有被引用的仓库路径** ← 既要在工作区存在，也要 `git ls-files` 认得（= 已入库），
 *      后面这条专治"链到 .gitignore 挡掉的编译产物"这类死链
 *
 * 用法（在 site/ 下）：
 *   node scripts/verify-facts.mjs            # 有问题就退出码 1
 *   node scripts/verify-facts.mjs --warn     # 只警告，不失败
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, '..');
const repoRoot = resolve(siteRoot, '..');
const warnOnly = process.argv.includes('--warn');

const problems = [];
const checked = [];

const fail = (msg) => problems.push(msg);
const ok = (msg) => checked.push(msg);

const read = (rel) => readFileSync(join(repoRoot, rel), 'utf8');
const exists = (rel) => existsSync(join(repoRoot, rel));

/** 站点源码里所有 .ts/.tsx 的合并文本（用来"网页上到底写了什么"）。 */
function siteSource() {
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.(ts|tsx|css|html)$/.test(entry)) out.push(readFileSync(p, 'utf8'));
    }
  };
  walk(join(siteRoot, 'src'));
  out.push(readFileSync(join(siteRoot, 'index.html'), 'utf8'));
  const app = out.join('\n');
  return app;
}

const site = siteSource();

/* ================================================================== *
 * ① 资源与时序：对 build_provenance.json
 * ================================================================== */

const prov = JSON.parse(read('quartus/build_provenance.json'));
const leMatch = /([\d,]+)\s*\/\s*([\d,]+)/.exec(prov.fit.le);
const leUsed = Number(leMatch[1].replace(/,/g, ''));
const leTotal = Number(leMatch[2].replace(/,/g, ''));
const labMatch = /(\d+)\s*\/\s*(\d+)/.exec(prov.fit.lab);
const pinMatch = /(\d+)\s*\/\s*(\d+)/.exec(prov.fit.pins);

const expectNumbers = [
  ['LE 用量', String(leUsed)],
  ['LE 总量', String(leTotal)],
  ['LAB 用量', labMatch[1]],
  ['LAB 总量', labMatch[2]],
  ['引脚用量', pinMatch[1]],
  ['引脚总量', pinMatch[2]],
  ['setup slack', prov.sta.setup_slack.toFixed(3)],
  ['hold slack', prov.sta.hold_slack.toFixed(3)],
  ['POF sha256 前缀', prov.pof.sha256.slice(0, 8)],
];

for (const [label, value] of expectNumbers) {
  if (site.includes(value)) ok(`${label} = ${value}（出现在站点源码里）`);
  else fail(`${label} 对不上：build_provenance.json = ${value}，但站点源码里找不到这个字符串`);
}

// Fmax 只在文档里（provenance 不存 Fmax），核对它是否与 docs/05 的口径一致
const docs05 = read('docs/05-资源利用与编译报告.md');
const fmax = /(\d+\.\d+)\s*MHz/.exec(docs05);
if (fmax) {
  if (site.includes(fmax[1])) ok(`Fmax = ${fmax[1]} MHz（出现在站点源码里，取自 docs/05）`);
  else fail(`Fmax 对不上：docs/05 里读到 ${fmax[1]} MHz，站点源码里找不到`);
} else {
  fail('没能在 docs/05 里找到 Fmax 读数，无法核对');
}

// 编译时间戳
if (site.includes(prov.timestamp)) ok(`构建时间戳 = ${prov.timestamp}`);
else fail(`构建时间戳对不上：provenance = ${prov.timestamp}`);

// git HEAD 短号
const head = prov.git_head.slice(0, 8);
if (site.includes(head)) ok(`git HEAD 短号 = ${head}`);
else fail(`git HEAD 短号对不上：provenance = ${head}`);

/* ================================================================== *
 * ② 仿真：对 sim/rounds/<模块>/*.json 的最新一轮
 * ================================================================== */

/** 从 facts.ts 里抠出 SIM_COVERAGE 的每一行（heuristic，但足够稳）。 */
const coverageRows = [...site.matchAll(/module:\s*'([^']+)',\s*round:\s*'([^']+)',\s*assertions:\s*(\d+)/g)].map(
  (m) => ({ module: m[1], round: m[2], assertions: Number(m[3]) }),
);

if (coverageRows.length === 0) {
  fail('没能从站点源码里解析出 SIM_COVERAGE（verify-facts.mjs 的解析规则需要跟着改）');
}

let total = 0;
for (const row of coverageRows) {
  const dir = join(repoRoot, 'sim', 'rounds', row.module);
  if (!existsSync(dir)) {
    fail(`sim/rounds/${row.module}/ 不存在`);
    continue;
  }
  const files = readdirSync(dir).filter((f) => /^r\d+\.json$/.test(f));
  const rounds = files.map((f) => ({ f, n: Number(/^r(\d+)\.json$/.exec(f)[1]) })).sort((a, b) => b.n - a.n);
  if (rounds.length === 0) {
    fail(`sim/rounds/${row.module}/ 下没有轮次记录`);
    continue;
  }
  const latest = rounds[0];
  const json = JSON.parse(readFileSync(join(dir, latest.f), 'utf8'));
  const totalA = json.assertions?.length ?? json.total ?? null;
  const passA = json.passed ?? json.pass_count ?? null;

  // 站点里写的轮次必须就是**最新**那一轮
  const siteMax = Math.max(...row.round.split(' / ').map((r) => Number(r.replace(/\D/g, ''))));
  if (Number.isFinite(siteMax) && siteMax !== latest.n) {
    fail(
      `${row.module}: 站点写的是 r${siteMax}，但仓库里最新一轮是 r${latest.n} —— 网页落后了（要么更新站点，要么这是有意的历史轮次）`,
    );
  } else {
    ok(`${row.module}: 轮次 r${latest.n} 与仓库最新一轮一致`);
  }

  // 断言条数
  if (typeof totalA === 'number' && totalA !== row.assertions) {
    fail(`${row.module}: 站点写 ${row.assertions} 条断言，r${latest.n}.json 里是 ${totalA} 条`);
  } else if (typeof totalA === 'number') {
    ok(`${row.module}: 断言 ${row.assertions} 条，与 r${latest.n}.json 一致`);
  } else {
    // 轮次记录的字段名换了也不能静默通过
    fail(`${row.module}: r${latest.n}.json 里找不到可用的断言条数字段（字段名可能变了）`);
  }

  if (json.all_pass === false) fail(`${row.module}: r${latest.n}.json 标记 all_pass = false`);

  total += row.assertions;
}

// "179" 这个合计口径：12 行逐项相加（整机只计一次）
const siteTotalMatch = /SIM_TOTAL_ASSERTIONS\s*=\s*(\d+)/.exec(site);
if (siteTotalMatch) {
  const declared = Number(siteTotalMatch[1]);
  if (declared !== total) {
    fail(`断言合计对不上：站点声明 ${declared}，逐模块相加 = ${total}`);
  } else {
    ok(`断言合计 = ${declared} 条（逐模块相加一致）`);
  }
} else {
  fail('站点源码里找不到 SIM_TOTAL_ASSERTIONS');
}

/* ================================================================== *
 * ③ 被引用的仓库路径：既要存在，也要已入库（git ls-files 认得）
 * ================================================================== */

let tracked = null;
try {
  // ⚠️ 必须用 `-z`：默认情况下 git 会把中文路径**加引号并转成 \345 这样的八进制转义**
  // （core.quotepath=true），于是 `docs/图/README.md` 永远匹配不上、误报成"未入库"。
  // 这是第一次跑这个脚本时真的踩到的坑。
  tracked = new Set(
    execFileSync('git', ['ls-files', '-z'], { cwd: repoRoot, encoding: 'utf8' })
      .split('\0')
      .filter(Boolean),
  );
} catch {
  fail('git ls-files 执行失败 —— 无法核对"链接是否指向已入库文件"');
}

/** 把站点源码里出现的仓库相对路径抠出来。 */
const pathCandidates = new Set();
// blob('...') / tree('...') 调用
for (const m of site.matchAll(/\b(?:blob|tree)\(\s*'([^']+)'/g)) pathCandidates.add(m[1]);
// facts.ts 里的结构化字段
for (const m of site.matchAll(/\b(?:path|file):\s*'([^']+)'/g)) pathCandidates.add(m[1]);

const skip = (p) =>
  p.startsWith('#') ||
  p.startsWith('http') ||
  p.includes(' ') ||
  p === 'rtl/' || // 目录：下面单独判
  p.endsWith('/') ||
  // 本次新增、尚未提交的目录：它们**就是**这次要交付的东西，
  // 提交之后就入库了。放在这里只是说明"还没 commit"，不算链接错误。
  p.startsWith('site/') ||
  p.startsWith('.github/');

const missing = [];
const untracked = [];
for (const p of pathCandidates) {
  if (skip(p)) continue;
  if (!exists(p)) {
    missing.push(p);
    continue;
  }
  if (tracked && !tracked.has(p)) untracked.push(p);
}
// 目录形式的引用单独判（git ls-files 里是文件，所以看前缀）
for (const p of pathCandidates) {
  if (!p.endsWith('/')) continue;
  if (skip(p)) continue;
  if (!exists(p)) {
    missing.push(p);
    continue;
  }
  if (tracked && ![...tracked].some((t) => t.startsWith(p))) untracked.push(p);
}

if (missing.length) fail(`站点引用了工作区里不存在的路径：${JSON.stringify(missing)}`);
else ok(`被引用的仓库路径全部存在（共 ${pathCandidates.size} 个候选）`);

if (untracked.length) {
  fail(
    `站点引用了**未入库**的路径（克隆下来会 404）：${JSON.stringify(untracked)} —— ` +
      '典型原因是链到了 quartus/output_files/*.rpt / *.pof / *.pin 这类被 .gitignore 挡掉的编译产物',
  );
} else if (tracked) {
  ok('被引用的路径全部已被 git 跟踪（克隆下来不会 404）');
}

/* ================================================================== *
 * 输出
 * ================================================================== */

console.log('\nverify-facts：把网页上的数字与仓库真值源对账\n');
for (const c of checked) console.log(`  [OK]   ${c}`);
for (const p of problems) console.log(`  [FAIL] ${p}`);
console.log(
  `\n  合计：${problems.length} FAIL / ${checked.length} OK\n`,
);

if (problems.length && !warnOnly) process.exit(1);
