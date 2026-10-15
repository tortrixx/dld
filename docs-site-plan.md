# 文档站实施计划（`docs-site-plan.md`）

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
**关键约束：`vite build` 会先把 `site/dist` 清空**，所以文档站必须在它**之后**
构建，并且直接输出到 `site/dist/docs/`。

---

## 2. 最终架构：两层站点，一套事实

```
                         facts/facts.json          ← 唯一机读事实模型
                    （scripts/extract_facts.py 生成）
                          /              \
                         /                \
        site/ 工程展示站                    book/ 技术文档站
   （观感、交互、演示动画）           （架构、接口、时序、证据、答辩）
        /dld/                              /dld/docs/
        └──────────── 互相链接 ────────────┘
```

| 内容 | 主要承载 | 理由 |
|---|---|---|
| 首屏观感、交互点阵、时序播放器、演示动画 | `site/` | 已有可用实现，重写没有收益 |
| 系统架构交互展示 | `site/`，链接到文档 | 展示站负责"一眼看懂"，文档站负责"逐条可查" |
| 模块接口契约、逐模块设计 | `book/` | 需要长表格与深链接，MkDocs 更合适 |
| 数据字典、时序契约、端到端流程 | `book/` | 同上 |
| 仿真断言与证据索引 | `book/` | 需要按"模块→场景→断言→波形→结论"组织 |
| 资源/时序报告、答辩讲稿、FAQ | `book/` | 同上 |

**"同一套事实"不是口号**：`book/` 的表格由 `gen_pages.py` 从 `facts.json` 机械生成；
页面里的关键数字用 `{{fact:...}}` 占位符注入，解析不了就**构建失败**。

---

## 3. 目录规划

```
facts/facts.json               唯一事实模型（入库，供两个站点消费）
scripts/extract_facts.py       抽取器（入库）
scripts/check_book.py          文档站一致性门禁（入库）

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

| 项 | 决定 |
|---|---|
| 展示站 | `https://tortrixx.github.io/dld/`（不变） |
| 文档站 | `https://tortrixx.github.io/dld/docs/` |
| 产物组织 | 先 `vite build` → `site/dist/`；再 `BOOK_SITE_DIR=site/dist/docs mkdocs build` |
| 顺序理由 | **`vite build` 会清空 `site/dist`**，所以文档必须在它之后构建；反过来做会被删掉 |
| 上传 | `actions/upload-pages-artifact` 仍旧只上传 `site/dist`（现在是合并后的完整站点） |
| 触发路径 | 增加 `book/**`、`facts/**`、`docs-*.md`、`scripts/extract_facts.py` |
| 不提交 | `.venv/`、`book/site/`、`_generated/`、同步来的素材副本、`site/dist/` |
| 不改硬件 | 工作流依旧不调用 Quartus、不跑仿真、不改 `rtl/` |

---

## 7. 风险与对策

| # | 风险 | 对策 |
|---|---|---|
| R1 | **无真实硬件照片**，容易"用渲染图充当实拍" | 文档站显式声明缺失；`gen_pages.py` 把 `真实硬件实测照片 = 0` 写进统计表；`assets/hardware/README.md` 说明补拍内容 |
| R2 | 一页图堆太多、图注缺失 | 每图必须"测试场景 / 观察信号 / 预期 / 实测 / 证据链接"；证据按类别分页 |
| R3 | 手写数字与仓库漂移 | `{{fact:}}` 占位符 + `mkdocs --strict` + `scripts/check_book.py`（重新生成 `facts.json` 并比对） |
| R4 | 中文路径 / 子路径 404 | 素材同步进 `docs/assets/`；引用源码走 GitHub URL 且逐段编码；`--strict` 拦截缺图 |
| R5 | 中文搜索搜不到 | 锁 `jieba` 版本做分词；搜索索引覆盖标识符与 `ERR-xxx` |
| R6 | 文档站构建顺序被 Vite 清掉 | 顺序写进工作流注释 + `docs-site-plan.md` §6；本地用 `book.py build --site-dir` 复现同一布局 |
| R7 | 本机网络需代理（pip / npm） | `requirements.txt` 锁版本；`book/README.md` 写明代理用法；CI 无需代理 |
| R8 | 把 `puzzle_pkg` 画成模块、把诊断顶层画进游戏通路 | 架构图与层级页显式分色/分区，并在正文里点名说明 |
| R9 | 文档变成"只有标题的空页" | 验收时逐页检查正文字数与非表格段落；空壳页视为未完成 |
| R10 | 覆盖现有展示站 | 对 `site/` 只做加法；改动后跑 `npm test`、`verify:facts`、`npm run build` |

---

## 8. 验收标准

**内容**
- [ ] 15 个实体全部有独立说明页或独立小节；11 个游戏子模块各有端口契约 + 内部原理 + 输入输出示例 + 验证证据
- [ ] 系统级框图与真实例化关系逐条对得上（实例名/实体名/端口名可核对）
- [ ] 端口方向、位宽、类型与源码一致（由 `gen_pages.py` 机械保证）
- [ ] 关键跨模块接口有完整说明（发送方/接收方/端口/位宽/语义/时机/有效条件/证据）
- [ ] ≥5 条端到端流程（A~E）各有：图 + 信号表 + 逐步解释 + 证据
- [ ] 关键仿真结果有图注与判据；明确"这张图能证明什么/不能证明什么"
- [ ] 资源与时序数据有明确出处；已知限制与取舍未被隐藏
- [ ] 答辩 FAQ ≥24 问，每问含 30 秒口头回答 + 深入解释 + 可展示图/源码 + 追问

**工程**
- [ ] `mkdocs build --strict` 零警告（`python book/scripts/book.py build`）
- [ ] 内部链接、图片存在性、RTL 路径引用、模块接口名、关键工程数据、Pages 子路径六类检查全过（`scripts/check_book.py`）
- [ ] `python book/scripts/book.py serve` 一条命令起本地站
- [ ] 展示站原有测试全过：`npm test`、`verify:facts`、`npm run build`
- [ ] 合并产物可部署：`site/dist/index.html` 与 `site/dist/docs/index.html` 都在
- [ ] `facts/facts.json` 与源码一致（`python scripts/extract_facts.py --check`）

**诚实性**
- [ ] 全文没有把脚本渲染图说成 Quartus 截图、没有把仿真说成实测
- [ ] 缺失的证据（硬件照片）显式标注，并给出补拍清单
- [ ] 无法核实的说法标 **待核实** 并给出核实路径
