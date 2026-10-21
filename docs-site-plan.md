# 文档站实施计划（`docs-site-plan.md`）

> ⚠️ **本文已过期（2026-10-21 归档）**。它描述的是**已退役的 MkDocs `book/` 站点**（41 页 + 展示站双层架构），
> `book/` 与 `site/` 两个目录都已被删除。**当前文档站是 `docs/` 下的 Docsify 站点**，
> 架构、内容规范、门禁与发布面一律以 [`HANDOVER.md`](HANDOVER.md) 为准。
> 本文仅作历史决策留档（其中 §1 的 RTL 审计结论仍有参考价值），**不要再按它动手**。

> **第 27 工作阶段 · 2026-10-15** ｜ 目标：把 `tortrixx/dld` 升级为「工程展示站 + 技术文档站」
> 双层站点，两层共用同一套工程事实。
>
> 本文件是**审计结论 + 设计决策 + 验收标准**，先写计划再动手（任务书 §三的要求）。
> 它不是宣传材料，**每一个数字都标了出处**，读不出出处的地方就是我没有核实。

---

## 1. 审计结论（动手前必须确认的事）

### 1.1 真实的 RTL 结构（由 `scripts/extract_facts.py` 从源码抽出，不是从旧文档抄的）

| 项 | 值 | 证据 |
|---|---|---|
| VHDL 文件 | 16 | `rtl/*.vhd` |
| 实体（entity） | 15 | `facts/facts.json` → `hierarchy.counts` |
| · 游戏子模块 | **11** | `clk_gen` `keypad_scan` `game_fsm` `puzzle_ctrl` `pattern_rom` `piece_rom` `rng_lfsr` `dot_matrix_scan` `seg_scan` `disp_format` `buzzer_ctrl` |
| · 诊断顶层 | 3 | `board_test_top` `keypad_diag_top` `keypad_raw_top` —— **不在游戏数据通路上** |
| · 正常游戏顶层 | **1** | `puzzle_top`（唯一绑定引脚的文件） |
| 设计包（package，不是模块） | 1 | `puzzle_pkg`：90 常量 / 2 类型 / 2 子类型 / 24 纯函数 |

**`puzzle_top` 的例化关系（11 个子模块，逐条来自真实 `port map`）**：

```
puzzle_top
├── u_clk      : clk_gen          S1 时钟与复位
├── u_keypad   : keypad_scan      S2 键盘输入
├── u_fsm      : game_fsm         S3 游戏控制
├── u_puzzle   : puzzle_ctrl      S4 拼图引擎
├── u_pieces   : piece_rom        S5 零片形状
├── u_pattern  : pattern_rom      S5 目标图案
├── u_rng      : rng_lfsr         S5 伪随机数
├── u_disp     : disp_format      S6 数码管内容
├── u_seg      : seg_scan         S6 数码管扫描
├── u_dot      : dot_matrix_scan  S6 点阵行驱动
└── u_buzz     : buzzer_ctrl       S7 音效
```

**审计中发现的、必须写进文档而不能回避的事实**：

1. **`puzzle_top` 里有 9 个信号"无人读"**（`release` `kp_raw` `piece_n` `sel_idx`
   `pos_dbg` `lock_dbg` `scanrow` `t_100` `t_40`）与 **2 个输出端口显式 `open`**
   （`o_tick_2hz`、`o_ori`）。这是**设计事实**：一部分是顶层保留的调试观测点，
   一部分是历史遗留（`t_100` 的常量注释里已写明"无使用者"）。
   文档要给每个都写清"为什么留着"，写不出来的就标 **待核实**。
2. **`o_tick_2hz` 在 `puzzle_top` 里接 `open`**，但它**不是死逻辑** ——
   `board_test_top` 是它唯一的实读者（`rtl/clk_gen.vhd:58` 的端口注释已
   在上一阶段专门订正过这一点）。任何"这个信号没人用"的说法都必须限定到具体顶层。
3. **`puzzle_pkg` 的 24 个函数全是纯函数**（无状态），综合时被展开成常量/组合逻辑 ⇒
   它在框图里**不能**画成带端口的方框。
4. **`README.md` 记录 184 条断言 / 12 个模块，与 `sim/rounds/` 逐条求和一致**；
   任务书里写的"179 条"是**旧基线**，以 `facts/facts.json` 为准。

### 1.2 证据的真实性分级（图片是重灾区）

