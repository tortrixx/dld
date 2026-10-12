#!/usr/bin/env node
/**
 * browser-check.mjs —— 用真实浏览器打开页面做检查与截图
 *
 * 为什么要有这个脚本（而不是"读代码觉得没问题"）：
 *   · 静态检查看不出布局溢出、对比度、字体有没有真的加载、GIF 有没有 404、
 *     播放器点了到底动没动、控制台报错；
 *   · 这个项目的纪律是"能实测就别靠推断"，前端也一样。
 *
 * 实现方式：**零依赖**。用 CDP（Chrome DevTools Protocol）直接驱动无头 Chrome/Edge，
 * 靠 Node 22+ 内置的全局 WebSocket 通信 —— 不装 puppeteer / playwright。
 *
 * 它检查的东西（任一条不满足就非 0 退出）：
 *   ① 控制台报错 / 未捕获异常 / React 未挂载 / 没有 h1
 *   ② 字体真的加载了（`document.fonts.check`）—— "字体挂了"表现为静默回落，肉眼很难发现
 *   ③ 演示 GIF 真的解码出来了（`naturalWidth > 0`）—— 防 404 静默失败
 *   ④ 主题切换真的生效（data-theme 变化 + 背景色变化）
 *   ⑤ 时序播放器：场景切换、播放推进、时间轴拖动、仪表点阵真的亮
 *   ⑥ 模块地图与案例切换器：点一下详情真的换
 *   ⑦ 图表画出来了（SVG 里有 bar / path）
 *   ⑧ 390 / 320px 无横向溢出；触控目标 ≥44px
 *   ⑨ 页内锚点全部命中；不出现无法分类的外链
 *   ⑩ 正文对比度 ≥4.5:1；正文没有裸露的 Markdown 记号
 *
 * ⚠️ 两个踩过的坑（别重犯）：
 *   · **溢出检测不要用 `mobile: true`**：Chrome 的移动端仿真会在内容超宽时把
 *     layout viewport 一起撑大（shrink-to-fit），溢出被"仿真"吃掉、永远看起来没问题。
 *   · **背景色要沿祖先链取**：拿 body 的颜色去量深色面板里的小字会得到假的不合格。
 *
 * 用法：node scripts/browser-check.mjs [url]
 */

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, '..');
const outDir = join(siteRoot, '.shots');
const TARGET_URL = process.argv[2] ?? 'http://localhost:4173/dld/';

// ⚠️ Node < 22 没有全局 WebSocket，脚本会直接 `WebSocket is not defined`。
// CI 用的是 node 22；本地若版本过低，这里给一句人能看懂的提示。
if (typeof WebSocket === 'undefined') {
  console.error(
    `需要 Node 22 以上（本脚本用内置全局 WebSocket 说 CDP）。当前版本：${process.version}`,
  );
  process.exit(2);
}

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].filter(Boolean);

const chromePath = CHROME_CANDIDATES.find((p) => existsSync(p));
if (!chromePath) {
  console.error('找不到 Chrome / Edge。设 CHROME_PATH 环境变量，或把浏览器装到常见位置。');
  process.exit(2);
}

mkdirSync(outDir, { recursive: true });
const profile = join(tmpdir(), `dld-browser-check-${Date.now()}`);
/**
 * 调试端口不能写死：9333 被占（上次崩溃残留、别的调试实例）时新 Chrome 会绑定失败，
 * 但 `stdio: 'ignore'` 把报错吞了，而 `json/list` 仍可能返回**另一个浏览器**的页面 —
 * 断言就会对着一个无关页面跑（假绿/假红）。这里先探一次端口是否空闲。
 */
async function pickPort() {
  const base = 9333 + (Number(process.env.CDP_PORT_OFFSET ?? 0) || 0);
  for (let port = base; port < base + 25; port += 1) {
    try {
      await fetch(`http://127.0.0.1:${port}/json/version`, { signal: AbortSignal.timeout(400) });
      // 有响应 ⇒ 已被占用，换下一个
    } catch {
      return port;
    }
  }
  throw new Error(`从 ${base} 起的 25 个端口都被占用，请设 CDP_PORT_OFFSET 换一段`);
}

