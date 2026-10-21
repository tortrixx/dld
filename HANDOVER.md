# 《简易拼图游戏》Docsify 站点交接说明

> 本文只讲**站点现在是什么样、怎么改、怎么验收**。工程历史见 `HANDOFF.md` / `PROGRESS.md` / `AI_LOG.md`，
> 硬件事实以 `facts/facts.json` 与 `rtl/` 为准。

---

## 1. 站点定位

给**答辩现场**用的硬件文档，读者是学生本人和随机抽问的老师。三条设计目标：

1. **3 秒看懂**：每页开头一句大白话，不用术语；
2. **能应对抽问**：每页有「三个设计选择」+「答辩问答」；
3. **对着波形能讲**：每页有「波形怎么读」，写清时间刻度 + 信号名 + 跳变。

线上地址：<https://tortrixx.github.io/dld/>（推送 `main` 后由 GitHub Actions 自动部署）。

---

## 2. 文件结构

```
docs/
├── index.html                 # Docsify 入口：CDN 版本、插件开关（改动前先读第 4 节）
├── _sidebar.md                # 侧边栏：总览 + 6 个模块，平铺，不要嵌套
├── README.md                  # 首页：一句话 + 指标条 + 演示 GIF + 6 张模块卡片
├── assets/
│   ├── custom.css             # 全部样式（配色变量、版心、卡片、图框）
│   ├── custom.js              # 唯一行为：把「图片 + 斜体图注」包成 <figure>
│   └── images/                # 站点用图（波形截图、架构图、演示 GIF）
├── subsystems/                # 6 个模块页，每页 90～140 行
│   ├── 01_system_top.md       # puzzle_top / puzzle_pkg
│   ├── 02_clock_keypad.md     # clk_gen / keypad_scan
│   ├── 03_game_fsm.md         # game_fsm
│   ├── 04_puzzle_engine.md    # puzzle_ctrl
│   ├── 05_rom_random.md       # pattern_rom / piece_rom / rng_lfsr
│   └── 06_display_audio.md    # disp_format / seg_scan / dot_matrix_scan / buzzer_ctrl
├── 图/                        # ⚠️ 事实模型的证据目录，被 facts.json 按字节锚定，不要动
└── report/                    # 实验报告三件套（md / docx / pdf）与制图源文件
```

`docs/` 下还有几个 **MkDocs 时代的证据文件**（`00-规范理解与需求.md`、`02-模块详细设计.md`、
`03-仿真验证方案.md`、`05-资源利用与编译报告.md`、`06-硬件调试记录.md`）。它们不在侧边栏里、
不影响阅读，但被 `scripts/extract_facts.py` 与 `scripts/audit_evidence.py` 读取，**不要删**。

---

## 3. 内容约定

### 每页固定骨架（一节都不要增删）

```markdown
# <模块中文名>（<实体名>.vhd）

> **一句话**：<≤40 字，不用术语>

## 1. 它管什么          # 吃进 / 吐出 / 节拍 / 代价，3～6 条
## 2. 它在系统里的位置  # 1 张图 + 上游 / 下游 / 少了它会怎样
## 3. 三个设计选择      # 恰好 3 条，标题是一句结论，正文含数字
## 4. 波形怎么读        # 3 条要点，每条 = 时间刻度 + 信号名 + 跳变
## 5. 答辩问答          # 4～5 条，答案第一句是结论，≤120 字，含信号名
```

### 三条容易踩的坑

1. **粗体必须以汉字、字母、数字或全角括号结尾。**
   `**1,264 个逻辑单元 (LE)**` 和 `` **图案库 (`pattern_rom`)** `` 会渲染失败，
   页面上直接显示两个星号。正确写法：`**1,264 个逻辑单元（LE）**`、`` **图案库**（`pattern_rom`） ``。
2. **不要用 `<div>` 等原始 HTML 包问答。**
   marked 会把「块级标签开头、中间没有空行」的整段当 HTML 直通，块内的 `**` 和 `` ` `` 全部原样显示。
   问答用 `### Q…` + 段落即可。
3. **不要写 `$$…$$`。** 站点没有启用数学公式渲染，公式请写成行内代码或纯文本
   （例如 `x^8+x^6+x^5+x^4+1`）。上面三条 `scripts/check_docs.py` 都会拦。

### 图片

- 图片下一行**紧跟** `*斜体图注*`，中间不留空行；`custom.js` 会自动包成图框和题注。
- 图注里**不要写「图 1」「图 15」**：站点编号与实验报告不一致，会串。用描述性图注。
- 图注里写「在图上找：①②③」时，**必须真的能在图上看到**，否则老师一放大就露馅。