| 类别 | 数量 | 能不能当硬件证据 |
|---|---|---|
| `docs/图/GUI-*.png` | **12** | ✅ **真实 Quartus GUI 仿真截图**（上一阶段按"只保留波形编辑器区域"重拍） |
| `docs/图/SIM-*.svg` | 12 | ❌ 脚本渲染的辅助波形，**不是** GUI 截图 |
| `docs/图/*.drawio` | 1 | 可编辑图表源 |
| `docs/图/演示-*.gif` / `演示-首帧.png` / `结算画面-预览.png` | 3 | ❌ 浏览器里由 TypeScript 引擎渲染，**不是**硬件实拍 |
| **真实开发板实拍照片** | **0** | ⚠️ **缺失** —— 这是本次审计最重要的一个发现 |

⇒ 文档站首条图片规则：**每一张图都必须标出它属于哪一级证据**，
`docs/图/` 下没有的东西不补、不造、不"看起来像"。

### 1.3 现有展示站（`site/`）必须保护的能力

`site/` 是 Vite + React + TS 的独立前端工程，已有 41 个源文件、vitest 单测、
`verify-facts.mjs`（43 项事实对账）、`browser-check.mjs`（浏览器自动化）。
**本次不动它的既有实现**，只做三件加法：

1. 在页面里加"查看详细设计 →"的入口指向文档站；
2. 让 `verify-facts.mjs` 额外与 `facts/facts.json` 对账（同一套事实，两个消费者）；
3. `.github/workflows/pages.yml` 增加文档站构建步骤（见 §6）。

### 1.4 现有 CI

`.github/workflows/pages.yml` 单流程：`npm ci` → `npm test` → `verify:facts` →
`vite build`（`VITE_BASE=/dld/`）→ `upload-pages-artifact(site/dist)`。
**关键约束：`vite build` 会先把 `site/dist` 清空** ⇒ 若要让两个站点共存，
文档站必须在它**之后**构建（这条约束在本工作阶段后期随展示站被删除而失效，见 §2 变更记录）。

---

## 2. 最终架构

> ### ⚠️ 变更记录（2026-10-15 第 27 工作阶段 · 用户裁决）
>
> 本节最初设计的是**两层站点**：`site/`（Vite + React 工程**展示**站，`/dld/`）
> + `book/`（Material **文档**站，`/dld/docs/`），两者共用 `facts/facts.json`。
>
> **随后用户决定：去掉 `site/`，只保留 `book/` 并让它占用根路径 `/dld/`。**
> 于是：
>
> * `site/` 整个目录已删除（41 个跟踪文件；连同交互点阵、时序播放器、演示动画、
>   `verify-facts.mjs` 与 74 个前端单测）；
> * `book/mkdocs.yml` 的 `site_url` 从 `/dld/docs/` 改为 `/dld/`；
> * `.github/workflows/pages.yml` 从"两站点合并发布"改为"只构建并上传 `book/site`"；
> * `book/hooks/facts.py` 删除 `{{showcase}}`（不再有第二个站点可指），
>   保留 `{{docs_site}}`；
> * 页面里 6 处"展示站"引用改为措辞如实的"**原**展示站"，
>   并说明其产物仍在 `docs/图/`（且已标注是网页引擎渲染，不是硬件实拍）；
> * `.gitignore` 的 `site/` 一节删除，只留 `book/` 的构建产物规则。
>
> **代价（如实记）**：交互点阵、可播放时序播放器、一局演示动画**不再提供**；
> 前端那套"浏览器里跑规则模型"的独立实现随之消失。相关静态产物
> （`演示-跑一局.gif` 等）仍归档在 `docs/图/`。
>
> **收益**：只有**一份事实、一个构建、一个门禁** —— 不再有
> "两个站点事实打架"的整类风险（本工作阶段就在 `site/` 里抓到过 3 处过期数字）。

### 变更后的最终架构

```
                    rtl/*.vhd   sim/rounds/**   quartus/**
                            \        |        /
                     scripts/extract_facts.py        ← 唯一机读事实模型的生产者
                                │
                        facts/facts.json              ← 唯一事实源（入库）
                                │
                     book/scripts/gen_pages.py        ← 端口表/连接表/层级/引脚/断言/图片/ERR 索引
                                │
                    book/docs/_generated/**           ← 机械生成的表格片段（不入库，构建前重生成）
                                │
                     book/hooks/facts.py              ← {{fact:}} / {{src:path:line}} / {{tree:}}
                                │
                     mkdocs build --strict            ← 导航/链接/图片/锚点全检查
                                │
                    https://tortrixx.github.io/dld/   ← 项目唯一的站点
```

