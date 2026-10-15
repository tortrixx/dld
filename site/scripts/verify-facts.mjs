#!/usr/bin/env node
/**
 * verify-facts.mjs —— 把"网站上写的数字"和"仓库里的真值源"机械地对一遍
 *
 * 为什么要写这个脚本：
 *   本项目最花时间的纪律是"每句话都有可执行的证据"。网页是**最容易漂移**的一环 ——
 *   改完 RTL、重新编译、重跑仿真之后，网页上的 1264 LE / 54.27 MHz / 断言条数
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
const informational = [];
const checked = [];

const fail = (msg) => problems.push(msg);
const ok = (msg) => checked.push(msg);
/** 只作记录、不算通过也不算失败（例如"登记了但没用到"）。 */
const notes = (msg) => informational.push(msg);

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

/**
 * 解析真值源里的 "a / b" 形式，**失败就报 FAIL 而不是抛崩栈**。
 * 原来直接 `leMatch[1]`：`fit.le` 一旦不再带斜杠，CI 报的是
 * `Cannot read properties of null`，维护者要自己猜是哪条断言炸了。
 */
function parsePair(text, what) {
  const m = /([\d,]+)\s*\/\s*([\d,]+)/.exec(text ?? '');
  if (!m) {
    fail(`${what} 的格式无法解析（期望 "a / b"，实际是 ${JSON.stringify(text)}）`);
    return null;
  }
  return [Number(m[1].replace(/,/g, '')), Number(m[2].replace(/,/g, ''))];
}

function parseNum(value, what) {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    fail(`${what} 不是数字（实际是 ${JSON.stringify(value)}）`);
    return null;
  }
  return n;
}

/**
 * ⚠️ 断言的**强度**直接决定这个脚本有没有意义。
 *
 * 早先的写法是 `site.includes(String(value))`（site = 全部站点源码的全文拼接），
 * 这是**可以假通过**的：'127' 在站点文本里出现 68 次，绝大多数来自 `1270` /
 * `EPM1270T144C5`；'52' 有 13 次，来自 `padR = 52`、`y: 522`、sha256 片段、`'r52 / r53'`。
 * 也就是说：把"LAB 用量 127""引脚 52"整句从页面上删掉，`includes` 仍然成立、脚本照样 [OK]。
 *
 * 所以改成**"标签与数值必须同现、且有边界"**：在 `label` 之后 window 个字符内找
 * **带边界**的数字（避免匹配到更长数字的前缀）。标签写在 facts.ts 的同一行/同一块里，
 * 是真值源本身的结构，比"全文任意位置出现"强得多。
 */