### 事实纪律

- 数字只从 `facts/facts.json`、`rtl/`、`quartus/output_files/*.rpt`、报告原文里取；
  **查不到出处就不写**。
- 口径要分清：整机是 1,264 / 1,270 LE，而 `puzzle_ctrl` 单模块在 fit 报告里是 760 LE；
  v1～v7 的 4,690 / 3,751 / 994 等是**单独综合**读数。混着说会被追问。
- 波形是**时间压缩仿真**（测试台把 `puzzle_pkg.CLK_HZ` 从 50 MHz 补丁成更小的值），
  页面里必须说明，否则读者会把横轴当真实秒数。

---

## 4. 站点配置（`docs/index.html`）

- Docsify 与插件版本**全部固定**（`docsify@4.13.1`、`docsify-copy-code@2.1.1`、
  `docsify-pagination@2.10.1`、`prismjs@1.29.0`），不要改回 `@latest`。
- **没有** `docsify-sidebar-collapse`：它会注入 CSS 把嵌套列表折叠，导致首页侧边栏里
  6 个模块链接全部不可见。侧边栏因此写成平铺结构。
- **没有** KaTeX：站内已无公式，去掉一个依赖。若将来要写公式，需要同时补回
  `katex.min.js` + `auto-render.min.js` 并删掉 `check_docs.py` 里的 `$$` 规则。
- `subMaxLevel: 2`：侧边栏展开当前页的二级标题。

样式全在 `docs/assets/custom.css`，配色和尺寸都在 `:root` 变量里。几个关键约定：

- 正文版心 780px（中文一行 35～40 字），**图片可突破到 1000px**，因为仿真截图的信息全在细节里；
- 图框用 `width: fit-content; max-width: min(100%, 1000px)`，
  **不要改成 `max-width: 1000px`**：那样小图会被拉伸、窄屏会被撑破；
- 首页两个组件：`.metrics`（指标条）和 `.mod-grid` / `.mod-card`（模块卡片）。

---

## 5. 改完必须做的三件事

```powershell
# 1. 站点体检：链接、图片是否存在，粗体与原始 HTML 块会不会渲染失败，是否有 $$
python scripts/check_docs.py          # 必须 0 错误

# 2. 事实模型对账
python scripts/extract_facts.py --check

# 3. 肉眼确认（本地起服务 + 无头浏览器截图）
python -m http.server 8899 --bind 127.0.0.1     # 在 docs/ 目录下起
# 另开一个终端：
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu `
  --hide-scrollbars --window-size=1440,2400 --virtual-time-budget=11000 `
  --screenshot=shot.png "http://127.0.0.1:8899/#/subsystems/01_system_top"
```

> 无头 Chrome 在 Windows 上**视口最小约 512px**，用 `--window-size=390` 截图会得到
> 512px 的渲染被裁到 390px，看起来像溢出——那是假象。窄屏请用 512px 验证。

CI 会把上面第 1、2 步跑在部署之前（`.github/workflows/pages.yml`），
所以本地过了基本就不会部署失败。

---

## 6. 部署

```powershell
git add docs/ scripts/ .github/
git commit -m "docs: ..."
git push origin main
gh run watch $(gh run list --limit 1 --json databaseId -q '.[0].databaseId')
```

推送后 GitHub Actions 会自动构建并发布到 <https://tortrixx.github.io/dld/>。
工作流只在 `docs/**`、`rtl/**`、`sim/**`、`facts/**`、`scripts/**` 或工作流本身变动时触发。

---

## 7. 已知取舍

| 取舍 | 原因 |
|:---|:---|
| `docs/图/SIM-*.svg` 不在站内使用 | 是脚本按跳变画出的示意图，多数信号在整段时基上是平线，读不出信息；站内统一用 Quartus 截图（`GUI-*.png`）作为证据 |
| `docs/assets/images/GUI-*.png` 是裁过的 | 裁掉了窗口标题栏、工具条、左侧工具栏和空白行，只留时间轴 + 信号名 + 波形；**原始截图仍在 `docs/图/`** |
| 首页放的是规则模型重放 GIF | 不是板子实录，图注里已明确标注；用来让人 3 秒明白这游戏长什么样 |
| `docs/` 下保留 MkDocs 时代的证据 md | 被 `extract_facts.py` / `audit_evidence.py` 读取，删了会破坏事实模型对账 |
