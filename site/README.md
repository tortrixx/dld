# `site/` —— 工程展示站

`tortrixx/dld`（MAX II EPM1270 上的 8×8 双色点阵拼图游戏）的静态工程项目站。
与硬件工程**完全隔离**：这里只是 `rtl/` / `sim/` / `quartus/` 的**读者**，
不参与、也不影响编译、仿真与烧录。

---

## 1. 本地运行

```powershell
cd site
npm install
npm run dev        # http://localhost:5173/dld/
npm run test       # 规则模型的单元测试（45 条）
npm run build      # 产物在 site/dist/
npm run preview    # http://localhost:4173/dld/
```

> ⚠️ **dev / preview / build 三个命令都挂在 `/dld/` 子路径下**，这不是笔误。
> 早先 `vite.config.ts` 写成"只有 build 用 `/dld/`、dev 用 `/`"，
> 结果 `vite preview` 走到 `command === 'serve'` 分支拿到 `base = '/'`：
> 它一边吐出一个引用 `/dld/assets/...` 的 `index.html`、一边在 `/` 下找文件，
> **构建产物的 JS/CSS 全部 404、页面白屏**。
> 现在三个命令共用同一个 base，好处不止是修 bug —— 本地开发走的就是线上那条子路径，
> 这类"子路径 404"从此在开发阶段就会暴露。

## 2. 部署到 GitHub Pages

仓库用的是**项目级** Pages，所以线上地址是 `https://<user>.github.io/dld/`，
`base` 默认就是 `/dld/`。

1. 仓库 `Settings → Pages → Source` 选 **GitHub Actions**；
2. 推送到 `main` 后 `.github/workflows/pages.yml` 自动构建并发布 `site/`；
3. 换成**用户级** Pages 或改仓库名时**不用改代码**：
   workflow 里通过 `VITE_BASE` 环境变量传 `base`，本地也可以
   `VITE_BASE=/ npm run build` 覆盖。

> **当前状态**：本工作区没有 GitHub 凭据、也没有配置过 Pages，
> 所以只做到"本地构建可复现 + workflow 已就位"。
> 线上地址**未经访问验证** —— 这一点在页面上和交付说明里都如实标注了。

## 3. 目录结构

```
site/
  index.html              入口（唯一一个 HTML）
  vite.config.ts          base / 构建 / 测试配置（base 的口径见 §1 的警告）
  scripts/
    sync-figures.mjs      每次 dev/build 前把 docs/图/ 里**已入库**的真实图同步进 public/figures/
    browser-check.mjs     用无头 Chrome 打开页面做检查与截图（零依赖，见 §5）
  src/
    main.tsx / App.tsx    入口与页面骨架
    engine/
      geometry.ts         几何真值表（形状/图案/胜负画面/关卡/键位）
      engine.ts           规则模型（纯函数 + reducer）
      engine.test.ts      45 条单元测试
    state/useGame.ts      把规则模型接到 React（250 ms 心跳、SW7 开关、键盘）
    components/           点阵 / 数码管 / 键盘 / 框图 / 共用结构件
    sections/             首屏 / 模拟器 / 架构 / 证据 / 工程取舍 / 文档导航 / 页脚
    data/facts.ts         全部事实、数字、案例与链接的**唯一真值源**
    styles/               tokens.css（设计变量）+ app.css（版式与全部组件）
  public/figures/         构建时同步进来的图（**不入库**，见 site/.gitignore）
```

## 4. 为什么图不入库，而是每次构建前同步

`docs/图/` 是图素材的**唯一真值源**，清单所有者是 `docs/图/README.md`。
如果把图复制进 `site/public/` 并入库，同一张图就有两份，早晚会不同步
（这个项目最忌讳的一类错误就是"同一个读数/素材有两份真值源"）。
所以 `scripts/sync-figures.mjs` 在 `predev` / `prebuild` 自动跑一次，
副本放在被 gitignore 的 `public/figures/` 里。

图源缺失时页面会显示"素材缺失"占位而不是留白，日志里也会警告 ——
免得"图挂了"被当成"图没问题"。

## 5. `browser-check.mjs`：真实浏览器检查

静态检查看不出布局溢出、对比度、焦点态、闪烁相位与控制台报错，
所以这个脚本用 CDP（Chrome DevTools Protocol）直接驱动无头 Chrome/Edge：

```powershell
npm run build
npm run preview -- --port 4195        # 另一个终端
node scripts/browser-check.mjs http://localhost:4195/dld/
```

它**零依赖**（靠 Node 22+ 内置的全局 `WebSocket` 直接说 CDP，不装 puppeteer/playwright），
并且真的会失败退出（非 0）当出现下面任何一项时：

* 控制台报错 / 未捕获异常；
* React 没挂载、`h1` 缺失；
* 实测交互失效：自检后没进待机、待机点阵没全灭、按【开始】没进预览、预览 5 s 后没进对局、
  对局点亮格数 ≠ 12、点一下零片没被选中、按【旋转】没生效、按方向键没生效、
  三块直接确认没判负、失败时数码管不是 `FAIL`；
