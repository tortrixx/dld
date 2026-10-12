# `site/` —— 工程展示站

`tortrixx/dld`（MAX II EPM1270 上的 8×8 双色点阵拼图游戏）的静态工程项目站。
与硬件工程**完全隔离**：这里只是 `rtl/` / `sim/` / `quartus/` 的**读者**，
不参与、也不影响编译、仿真与烧录。

线上地址：<https://tortrixx.github.io/dld/>

---

## 1. 本地运行

```powershell
cd site
npm install
npm run dev        # http://localhost:5173/dld/
npm run test       # 规则模型的单元测试（45 条）
npm run build      # 产物在 site/dist/
npm run preview    # http://localhost:4173/dld/
npm run check      # 类型 + 测试 + 事实对账 + 构建（提交前跑这个）
```

> ⚠️ **dev / preview / build 三个命令都挂在 `/dld/` 子路径下**，这不是笔误。
> 早先写成"只有 build 用 `/dld/`、dev 用 `/`"，结果 `vite preview` 走
> `command === 'serve'` 分支拿到 `base = '/'`：它一边吐出一个引用 `/dld/assets/...`
> 的 `index.html`、一边在 `/` 下找文件，**构建产物的 JS/CSS 全部 404、页面白屏**。
> 现在三个命令共用同一个 base，好处不止是修 bug —— 本地开发走的就是线上那条子路径，
> 这类"子路径 404"从此在开发阶段就会暴露。

## 2. 部署到 GitHub Pages

仓库用的是**项目级** Pages，所以线上地址是 `https://tortrixx.github.io/dld/`，`base` 默认就是 `/dld/`。

1. 仓库 `Settings → Pages → Source` 选 **GitHub Actions**；
2. 推送到 `main` 后 `.github/workflows/pages.yml` 自动构建并发布 `site/`；
3. 换成**用户级** Pages 或改仓库名时**不用改代码**：workflow 里通过 `VITE_BASE` 传 base，
   本地也可以 `VITE_BASE=/ npm run build` 覆盖。

> **当前状态：已上线并通过线上实测（2026-10-12）。**
> workflow 每一步（安装依赖 → 单元测试 → **事实对账** → 构建 → 上传 → 发布）全部 `success`；
> `index.html` 的标题与资源路径均为 `/dld/` 前缀，CSS / JS / 图素材逐个抓到 200；
> **用 `scripts/browser-check.mjs` 对线上地址跑过完整检查**（字体已加载、GIF 已解码、
> 主题/播放器/图表/切换器都实测生效、无控制台报错、无横向溢出、对比度达标）；
> 线上 JS/CSS 的文件名哈希与本地验证过的构建**逐字节同源**。

## 3. 目录结构

```
site/
  index.html              入口（唯一一个 HTML；含"首帧前定主题"的内联脚本，防深色下白屏闪烁）
  vite.config.ts          base / 构建 / 测试配置（base 的口径见 §1 的警告）
  scripts/
    sync-figures.mjs            dev/build 前把 docs/图/ 里**已入库**的真实图同步进 public/figures/
    browser-check.mjs           零依赖的真实浏览器检查 + 截图（见 §5）
    verify-facts.mjs            网页上的数字 ↔ 仓库真值源 机械对账（见 §6）
    gen-architecture-drawio.mjs 生成可编辑的 docs/图/dld-架构.drawio（见 §7）
    gen-demo-frames.ts          用规则模型模拟一局、导出帧数据（vite-node 跑）
    render-demo-gif.py          把帧数据画成演示 GIF（唯一需要 Pillow 的脚本）
  src/
    main.tsx / App.tsx    入口与页面骨架（含背景虚线网格）
    engine/               规则模型：geometry.ts（几何真值表）+ engine.ts（状态机与渲染）+ 45 条测试
    components/           DotMatrix / SegDisplay / Keypad / charts / DataFlow / ModuleMap /
                          BlockDiagram / ThemeToggle / ui
    sections/             Hero / Demo / Flow / Architecture / Evidence / Tradeoffs / DocsNav / Footer
    data/                 facts.ts（全部事实、数字、案例、链接的**唯一真值源**）+ timeline.ts（时序场景）
    styles/               tokens.css（设计变量）+ app.css（版式与全部组件）
  public/figures/         构建时同步进来的图（**不入库**，见 site/.gitignore）
```