| 内容 | 承载 | 备注 |
|---|---|---|
| 项目首屏与整体观感 | `book/docs/index.md` | 一屏看懂"是什么 + 现状 + 怎么读" |
| 系统架构（图 + 层级 + 数据流 + 节拍 + 面积） | `book/docs/02-architecture/` | 9 张 Mermaid + 机械生成的层级/连接表 |
| 模块接口契约与逐模块设计 | `book/docs/03-modules/` | 15 个实体 + 设计包，端口表机械生成 |
| 数据字典、时序契约、端到端流程 A~E | `book/docs/04-interfaces/` | 答辩时"跟着一次按键走完信号链" |
| 游戏流程（自检 → 胜负） | `book/docs/05-gameplay/` | |
| 仿真断言、波形证据、上板验证 | `book/docs/06-verification/` | 184 条断言的六要素 + 12 张真实 GUI 截图 |
| 资源 / 时序 / 引脚 / 可复现性 | `book/docs/07-implementation/` | |
| 故障复盘与工程取舍 | `book/docs/08-debugging/` | ERR 索引机械生成 |
| 答辩讲稿、演示脚本、FAQ | `book/docs/09-defense/` | FAQ 31 问 |

**"只有一套事实"不是口号**：`book/` 的表格由 `gen_pages.py` 从 `facts.json` 机械生成；
页面里的关键数字用 `{{fact:...}}` 占位符注入，解析不了就**构建失败**。

---

## 3. 目录规划

```
facts/facts.json               唯一事实模型（入库；站点与所有对账脚本都读它）
scripts/extract_facts.py       抽取器（入库）
scripts/check_book.py          ⚠️ 实际在 book/scripts/ 下（见下）；本行保留历史路径说明

docs-site-plan.md              本文件

book/
├── mkdocs.yml                 Material 配置（strict + hooks + snippets）
├── requirements.txt           锁版本的 Python 依赖
├── README.md                  怎么装、怎么起、怎么构建
├── hooks/facts.py             {{fact:}} / {{src:path:line}} 注入
├── scripts/
│   ├── book.py                唯一入口：gen / build / serve / check
│   ├── gen_pages.py           生成 _generated/ 下的表格页
│   └── sync_assets.py         把 docs/图/ 同步进 docs/assets/
└── docs/
    ├── index.md               总览（项目介绍页）
    ├── 01-project/ ... 09-defense/    41 个内容页（见 §4）
    ├── stylesheets/extra.css  自持字体栈 + 表格/图注/代码排版
    ├── assets/brand/mark.svg  品牌图标（手写，入库）
    ├── assets/hardware/README.md      说明"真实照片缺失"（手写，入库）
    └── _generated/            ★ 机械生成的表格页（**不入库**，每次构建前重生成）
```

**为什么 `_generated/` 不入库**：入库就意味着"可能过期"。本项目已经被
"文档与代码不一致"咬过（ERR-022），所以这里选择**每次构建都重新生成**，
再从根上消灭"忘了更新"这种状态。

---

## 4. 页面规划（41 页 + 首页）

导航顺序刻意做成一条**学习路径**：
**项目是什么 → 系统如何划分 → 模块如何协作 → 信号如何流动 → 如何验证 →
如何实现到板子 → 为什么这样设计 → 如何答辩**。

| 章节 | 页数 | 关键交付 |
|---|---|---|
| 一、项目 | 5 | 概览 / 题目要求落点 / 功能实现状态 / 亮点 / **已知限制（不隐藏）** |
| 二、系统架构 | 5 | 系统总体框图 + 7 张子系统图 + RTL 层级表 + 时钟节拍 + 面积账 |
| 三、模块设计 | 11 | 11 个模块（+ 诊断顶层 + 设计包）逐一的端口契约 / 内部原理 / 输入输出示例 / 验证证据 |
| 四、接口与信息传递 | 6 | 接口分类学 / 跨模块连接总表 / 控制信号握手 / **数据字典与位序约定** / 时序契约 / 端到端流程 A~E |
| 五、游戏流程 | 6 | 从自检到胜负的完整行为描述 |
| 六、验证与证据 | 6 | 策略 / 模块测试 / 整机测试 / **184 条断言** / 波形与图注 / 上板验证与**缺失证据** |
| 七、实现到 FPGA | 5 | 编译 / 资源 / 时序 / 引脚 / 可复现性 |
| 八、调试与取舍 | 3 | ERR 索引 / 典型复盘 / 工程取舍 |
| 九、答辩 | 4 | 介绍页 / 演示脚本 / **≥24 问 FAQ** / 技术深挖 |