* SW7 关掉后点阵/数码管没有全部熄灭；
* 390px / 320px 出现横向溢出，或有触控目标小于 44px；
* 页内锚点指向不存在的元素、出现无法分类的链接；
* 正文对比度低于 4.5:1（沿祖先链取**真实背景色**再算，不是拿 body 的颜色糊一遍）。

截图输出到 `site/.shots/`（已 gitignore）。

> 这个脚本抓出来过 4 个真 bug，记在这里给后来人：
> ① 指针捕获把 `pointerup` 重定向到容器，导致**点零片完全没反应**；
> ② 12 栅格在窄屏没有塌成单栏（390px 下两栏卡片只有约 126px 宽）；
> ③ `.tag` 上的 `white-space: nowrap` 被长文案撑出 358px，把整页顶宽；
> ④ 对比度抽样第一版拿 `body` 的背景去量深色面板里的小字，报了**假阳性**。

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

  它会把**网页上写的数字**和**仓库里的机读真值源**机械地对一遍（当前 0 FAIL / 39 OK）：

  | 对什么 | 拿谁当真值源 |
  |---|---|
  | LE / LAB / 引脚 / setup·hold slack / POF sha256 / 构建时间戳 / git HEAD | `quartus/build_provenance.json` |
  | Fmax | `docs/05-资源利用与编译报告.md` |
  | 每个模块的**最新轮次**与断言条数、断言合计 | `sim/rounds/<模块>/rNN.json` |
  | 所有被引用的仓库路径是否存在、是否**已入库** | 工作区 + `git ls-files` |

  第三项专治两类事故：网页上的数字悄悄过期（页面照样好看，没人会发现）、
  以及链到了 `.gitignore` 挡掉的编译产物（克隆下来 404）。

* 单元测试会把 `scripts/check_geometry.py` 的穷举结论**在浏览器模型里重算一遍**
  （PAT0/PAT1/PAT2 各 1 种铺法、PAT3 两种；保持初始朝向只许平移时全部无解），
  所以几何一旦抄错，`npm test` 会当场失败。

* 改了 `rtl/puzzle_pkg.vhd` 的几何常量，必须重新解码几何真值表：

  ```powershell
  # 在仓库根执行：把 64 位常量解码成"每行一个字节"的掩码（与 scripts/check_geometry.py 同口径）
  python -c "import re,pathlib;s=pathlib.Path('rtl/puzzle_pkg.vhd').read_text(encoding='utf-8');f=lambda n:re.search(r'constant\s+'+n+r'\s*:\s*std_logic_vector\(63 downto 0\)\s*:=\s*\"([01]{64})\"',s,re.S).group(1);[print(n,[sum((int(f(n),2)>>(8*r+c))&1<<c for c in range(8)) for r in range(8)]) for n in ['L1_TARGET_MASK','L2_PAT0','L2_PAT1','L2_PAT2','L2_PAT3','WIN_MASK','FAIL_MASK']]"
  ```

---

## 7. 设计方向（视觉系统与页面结构）

**关键词：Swiss Editorial × Digital Hardware × Engineering Notebook。**
要同时体现瑞士国际主义的网格与排版纪律、数字硬件的精确与秩序、
以及工程实验记录的真实感与可追溯性。

### 7.1 三条设计原则（写样式前先读）

1. **网格与排版优先于装饰。** 层级靠字号、字重、字距、留白和**细线**建立，
   不用圆角卡片、阴影、渐变和发光边框。全站只有一种"卡片"（`.figure-cell` /
   `.case__step` / `.navlist__item`），而且都是**直角 + 细线**的表格化块。
2. **只有一支强调色。** `--acc`（信号红偏橙 `#c8370a`）只用在章节编号、强调线、
   焦点态与关键数字上；硬件的红/绿/黄**只允许出现在点阵面板内部**，不参与页面配色。
   点阵里的 4 种状态（灭/红/绿/黄）不是设计选择，是双色点阵的物理事实。
3. **注释即图注。** 所有技术注释、单位、来源一律等宽字体 + 小字号 + 次级色，
   并带可点的仓库路径 —— 这是"工程实验记录"的视觉语言，也让页面自带证据感。

### 7.2 色彩 / 字体 / 间距