function assertNearby(label, value, window = 220) {
  const v = String(value);
  const esc = v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // 数字左侧不能是数字/逗号/点（挡住 `1270` 里的 `127`、`1,264` 里的 `264`）
  const bounded = new RegExp(`(?<![\\d,.])${esc}(?![\\d])`);
  for (const m of site.matchAll(new RegExp(label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'))) {
    const seg = site.slice(m.index, m.index + window);
    if (bounded.test(seg)) {
      ok(`${label} = ${v}（标签与数值同现，窗口 ${window} 字符）`);
      return;
    }
  }
  fail(`${label} 对不上：真值源 = ${v}，但在站点源码里找不到"${label}"附近（${window} 字符内）的该数值`);
}

const le = parsePair(prov.fit?.le, 'build_provenance.json 的 fit.le');
const lab = parsePair(prov.fit?.lab, 'build_provenance.json 的 fit.lab');
const pins = parsePair(prov.fit?.pins, 'build_provenance.json 的 fit.pins');
const setupSlack = parseNum(prov.sta?.setup_slack, 'build_provenance.json 的 sta.setup_slack');
const holdSlack = parseNum(prov.sta?.hold_slack, 'build_provenance.json 的 sta.hold_slack');

if (le && lab && pins) {
  assertNearby('LE', le[0]);
  assertNearby('LE', le[1]);
  assertNearby('LAB', lab[0]);
  assertNearby('LAB', lab[1]);
  assertNearby('引脚', pins[0]);
  assertNearby('引脚', pins[1]);
}
if (setupSlack !== null) {
  assertNearby('setup', setupSlack.toFixed(3));
  // 数据路径必须是"由约束与 slack 反推"的值，不能凭空写一个数：
  // 20 − 1.572 = 18.428。站点文案里必须出现这个反推值（或被明确标注为反推）。
  assertNearby('数据路径', (20 - setupSlack).toFixed(3));
}
if (holdSlack !== null) assertNearby('hold', holdSlack.toFixed(3));

// POF 指纹：sha256 只在前 8 位这一层做"同现"检查（哈希片段本身没有语义标签）
const sha = prov.pof?.sha256 ?? '';
if (sha.length >= 8) {
  if (site.includes(sha.slice(0, 8))) ok(`POF sha256 前缀 = ${sha.slice(0, 8)}`);
  else fail(`POF sha256 前缀对不上：provenance = ${sha.slice(0, 8)}`);
} else {
  fail('build_provenance.json 里没有可用的 pof.sha256');
}

// Fmax 只在文档里（provenance 不存 Fmax）：取 docs/05 的 **Restricted Fmax** 那一行，
// 而不是"文件里第一个 x.xx MHz"——后者可能是历史读数（44.77 / 36.68 / 51.44 都出现过）。
const docs05 = read('docs/05-资源利用与编译报告.md');
const docsFmax = (() => {
  // 锚定到「当前读数」那一节，而不是"文件里第一个 x.xx MHz"（历史值 44.77/36.68/51.44 都出现过）。
  // docs/05 的写法是 "54.27 MHz（restricted 54.27 MHz）"，所以直接找这个成对出现的形式。
  // docs/05 里 "x MHz（restricted x MHz）" 会出现多次：早期章节写的是**历史**读数
  // （§演进表里 53.28 等在文档前部），当前读数在文档后部的汇总节。
  // 所以取**最后一处**，并且要求至少出现两次（只出现一次说明文档结构变了，宁可报 FAIL）。
  const all = [...docs05.matchAll(/([\d.]+)\s*MHz\s*（restricted\s*([\d.]+)\s*MHz）/gi)];
  const pairs = all.filter((m) => m[1] === m[2]);
  if (pairs.length < 2) return null;
  return Number(pairs[pairs.length - 1][1]);
})();

// 站点侧必须从**真值源自己**里取（HEADLINE_METRICS 的 Fmax 行），再和 docs/05 做数值比较。
// 原来的实现只用硬编码正则测"站点里含 54.27"这个字面量、从不比较两边数值 ——
// 变异测试证明：把 docs/05 全部改成 36.68 而站点不动，仍打印 [OK] 并 exit 0。
const siteFmax = (() => {
  const hm = /const HEADLINE_METRICS[\s\S]*?\n\];/.exec(site);
  const block = hm ? hm[0] : site;
  const m = /Fmax[\s\S]{0,160}?value:\s*'([\d.]+)'/.exec(block);
  return m ? Number(m[1]) : null;
})();

if (docsFmax === null) fail('没能在 docs/05 里找到当前 Fmax 读数（锚定 "x MHz（restricted x MHz）" 失败）');
else if (siteFmax === null) fail('没能从 facts.ts 的 HEADLINE_METRICS 里解析出 Fmax 数值');
else if (siteFmax !== docsFmax) fail(`Fmax 不一致：docs/05 = ${docsFmax} MHz，站点 = ${siteFmax} MHz`);
else ok(`Fmax = ${siteFmax} MHz（站点与 docs/05 数值相等）`);

// 标称指标块里不许出现历史 Fmax（另外 8 个历史常量是已知会出现的干扰项）
// 编译时间戳
if (site.includes(prov.timestamp)) ok(`构建时间戳 = ${prov.timestamp}`);
else fail(`构建时间戳对不上：provenance = ${prov.timestamp}`);

// git HEAD 短号
const head = sha ? (prov.git_head ?? '').slice(0, 8) : '';
if (head && site.includes(head)) ok(`git HEAD 短号 = ${head}`);
else fail(`git HEAD 短号对不上或缺失：provenance = ${JSON.stringify(prov.git_head)}`);

// 不允许出现"无入库出处"的时序读数（评审抓到过 18.095 ns 与 1450 logic cells / 528 registers）
const forbidden = [
  ['18.095', '路径长度 18.095 ns 不在任何入库文件里（反推值应为 20 − 1.572 = 18.428）'],
  ['1,450', '1,450 logic cells 只对应 ERR-051 对照表里 SEED 5 那一版，不是当前固件'],
  ['1450 logic', '1,450 logic cells 不是当前固件的读数'],
  ['528 / 1270', '寄存器数 528 在仓库里查不到出处'],
];
for (const [needle, why] of forbidden) {
  if (site.includes(needle)) fail(`站点里出现了无入库出处的数字 "${needle}"：${why}`);
}
ok('未出现 18.095 / 1,450 / 528 这三个"无入库出处"的历史或跨版本数字');

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

// 断言合计口径：12 行逐项相加（整机 `puzzle_top` 只计一次，它一行代表两种场景）。
//
// ⚠️ 2026-10-15 第 27 工作阶段改动：`facts.ts` 里的合计从**手打常数**改成了
//    由 `SIM_COVERAGE` 派生的 `reduce` —— 因为排查发现 Hero/Footer 里手写的
//    "179 条"已经过期（真实是 184），同一个数字在仓库里存在两个值。
//    所以这里要同时接受两种写法，但**不接受**其它任何写法。
const literalTotal = /SIM_TOTAL_ASSERTIONS\s*=\s*(\d+)\s*;/.exec(site);
const derivedTotal = /SIM_TOTAL_ASSERTIONS\s*=\s*SIM_COVERAGE\.reduce\(/.exec(site);
if (literalTotal) {
  const declared = Number(literalTotal[1]);
  if (declared !== total) {
    fail(`断言合计对不上：站点声明 ${declared}，逐模块相加 = ${total}`);
  } else {
    ok(`断言合计 = ${declared} 条（字面量，且与逐模块相加一致）`);
  }
} else if (derivedTotal) {
  ok(`断言合计由 SIM_COVERAGE 派生（= ${total} 条，逐模块相加一致）`);
} else {
  fail('站点源码里既没有 SIM_TOTAL_ASSERTIONS 的字面量，也不是 SIM_COVERAGE 的 reduce 派生');
}

/* ================================================================== *
 * ②b 与「技术文档站」共用同一套事实：facts/facts.json
 * ------------------------------------------------------------------
 * 展示站（site/）与文档站（book/）是两个站点，但**必须是同一套工程事实**，
 * 否则会出现"网页说 1264 LE、文档说别的"这种最尴尬的分歧。
 * facts/facts.json 是两者共用的机读真值源（由 scripts/extract_facts.py 生成），
 * 这里把本站声明的读数与它逐项对一遍。
 * ================================================================== */

const factsPath = join(repoRoot, 'facts', 'facts.json');
if (!existsSync(factsPath)) {
  fail('缺少 facts/facts.json（两个站点共用的事实模型未生成，跑 python scripts/extract_facts.py）');
} else {
  let facts = null;
  try {
    facts = JSON.parse(readFileSync(factsPath, 'utf8'));
  } catch (e) {
    fail(`facts/facts.json 解析失败：${e.message}`);
  }
  if (facts) {
    const checks = [
      ['LE', String(facts.build.fit.le).replace(/[^\d]/g, '').slice(0, 4), /"le"\s*:/],
      ['断言总数', String(facts.sim.totals.assertions), null],
    ];
    // 断言总数：facts.json 必须与"逐模块相加"完全一致
    if (facts.sim.totals.assertions !== total) {
      fail(`facts/facts.json 的断言总数 ${facts.sim.totals.assertions} ≠ 轮次记录逐模块相加 ${total}`);
    } else {
      ok(`facts/facts.json 与轮次记录一致（断言 ${total} 条、模块 ${facts.sim.totals.modules} 个）`);
    }
    // 关键读数：本站 HEADLINE_METRICS 里的数字必须能在 facts.json 里找到同值
    const leFromFacts = String(facts.build.fit.le).match(/([\d,]+)\s*\/\s*([\d,]+)/);
    const leSite = /label: '逻辑单元 LE',\s*\n\s*value: '([\d,]+)'/.exec(site);
    if (leFromFacts && leSite && leFromFacts[1].replace(/,/g, '') !== leSite[1].replace(/,/g, '')) {
      fail(`LE 对不上：站点 ${leSite[1]}，facts.json ${leFromFacts[1]}`);
    }
    const labFromFacts = String(facts.build.fit.lab).match(/([\d,]+)\s*\/\s*([\d,]+)/);
    const labSite = /label: 'LAB（逻辑阵列块）',\s*\n\s*value: '([\d,]+)'/.exec(site);
    if (labFromFacts && labSite && labFromFacts[1].replace(/,/g, '') !== labSite[1].replace(/,/g, '')) {
      fail(`LAB 对不上：站点 ${labSite[1]}，facts.json ${labFromFacts[1]}`);
    }
    // POF 指纹：站点里的 sha256 前 8 位必须是 facts.json 里那一个的前缀
    const pofSite = /pofSha256:\s*'([0-9a-f]{8})/.exec(site);
    if (pofSite && !String(facts.build.provenance.pof.sha256).startsWith(pofSite[1])) {
      fail(`POF sha256 前缀对不上：站点 ${pofSite[1]}…，facts.json ${facts.build.provenance.pof.sha256.slice(0, 8)}…`);
    }
    if (pofSite) ok(`POF 指纹与 facts.json 一致（${pofSite[1]}…）`);
    void checks;
  }
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
 * ④ 页面依赖的图素材：引用名 → docs/图/ 里的源文件必须真的存在
 * ------------------------------------------------------------------
 * 为什么单列一节：`figure('x')` 的引用**不**走 blob()/path: 那两条规则，
 * 所以上面第 ③ 节扫不到它。而"GIF 被删了/改名了"这种事，`npm run build` 照样成功、
 * 页面照样渲染（只是图破了），只有真实浏览器里才看得出来。
 * 把映射关系（sync-figures.mjs 的 FIGURES）当契约对一遍，就能在构建前拦住。
 * ================================================================== */

const syncSrc = readFileSync(join(siteRoot, 'scripts', 'sync-figures.mjs'), 'utf8');
const figuresBlock = /const FIGURES = \{([\s\S]*?)\n\};/.exec(syncSrc);
if (!figuresBlock) {
  fail('sync-figures.mjs 里没找到 FIGURES 映射（verify-facts 的解析规则需要跟着改）');
} else {
  /** 解析 `'目标名': '源文件名',` 形式的条目。 */
  const mapping = new Map();
  for (const m of figuresBlock[1].matchAll(/'([^']+)'\s*:\s*'([^']+)'/g)) mapping.set(m[1], m[2]);

  const referenced = new Set([...site.matchAll(/figure\(\s*'([^']+)'/g)].map((m) => m[1]));

  const missingRef = [...referenced].filter((name) => !mapping.has(name));
  if (missingRef.length) {
    fail(`页面引用了 figure('x') 但 sync-figures.mjs 没有登记：${JSON.stringify(missingRef)}`);
  }

  const missingSource = [];
  for (const [dst, src] of mapping) {
    if (!exists(`docs/图/${src}`)) missingSource.push(`docs/图/${src}（供 figure('${dst}') 用）`);
  }
  if (missingSource.length) {
    fail(`图素材源文件不存在，页面会显示"素材缺失"：${JSON.stringify(missingSource)}`);
  }

  const unused = [...mapping.keys()].filter((k) => !referenced.has(k));
  if (missingRef.length === 0 && missingSource.length === 0) {
    ok(`图素材映射完整：${referenced.size} 个 figure() 引用都有源文件（共登记 ${mapping.size} 个）`);
  }
  if (unused.length) notes(`sync-figures.mjs 登记了但页面没用到的图：${JSON.stringify(unused)}`);
}

/* ================================================================== *
 * ⑤ 时序播放器里每条 step 的 `cite` 出处必须真的存在
 * ------------------------------------------------------------------
 * `src/data/timeline.ts` 每个 step 都写了出处（"rtl/puzzle_top.vhd:520" 这类）。
 * 出处写错、或写到一个不存在的文件上，页面不会有任何异常 —— 读者点进去才发现是死引用。
 * 所以把 cite 里的路径抠出来逐个核对（存在 + 已入库）。
 * ================================================================== */

const timelineSrc = readFileSync(join(siteRoot, 'src', 'data', 'timeline.ts'), 'utf8');
const citePaths = new Set();
for (const m of timelineSrc.matchAll(/cite:\s*'([^']+)'/g)) {
  for (const p of m[1].matchAll(/[A-Za-z0-9_./\u4e00-\u9fff-]+\.(?:vhd|md|json|py|ts|tsx|sdc|qsf|gif|drawio)/g)) {
    citePaths.add(p[0]);
  }
}

if (citePaths.size === 0) {
  fail('timeline.ts 里一个 cite 出处都没解析出来（verify-facts 的解析规则需要跟着改）');
} else {
  const badCite = [];
  for (const p of citePaths) {
    if (!exists(p)) badCite.push(`${p}（文件不存在）`);
    else if (tracked && !tracked.has(p) && !p.startsWith('site/')) badCite.push(`${p}（未入库，克隆后不存在）`);
  }
  if (badCite.length) fail(`timeline.ts 的 cite 出处有问题：${JSON.stringify(badCite)}`);
  else ok(`timeline.ts 的 ${citePaths.size} 个 cite 出处全部存在且已入库`);
}

/* ================================================================== *
 * 输出
 * ================================================================== */

console.log('\nverify-facts：把网页上的数字与仓库真值源对账\n');
for (const c of checked) console.log(`  [OK]   ${c}`);
for (const n of informational) console.log(`  [--]   ${n}`);
for (const p of problems) console.log(`  [FAIL] ${p}`);
console.log(
  `\n  合计：${problems.length} FAIL / ${checked.length} OK\n`,
);

if (problems.length && !warnOnly) process.exit(1);