### 机械生成 vs 手写（哪一部分谁负责）

| 内容 | 方式 | 生成者 |
|---|---|---|
| 端口契约表（15 个实体） | 🆕 生成 | `gen_pages.py` → `_generated/ports/*.md` |
| 跨模块连接总表（4 个顶层） | 🆕 生成 | `_generated/connections*.md` |
| RTL 层级与实例表、统计口径 | 🆕 生成 | `_generated/hierarchy.md` |
| `puzzle_pkg` 常量/类型/函数表 | 🆕 生成 | `_generated/pkg-*.md` |
| 引脚锁定表 | 🆕 生成 | `_generated/pins.md` |
| 12 个模块的最新轮次与逐条断言 | 🆕 生成 | `_generated/sim-rounds.md`、`assertions/*.md` |
| 图片清单（含证据分级） | 🆕 生成 | `_generated/figures.md` |
| ERR 索引 | 🆕 生成 | `_generated/errors.md` |
| 关键读数（LE/LAB/Fmax/slack/POF） | 🆕 生成 | `_generated/metrics.md` |
| 架构叙事、状态机讲解、时序推理、设计取舍、答辩稿 | ✍️ 手写 | `book/docs/**`（人写，引用源码与证据） |

---

## 5. 事实来源与引用规则

1. **机读真值源**（唯一）：
   `quartus/build_provenance.json`、`sim/rounds/<模块>/rNN.json`、
   `rtl/*.vhd`、`quartus/puzzle.qsf`、`quartus/puzzle.sdc`、`docs/图/`。
2. **页面里禁止手打这些数字**，一律用 `{{fact:...}}`；表格一律 `--8<--` 引入生成页。
3. **源码引用**用 `{{src:rtl/clk_gen.vhd:58}}`（钩子展开成 GitHub 行链接，
   并做 URL 逐段编码，`docs/图/` 这类中文路径不会 404）。
4. **没有证据就不写结论**。无法从源码证明的（例如"这个脉冲要多宽"）
   写成 **待核实**，并给出核实路径。
5. **三类证据必须分开标注**：RTL 仿真 / 编译与静态时序分析 / 板级实测。
   **不允许用仿真通过代替硬件验收**。

---

## 6. 部署方案

> ⚠️ 本节已按 §2 的**变更记录**更新：不再有第二个站点。

| 项 | 决定 |
|---|---|
| 线上地址 | **`https://tortrixx.github.io/dld/`**（项目唯一的站点） |
| `site_url` | `https://tortrixx.github.io/dld/` —— Material 由它推出 `base_url = /dld/`，静态资源全部带此前缀；写错会表现为"本地好、线上 CSS/JS 全 404" |
| 构建 | `python book/scripts/book.py build`（先生成 `facts.json` → `_generated/` → `assets/`，再 `mkdocs build --strict`） |
| 产物 | `book/site/`（相对 `book/mkdocs.yml` 所在目录；可用 `BOOK_SITE_DIR` 覆盖） |
| 上传 | `actions/upload-pages-artifact` 显式指向 `book/site`（**不能**用默认的仓库根，否则会把整个硬件工程传上去） |
| 发布前对账 | `scripts/extract_facts.py --check` → `book/scripts/book.py check` → 构建 → **自证产物完整 + 产物里没有外部 CDN 的 `<script src>`** |
| 触发路径 | `book/**`、`facts/**`、`rtl/**`、`sim/**`、`docs/*.md`、`docs/图/**`、`scripts/**`、`quartus/{build_provenance.json,puzzle.qsf,puzzle.sdc}`、根目录 `.md`、本工作流自身 |
| 不提交 | `book/.venv/`、`book/site/`、`book/docs/_generated/`、同步来的素材副本、`jieba.cache` |
| 不改硬件 | 工作流不调用 Quartus、不跑仿真、不改 `rtl/` |
| 仓库设置 | 只需一次人工操作：**Settings → Pages → Source 选 "GitHub Actions"** |

---