## 4. 字体：为什么自持 latin、中文走系统栈

| 用途 | 选择 | 理由 |
|---|---|---|
| 西文 / 数字 | **Inter Variable**（自持，latin woff2 48 KB） | 业界产品 UI 的事实标准（Linear / Figma / Notion 一类都在用），字重轴 100–900，数字是等宽表格数字 |
| 等宽 / 标识符 | **JetBrains Mono Variable**（自持，latin woff2 40 KB） | JetBrains 出品、为读代码而设计；`0/O`、`1/l/I` 可分辨 —— 这个站满屏 `t_1k`、`o_rowr`、`L1_TARGET_MASK`，这条很实用 |
| 中文 | **系统栈**：Noto Sans SC → PingFang SC → Hiragino Sans GB → Microsoft YaHei | CJK 网络字体的代价在另一个量级（`@fontsource/noto-sans-sc` 解包 **71.2 MB**），而系统里的中文字体质量已经很好。参照项目 `tortrixx/slides` 也是这个口径：Noto CJK 只用在 **PDF 渲染**（无下载成本），它的**网页**同样走系统字体栈 |

刻意不做的事：不加 Google Fonts / 任何外部 CDN（国内网络下经常不可达，而"字体挂了"
表现为静默回落到默认字体 —— 版式全变但没人会报错）。`browser-check.mjs` 里有一条
`document.fonts.check(...)` 断言，**字体没加载进会直接红**。

## 5. `browser-check.mjs`：真实浏览器检查

静态检查看不出布局溢出、对比度、字体有没有真的加载、GIF 有没有 404、播放器点了动没动。
所以这个脚本用 CDP（Chrome DevTools Protocol）直接驱动无头 Chrome/Edge：

```powershell
npm run build
npm run preview -- --port 4195        # 另一个终端
node scripts/browser-check.mjs http://localhost:4195/dld/
```

**零依赖**（靠 Node 22+ 内置的全局 `WebSocket` 直接说 CDP，不装 puppeteer/playwright），
并且任一条不满足就非 0 退出：

* 控制台报错 / 未捕获异常 / React 未挂载 / 缺少 `h1`；
* **字体真的加载**（`document.fonts.check`）；
* **演示 GIF 真的解码**（`naturalWidth > 0`）—— 防 404 静默失败；
* **主题切换**：属性真的变、真的写 localStorage、**浅色与深色各量一遍对比度**；
* **时序播放器**：场景切换、播放推进、仪表点阵真的亮；
* **模块地图 / 案例切换器**：点一下详情真的换；
* 图表画出来了（条形 / 折线 / 利用率行数）；
* 390 / 320px 无横向溢出；可点元素不小于 32px；
* 页内锚点全部命中；不出现无法分类的外链；
* 正文对比度 ≥4.5:1（**浅色与深色分别测**）；正文没有裸露的 Markdown 记号。

截图输出到 `site/.shots/`（已 gitignore）。这个脚本抓出过 8 个真 bug，记在这里给后来人：

1. 指针捕获把 `pointerup` 重定向到容器 ⇒ **点零片完全没反应**；
2. 12 栅格在窄屏没塌成单栏（390px 下两栏卡片只有约 126px 宽）；
3. `.tag` 上的 `white-space: nowrap` 被长文案撑出 358px，把整页顶宽；
4. 对比度抽样拿 `body` 的背景去量深色面板里的小字 ⇒ **假阳性**；
5. 页面开了 `scroll-behavior: smooth`，`scrollIntoView` 还在动画中就去取坐标 ⇒ **点击丢失**（播放器/模块卡/案例都点不动）；
6. `--muted`（**背景**令牌）被当成文字色用 ⇒ 次级文字几乎不可见（1.04:1）；
7. 对比度的"有效背景"没走到 `<html>` ⇒ 深色主题下报一堆假不合格（背景设在 html 上）；
8. GIF 里数码管的"熄灭段"画得太亮 ⇒ 每一位都像 `8`，"其余全灭"这条信息被吃掉。

## 6. 内容维护约定