| 类别 | 取值 | 说明 |
|---|---|---|
| 纸白 | `#f4f1ea` / `#ebe7dd` / `#e2ddd0` | 暖灰纸底，像工程图纸而不是纯白屏 |
| 墨黑 | `#131311` / `#474540` / `#5f5c55` | 三级文字；`--ink-3` 特意压深到 5.9:1，保证 11px 等宽小字也过 AA |
| 强调 | `#c8370a` / `#8f2706` / `#f2e0d6` | 唯一强调色 + 深色变体 + 极浅底（只用于声明块） |
| 仪器面 | `#121214` / `#1b1b1f` / `#33333a` | 点阵、数码管、键盘、页脚所在的深色面 |
| LED | `#ff3b20` / `#17d96a` / `#ffbe0b` | 只出现在点阵内部 |
| 字体 | 系统 sans 栈（含 Noto Sans SC / PingFang SC / 微软雅黑）+ 系统等宽栈 | **不加载任何外部字体**：性能与离线可用性优先，瑞士风格靠排版纪律而不是字体文件 |
| 字号 | `clamp()` 流体阶：display 2.1→4.6rem、h2 1.35→2rem、正文 0.95→1.02rem、注释 0.8125rem、等宽 0.75rem | 320px 不溢出、1440px 不空旷 |
| 间距 | 8px 基准的 10 级（4/8/12/16/24/32/48/64/96/128） | 章节之间用 96px，块之间 24–32px |
| 版心 | 1320px，栅格 12 列（`minmax(0,1fr)`），栏宽工具类 `.col-*` | 窄屏塌成单栏（≤700px） |

### 7.3 章节与阅读顺序

| # | 章节 | 为什么排在这里 |
|---|---|---|
| — | 报头（52px 固定） | 只放项目标识与 5 个章节锚点；不遮挡内容 |
| 00 | 首屏 Hero | 30 秒内回答：这是什么、跑在什么硬件上、解决什么任务、源码与文档在哪 |
| 01/02 | **可操作的 8×8 点阵模拟器** | 全站最重要的交互；紧跟首屏，因为"能玩"比"能读"更快建立可信度 |
| 03 | 系统架构 | 玩过之后再看结构，读者已经有具体问题（谁管时间、谁管空间） |
| 04 | 实验结果与工程证据 | 用真实读数回答"做得好不好"，每个数字带单位与出处 |
| 05 | 工程设计与关键权衡 | 体现技术深度：问题→约束→方案→验证→结果→局限 |
| 06 | 文档与源码导航 + 局限清单 | 让人能继续深挖，也把限制说在前面 |
| — | 页脚 | 仓库入口、技术栈、完成状态；不含任何个人简介/奖项/背书 |

### 7.4 点阵模拟器的交互设计

* **数据模型**：纯函数 + `reducer`（`src/engine/engine.ts`），状态机
  `selftest → idle → preview → playing → win/fail`，与 RTL 的状态编码一一对应。
* **时间轴**：单一 **250 ms 心跳**（= RTL 的 `tick_4hz`），由它派生 2 Hz 闪烁与
  1 Hz 秒计数 —— 与板子上"一条 4 Hz 节拍派生出闪烁与秒计数"的结构一致。
* **三种操作方式**：鼠标点选/拖动、触屏点选/滑动（阈值 18px，防手抖误移动）、
  键盘快捷键（挂在面板自己的 `keydown` 上，不抢 Tab 与页面滚动）。
* **反馈**：选中零片加内描边（不只靠颜色）+ 点阵下方状态行 + 事件日志；
  被拒绝的操作明说原因（越界/重叠/已锁定）—— 并注明"硬件上被拒是**没有**提示音的"。
* **SW7 开关**：关掉即"所有显示器件不显示"（B1），重新合上走一次上电自检。

### 7.5 真实实验数据怎么呈现

* 大数字条（`.figures`，4 列 × 2 行，不秃边）+ 细线利用率条（LE / LAB / 引脚 / UFM）；
* 每张数据卡自带"来源：文件名:行号"并链到仓库里的**已入库**文件；
* 图素材严格分两类并分别标注：`GUI-*.png` = Quartus 图形界面实测截图，
  `SIM-*.svg` = 脚本渲染的辅助波形（**不能当实测截图**，只能逐点对照）；
* 缺失的素材显示"素材缺失"占位，而不是留白；
* 数字的过期由 `npm run verify:facts` 机械拦截。

### 7.6 技术栈与依赖

Vite 5 + React 18 + TypeScript 5（strict）+ Vitest 2。**运行时零第三方依赖**
（只有 react / react-dom）：没有 UI 库、没有 CSS 框架、没有动画库、
没有图标库、没有字体请求、没有分析脚本。全部图形（点阵、数码管、框图、
套准记号）都是手写的 SVG / CSS。开发期依赖只有 vite / vitest / typescript /
@vitejs/plugin-react / 类型声明。

### 7.7 关于设计类 Skill 的说明（如实交代）

任务里点名的三个 Skill —— **`frontend-design`、`design-review`、`product-showcase`
在本 DSH 会话里都不存在**。本会话实际可加载的 Skill 只有
`diagnose-windows-sandbox-acl` 与 `office-docx / office-pptx / office-xlsx`，
都与前端设计无关。

因此：**本站没有"加载过"任何设计 Skill，也不声称调用过**。
设计方向是照任务书给出的关键词（Swiss International Typographic Design、
Dieter Rams 式功能主义、product-showcase 的叙事章节）**自行制定**的，
并把三条设计原则、配色/字体/间距系统、章节顺序与交互设计写在上面
（§7.1–7.6），以便任何人复核"设计是不是有立场的"而不是套模板。