## 7. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | **无真实硬件照片**，容易"用渲染图充当实拍" | 站点显式声明缺失；`gen_pages.py` 把 `真实硬件实测照片 = 0` 写进统计表；`assets/hardware/README.md` 说明补拍内容；页面里 3 处引用演示图的图注都标"❌ 网页引擎渲染" |
| R2 | 一页图堆太多、图注缺失 | 每图必须"测试场景 / 观察信号 / 预期 / 实测 / 证据链接 / 能证明什么 / 不能证明什么"；证据按类别分页 |
| R3 | 手写数字与仓库漂移 | `{{fact:}}` 占位符（解析不了就构建失败）+ `mkdocs --strict` + `book/scripts/check_book.py` + `extract_facts.py --check` |
| R4 | 中文路径 / 子路径 404 | 素材同步进 `docs/assets/`（`docs/图/` 不在 `docs_dir` 里）；引用源码走 GitHub URL 且逐段编码；`--strict` 拦截缺图与死链 |
| R5 | 中文搜索搜不到 | 锁 `jieba` 版本做分词（`lang: [zh, en]`）；搜索索引覆盖模块名、端口名、`ERR-xxx` |
| R6 | ~~文档站构建顺序被 Vite 清掉~~ | **已消除**：`site/` 删除后不再有 Vite 清理动作。保留此条是为了说明"为什么当初的合并顺序是硬的" |
| R7 | 本机网络需代理（pip） | `requirements.txt` 锁版本；`book/README.md` 写明代理用法；CI 无需代理 |
| R8 | 把 `puzzle_pkg` 画成模块、把诊断顶层画进游戏通路 | 架构图与层级页显式分色/分区，并在正文里点名说明 |
| R9 | 文档变成"只有标题的空页" | 验收时逐页检查正文字数与非表格段落；空壳页视为未完成；`check_book.py` 会把残留占位标记判 FAIL |
| R10 | ~~覆盖现有展示站~~ | **已失效**：用户在第 27 工作阶段决定删除 `site/`（见 §2 变更记录），只剩本站，不再有"覆盖别人"的风险 |

---

## 8. 验收标准

**内容**
- [x] 15 个实体全部有独立说明页或独立小节；11 个游戏子模块各有端口契约 + 内部原理 + 输入输出示例 + 验证证据
- [x] 系统级框图与真实例化关系逐条对得上（实例名/实体名/端口名可核对）
- [x] 端口方向、位宽、类型与源码一致（由 `gen_pages.py` 机械保证）
- [x] 关键跨模块接口有完整说明（发送方/接收方/端口/位宽/语义/时机/有效条件/证据）
- [x] ≥5 条端到端流程（A~E）各有：图 + 信号表 + 逐步解释 + 证据
- [x] 关键仿真结果有图注与判据；明确"这张图能证明什么/不能证明什么"
- [x] 资源与时序数据有明确出处；已知限制与取舍未被隐藏
- [x] 答辩 FAQ ≥24 问（实际 **31 问**），每问含 30 秒口头回答 + 深入解释 + 可展示图/源码 + 追问

**工程**
- [x] `mkdocs build --strict` 零警告（`python book/scripts/book.py build`）
- [x] 内部链接、图片存在性、RTL 路径引用、模块接口名、关键工程数据、Pages 子路径六类检查全过（`book/scripts/check_book.py`）
- [x] `python book/scripts/book.py serve` 一条命令起本地站
- [x] 产物可部署：`book/site/index.html`、`search/search_index.json`、`sitemap.xml` 都在，且静态资源带 `/dld/` 前缀
- [x] `facts/facts.json` 与源码一致（`python scripts/extract_facts.py --check`）
- [x] 站点产物里**没有外部 CDN 的 `<script src>`**（Mermaid 自持）

**诚实性**
- [x] 全文没有把脚本渲染图说成 Quartus 截图、没有把仿真说成实测
- [x] 缺失的证据（硬件照片）显式标注，并给出补拍清单
- [x] 无法核实的说法标 **待核实** 并给出核实路径

---

## 9. 视觉系统（第 27 工作阶段后期追加）

### 9.1 为什么追加