* **所有数字与出处只写在 `src/data/facts.ts`**，页面组件只做排版。
  改 RTL 之后要更新的地方一处就能找到。
* 引用仓库文件一律走 `blob(path, line)` / `tree(path)`（中文路径逐段编码）。
  **不要**链接 `quartus/output_files/*.rpt`、`*.pof`、`*.pin` 这类文件 ——
  它们被 `.gitignore` 挡掉了，克隆下来根本不存在，链过去就是死链。
* 改完仓库里的 RTL / 重新编译 / 重跑仿真之后，跑一次对账脚本：

  ```powershell
  npm run verify:facts
  ```

  它把**网页上写的数字**和**仓库里的机读真值源**机械地对一遍（当前 0 FAIL / 39 OK）：
  LE/LAB/引脚/slack/POF sha256/时间戳 对 `quartus/build_provenance.json`；Fmax 对 `docs/05`；
  各模块的**最新轮次**与断言数对 `sim/rounds/<模块>/rNN.json`；
  被引用的路径是否存在、是否**已入库**（对 `git ls-files`，专治链到被 gitignore 挡掉的编译产物）。
* 时序播放器的每一个刻度与信号名写在 `src/data/timeline.ts`，每条都带 `cite` 出处。
  **改之前先回源码核**：这个文件里就抓到过一处流传很广的错说法 ——
  "引擎 `i_tick` 接 `tick_200`、所以内容刷新 25/21 Hz"，而源码是
  `u_puzzle.i_tick => t_1k`（`rtl/puzzle_top.vhd:520`），25/21 Hz 的真正来源是
  "一行 `npc+2` 拍 × 8 行 = 40/48 拍"（`docs/02-模块详细设计.md:240`）。
* 单元测试会把 `scripts/check_geometry.py` 的穷举结论**在浏览器模型里重算一遍**
  （PAT0/PAT1/PAT2 各 1 种铺法、PAT3 两种；保持初始朝向只许平移时全部无解），
  几何一旦抄错，`npm test` 会当场失败。

## 7. 演示 GIF 与 draw.io 图：怎么重新生成

```powershell
# ① 演示 GIF（改了规则模型或想换演示内容时才需要）
npm run gen:frames      # vite-node 跑规则模型、导出一局 48 帧到 .shots/demo-frames.json
npm run gen:gif:render  # 画成 docs/图/演示-跑一局.gif（需要带 Pillow 的 Python）
npm run gen:drawio      # 重新生成 docs/图/dld-架构.drawio
```

* `npm run gen:frames` 会**自动求解**这一局：精确覆盖搜索求出每块的
  (锚点, 朝向)，再对每种处理顺序做单块 BFS（动作 = 上下左右 + 顺时针旋转，
  约束 = 不越界 / 不压别的块），取按键最少的一版；每一步都经真实 `reducer` 重放
  **并断言被受理**（被拒绝就抛错）。当前结果：16 次按键（含 **2 次旋转**）——
  这是"不旋转就拼不出来"的正面证据。
* `gen:gif:render` 是**本站唯一需要第三方 Python 包（Pillow）的脚本**。
  仓库自身的 `scripts/*.py` 全是标准库。**只想构建/部署站点时不必跑它** ——
  GIF 产物已入库（`docs/图/演示-跑一局.gif`）。
* `docs/图/dld-架构.drawio` 是纯文本 XML，可直接在
  <https://app.diagrams.net/> 或 VS Code 的 draw.io 插件里改。
  **它由脚本生成**（改 RTL 之后改 `gen-architecture-drawio.mjs`、重跑一次即可，别手改）——
  与 `quartus/puzzle.qsf` 由 `gen_project.py` 生成同一个道理。

## 8. 设计方向（视觉系统与页面结构）

**关键词：Swiss Editorial × Digital Hardware × Engineering Notebook。**
视觉语言参照本仓库姊妹项目 `tortrixx/slides` 的站点：等宽优先、neutral 色阶、
虚线网格底纹、两级分隔线、深浅双主题、克制的入场动效且全部可降级。

### 8.1 三条设计原则

1. **网格与排版优先于装饰。** 层级靠字号、字重、字距、留白和**细线**建立，不用阴影和渐变背景。
   全站只有一类"盒子"（1px 描边 + 4px 圆角）。