const PORT = await pickPort();

const chrome = spawn(
  chromePath,
  [
    '--headless=new',
    '--disable-gpu',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--force-device-scale-factor=1',
    '--hide-scrollbars',
    `--user-data-dir=${profile}`,
    `--remote-debugging-port=${PORT}`,
    'about:blank',
  ],
  { stdio: 'ignore' },
);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let cleanedUp = false;
let cdpRef = null;
/** 关连接、杀浏览器、删临时 profile —— 成功与失败两条路径都要走一遍
 *  （原来失败路径会每次残留一个数十 MB 的 Chrome profile）。 */
function cleanup() {
  if (cleanedUp) return;
  cleanedUp = true;
  try { cdpRef?.close(); } catch { /* 已关 */ }
  try { chrome.kill(); } catch { /* 已退 */ }
  try { rmSync(profile, { recursive: true, force: true }); } catch { /* Windows 上偶发占用 */ }
}
const problems = [];
const notes = [];

async function pageTarget() {
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const page = (await res.json()).find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) return page;
    } catch {
      /* 还没起来 */
    }
    await sleep(250);
  }
  throw new Error('Chrome 的调试端口没起来');
}

function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let nextId = 1;
  const pending = new Map();
  const events = [];
  ws.addEventListener('message', (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve: res, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(`${msg.error.message} ${JSON.stringify(msg.error.data ?? '')}`));
      else res(msg.result);
    } else if (msg.method) events.push(msg);
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener('open', () => res());
    ws.addEventListener('error', () => rej(new Error('CDP 连接失败')));
  });
  const send = (method, params = {}) =>
    new Promise((res, rej) => {
      const id = nextId++;
      pending.set(id, { resolve: res, reject: rej });
      ws.send(JSON.stringify({ id, method, params }));
    });
  return { send, ready, events, close: () => ws.close() };
}