第一版站点用的是 Material 的**默认观感**（indigo/teal、圆角卡片、默认字体）。
用户看过之后判定"还是不太好"，并给了一个参照：
[`bojieli.github.io/ai-agent-book/astro`](https://bojieli.github.io/ai-agent-book/astro/)。
那是一个 **Astro + 完全自制排版系统**的书站。

读它源码得到的结论（逐条都能在它的 `web-astro/src/styles/global.css` 里对上）：

| 维度 | 它的做法 | 本站的落地 |
|---|---|---|
| 字体 | `Manrope Variable`（无衬线）+ `Newsreader Variable`（衬线斜体，只用于标题强调半句） | 同样两套，**woff2 入库自持**（`book/docs/assets/fonts/`），中文交给系统字体 |
| 字号 | 首页 h1 `clamp(4rem, 6.5vw, 6.5rem)`、`letter-spacing −0.065em`、`line-height 0.97` | `clamp(2.6rem, 4.6vw, 4.6rem)`（中文按字距调过，避免任意断行） |
| 配色 | 暖白 `#fcfcf9` / surface `#f2f3ed` / 墨 `#20231e` / 发丝线 `#dedfd7` / 强调柠檬绿 `#d8ed7a`；深色换 `#18191c` + 长春花蓝 `#aac7ff` | 逐色采纳为设计令牌 |
| 分隔 | 一律 `1px` 发丝线，**不用卡片、不用阴影、不用圆角** | 同（表格、章节栅格、事实条、强调条全用细线） |
| 版式 | 页宽 1400 / 头部 1600、`padding-inline: 64px`、`padding-block: 76px`、eyebrow 大写小字 + 状态点 | 同 |
| 中文 | `:root:lang(zh-CN)` 换字体栈、`:lang(zh) .prose { line-height: 1.95 }` | 同（`--sans`/`--serif` 的回退栈 + `:lang(zh)` 行高） |
| 动效 | 只有 `0.18s` 颜色过渡，`prefers-reduced-motion` 全关 | 同 |

**用户裁决：只重做视觉层，保留 MkDocs**（不引入 Astro）——
这样搜索、事实注入、`--strict` 门禁、CI 全部不动，风险最低。

### 9.2 具体改了什么

* `book/docs/stylesheets/extra.css` **整份重写**（约 1300 行，分 12 节：字体 / 令牌 / 报头 /
  导航 / 正文 / 表格 / 代码 / 提示框 / 图注 / 页脚 / 首页 / 打印）。
* `book/mkdocs.yml`：`primary: custom` + `accent: custom`（颜色交给 CSS），
  `font: false` 保持（不连 Google Fonts）。
* `book/docs/index.md`：首页改写成**裸 HTML 的编辑式着陆页** ——
  hero（含一枚手绘 8×8 双色点阵 SVG）+ 事实条 + 9 章发丝线栅格 + 两条强调条；
  配 `hide: [navigation, toc]`。
* `book/docs/assets/brand/mark.svg`：重画成与令牌同色的点阵标记。
* `book/docs/assets/fonts/`：4 个 woff2 子集 + `PROVENANCE.txt`（来源 / sha256 / OFL 授权）。

### 9.3 靠"看图"才抓到的三个真缺陷

`mkdocs --strict` 对版式一无所知，所以这一步是**新增的视觉回归**：
`book/scripts/shoot.py`（无头 Chrome/Edge，浅色 + 深色各拍一遍，产物在 `book/review/`，不入库）。

1. **深色主题下"深色报头 + 浅色正文"**：自定义属性只在**声明它的元素**上求值 ——
   `--md-*` 映射写在 `:root` 上，取到的就永远是浅色 `--paper`，而 `.md-header`
   在 body 上求值拿到深色 ⇒ 报头与正文分裂。改成 `:root, [data-md-color-scheme]` 后一致。
2. **同一页里两张表宽度不一致**：Material 的 JS 把表格包进 `.md-typeset__table`
   （shrink-to-fit），窄内容的表就缩成半宽；只给 `table` 写 `width:100%` 没用
   （100% 的参照物就是那个收缩后的盒子）。靠**注入 outline 逐层定位**找到真凶。
3. **表格里的 `<code>` 几乎读不出来**：浅色主题下渲成 ~`#b9b9b9`，
   而本项目几乎每张表的每格都是代码（引脚名 / 端口名 / 位宽）。

⇒ 结论：**改了 CSS 就要重拍一遍截图**，这条已写进 `book/README.md`。

### 9.4 仍受 MkDocs 限制的地方（如实记）

* 报头/侧栏/目录的 DOM 是 Material 的，只能"改样式"不能"改结构"；
  纯编辑式的**单栏阅读页**（像参照站的章节页那样）在 Material 里做不到。
* 参照站的阅读器功能（阅读进度、划词高亮、笔记、图片查看器）本站**没有** ——
  那些是它在 `src/scripts/` 里自己写的，属于"完全自制"，不在本次范围内。
* 首页之外的页面仍是"文档版式"：左侧导航 + 正文 + 右侧目录。
  本次把它做得克制、精确，但**没有**伪装成书。