2. **唯一强调色。** `--acc`（LED 信号红橙）只用在章节编号、强调线、焦点态、关键数字与数据流脉冲上。
   硬件的红/绿/黄**只允许出现在点阵内部** —— 那不是设计选择，是双色点阵的物理事实。
3. **等宽字体承担技术信息。** 标识符、数值、单位、图注、来源一律 mono；正文叙述用 sans。
   这条沿用参照站的语言，也是"工程记录"的视觉语法。

### 8.2 色彩 / 字体 / 间距

| 类别 | 取值 | 说明 |
|---|---|---|
| 色阶 | shadcn neutral（HSL 三元组） | 浅色 `0 0% 100%` / `0 0% 3.9%`；深色 `0 0% 3.9%` / `0 0% 98%` |
| 文字 | `--foreground` / `--muted-foreground` | 深色 66%（9.5:1）、浅色 42%（5.4:1）；**两套主题都过 AA**（实测最低 5.24 / 6.65） |
| 强调 | `#c8370a`（浅）/ `#ff6a45`（深） | 唯一强调色，按背景提亮以保对比度 |
| LED | `#ff3b20` / `#17d96a` / `#ffbe0b` | 只出现在点阵内部 |
| 网格底纹 | 24px 虚线，`fixed` + 中心径向遮罩 | 背景设在 `html` 上（Safari 会提升 `body` 背景、深色下露底） |
| 线 | 区块边界 2px、条目分隔 1px 两端渐隐 | 两条线"重量"不同，层级才分得出来 |
| 字体 | Inter Variable + JetBrains Mono Variable + 系统中文栈 | 见 §4 |
| 间距 | 4px 基准 9 级 | 章节间 96px、块间 24–32px |
| 版心 | 1240px / 12 列 / 窄屏塌单栏 | |

### 8.3 章节与阅读顺序

| # | 章节 | 为什么排在这里 |
|---|---|---|
| 00 | 首屏 | 30 秒内回答：这是什么、跑在什么硬件上、解决什么任务、源码与文档在哪；右侧直接放**演示 GIF** |
| 01 | 玩法 | 把一局拆成四步讲清；键位用键盘图而不是表格 |
| 02 | **时序播放器** | 本次改版的核心：四个场景可逐步播放，看数据流随时间传播、每拍在动哪个模块 |
| 03 | 架构 | 带图（相邻层主干）+ **可点模块地图**（点一个只看它）+ 时钟拓扑 |
| 04 | 数据与证据 | 全部改成**图表**：利用率 / 时序预算尺 / 逐模块断言条 / 演进折线 |
| 05 | 工程取舍 | 左侧列 7 个案例、右侧只渲染选中的那一个，六步做成竖向 stepper |
| 06 | 文档与源码 | 文档、源码、部署说明 |
| — | 页脚 | 仓库入口、技术栈、完成状态；不含任何个人简介/奖项/背书 |

### 8.4 时序播放器的设计取舍

一开始想做一张"所有模块 + 所有连线"的大图，再把脉冲跑在连线上。但那张图必然有 20 条交叉线，
**而且会说错话**：一张"每层一根竖箭头"的图天生只能表达相邻层关系，硬画就会把
"`clk_gen` 把 `t_4hz` 送给 `buzzer_ctrl`"画成"送给 `game_fsm`"。
所以改成**每个场景一条线性流水线**：没有交叉、窄屏自动换行、每步只高亮"这一拍真正在动的部分"；
想看完整互联关系就用 `docs/图/dld-架构.drawio`（那里把跨层连线也画全了，因为它可以缩放拖拽）。

### 8.5 关于设计类 Skill（如实交代）

任务书点名的 `frontend-design`、`design-review`、`product-showcase` **在本 DSH 会话里都不存在**；
本会话实际可加载的 Skill 只有 `diagnose-windows-sandbox-acl` 与 office 系列，都与前端设计无关。
因此：**本站没有加载过任何设计 Skill，也不声称调用过**。设计方向是照任务书给的关键词
自行制定的，并把原则、色阶、字体、间距与章节顺序写在本节，便于复核
"设计是不是有立场的"，而不是套模板。
