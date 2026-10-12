#!/usr/bin/env node
/**
 * browser-check.mjs —— 用真实浏览器打开页面做检查与截图
 *
 * 为什么要有这个脚本（而不是"读代码觉得没问题"）：
 *   · 静态检查看不出布局溢出、对比度、焦点态、闪烁相位、控制台报错；
 *   · 这个项目的纪律是"能实测就别靠推断"，前端也一样。
 *
 * 实现方式：**零依赖**。用 CDP（Chrome DevTools Protocol）直接驱动无头 Chrome/Edge，
 * 靠 Node 22+ 内置的全局 WebSocket 通信 —— 不装 puppeteer / playwright，
 * 不给站点引入任何运行时或开发依赖。
 *
 * 它做五件事：
 *   1. 收集控制台报错与未捕获异常（有报错就返回非 0，绝不"看着没事就放过"）；
 *   2. 走一遍真实交互：等自检 → 按【开始】→ 等预览结束 → **点中零片** → 旋转 → 移动；
 *      点击用 CDP 的 Input.dispatchMouseEvent（真的鼠标事件），不是 `el.click()`；
 *   3. 桌面 / 390 / 320 三种宽度检查横向溢出，并统计每个点阵面板的点亮格数；
 *   4. 数据自检：关灯态（SW7=0）必须整屏熄灭；幽灵在 >10 s 时不得出现；
 *   5. 抓图（视口截图，避免 clip 坐标算错），输出到 site/.shots/（已 gitignore）。
 *
 * ⚠️ 两个踩过的坑，写在这里免得下次再犯：
 *   · **溢出检测不要用 `mobile: true`**：Chrome 的移动端仿真会在内容超宽时把
 *     layout viewport 一起撑大（shrink-to-fit），于是 scrollWidth == innerWidth，
 *     溢出被"仿真"吃掉了 —— 看起来永远没问题。所以量溢出时用 `mobile: false`。
 *   · **clip 截图不可靠**（截到空白），所以改成"滚动到目标 + 视口截图"。
 *
 * 用法：
 *   node scripts/browser-check.mjs [url]     # 默认 http://localhost:4173/dld/
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
const PORT = 9333 + (Number(process.env.CDP_PORT_OFFSET ?? 0) || 0);

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
const problems = [];
const notes = [];

async function pageTarget() {
  for (let i = 0; i < 80; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await res.json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
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
        // 404 之类资源错误也算错，但要排除"故意探测"的 favicon
        if (e.level === 'error') consoleErrors.push(`${e.text} ${e.url ?? ''}`);
      }
    }
  };

  const evaluate = async (expression) => {
    const r = await cdp.send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
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

  /** 滚动到元素并把**视口**截下来（不做 clip 运算，避免截到空白）。 */
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
      el.scrollIntoView({ block: 'center' });
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
    await sleep(120);
    return true;
  };

  const clickButtonByText = async (scope, text) => {
    const idx = await evaluate(`[...document.querySelectorAll(${JSON.stringify(scope)})].findIndex(n => n.textContent.includes(${JSON.stringify(text)}))`);
    if (idx < 0) return false;
    return realClick(scope, idx);
  };

  console.log(`\nbrowser-check: ${TARGET_URL}`);
  console.log(`chrome: ${chromePath}\n`);

  /* ================= 桌面 1440×1000 ================= */
  await setViewport(1440, 1000);
  await cdp.send('Page.navigate', { url: TARGET_URL });
  await sleep(2600);
  drain();

  const title = await evaluate('document.title');
  const h1 = await evaluate("document.querySelector('h1')?.textContent?.trim().slice(0,40) ?? ''");
  console.log(`  title : ${title}`);
  console.log(`  h1    : ${h1}`);
  if (!h1) problems.push('页面没有 h1');
  if (!/拼图/.test(title)) problems.push(`<title> 不含项目名：${title}`);

  const rootKids = await evaluate("document.getElementById('root')?.childElementCount ?? -1");
  if (rootKids <= 0) problems.push('React 没有挂载：#root 下没有子元素');

  // 每个点阵面板分别统计：首屏那张是静态散落帧（12 格），模拟器那张随状态变化
  const matrixStats = await evaluate(`[...document.querySelectorAll('.matrix')].map(m => ({
    lit: m.querySelectorAll('.matrix__cell--red, .matrix__cell--green, .matrix__cell--yellow').length,
    cells: m.querySelectorAll('.matrix__cell').length
  }))`);
  console.log(`  点阵面板: ${JSON.stringify(matrixStats)}`);
  for (const m of matrixStats) if (m.cells !== 64) problems.push(`点阵格数不是 64：${m.cells}`);
  if (matrixStats[0] && matrixStats[0].lit !== 12) {
    problems.push(`首屏第 1 关散落帧的点亮格数应为 12（3+6+3），实测 ${matrixStats[0].lit}`);
  }

  await shot('01-desktop-hero.png');
  drain();

  /* ================= 自检 → 待机 ================= */
  await sleep(2200);
  const idlePhase = await evaluate("(document.querySelector('.sim__status-v')?.textContent ?? '').trim()");
  console.log(`  自检后: ${idlePhase}`);
  if (!/S_IDLE/.test(idlePhase)) problems.push(`自检 2 s 后应进入待机，实测 ${idlePhase}`);
  const idleLit = await evaluate("document.querySelectorAll('.matrix')[1]?.querySelectorAll('.matrix__cell--red, .matrix__cell--green, .matrix__cell--yellow').length ?? -1");
  if (idleLit !== 0) problems.push(`待机时点阵应全灭（B2），实测点亮 ${idleLit} 格`);
  const idleSeg = await evaluate("(document.querySelectorAll('.sim__status-v')[7]?.textContent ?? '').trim()");
  console.log(`  待机数码管: ${idleSeg}`);
  notes.push(`待机读数：${idleSeg}`);

  await shotElement('02-desktop-idle.png', '#sim');
  drain();

  /* ================= SW7 关掉：所有显示器件不显示 ================= */
  const swOk = await realClick('.toggle input');
  await sleep(500);
  const swOff = await evaluate(`({
    lit: document.querySelectorAll('.matrix')[1]?.querySelectorAll('.matrix__cell--red, .matrix__cell--green, .matrix__cell--yellow').length ?? -1,
    seg: (document.querySelectorAll('.sim__status-v')[7]?.textContent ?? '').trim(),
    feedback: (document.querySelector('.sim__feedback')?.textContent ?? '').trim()
  })`);
  console.log(`  SW7=0: ${JSON.stringify(swOff)}`);
  if (!swOk) problems.push('找不到 SW7 开关');
  if (swOff.lit !== 0) problems.push(`SW7=0 时点阵应全灭（B1），实测 ${swOff.lit} 格`);
  if (!/全灭/.test(swOff.seg)) problems.push(`SW7=0 时数码管读数应显示"全灭"，实测 "${swOff.seg}"`);
  await shotElement('03-desktop-sw7-off.png', '#sim');
  await realClick('.toggle input'); // 合上 → 重新上电自检
  await sleep(2600);
  drain();

  /* ================= 按【开始】→ 预览 → 对局 ================= */
  const started = await clickButtonByText('.sim__actions button', '开始');
  if (!started) problems.push('找不到【开始】按钮');
  await sleep(800);
  const previewPhase = await evaluate("(document.querySelector('.sim__status-v')?.textContent ?? '').trim()");
  console.log(`  预览: ${previewPhase}`);
  if (!/S_PREVIEW/.test(previewPhase)) problems.push(`按【开始】后应进入预览，实测 ${previewPhase}`);

  await sleep(5200);
  const playPhase = await evaluate("(document.querySelector('.sim__status-v')?.textContent ?? '').trim()");
  const playStats = await evaluate(`({
    lit: document.querySelectorAll('.matrix')[1]?.querySelectorAll('.matrix__cell--red, .matrix__cell--green, .matrix__cell--yellow').length ?? -1,
    ghost: (document.querySelectorAll('.sim__status-v')[6]?.textContent ?? '').trim(),
    progress: (document.querySelectorAll('.sim__status-v')[5]?.textContent ?? '').trim()
  })`);
  console.log(`  对局: ${playPhase} · ${JSON.stringify(playStats)}`);
  if (!/S_PLAYING/.test(playPhase)) problems.push(`预览 5 s 后应进入对局，实测 ${playPhase}`);
  if (playStats.lit !== 12) problems.push(`第 1 关对局点亮格数应为 12，实测 ${playStats.lit}`);
  if (!/未显示/.test(playStats.ghost)) problems.push(`倒计时 30 s 时不应显示告急幽灵，实测 "${playStats.ghost}"`);
  await shotElement('04-desktop-playing.png', '#sim');
  drain();

  /* ================= 点中零片（真鼠标）→ 旋转 → 移动 ================= */
  const tapOk = await evaluate(`(() => {
    const cells = [...document.querySelectorAll('.matrix')][1].querySelectorAll('.matrix__cell--red');
    if (!cells.length) return null;
    const r = cells[0].getBoundingClientRect();
    return { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
  })()`);
  if (!tapOk) {
    problems.push('对局里找不到可点的红色零片');
  } else {
    for (const type of ['mousePressed', 'mouseReleased']) {
      await cdp.send('Input.dispatchMouseEvent', { type, x: tapOk.x, y: tapOk.y, button: 'left', clickCount: 1, pointerType: 'mouse' });
      await sleep(30);
    }
    await sleep(300);
    const selText = await evaluate("(document.querySelectorAll('.sim__status-v')[4]?.textContent ?? '').trim()");
    const greenCells = await evaluate("document.querySelectorAll('.matrix')[1]?.querySelectorAll('.matrix__cell--green, .matrix__cell--yellow').length ?? 0");
    console.log(`  点选后: ${selText}（绿色格数 ${greenCells}）`);
    if (/还没选/.test(selText)) problems.push('点一下零片之后仍然没有选中（点选交互失效）');
    if (greenCells === 0) problems.push('选中零片后点阵里没有出现绿色格（B6：选中的零片变绿）');
  }

  // 旋转：记录朝向再旋转，看日志是否变化
  const beforeRot = await evaluate("(document.querySelector('.sim__feedback')?.textContent ?? '').trim()");
  const rotOk = await clickButtonByText('.sim__actions button', '旋转');
  const afterRot = await evaluate("(document.querySelector('.sim__feedback')?.textContent ?? '').trim()");
  console.log(`  旋转: ${rotOk ? '已按下' : '失败'} · 反馈 "${afterRot.slice(0, 40)}"`);
  if (!rotOk) problems.push('找不到【旋转】按钮');
  if (beforeRot === afterRot) problems.push('按【旋转】之后反馈没有变化（旋转交互可能没生效）');

  // 移动：连按右键，看状态行的锚点/日志是否变化
  const beforeMove = await evaluate("(document.querySelector('.sim__feedback')?.textContent ?? '').trim()");
  const moveOk = await clickButtonByText('.sim__actions button', '选择');
  await sleep(150);
  await clickButtonByText('.dpad__btn', '右');
  await sleep(200);
  const afterMove = await evaluate("(document.querySelector('.sim__feedback')?.textContent ?? '').trim()");
  console.log(`  移动: 选择=${moveOk} · 反馈 "${afterMove.slice(0, 40)}"`);
  if (beforeMove === afterMove) problems.push('按方向键之后反馈没有变化（移动交互可能没生效）');

  await shotElement('05-desktop-interaction.png', '#sim');
  drain();

  /* ================= 结算画面：三块直接确认 → 判负 ================= */
  await clickButtonByText('.sim__actions button', '开始');
  await sleep(6200);
  for (let i = 0; i < 3; i += 1) {
    await clickButtonByText('.sim__actions button', '选择');
    await sleep(120);
    await clickButtonByText('.dpad__btn', '确认');
    await sleep(200);
  }
  const endPhase = await evaluate("(document.querySelector('.sim__status-v')?.textContent ?? '').trim()");
  const endSeg = await evaluate("(document.querySelectorAll('.sim__status-v')[7]?.textContent ?? '').trim()");
  console.log(`  三块直接确认: ${endPhase} · 数码管 ${endSeg}`);
  if (!/S_FAIL/.test(endPhase)) problems.push(`三块直接确认（画面不对）应判负，实测 ${endPhase}`);
  if (!/FAIL/.test(endSeg)) problems.push(`失败时数码管 DISP7..4 应为 FAIL，实测 "${endSeg}"`);
  await shotElement('06-desktop-fail.png', '#sim');
  drain();

  /* ================= 链接与锚点 ================= */
  const links = await evaluate("[...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))");
  // 允许三类链接：页内锚点、本仓库的 GitHub 链接、以及**本站自己的线上地址**。
  // 其他一律报出来 —— 这条检查的目的是抓"写错的/意外的链接"，不是禁掉自有域名；
  // 新增任何一类外链时都要在这里显式登记，否则会被挡下（这是有意的）。
  const ALLOWED_PREFIXES = ['#', 'https://github.com/tortrixx/dld', 'https://tortrixx.github.io/dld', 'data:'];
  const bad = links.filter((h) => !ALLOWED_PREFIXES.some((p) => h.startsWith(p)));
  if (bad.length) problems.push(`出现无法分类的链接：${JSON.stringify([...new Set(bad)].slice(0, 8))}`);
  const deadAnchors = await evaluate(
    `[...document.querySelectorAll('a[href^="#"]')].map(a => a.getAttribute('href')).filter(h => h.length > 1 && !document.querySelector(h))`,
  );
  if (deadAnchors.length) problems.push(`页内锚点指向不存在的元素：${JSON.stringify(deadAnchors)}`);
  const ghLinks = await evaluate(`[...document.querySelectorAll('a[href^="https://github.com"]')].length`);
  notes.push(
    `链接：总数 ${links.length}，仓库链接 ${ghLinks}，页内锚点 ${links.filter((h) => h.startsWith('#')).length}，无法分类 ${bad.length}`,
  );

  /* ================= 对比度抽样 ================= */
  // ⚠️ 背景色必须**沿祖先链找第一个不透明的背景**：直接拿 body 的颜色去量深色面板里的
  //    小字会得到假的不合格（第一版就这么报了一次假阳性）。
  const contrast = await evaluate(`(() => {
    const parse = (c) => {
      const m = c.match(/rgba?\\(([^)]+)\\)/);
      if (!m) return null;
      const p = m[1].split(',').map(v => parseFloat(v.trim()));
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    };
    const lum = ({r,g,b}) => {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
      return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b);
    };
    const ratio = (fg, bg) => { const l1 = lum(fg), l2 = lum(bg); const hi = Math.max(l1,l2), lo = Math.min(l1,l2); return (hi+0.05)/(lo+0.05); };
    const effBg = (el) => {
      let n = el;
      while (n && n !== document.documentElement) {
        const c = parse(getComputedStyle(n).backgroundColor);
        if (c && c.a > 0.5) return c;
        n = n.parentElement;
      }
      return { r: 255, g: 255, b: 255, a: 1 };
    };
    return ['.hero__lede', '.sec__lede', '.figure-cell__n', '.note', '.case__step dd', '.tbl td', '.limits__d', '.figcap', '.panel .figcap', '.sim__status-v', '.keypad__key b']
      .map(sel => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const fg = parse(getComputedStyle(el).color);
        const bg = effBg(el);
        if (!fg) return null;
        return { sel, ratio: Number(ratio(fg, bg).toFixed(2)), size: getComputedStyle(el).fontSize };
      })
      .filter(Boolean);
  })()`);
  for (const c of contrast) {
    notes.push(`对比度 ${c.sel} = ${c.ratio}:1 (${c.size})`);
    // 正文/说明文字要求 ≥ 4.5:1
    if (c.ratio < 4.5) problems.push(`对比度不足：${c.sel} = ${c.ratio}:1`);
  }

  /* ================= 窄屏：溢出与触控目标 ================= */
  for (const [name, w, h] of [
    ['07-narrow-390.png', 390, 900],
    ['08-narrow-320.png', 320, 760],
  ]) {
    // ⚠️ 这里刻意用 mobile:false：mobile:true 会把 layout viewport 撑大、吃掉溢出
    await setViewport(w, h, false);
    await evaluate("window.scrollTo(0,0)");
    await sleep(900);
    const ov = await evaluate(`(() => {
      // 只在**没有被内部滚动容器裁掉**的元素里找真凶：数据表故意在 .table-wrap 里
      // 横向滚动，它的子元素 getBoundingClientRect 一定超出视口，那是设计如此、不是溢出。
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
      `[...document.querySelectorAll('.dpad__btn, .sim__actions button, .keypad__key, .btn')]
         .map(b => ({ t: b.textContent.trim().slice(0,10), h: Math.round(b.getBoundingClientRect().height), w: Math.round(b.getBoundingClientRect().width) }))
         .filter(x => x.h > 0 && x.h < 44)`,
    );
    if (small.length) problems.push(`${w}px 下触控目标小于 44px：${JSON.stringify(small.slice(0, 6))}`);
    await shot(name);
  }

  // 真移动端仿真（只是为了出一张"手机上长什么样"的图）
  await setViewport(390, 844, true);
  await evaluate("window.scrollTo(0,0)");
  await sleep(700);
  await shot('09-mobile-emulated-hero.png');
  await shotElement('10-mobile-emulated-sim.png', '#sim');

  /* ================= 逐节截图（给视觉审查用） ================= */
  await setViewport(1440, 1050, false);
  for (const [name, sel] of [
    ['11-sec-arch-diagram.png', '#arch'],
    ['12-sec-evidence.png', '#evidence'],
    ['13-sec-cases.png', '#cases'],
    ['14-sec-docs.png', '#docs'],
    ['15-footer.png', 'footer.foot'],
  ]) {
    await shotElement(name, sel);
  }

  /* ================= 文本卫生：不得出现裸露的 Markdown 记号 ================= */
  // facts.ts 里的文案用 `**强调**` 标注关键约束，渲染时必须变成 <strong>。
  // 直接把字符串塞进 JSX 会把星号原样显示（第一版真发生过：案例卡上写着 `**保证存在…**`），
  // 所以这条断言是**永久**的，不是一次性的排查。
  const textHygiene = await evaluate(`(() => {
    const bad = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const t = n.nodeValue || '';
      if (/\\*\\*[^*]+\\*\\*/.test(t) || /\\[\\[[^\\]]+\\]\\]/.test(t)) {
        bad.push(t.trim().slice(0, 60));
        if (bad.length >= 5) break;
      }
    }
    return bad;
  })()`);
  if (textHygiene.length) {
    problems.push(`页面正文里出现裸露的 Markdown 记号（应渲染成 <strong>）：${JSON.stringify(textHygiene)}`);
  } else {
    notes.push('文本卫生：正文里没有裸露的 ** 或 [[ ]] 记号');
  }

  /* ================= 汇总 ================= */
  drain();
  await sleep(200);
  drain();

  if (consoleErrors.length) {
    problems.push(`控制台报错 ${consoleErrors.length} 条：${consoleErrors.slice(0, 5).join(' | ')}`);
  }
  for (const w of consoleWarns) notes.push(`控制台警告：${w}`);

  cdp.close();
  chrome.kill();
  try {
    rmSync(profile, { recursive: true, force: true });
  } catch {
    /* Windows 上偶发占用 */
  }

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
    console.log('\n✅ 浏览器检查通过：交互生效、无控制台报错、无横向溢出、锚点全部命中、触控目标 ≥44px。');
    console.log(`   截图目录：${outDir}`);
  }
}

main().catch((err) => {
  console.error('browser-check 失败：', err);
  chrome.kill();
  process.exit(1);
});