async function main() {
  const target = await pageTarget();
  const cdp = connect(target.webSocketDebuggerUrl);
  cdpRef = cdp;
  await cdp.ready;
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable');

  const consoleErrors = [];
  const consoleWarns = [];
  const pageErrors = [];

  const drain = () => {
    for (const ev of cdp.events.splice(0)) {
      if (ev.method === 'Runtime.consoleAPICalled') {
        const text = ev.params.args.map((a) => a.value ?? a.description ?? a.type).join(' ');
        if (ev.params.type === 'error') consoleErrors.push(text);
        else if (ev.params.type === 'warning') consoleWarns.push(text);
      } else if (ev.method === 'Runtime.exceptionThrown') {
        pageErrors.push(ev.params.exceptionDetails?.exception?.description ?? 'unknown exception');
      } else if (ev.method === 'Log.entryAdded') {
        const e = ev.params.entry;
        if (e.level === 'error') consoleErrors.push(`${e.text} ${e.url ?? ''}`);
      }
    }
  };

  const evaluate = async (expression) => {
    // ⚠️ 加超时：CDP 连接一旦断掉（浏览器被杀 / 端口串台），await 会**永远不返回**，
    //    而 Node 在事件循环空掉时会以 code 0 静默退出 —— 后半段检查全部被跳过却"看起来成功"。
    //    这是最危险的一类假绿（实测踩过：移动端那一步之后整段消失、退出码还是 0）。
    const r = await Promise.race([
      cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }),
      new Promise((_, rej) => setTimeout(() => rej(new Error('CDP evaluate 超时 15s（连接可能已断）')), 15000)),
    ]);
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? 'evaluate failed');
    return r.result.value;
  };

  const setViewport = async (width, height, mobile = false) => {
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width,
      height,
      deviceScaleFactor: 1,
      mobile,
      screenWidth: width,
      screenHeight: height,
    });
  };

  const shot = async (name) => {
    const r = await cdp.send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(outDir, name), Buffer.from(r.data, 'base64'));
    console.log(`  shot  ${name}`);
  };

  const shotElement = async (name, selector) => {
    const ok = await evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 12);
      return true;
    })()`);
    if (!ok) {
      notes.push(`截图 ${name} 跳过：找不到 ${selector}`);
      return;
    }
    await sleep(450);
    await shot(name);
  };

  /** 真鼠标点击（CDP 输入域 ⇒ 浏览器会派发 pointerdown/mouseup/click）。 */
  const realClick = async (selector, index = 0) => {
    const box = await evaluate(`(() => {
      const el = document.querySelectorAll(${JSON.stringify(selector)})[${index}];
      if (!el) return null;
      el.scrollIntoView({ block: 'center', behavior: 'instant' });
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
    })()`);
    if (!box) return false;
    for (const type of ['mousePressed', 'mouseReleased']) {
      await cdp.send('Input.dispatchMouseEvent', {
        type,
        x: box.x,
        y: box.y,
        button: 'left',
        clickCount: 1,
        pointerType: 'mouse',
      });
      await sleep(40);
    }
    await sleep(160);
    return true;
  };

  // 拿到 target 后必须校验它就是我们导航的那个页面：否则端口串台时会对着别的页面断言。
  await cdp.send('Page.navigate', { url: 'about:blank' });
  const wantPath = new URL(TARGET_URL).pathname;
  const localPath = new URL(target.url).pathname;
  if (localPath !== 'blank' && localPath !== wantPath && target.url !== 'about:blank') {
    throw new Error(`CDP 目标页面不是我们启动的那个（target=${target.url}，期望 path=${wantPath}）——可能端口串台`);
  }

  console.log(`\nbrowser-check: ${TARGET_URL}`);
  console.log(`chrome: ${chromePath}\n`);

  /* ================= 桌面 ================= */
  await setViewport(1440, 1000);
  await cdp.send('Page.navigate', { url: TARGET_URL });
  await sleep(2800);
  // ⚠️ 页面开了 scroll-behavior: smooth；不平滑化的话 scrollIntoView 还在动画中
  //    就去取 getBoundingClientRect，点到的坐标是旧的 ⇒ 点击"丢失"（实测踩过）。
  await evaluate("document.documentElement.style.scrollBehavior='auto'");
  drain();

  const title = await evaluate('document.title');
  const h1 = await evaluate("document.querySelector('h1')?.textContent?.trim().slice(0,40) ?? ''");
  console.log(`  title : ${title}`);
  console.log(`  h1    : ${h1}`);
  if (!h1) problems.push('页面没有 h1');
  if (!/拼图/.test(title)) problems.push(`<title> 不含项目名：${title}`);

  const rootKids = await evaluate("document.getElementById('root')?.childElementCount ?? -1");
  if (rootKids <= 0) problems.push('React 没有挂载：#root 下没有子元素');

  /* ---- ② 字体真的加载了吗 ---- */
  await evaluate('document.fonts.ready');
  const fonts = await evaluate(`({
    inter: document.fonts.check('16px "Inter Variable"'),
    mono: document.fonts.check('12px "JetBrains Mono Variable"'),
    loaded: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family + ' ' + f.weight).slice(0, 6)
  })`);
  console.log(`  字体: Inter=${fonts.inter} Mono=${fonts.mono}`);
  notes.push(`已加载字体：${JSON.stringify(fonts.loaded)}`);
  if (!fonts.inter) problems.push('Inter Variable 没有加载（字体回落了）');
  if (!fonts.mono) problems.push('JetBrains Mono Variable 没有加载（字体回落了）');

  /* ---- ③ 演示 GIF 真的解码了吗 ---- */
  const gif = await evaluate(`(() => {
    const img = document.querySelector('img.demo__gif');
    if (!img) return null;
    return { ok: img.complete && img.naturalWidth > 0, nw: img.naturalWidth, nh: img.naturalHeight, src: img.getAttribute('src') };
  })()`);
  console.log(`  GIF : ${JSON.stringify(gif)}`);
  if (!gif) problems.push('首屏找不到演示 GIF（img.demo__gif）');
  else if (!gif.ok) problems.push(`演示 GIF 没有解码出来（404 或损坏）：${gif.src}`);
  else notes.push(`演示 GIF 已解码：${gif.nw}×${gif.nh}`);

  await shot('01-desktop-hero.png');
  drain();

  /* ---- ④ 主题切换：**两套主题都要量一遍** ---- */
  // 断言三件事：切换真的改属性、真的写 localStorage、两套主题下正文都过 AA。
  // 踩过的坑：先一次性把所有对比度量完，而那时主题停在被点到的那一套上，
  // 于是"深色下的正文"被拿白底去算 —— 全是假不合格。
  const readTheme = async () =>
    evaluate(
      "JSON.stringify({t: document.documentElement.getAttribute('data-theme'), bg: getComputedStyle(document.documentElement).backgroundColor})",
    );

  const contrastOf = async () =>
    evaluate(`(() => {
      const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
        const p = m[1].split(',').map(v => parseFloat(v.trim())); return { r:p[0], g:p[1], b:p[2], a:p.length>3?p[3]:1 }; };
      const lum = ({r,g,b}) => { const f=(v)=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}; return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
      const ratio = (fg,bg) => { const l1=lum(fg),l2=lum(bg),hi=Math.max(l1,l2),lo=Math.min(l1,l2); return (hi+0.05)/(lo+0.05); };
      /* ⚠️ 必须一直走到 documentElement：本站背景设在 html 上（Safari 会把 body 背景提升为
         画布背景、深色下露底），漏掉 html 就永远按白底算 ⇒ 深色主题报一堆假的不合格。 */
      const effBg = (el) => { let n=el; while (n) { const c=parse(getComputedStyle(n).backgroundColor); if (c&&c.a>0.5) return c; n=n.parentElement; } return {r:255,g:255,b:255,a:1}; };
      return ['.hero__lede','.sec__lede','.note','.figcap','.chart__cap','.mod__job','.mod-detail__v','.case-list__t','.case-list__err','.limits-item__d','.flow__step-d','.demo__step-d','.spec__v','.docs-item__d','.step__v','.pipe__sub']
        .map(sel => { const el=document.querySelector(sel); if(!el) return null; const cs=getComputedStyle(el);
          const fg = parse(cs.color); const bg=effBg(el);
          return fg ? { sel, ratio: Number(ratio(fg,bg).toFixed(2)), size: cs.fontSize } : null; })
        .filter(Boolean);
    })()`);

  const setTheme = async (target) => {
    for (let i = 0; i < 4; i += 1) {
      const cur = await evaluate("document.documentElement.getAttribute('data-theme')");
      if ((target === 'system' && !cur) || cur === target) return true;
      await realClick('.icon-btn');
      await sleep(320);
    }
    return false;
  };

  const themeClicked = await realClick('.icon-btn');
  if (!themeClicked) problems.push('找不到主题切换按钮');
  else {
    const stored = await evaluate("localStorage.getItem('dld-theme')");
    console.log(`  主题切换后: ${await readTheme()} (stored=${stored})`);
    if (!stored) problems.push('主题切换没有写进 localStorage（刷新后会丢）');
    await shot('02-desktop-theme-toggled.png');
  }

  for (const theme of ['light', 'dark']) {
    const okTheme = await setTheme(theme);
    if (!okTheme) {
      problems.push(`切不到 ${theme} 主题（按钮三态循环失效）`);
      continue;
    }
    const t = JSON.parse(await readTheme());
    const rows = await contrastOf();
    const min = rows.reduce((m, c) => Math.min(m, c.ratio), Infinity);
    console.log(`  主题=${theme}: html背景=${t.bg} · 对比度最低 ${min}:1（抽样 ${rows.length} 处）`);
    // ⚠️ 必须钉住抽样条数：选择器一旦改名，rows 会变空 ⇒ reduce 初值 Infinity ⇒
    //    "每一条都 ≥4.5"**静默成立**。这是检查脚本最典型的一类假通过。
    if (rows.length < 12) {
      problems.push(
        `[${theme}] 对比度抽样只拿到 ${rows.length} 处（预期 ≥12）—— 可能是选择器改名导致检查空转，此时"全部合格"没有意义`,
      );
    }
    for (const c of rows) {
      if (c.ratio < 4.5) problems.push(`[${theme}] 对比度不足：${c.sel} = ${c.ratio}:1`);
    }
    notes.push(`对比度（${theme}）：最低 ${min}:1，抽样 ${rows.length} 处，不合格 ${rows.filter((r) => r.ratio < 4.5).length} 处`);
    await shot(theme === 'light' ? '02b-desktop-light.png' : '02c-desktop-dark.png');
  }
  await setTheme('system');
  await sleep(300);

  /* ---- ⑤ 时序播放器 ---- */
  await shotElement('03-desktop-flow.png', '#flow');
  const flowInit = await evaluate(`({
    scenarios: document.querySelectorAll('.flow__scenario').length,
    nodes: document.querySelectorAll('.pipe__node').length,
    buses: document.querySelectorAll('.pipe__arrow--busy').length,
    stepText: (document.querySelector('.flow__step-t')?.textContent ?? '').trim().slice(0, 30),
    counter: (document.querySelector('.flow__time')?.textContent ?? '').trim()
  })`);
  console.log(`  播放器初始: ${JSON.stringify(flowInit)}`);
  if (flowInit.scenarios < 4) problems.push(`时序场景应有 4 个，实测 ${flowInit.scenarios}`);
  if (flowInit.nodes < 5) problems.push(`流水线节点太少（${flowInit.nodes}），图可能没渲染`);

  // 切换到另一个场景（"旋转的几何"）
  const switched = await realClick('.flow__scenario', 3);
  await sleep(500);
  const flowSwitched = await evaluate(`({
    stepText: (document.querySelector('.flow__step-t')?.textContent ?? '').trim().slice(0, 30),
    nodes: document.querySelectorAll('.pipe__node').length,
    pressed: [...document.querySelectorAll('.flow__scenario')].findIndex(b => b.getAttribute('aria-pressed') === 'true')
  })`);
  console.log(`  切到场景 3: ${JSON.stringify(flowSwitched)}`);
  if (!switched) problems.push('点不动场景按钮');
  if (flowSwitched.pressed !== 3) problems.push('点了第 4 个场景但 aria-pressed 没落上去');

  // 播放：点播放后等一会儿，步骤应当推进
  await realClick('.flow__play', 0);
  const beforePlay = await evaluate("(document.querySelector('.flow__time')?.textContent ?? '').trim()");
  await sleep(2200);
  const afterPlay = await evaluate("(document.querySelector('.flow__time')?.textContent ?? '').trim()");
  console.log(`  播放: ${beforePlay} -> ${afterPlay}`);
  if (beforePlay === afterPlay) problems.push('点了播放但时间轴没有推进（播放器没在动）');
  await shotElement('04-desktop-flow-playing.png', '#flow');
  drain();

  // 仪表（点阵）在这一场景下应当有点亮的格子
  const lit = await evaluate(
    "document.querySelectorAll('#flow .matrix__cell--red, #flow .matrix__cell--green, #flow .matrix__cell--yellow').length",
  );
  console.log(`  仪表点亮格数: ${lit}`);
  if (!(lit > 0)) problems.push('播放器右侧的"仪表"点阵没有点亮的格子（应当是规则模型实算的画面）');

  /* ---- ⑥ 模块地图 + 案例切换器 ---- */
  await shotElement('05-desktop-modules.png', '#arch');
  const modBefore = await evaluate("(document.querySelector('.mod-detail .chart__title')?.textContent ?? '').trim()");
  await realClick('.mod', 0);
  const modAfter = await evaluate("(document.querySelector('.mod-detail .chart__title')?.textContent ?? '').trim()");
  console.log(`  模块地图: "${modBefore}" -> "${modAfter}"`);
  if (modBefore === modAfter) problems.push('点了模块卡片但详情没换');

  await shotElement('06-desktop-cases.png', '#cases');
  const caseBefore = await evaluate("(document.querySelector('.case-detail__title')?.textContent ?? '').trim().slice(0,24)");
  await realClick('.case-list__item', 3);
  const caseAfter = await evaluate("(document.querySelector('.case-detail__title')?.textContent ?? '').trim().slice(0,24)");
  console.log(`  案例切换: "${caseBefore}" -> "${caseAfter}"`);
  if (caseBefore === caseAfter) problems.push('点了案例但详情没换');

  /* ---- ⑦ 图表画出来了吗 ---- */
  const charts = await evaluate(`({
    charts: document.querySelectorAll('#evidence .chart').length,
    bars: document.querySelectorAll('#evidence .chart__bar').length,
    lines: document.querySelectorAll('#evidence .chart__line').length,
    dots: document.querySelectorAll('#evidence .chart__dot').length,
    utilRows: document.querySelectorAll('#evidence .bar-row').length,
    figures: document.querySelectorAll('#evidence .figbox img').length,
    /* 注意：complete && naturalWidth===0 会漏掉"还没开始加载"的懒加载图；
       更要紧的是素材缺失时 Figure 根本不渲染 img（改渲染 .figbox--missing 占位），
       所以"图全挂了"时 brokenFigures 恒为 0，必须同时断言 img 数量与占位数量。 */
    brokenFigures: [...document.querySelectorAll('figure img')].filter(i => !i.complete || i.naturalWidth === 0).length,
    missingPlates: document.querySelectorAll('.figbox--missing').length
  })`);
  console.log(`  图表: ${JSON.stringify(charts)}`);
  if (charts.charts < 4) problems.push(`证据区应有 ≥4 张图，实测 ${charts.charts}`);
  if (charts.bars < 12) problems.push(`条形图的条数偏少（${charts.bars}）`);
  if (charts.lines < 2) problems.push('演进折线没画出来');
  if (charts.utilRows < 4) problems.push('利用率条不是 4 行');
  if (charts.brokenFigures > 0) problems.push(`有 ${charts.brokenFigures} 张图没加载出来（404 或未解码）`);
  if (charts.figures < 5) problems.push(`图素材只有 ${charts.figures} 张（预期 ≥5）—— 图没渲染或素材没同步`);
  if (charts.missingPlates > 0) problems.push(`有 ${charts.missingPlates} 个"素材缺失"占位框——sync-figures 没跑或源文件被删`);

  /* ---- ⑧ 窄屏 ---- */
  for (const [name, w, h] of [
    ['07-narrow-390.png', 390, 900],
    ['08-narrow-320.png', 320, 760],
  ]) {
    await setViewport(w, h, false);
    await evaluate('window.scrollTo(0,0)');
    await sleep(900);
    const ov = await evaluate(`(() => {
      const clipped = (el) => {
        let n = el.parentElement;
        while (n && n !== document.body) {
          if (getComputedStyle(n).overflowX !== 'visible') return true;
          n = n.parentElement;
        }
        return false;
      };
      return {
        doc: document.documentElement.scrollWidth,
        win: document.documentElement.clientWidth,
        wide: [...document.querySelectorAll('body *')]
          .filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !clipped(e))
          .slice(0, 8)
          .map(e => e.tagName.toLowerCase() + '.' + String(e.className || '').split(' ').filter(Boolean).slice(0,2).join('.'))
      };
    })()`);
    console.log(`  ${w}px: scrollWidth=${ov.doc} innerWidth=${ov.win} 超宽=${JSON.stringify(ov.wide)}`);
    if (ov.doc > ov.win + 1) {
      problems.push(`${w}px 出现横向溢出：scrollWidth=${ov.doc} > innerWidth=${ov.win}；超宽元素 ${JSON.stringify(ov.wide)}`);
    }
    const small = await evaluate(
      `[...document.querySelectorAll('.btn, .flow__play, .flow__scenario, .mod, .case-list__item, .keypad__key')]
         .map(b => ({ t: b.textContent.trim().slice(0,10), h: Math.round(b.getBoundingClientRect().height) }))
         .filter(x => x.h > 0 && x.h < 32)`,
    );
    if (small.length) problems.push(`${w}px 下有过小的可点元素（<32px）：${JSON.stringify(small.slice(0, 6))}`);
    await shot(name);
  }

  // 真移动端仿真（只为出一张"手机上长什么样"的图）
  await setViewport(390, 844, true);
  await evaluate('window.scrollTo(0,0)');
  await sleep(700);
  await shot('09-mobile-hero.png');
  await shotElement('10-mobile-flow.png', '#flow');

  console.log('  …⑨ 链接与锚点');
  /* ---- ⑨ 链接与锚点 ---- */
  const links = await evaluate("[...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))");
  const ALLOWED_PREFIXES = [
    '#',
    // Figure 的"点开看原图"用的是站内相对路径（/dld/figures/...），同源静态资源
    '/',
    'https://github.com/tortrixx/dld',
    'https://tortrixx.github.io/dld',
    'https://app.diagrams.net',
    'data:',
  ];
  const bad = links.filter((h) => !ALLOWED_PREFIXES.some((p) => h.startsWith(p)));
  if (bad.length) problems.push(`出现无法分类的链接：${JSON.stringify([...new Set(bad)].slice(0, 8))}`);
  const deadAnchors = await evaluate(
    `[...document.querySelectorAll('a[href^="#"]')].map(a => a.getAttribute('href')).filter(h => h.length > 1 && !document.querySelector(h))`,
  );
  if (deadAnchors.length) problems.push(`页内锚点指向不存在的元素：${JSON.stringify(deadAnchors)}`);
  notes.push(
    `链接：总数 ${links.length}，仓库链接 ${links.filter((h) => h.startsWith('https://github.com')).length}，页内锚点 ${links.filter((h) => h.startsWith('#')).length}，无法分类 ${bad.length}`,
  );

  console.log('  …⑩ 对比度 + 文本卫生');
  /* ---- ⑩ 对比度 + 文本卫生 ---- */
  const contrast = await evaluate(`(() => {
    const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null;
      const p = m[1].split(',').map(v => parseFloat(v.trim())); return { r:p[0], g:p[1], b:p[2], a:p.length>3?p[3]:1 }; };
    const lum = ({r,g,b}) => { const f=(v)=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}; return 0.2126*f(r)+0.7152*f(g)+0.0722*f(b); };
    const ratio = (fg,bg) => { const l1=lum(fg),l2=lum(bg),hi=Math.max(l1,l2),lo=Math.min(l1,l2); return (hi+0.05)/(lo+0.05); };
    /* ⚠️ 必须一直走到 documentElement：本站背景设在 html 上（Safari 会把 body 背景提升为
       画布背景，深色下露底），漏掉 html 就永远按白底算 ⇒ 深色主题会报一堆假的不合格。 */
    const effBg = (el) => { let n=el; while (n) { const c=parse(getComputedStyle(n).backgroundColor); if (c&&c.a>0.5) return c; n=n.parentElement; } return {r:255,g:255,b:255,a:1}; };
    return ['.hero__lede','.sec__lede','.note','.figcap','.chart__cap','.mod__job','.case-list__t','.limits-item__d','.flow__step-d','.demo__step-d','.spec__v','.docs-item__d']
      .map(sel => { const el=document.querySelector(sel); if(!el) return null; const fg=parse(getComputedStyle(el).color); const bg=effBg(el);
        return fg ? { sel, ratio: Number(ratio(fg,bg).toFixed(2)), size: getComputedStyle(el).fontSize } : null; })
      .filter(Boolean);
  })()`);
  for (const c of contrast) {
    notes.push(`对比度 ${c.sel} = ${c.ratio}:1 (${c.size})`);
    if (c.ratio < 4.5) problems.push(`对比度不足：${c.sel} = ${c.ratio}:1`);
  }

  const textHygiene = await evaluate(`(() => {
    const bad = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const t = n.nodeValue || '';
      if (/\\*\\*[^*]+\\*\\*/.test(t)) { bad.push(t.trim().slice(0, 60)); if (bad.length >= 5) break; }
    }
    return bad;
  })()`);
  if (textHygiene.length) problems.push(`页面正文里出现裸露的 Markdown 记号：${JSON.stringify(textHygiene)}`);
  else notes.push('文本卫生：正文里没有裸露的 ** 记号');

  // ⚠️ 这一段必须在 cdp.close()/chrome.kill() **之前**跑：
  //    放在后面会让 await 永远不返回，而 Node 在事件循环空掉时
  //    以 code 0 静默退出 —— 后半段检查全被跳过、退出码却是 0（最危险的假绿，实测踩过）。

  /* ---- ⑪ prefers-reduced-motion 实测 ----
     这是最容易"以为降级了、其实丢了信息"的地方：GIF 的降级、告急幽灵的绿色
     （靠闪烁传达"该拼哪几格"）、脉冲点……都必须真的检查。 */
  await cdp.send('Emulation.setEmulatedMedia', {
    features: [{ name: 'prefers-reduced-motion', value: 'reduce' }],
  });
  await evaluate('window.scrollTo(0,0)');
  await sleep(900);
  const rm = await evaluate(`(() => {
    const fade = document.querySelector('.fade');
    const fadeStyle = fade ? getComputedStyle(fade) : null;
    const pulse = document.querySelector('.pipe__pulse');
    const ghost = document.querySelector('.matrix__cell--ghost');
    return {
      fadeOpacity: fadeStyle ? Number(fadeStyle.opacity) : null,
      fadeAnimation: fadeStyle ? fadeStyle.animationName : null,
      scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
      pulseDisplay: pulse ? getComputedStyle(pulse).display : 'absent',
      ghost: ghost ? { bg: getComputedStyle(ghost).backgroundColor, anim: getComputedStyle(ghost).animationName } : 'absent',
    };
  })()`);
  console.log(`  reduced-motion: ${JSON.stringify(rm)}`);
  // 入场元素在"减少动效"下必须是**可见**的（早先只压 duration 不归零 delay，
  // `.fade` 用了 fill-mode:both ⇒ 最多 0.56 s 内容不可见）
  if (rm.fadeOpacity !== null && rm.fadeOpacity < 0.99) {
    problems.push(`reduced-motion 下 .fade 的 opacity=${rm.fadeOpacity}（应当立即可见；很可能是 animation-delay 没归零）`);
  }
  if (rm.scrollBehavior === 'smooth') problems.push('reduced-motion 下 scroll-behavior 仍是 smooth（平滑滚动也是动效）');
  if (rm.pulseDisplay !== 'none' && rm.pulseDisplay !== 'absent') {
    problems.push('reduced-motion 下脉冲点没有隐藏（会静止停在箭头左端，看着像坏了）');
  }
  await shot('11-reduced-motion.png');
  await cdp.send('Emulation.setEmulatedMedia', { features: [] });

  console.log('  …汇总');
  /* ---- 汇总 ---- */
  drain();
  await sleep(200);
  drain();
  if (consoleErrors.length) problems.push(`控制台报错 ${consoleErrors.length} 条：${consoleErrors.slice(0, 5).join(' | ')}`);
  for (const w of consoleWarns) notes.push(`控制台警告：${w}`);

  cleanup();

  console.log('\n--- 记录 ---');
  for (const n of notes) console.log(`  · ${n}`);

  if (pageErrors.length) {
    console.log('\n--- 未捕获异常 ---');
    for (const e of pageErrors.slice(0, 5)) console.log(`  · ${String(e).split('\n')[0]}`);
    problems.push(`未捕获异常 ${pageErrors.length} 条`);
  }

  if (problems.length) {
    console.log('\n--- ❌ 问题 ---');
    for (const p of problems) console.log(`  · ${p}`);
    process.exitCode = 1;
  } else {
    console.log('\n✅ 浏览器检查通过：字体已加载、GIF 已解码、主题/播放器/图表/切换器都实测生效、');
    console.log('   无控制台报错、无横向溢出、锚点全部命中、对比度达标。');
    console.log(`   截图目录：${outDir}`);
  }
}

main().catch((err) => {
  console.error('browser-check 失败：', err);
  cleanup();
  process.exit(1);
});
