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
**站点不依赖任何外部 CDN**，依赖脚本全部放在 `docs/assets/vendor/`，见第 5 节。

---

## 2. 文件结构

```
docs/
├── index.html                 # Docsify 入口：插件开关与本地依赖清单
├── _sidebar.md                # 侧边栏：总览 + 一个分组（模块速查）+ 6 个模块
├── README.md                  # 首页：一句话 + 指标条 + 演示 GIF + 6 张模块卡片
├── assets/
│   ├── custom.css             # 全部样式（配色变量、版心、卡片、图框）
│   ├── custom.js              # 唯一行为：把「图片 + 斜体图注」包成 <figure>
│   ├── vendor/                # Docsify 及其插件的本地副本（不进 CDN）
│   └── images/                # 站点用图（波形截图、架构图、演示 GIF）
├── subsystems/                # 6 个模块页，每页 90～110 行
│   ├── 01_system_top.md       # puzzle_top / puzzle_pkg
│   ├── 02_clock_keypad.md     # clk_gen / keypad_scan
│   ├── 03_game_fsm.md         # game_fsm
│   ├── 04_puzzle_engine.md    # puzzle_ctrl
│   ├── 05_rom_random.md       # pattern_rom / piece_rom / rng_lfsr
│   └── 06_display_audio.md    # disp_format / seg_scan / dot_matrix_scan / buzzer_ctrl
├── 图/                        # ⚠️ 事实模型的证据目录，被 facts.json 按字节锚定，不要动
└── report/                    # 实验报告（.typ 是唯一事实源，派生 md / docx / pdf）与制图源文件
```

`docs/` 下还有几个 **MkDocs 时代的证据文件**（`00-规范理解与需求.md`、`02-模块详细设计.md`、
`03-仿真验证方案.md`、`05-资源利用与编译报告.md`、`06-硬件调试记录.md`）。它们被
`scripts/extract_facts.py` 与 `scripts/audit_evidence.py` 读取，**不要删**；它们也**不对外发布**，见第 6 节。

侧边栏是**一层分组 + 平铺条目**（`_sidebar.md` 里 `* **模块速查**` 下面挂 6 个同级条目）。
不要再往下嵌套：docsify 的折叠插件已经移除，但多层嵌套会让 `subMaxLevel` 的展开行为变得难以预期。

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

页面 H1 必须与 `_sidebar.md`、首页卡片上的标题一致，否则目录和卡片会对不上。

### 三条容易踩的坑

1. **粗体不要以半角标点或反引号结尾。**
   `**1,264 个逻辑单元 (LE)**`、`` **图案库 (`pattern_rom`)** `` 会渲染失败，页面上直接显示两个星号。
   正确写法：`**1,264 个逻辑单元（LE）**`、`` **图案库**（`pattern_rom`） ``。
   注意：只有「收尾星号紧跟半角标点、且后面紧跟汉字或全角标点」才坏；
   `**Fmax 54.27 MHz**。` 这种以字母结尾的没问题。拿不准就跑门禁。
2. **不要用 `<div>` 等原始 HTML 包问答。**
   marked 会把「块级标签开头、中间没有空行」的整段当 HTML 直通，块内的 `**` 和 `` ` `` 全部原样显示。
   问答用 `### Q…` + 段落即可。
3. **不要写 `$$…$$`。** 站点没有启用数学公式渲染，公式请写成行内代码或纯文本
   （例如 `x^8+x^6+x^5+x^4+1`）。上面三条 `scripts/check_docs.py` 都会拦。

### 图片

- 图片下一行**紧跟** `*斜体图注*`，中间不留空行；`custom.js` 会自动包成图框和题注。
  图注里可以用行内代码，会被保留。
- 图注里**不要写「图 1」「图 15」**：站点编号与实验报告不一致，会串。用描述性图注。
- 图注里写「在图上找：①②③」时，**必须真的能在图上看到**，否则老师一放大就露馅。
- **不要把图片和正文写在同一段**。`custom.js` 遇到「图 + 文字」的段落会整段跳过（不包裹），
  这是刻意的保护：早期版本会把整段连同正文一起删掉。

### 事实纪律

- 数字只从 `facts/facts.json`、`rtl/`、`quartus/output_files/*.rpt`、报告原文里取；
  **查不到出处就不写**。
- 口径要分清：整机是 1,264 / 1,270 LE；`puzzle_ctrl` 单模块在 fit 报告里是 760 LE；
  v1～v7 的 4,690 / 3,751 / 994 / 563 是**单独综合**读数。混着说会被追问。
- 波形是**时间压缩仿真**（测试台把 `puzzle_pkg.CLK_HZ` 从 50 MHz 补丁成更小的值），
  页面里必须说明，否则读者会把横轴当真实秒数。截图刻度末值 ≠ 仿真总长，两者都要写清。

---

## 4. 站点配置（`docs/index.html`）

- 插件版本全部**固定**，且都从 `assets/vendor/` 本地加载，见第 5 节。
- **没有** `docsify-sidebar-collapse`：它会注入 CSS 把嵌套列表折叠，导致首页侧边栏里
  6 个模块链接全部不可见。
- **没有** KaTeX：站内已无公式。若将来要写公式，需要补回 katex 的 JS + auto-render，
  并删掉 `check_docs.py` 里的 `$$` 规则。
- `subMaxLevel: 2`：侧边栏展开当前页的二级标题。
- 末尾有一小段兜底脚本：如果 `docsify.min.js` 没加载成功，把「正在加载文档…」换成一句
  人能看懂的提示，而不是永远卡住。

样式全在 `docs/assets/custom.css`，配色和尺寸都在 `:root` 变量里。几个关键约定：

- 正文版心 780px（中文一行 35～40 字），**图片可突破到 1000px**，因为仿真截图的信息全在细节里；
- 图框用 `width: fit-content; max-width: min(100%, 1000px)`，
  **不要改成 `max-width: 1000px`**：那样小图会被拉伸、窄屏会被撑破；
- `--faint` 也当正文色用（卡片实体名、翻页标签），**必须保持 ≥4.5:1 对比度**，别再调浅；
- 首页两个组件：`.metrics`（指标条）和 `.mod-grid` / `.mod-card`（模块卡片）。

---

## 5. 本地依赖（不用 CDN）

答辩现场的网络未必能访问 `cdn.jsdelivr.net`；一旦 CDN 不可达，页面会永久停在
「正在加载文档…」。所以依赖全部下载到 `docs/assets/vendor/`：

| 文件 | 来源 |
|:---|:---|
| `docsify.min.js`、`vue.css`、`search.min.js`、`zoom-image.min.js` | `docsify@4.13.1` |
| `docsify-copy-code.min.js` | `docsify-copy-code@2.1.1` |
| `docsify-pagination.min.js` | `docsify-pagination@2.10.1` |
| `prism-vhdl.min.js` | `prismjs@1.29.0` |

升级版本：改 `scripts/vendor_assets.py` 顶部的 `ASSETS` 表，重跑脚本，再本地看一眼：

```powershell
python scripts/vendor_assets.py           # 下载/更新
python scripts/vendor_assets.py --check   # 只校验本地文件是否齐全
```

---

## 6. 发布面

**只有站点本身会被发布**，由 `.github/workflows/pages.yml` 的 `Stage Site Files` 步骤从
`docs/` 里挑出这些内容，其余一律不上线：

```
_site/
├── index.html  README.md  _sidebar.md  .nojekyll
├── assets/       （custom.css / custom.js / vendor/ / images/）
└── subsystems/   （6 个模块页）
```

这么做的原因：`docs/` 下还放着工程证据文档和报告四件套，它们不参与站点导航、
Markdown 也没有按 docsify 的规则维护，发布出去只会让线上多出一批没人看、渲染还半坏的页面
（实测那批文件里有 400+ 处粗体渲染失败）。

⚠️ **这个集合必须与 `scripts/check_docs.py` 的 `PUBLISHED_FILES` / `PUBLISHED_DIRS` 保持一致**，
门禁会检查「站点页有没有引用不会被发布的文件」。如果将来想让站点链接实验报告 PDF，
要同时把 `report/` 加进这两处。

---

## 7. 改完必须做的检查

```powershell
# 1. 站点体检：链接、图片、粗体、原始 HTML 块、$$、index.html 本地资源、发布面
python scripts/check_docs.py          # 必须 0 错误

# 2. 事实模型对账
python scripts/extract_facts.py --check

# 3. 本地依赖齐全（且不含任何会联网的外部引用）
python scripts/vendor_assets.py --check

# 4. 报告四件套是否同步（改过 docs/report/* 才需要）
python scripts/build_report.py --check

# 5. 隐私三面体检：跟踪文件 + **提交信息** + 作者身份
python scripts/check_privacy.py       # 必须 PASS

# 6. 交付用设计图是否与 RTL 一致（改过 rtl/ 或 facts/ 才需要）
python scripts/gen_design_diagram.py --check   # ① 数据对账 ② 几何体检 ③ 端口名核对，三关全过才写盘
python scripts/audit_diagram_selftest.py       # 体检脚本自身的回归（33 项断言）
python scripts/gen_overview_diagram.py --check # 功能总览：11 个 entity 被 6 块 + 时钟恰好划分一次
python scripts/drawio_render.py --check        # draw.io 渲染环境（viewer.min.js + chrome）
python scripts/gen_drawio_figures.py          # 出三个 .drawio 并用 draw.io 渲染三张主图 PNG

# 7. 肉眼确认（本地起服务 + 无头浏览器截图）
python -m http.server 8899 --bind 127.0.0.1     # 在 docs/ 目录下起
# 另开一个终端：
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu `
  --hide-scrollbars --window-size=1440,2400 --virtual-time-budget=11000 `
  --screenshot=shot.png "http://127.0.0.1:8899/#/subsystems/01_system_top"
```

### ⚠️ 两个解释器不能混用

| 脚本 | 用哪个 Python | 为什么 |
|:---|:---|:---|
| `audit_evidence.py`、`srcnorm.py` | **系统 Python 3.14** | `.py` 的逻辑指纹走 `ast.dump`，其输出随 Python 版本变化；轮次记录是 3.14 产生的。用 3.12 跑会把 12 条绿证报成"逻辑指纹口径不一致"（已降级为 WARN 并说明原因，不会误报 FAIL） |
| `sync_report_docx.py`、`build_report.py` | **捆绑 Python**（`load_workspace_dependencies` 给的那个） | 它们需要 `lxml`，系统 Python 没装 |


### ⚠️ Quartus 有 32 位和 64 位两套，**读数一样但 `.pof` 字节不同**（2026-10-22 踩到）

`C:\QuartusII91\QuartusII91\quartus\` 下同时有 `bin\quartus_sh.exe`（32 位）与
`bin64\quartus_sh.exe`（64 位）。实测同一个 `.qsf`：

| 用哪个 | LE / LAB / 引脚 | Fmax | `puzzle.pof` |
|:---|:---|:---|:---|
| `bin\`（32 位，**本项目的口径**） | 1,264 / 127 / 52 | 54.27 MHz | **27,312 B**，sha256 `cc3c69b3…` ✅ 与 `build_provenance.json` 一致 |
| `bin64\`（64 位） | 完全相同 | 相同 | 27,319 B，sha256 不同 ❌ |

后果：用 64 位编译一次，`quartus/output_files/` 里那份"逐字节可复现"的固件就没了
（`output_files/` 是 gitignore 的，**没有版本可回滚**），而报告里"清洁重编译后与烧录读回的
版本逐字节相同"这句话立刻变成假的。

⇒ 复现交付固件请一律用 **`quartus\bin\quartus_sh.exe`**；改完 `rtl/` 重编译后，
用 `python scripts/record_build.py --force` 更新 `build_provenance.json`，
并核对 `pof.sha256` 与实物一致。清洁重编译只需 **~15 s**（删掉 `quartus/db/` 与
`quartus/output_files/` 再跑 `quartus_sh -t scripts/build.tcl`）。

两个已知的**测量陷阱**，别被它们骗了：

- 无头 Chrome 在 Windows 上**视口最小约 512px**。用 `--window-size=390` 截图会得到
  512px 的渲染被裁到 390px，看起来像横向溢出——那是假象。窄屏请用 512px 验证。
- **不要用 PowerShell 的 `Get-Content -Raw` + `Set-Content` 改这些文件**：
  Windows PowerShell 5.1 会按系统 ANSI 代码页读写，把 UTF-8 中文写成乱码
  （本项目已经因此损坏过一次 `docs/README.md` 与 `docs/index.html`）。
  改文件请用编辑器/`edit` 工具，或 Python 里显式 `encoding="utf-8"`。

### ⚠️ 隐私面**包括提交信息**（2026-10-22 实盘踩到）

「文件干净」不等于「仓库干净」。当时工作树、全部 blob、`git grep`、`git log -S` 都是 0 命中，
但 **HEAD 的提交信息正文里**写着 `C:\Users\<用户>\Desktop\...\<真实姓名>_<真实学号>_....pdf`，
而且已经 push 到远端 —— 因为 `git grep` 扫的是**内容**、`git log -S` 扫的是**增删差异**，
两者都看不见 commit message，而 commit message 是随 push 一起公开的。

所以隐私体检必须跑 `python scripts/check_privacy.py`（跟踪文件 + 提交信息 + 作者身份三面）。
它挂了就说明**改文件没用**，得重写提交信息：

```powershell
# 只有最近一两个提交脏：改 message 不动 tree，最安全
git commit-tree <tree> -p <parent> -F 新信息.txt     # 用原提交的 tree/父提交重放
git update-ref refs/heads/main <新提交> <旧提交>      # compare-and-swap，防并发
git rev-parse HEAD^{tree}                            # 必须与重写前**逐字节相同**
git push --force-with-lease origin main
```

⚠️ 重写**较老的**提交会让它之后所有提交的哈希集体失效 —— 而 `HANDOFF.md`、`docs/03`、
`docs/06`、`PROGRESS.md`、`AI_LOG.md` 是按哈希引用那些提交的（`sim/rounds/*.json` 的
`git_head` 与 `quartus/build_provenance.json` 也存着提交 SHA）。所以老提交里的历史路径只在
`scripts/check_privacy.py` 的 `KNOWN_HISTORICAL` 里显式登记为"已知并接受"。

### ⚠️ 已知残留：历史 blob 里的本机账户名（**当前工作树已干净**）

`check_privacy.py` 的第 ④ 面会报出这类东西，并且**刻意分成两档**：

| 标签 | 含义 | 处理 |
|:---|:---|:---|
| `历史内容（当前树仍在）` | 同一个路径**现在**也命中 | **FAIL** —— 那是活的问题，直接改文件 |
| `历史内容` | 只留在被改掉 / 被删掉的旧 blob 里 | 归入"历史残留"，汇总成一行 + 抽样 |

实测（2026-10-22）：残留 **395 处 / 94 个路径**，全部是 2026-10-10 提交 `65ada93`
（"消除全部作者绝对路径"）**之前**的东西 —— `.ref/` 的一次性脚本、旧版 `scripts/*.py`、
旧版 `HANDOFF.md`、已删除的 `docs/modules/*.md`。**真实姓名与学号不在其中**。

要真清掉只能**重写全史**，而代价是：
1. 所有提交哈希变掉 ⇒ 上面那批文档里的哈希引用全部作废；
2. `sim/rounds/*.json` 与 `quartus/build_provenance.json` 里的 `git_head` 变成悬空 ⇒
   `audit_evidence.py` 的证据链核对会失败，必须同步改写；
3. 这是一次独立的、需要先点头的工程，**不要在"顺手清理"里做**。

⇒ 现状是**显式登记为已知并接受**（理由写在 `KNOWN_HISTORICAL` 里），门禁 PASS 但每次都会
把命中数与路径数打印出来，不会被静默忽略。

CI 会把上面第 1、2 步和「暂存发布面 + 校验暂存结果」跑在部署之前，
所以本地过了基本就不会部署失败。

---

## 8. 部署

```powershell
git add docs/ scripts/ .github/ HANDOVER.md
git commit -m "docs: ..."
git push origin main
gh run watch $(gh run list --limit 1 --json databaseId -q '.[0].databaseId')
```

推送后 GitHub Actions 自动构建并发布。工作流只在 `docs/**`、`rtl/**`、`sim/**`、`facts/**`、
`scripts/**` 或工作流本身变动时触发。

---

## 9. 实验报告怎么重建

报告有四种载体，**唯一事实源是 `docs/report/实验报告_题目4_简易拼图游戏.typ`**：

| 载体 | 怎么来 |
|:---|:---|
| `.typ` | **手写**，唯一事实源 |
| `.pdf` | `typst compile`（交付主件，27 页） |
| `.md` | `scripts/gen_report_md.py`（封面与正文都从 `.typ` 派生） |
| `.docx` | `scripts/sync_report_docx.py`（幂等同步，收敛后重跑是 0 变更） |

### 另外两个交付件：平台「实际设计方案」的作答稿与六张设计图

课程平台除了报告，还有一步「实际设计方案（10 分）」，要求**框图与实现电路(代码)一致**。
老师两次反馈过这张图：先是"更像流程图、缺模块间信号"，重画后又指出"**渲染出来的架构图不好**" ——
所以最终版把这件事拆成**三层**，每层只干一件事：

| 层 | 文件 | 职责 |
|:---|:---|:---|
| **数据（唯一事实源）** | `scripts/arch_data.py` | 方框集合（11 entity + 7 板载 + 2 顶层胶合）、35 组原始连线（按 `(源,目标)` 合并后图上画 32 条） / 60 个 `(源,目标,网名)` 三元组、每个模块消费的全局网络 —— 全部从 `facts/facts.json` 与 `rtl/puzzle_top.vhd` 现算，人工只能读不能改 |
| **布局（只管画）** | `scripts/fig1_layout.py` | 六列分层 + 空通道正交走线 + 顶部干线带 + 标签自动避让；产出 SVG **和** 一份 `layout.json` 供对账 |
| **裁判（客观体检）** | `scripts/audit_diagram.py` | 读 `layout.json` 做 16 项几何检查：线穿框、标签压框/互压、端点是否落在框边、越界、交叉数、空白率、对齐…；`--fidelity` 再和 `arch_data` 逐条对账 |

`gen_design_diagram.py` 只是个壳：**写盘之前必须连过三关**（① 数据对账 ② 几何体检 ③ 端口名核对），
过不了就不写盘。

| 交付件 | 怎么来 |
|:---|:---|
| `docs/report/fig_overview.png` + `.drawio` | `scripts/gen_overview_diagram.py`（几何）+ `scripts/gen_drawio_figures.py`（出 `.drawio` 并渲染 PNG）：**功能总览**；`--check` 验证 11 个 entity 恰好划分一次 |
| `docs/report/fig1_system_architecture.png` + `.drawio` | 几何来自 `scripts/gen_design_diagram.py`（三关：数据对账/几何体检/端口名），呈现由 `scripts/drawio_arch.py` + draw.io 渲染；报告 §2.2 与站点 `docs/assets/images/` 用同一张 |
| `docs/report/fig_game_flow.png` + `.drawio` | 几何来自 `scripts/gen_flow_diagram.py`，呈现由 `scripts/drawio_flow.py` + draw.io 渲染：**规范流程图** + 「回循环」总线 |
| `docs/report/实际设计方案-模块设计一览.svg/.png` | `scripts/gen_design_diagram.py`（11 格，逐模块给端口与设计要点） |
| `docs/report/fig2_game_fsm.svg/.png`、`fig3_puzzle_core.svg/.png` | **手工维护**的矢量图（状态转移图 / 引擎四级数据流图）；改完用 `scripts/render_hand_svgs.py` 重渲染 PNG |
| `docs/report/GUI-*.png`（14 张） | `scripts/gen_wave_figures.py`：从 `docs/图/` 的 Quartus 整窗截图里裁掉标题栏与左侧工具栏、裁掉底部空白（2 张编译截图已预先裁过，脚本跳过） |
| `docs/report/实际设计方案.md` | **手写**：游戏流程 → 设计方法 → 总体框图 → 各模块设计 → 信号传递表 |

### 图片质量台账（A4 版心 166 mm 下的实测字号）

> 口径：报告版心宽 **166 mm**（`template.typ` 页边距）；矢量图按 viewBox 宽度换算，
> 位图按像素宽度换算（Quartus 截图字高约 12 px）。
> 重算命令：`python .tmp/qa_figures.py`；`--out <路径>` 可直接重新生成下表。

| 图 | 显示宽 | 来源 | 最小字号 | 最大字号 |
|:--|--:|:--|--:|--:|
| `fig1_system_architecture.png` | 100% | draw.io 3645x2584 | 3.4 pt | 7.1 pt |
| `fig_game_flow.png` | 88% | draw.io 4204x5363 | 3.9 pt | 7.2 pt |
| `GUI-buzzer_ctrl.png` | 100% | 1375x278 | 4.1 pt | 4.1 pt |
| `GUI-clk_gen.png` | 100% | 1375x388 | 4.1 pt | 4.1 pt |
| `GUI-disp_format.png` | 100% | 1375x335 | 4.1 pt | 4.1 pt |
| `GUI-dot_matrix_scan.png` | 100% | 1375x312 | 4.1 pt | 4.1 pt |
| `GUI-game_fsm.png` | 100% | 1375x607 | 4.1 pt | 4.1 pt |
| `GUI-keypad_scan.png` | 100% | 1375x350 | 4.1 pt | 4.1 pt |
| `GUI-pattern_rom.png` | 100% | 1375x103 | 4.1 pt | 4.1 pt |
| `GUI-piece_rom.png` | 100% | 1375x311 | 4.1 pt | 4.1 pt |
| `GUI-puzzle_ctrl.png` | 100% | 1375x609 | 4.1 pt | 4.1 pt |
| `GUI-puzzle_top.png` | 100% | 1375x609 | 4.1 pt | 4.1 pt |
| `GUI-rng_lfsr.png` | 100% | 1375x164 | 4.1 pt | 4.1 pt |
| `GUI-seg_scan.png` | 100% | 1375x276 | 4.1 pt | 4.1 pt |
| `fig_overview.png` | 100% | draw.io 4199x1776 | 4.1 pt | 7.4 pt |
| `fig3_puzzle_core.svg` | 100% | 矢量 910x? | 4.7 pt | 7.0 pt |
| `fig2_game_fsm.svg` | 100% | 矢量 890x? | 5.0 pt | 7.4 pt |
| `GUI-编译-面积.png` | 62% | 468x228 | 7.5 pt | 7.5 pt |
| `GUI-编译-时序.png` | 75% | 535x74 | 7.9 pt | 7.9 pt |

**当前结论**（2026-10-23 **第三轮（多 agent 工作流审查）改完、三张主图冻结后**重算，`python .tmp/qa_figures.py --out .tmp/fig_ledger.md`）：
19 张图的最小字号落在 **3.4 ~ 7.9 pt** —— 最差是 `fig1_system_architecture.png` **3.4 pt**，
最好是 `GUI-编译-时序.png` **7.9 pt**；3 张主图（draw.io 渲染）分别是 **3.4 / 3.9 / 4.1 pt**（`fig1` / `fig_game_flow` / `fig_overview`），
其余 16 张为 4.1 ~ 7.9 pt。主文字（方框标题）在 7.1 ~ 7.9 pt。改造前最差的三档是流程图 3.0 pt、模块级框图 3.4 pt、
12 张 Quartus 截图 3.75 pt（且带窗口标题栏与底部大片空白）。

> ⚠️ **`来源` 列的像素宽 ≠ 画布宽**：两轮改动都让 PNG 的导出框变大而**画布宽没变** ——
> `fig_game_flow` 由 **4110×5008 → 4204×5008**（左上角三行图例把导出框往左撑），
> 第三轮又因「按【开始】重开?」的否支绕到右侧 **4204×5363**（画布高 2121 → 2223）；
> `fig1_system_architecture` 由 3645×2526 → **3645×2584**（图例由 1 行变 3 行、整体上移）。
> **画布宽仍是 1700 / 1516**（`YS=0.78` 只压纵向）—— 字号是按画布宽换算的，所以
> **pt 一个没变**（3.4 / 3.9 / 4.1）。见到 `来源` 列尺寸变化不必当成字号回归。

**提字号的三条手法**（都可复现）：
1. **裁掉窗口装饰**：`scripts/gen_wave_figures.py` 从 `docs/图/` 的原件重裁截图；
2. **缩短画布**：`scripts/gen_flow_diagram.py` 把 `S_FAIL` 挪进主流程（宽 2320→1700），
   再只压缩纵向坐标（`YS=0.78`，字号不动）—— 图变矮，同样版心宽度下字相对变大；
   ⚠️ **画布高度不是单调下降的**（2026-10-23 那轮的实测）：为给 `lwin → win` 的「是」标签腾出
   **≥ 10 px 净距**，把 `win` / `fail` 及以下四个节点**整体下移 40** ⇒ 画布高 **2680 → 2720**
   （`YS=0.78` 缩放后 **2090 → 2121**）。**提字号靠的是"横向收窄 + 纵向相对紧凑"，不是把画布一味压矮**
   —— 压矮与"标签净距 ≥ 10 px"本来就在打架，见到高度回升别当成改错了；
3. **分级提档**：`fig1_layout.py` / `gen_overview_diagram.py` 的标题、组名、角标、注释
   各提一档，靠 `audit_diagram.py` 的 `E-TEXT-OVERFLOW` 守住不溢出边框。


### draw.io 渲染链路（2026-10-23 起，三张主图由它出图）

用户要求三张主图能在 draw.io 里维护/微调。桌面版装不上（`choco install drawio` 要管理员，
`C:\ProgramData\chocolatey\lib-bad` 拒绝访问），所以走**官方 viewer 渲染**：

| 步骤 | 命令 / 文件 |
|:--|:--|
| ① 取渲染器 | 下载 <https://viewer.diagrams.net/js/viewer-static.min.js> 到 `.tmp/tools/drawio/viewer.min.js`（**该路径命中 `*.tmp` 忽略规则，不在仓库里，换机器要重新下**） |
| ② 生成 `.drawio` | `python scripts/gen_drawio_figures.py`（写 `fig_overview` / `fig_game_flow` / `fig1_system_architecture` 三个 `.drawio`） |
| ③ 渲染 PNG | 同一脚本内置：`scripts/drawio_render.py` 用 headless Chrome 打开本地页面截图（2.4x），再自动裁白边 |
| ④ 只查环境 | `python scripts/drawio_render.py --check`（viewer 在不在、chrome 在不在） |

**分工**：方框位置 / 连线折点 / 标签位置仍由 `arch_data.py` + `fig1_layout.py` /
`gen_flow_diagram.py` / `gen_overview_diagram.py` 算（那份几何过 `audit_diagram.py` 的 16 项体检），
`.drawio` 只负责"用 draw.io 的箭头与线型画出来"。**改布局改生成脚本，改箭头样式改 `.drawio`。**

> ⚠️ **两个必踩的坑**（`scripts/drawio_lib.py`、`drawio_render.py` 注释里也写了）：
> 1. `<script src="viewer.min.js">` 必须放在图形 `div` **之后**，且该 div 必须带
>    `style="max-width:100%;"` —— 缺任一条会渲染成**全白且不报错**；
> 2. `mxCell` 的 `value="..."` 里若有双引号（HTML 富文本样式常见），必须转成 `&quot;`，
>    否则 XML 坏掉、同样全白。

> ⚠️ `gen_design_diagram.py` **不再写** `fig1_system_architecture.png`（该 PNG 归 draw.io 渲染），
> 只写 `.svg` 与「模块设计一览」；否则会把 draw.io 的图覆盖掉。

### 视觉验收台账（原「已知视觉缺陷」清单；2026-10-23：12 条**已逐条处理完**）

3 个 agent 逐图看出来的 12 条（上一轮的见提交 `3fb86a2`），本轮全部处理完毕：

**`fig1_system_architecture`**
1. ✅ **已修**：顶部干线带标签（`选择→引擎` / `选择→ROM`）原先离竖向干线太近、读起来像被劈开 —— 两个标签已移出干线带；
2. ✅ **已修**：`零片掩码` / `目标图案` / `帧平面` 三个组名与邻近竖线距离 < 10 px —— 改为显式标签并拉开净距；
3. ✅ **已确认无需改图**：板载 `50 MHz 有源晶振` 看起来"没接线"是**有意的** ——
   `arch_data.WIRE_GROUPS` 里**没有** `ext_clk` 出边，`clk` 是全局网络、用模块左下角角标表达
   （已核 `fig1_system_architecture.drawio`：**0 条**以晶振右边缘为起点的边，也 **0 处** `startArrow` 双向箭头；
   进 `clk_gen` 的那根箭头实际来自 `ext_btn → clk_gen` 的折线）；
   **已在报告 §2.2 的 fig1 图注里点明**（"板载 50 MHz 有源晶振到 `clk` 之间有意不画连线…这不是漏画接线"）；
4. ✅ **已修**：`piece_rom ↔ puzzle_ctrl`、`行计数器 ↔ seg_scan` 两处"看着像两头都有箭头" ——
   复查全图 `.drawio` **0 处 `startArrow`**，全部单向；原先的"双向"观感来自"两条各自单向的折线在同一区域相邻"。

**`fig_game_flow`**
5. ✅ **已修**：`剩余 ≤ 1 s ?` 的 `否` 回边改走**容器底部空白带**，不再横穿"有按键?→译码"的竖箭头、也不再贴着 `是` 字；
6. ✅ **已修**：`待机 S_IDLE` 框左下角内侧的 `否` 标签已**移出框外**，并贴到它自己的分支线上；
7. ✅ **已修**：`关卡 +1` 框内文字由「→ 回到待机」改为「**→ 进入下一关预览**」（与 `game_fsm` 的走向一致）；
   `失败 S_FAIL` / `关卡 +1` 的后续走向写进**图例**（"按【开始】重开 / 进入下一关预览"），
   图例并注明"为免长回线横穿全图，图中不画回边"；
8. ✅ **已修**：`全系统静默熄灭` 补了回到 `SW7 = 1 ?` 判定的回边（框内文字同步为"SW7 重新置 1 后回到上方判定"）。

**`fig_overview`**
9. ✅ **已修**：时钟虚线到 `图案与随机数据` 的竖直段与 `关卡号` 拉开 ≥ 12 px（rom tap **830 → 818**，`关卡号` 改显式标签）；
10. ✅ **已修**：容器标题 `内部核心功能框图（6 块 · 10 个 entity）` 与第一条时钟竖线拉开（标题 **x 430 → 215**）；顺带修 aud tap **1170 → 1160**。

**仍存的固有约束（是取舍，不是待办）**
11. ⚠️ **保留**：三张图在 A4 上最小字号 **3.4 / 3.9 / 4.1 pt**（`fig1_system_architecture` / `fig_game_flow` / `fig_overview`，
    见上表实测）—— 信息密度决定；再提只能**拆图**或**减少标注**；
12. ⚠️ **保留**：`.drawio` 的标签是**无底色**的：某条线若正好从标签下穿过就会"切断"文字。
    试过给标签加白底 —— 会把方框/连线切出白块，已回退；**正确做法是挪标签或挪线**（逐处手工指定坐标）。
    ⭐ **第一轮修图时新踩到的坑**：`scripts/drawio_lib.label` 生成的是 **`align="left"`** 的标签（**不是居中**）。
    布局脚本或 `audit_diagram.py` 若按"居中"估算标签占位，会整体偏 **w/2 ≈ 40 px** ——
    **渲染位置与体检口径必须用同一个对齐假设**，否则会出现"体检说没压线、渲染出来压了"（或反过来）。

### 第二轮独立视觉验收（2026-10-23，3 个 agent · 每人一张 · 共 60 张放大图）

第一轮 12 条修完后再跑了一轮**放大图验收**：每张主图切成 20 块放大（3 张 × 20 = **60 张**），
逐块问两件事 ——「有没有**线从文字上穿过**」「标签离**最近的深色像素**多远」。

**本轮遗留 + 新发现，且已全部修掉**

| 图 | 问题（第一轮遗留 / 本轮新发现） | 数量 / 量级 | 根因 |
|:--|:--|:--|:--|
| `fig1_system_architecture` | 文字压线 | **1 处真穿** + 12 处净距 **2.8 ~ 9.6 px** | 6 个 zone 虚线框只比模块框**外扩 3 px**，而线名按**框边**锚定 ⇒ 稍一浮动就压线 |
| `fig1_system_architecture` | 标签重复 | 「非 entity」**×2**、另有「行切片」重复 | 同一信息在组名与脚注各写了一份 |
| `fig1_system_architecture` | 跨主干共线 | **5 处**合并 | `trunk_x` 与 `lane_b` 各算各的槽位 |
| `fig_game_flow` | 图例压「上电/复位」框 | 净距 **0** | 图例条与首个流程框抢同一行 |
| `fig_game_flow` | 静默熄灭回边**箭尖悬空** | **47.5 px** | 回边终点没落在菱形边上 |
| `fig_game_flow` | `是` / `否` 标签贴线 | **11 个**，净距 **6.2 ~ 9.6 px** | 标签默认偏移 16 / 24 太小 |
| `fig_overview` | 「掩码/图案」贴线 | 距 rom → core 竖线 **3.3 px** | 标签跟着线走、没有独立坐标 |

**修法要点**

- `fig1_layout.py`：`penalty()` 把 **zone 四条边**也当障碍 + **分层罚分**（压线 ≫ 贴线 ≫ 浮动）；
  `trunk_x` / `lane_b` 改**共用一套槽位**，从根上消掉跨主干共线；
- `gen_flow_diagram.py`：图例**拆三行放左上角**；回边终点改用**菱形斜边求交**（不再悬空）；
  标签默认偏移 **16 / 24 → 21 / 29**；并把「按【开始】重开?」的「是」由 `idle` **改指 `preview`**
  （依据 `rtl/game_fsm.vhd:361-366`）；
- `gen_overview_diagram.py`：六条连线标签**全部改独立 `DL.label` 钉坐标**（不再跟线走）
  + 容器标题 y 与时钟块高微调 + 标题按**字宽居中**。

**客观自测（渲染级，不靠肉眼）**：三张图都跑过「**强调色文字块内是否含深色线像素** + 文字到最近深色像素的距离
（阈值 **10 画布 px**）」⇒ **0 处文字被线穿过**；`fig1` 另过 `gen_design_diagram.py --check`：
**SCORE 744.26**（原 823.86）、**跨主干共线 0 对**、**标签重复 0 组**。

**复核轮（同一批 3 个验收员，只读复看最终版）**：fig1 → **PASS**（A/B/C 全部解决：段/位选 0→13.98、复位键 12.45、
判定/推进 13.14、选择→ROM 13.13、选择→引擎 13.52、帧平面 13.78；共线 0 对；重复 0 组）；fig_overview → 复核发现
**返工把「控制」「帧平面」两个标签放到了时钟 tap 的行程上（新穿字）**，已改为：**rom / aud 的时钟 tap 从列间空隙
（818 / 1160）改到块中心（1100 / 1330）直落块顶、只穿过 `core` / `dsp` 方框（被压住）**，把 `800..860` 与
`1140..1215` 两个空隙完整让给标签；`dsp` 块右移 15 px（`1200→1215`）、容器宽 `1420→1440`；标题/副标题改用
`DL.label(..., align="center")` 真正居中（不再依赖字宽估算）。fig_game_flow → 复核发现两处净距仍差一点，已修：
「全系统静默熄灭」框高 `96→113`（pre-YS，≈88 画布 px，框内三行上下留白各 ≈7 px）、`lb22` 的「否」手工钉到
`(844,1809)`（到 `lvlq` 菱形左下斜边 9.5→≈12 px）、`lb11` 的「是」钉到 `(874,1008)`。

> ⚠️ **渲染级自测工具的两个坑**（`.tmp/render_check.py`，Lead 已修）：
> 1. 距离必须用**欧氏**：原来按方环（切比雪夫）逐圈找，对斜线会**高估**（实测 `lb22` 方环 28 px 判合格，
>    真实欧氏只有 22.8 px = 9.5 画布 px）；
> 2. 文字块高度过滤上限要放到 **44**（单连通块的「是」字渲染高约 37~38 px，卡在 36 会被整块丢掉）。
> 另外它内置的"画布坐标"换算偏移是**按图写死**的（`fig_game_flow` 重出后 PNG 宽度 4110→4204，偏移从
> `(-82.5,+38.4)` 变成 `(+9.0,+37.5)`），引用它的坐标前必须先反解一遍。

**已知取舍（诚实记录残余，是取舍不是待办）**

13. ⚠️ `fig1_system_architecture` 仍有 **10 / 17** 个主干信号组名 `d_own > 30 画布 px`（口径 = 标签矩形到
    **自己那条主干折线**的最短距离；最远：「选择→ROM」**87.0**、「选择→引擎」**71.0**、「零片掩码」**65.5**、
    「段码」**59.5**）—— 是被两条硬约束挤出来的：**通道净宽被 7~8 根竖线占满**、且**必须离分区虚线 ≥ 10 px**，
    放不下 78 ~ 88 px 宽的标签。取舍口径是「**宁可浮动也不压线**」：压线会被渲染级检查判死，浮动只是看着不贴身；
14. ⚠️ `fig_game_flow` 底部空白带 `y = 1505` 与 `lall → lsolved` 的竖线有 **1 处 90° 交叉** ——
    交叉处**没有标签邻近**（最近的「是」在 34 画布 px 外），属正常流程图的线交叉，不做处理；
    （复算：`python -c "import sys;sys.path.insert(0,'scripts');import gen_flow_diagram as G;
    print(G.pts_of('ltime','b','bus','b',[(1560,1278),(1560,1930)]));
    print(G.pts_of('lall','b','lsolved','t',[]))"`）
15. ⚠️ `fig1_system_architecture` 的 `ext_*` 浅灰框**框内文字到自身框边**的留白：水平口径下
    `ext_dot`「ROW/COLR/COLG」**7.7** 画布 px（其余 6 个 ≥ 11.6）；若改成"四向最小"口径则
    `ext_kp` 8.9 / `ext_seg` 9.2（都是下沿，被 `g`、`/` 的降部吃掉）。是框内边距、不是线穿字；
    再放大只能加宽 `ext_*` 框，而 `channel(0)` 只剩 46 px 要分给两根主干，故不再动。

**第三轮（2026-10-23，多 agent 工作流审查：5 个独立审查员 + 5 个对抗复核员）**
工作流对「三张图 + 脚本 diff + 文档/提交包」五路并行审查，再让另一名 agent 逐条证伪；19 条发现中 18 条
被确认为真，已全部处理：

- **`fig_game_flow` 的语义按 RTL 重画**（本轮最重的一条）：原图把「过关 S_WIN」画成每关必经、之后才判
  「关卡 < 3？」，与 `rtl/game_fsm.vhd:337-349` 相反（第一、二关拼对是 `level/lvl3` 置位后直接回
  `S_PREVIEW`，只有第三关才 `st <= S_WIN`）。现在拆成 **「全部零片已锁定？ → 全图并集 == 目标图案？」**
  两级判据（补上 `:350-352` 的 `i_all_lock` 分支：**全锁但拼错 → 立刻失败**），并把「过关 S_WIN（第三关）」
  放到「关卡 < 3？」的**否**支；「按【开始】重开?」补了**否**支（回到结算画面）与标签。
  报告 §2.4 的 S_WIN / S_FAIL 两段同步改写。
- **`fig_game_flow` 的箭头悬空**：`start/sw/gokey/lupd/lvlq/again` 的菱形中心原为 870/870/870/790/870/870，
  与下方矩形的 830 错开 ⇒ `lupd→lwin`、`win→lvlq` 两支箭头的尖端悬在菱形斜边上方 ~24 px。现在
  **所有菱形/矩形中心一律取 830**，竖线不再需要折点，箭头正落在顶点上。
- **`fig_game_flow` 的容器圆角**：draw.io 对 1220×702 的框默认给 ~104 px 圆角，弧线切进标题
  「对局循环 S_PLAYING…」；改为显式 `arcSize=14` + 标题拆两行（单行会伸到 x≈854、被 x=830 的竖箭头穿过）。
- **`fig1_system_architecture` 的事实错误**：`arch_data.GLOBALS["glue_row"]` 漏了 `rst`
  （`rtl/puzzle_top.vhd:371` 的 `mrow` 复位），导致图内角标少一个 `rst`、typ §2.2 的
  「消费者 10/8/4、共 22 根」少算 1 → 已改为 **10/9/4、共 23 根**。
- **PNG 与 SVG 两个交付件不一致**：`fig_overview` 的 `taps`（950/1300 vs 1100/1330）与音效码走线、
  `fig_game_flow` 的标签定位（SVG 里还留着"待机框内侧的否标签"）—— 现在 **`label_xy()` / `LABEL_POS` /
  `taps` 都由两边共用**；`fig1` 的 PNG 图例也补齐了 SVG 有的三路来源与消费者计数，并加了
  「晶振 → clk、SW7 → sw7 都有意不画线」一句。
- **`fig1_layout.py` 的死代码**：4b 的 60 轮"共线清零"循环在当前几何下一轮都进不去，且 `level_get`
  对 band 型控制量会 `KeyError` —— 已删除（保留 `h_runs` / `h_conflicts`，5b 仍在用）。
- 渲染级自测工具的两个坑（欧氏距离、文字块高度上限、强调色阈值 76）也一并修了，见上面那段引用块。


上述生成图的**方框集合、文件名、网名、位宽、端口名**全部从 `facts/facts.json` 与
`rtl/puzzle_top.vhd` 现算，`--check` 会逐条对账 ⇒ "与代码一致"是按构造保证的；
流程图的六个状态、三个判据信号、四个限时常量也与 `game_fsm.vhd` / `puzzle_ctrl.vhd` /
`puzzle_pkg.vhd` 对账。改完 RTL 记得重跑对应的生成脚本（它们还会顺手刷新
`docs/assets/images/` 下的站点副本）。

**量化记录（改造前后，同一把尺子）**：旧版 `fig1` 跑 `audit_diagram` 得到 **35 个 ERROR**
（32 处线穿方框 + 3 处标签重叠）、16 处交叉、55% 空白、`SCORE 4156`；
新版 **0 ERROR / 0 穿框 / 0 标签冲突 / 0 标签压线**（`audit_diagram` 口径）。`SCORE` 演进：
**893.86**（2026-10-22 的"总线主干 + 只标信号组名"版）→ **823.86**（本轮整改前）→
**744.26**（第二轮视觉验收后；`gen_design_diagram.py --check` 实测，本轮已独立复核 ①数据对账/②几何体检/③端口名 三关全 PASS）。
⚠️ `audit_diagram` 之外还有一道**更严的渲染级检查**（"文字块内不得含深色线像素、且离最近深色像素 ≥ 10 画布 px"），
见上面「第二轮独立视觉验收」一节。数字与命令见 `.tmp/cand/BASELINE.md`。

> ⚠️ **不要用 PowerShell 的 `Get-Content | Set-Content` 改这些脚本**：
> `-NoNewline` 会把整个文件的行首尾连成一行（2026-10-22 因此重写过一次
> `gen_flow_diagram.py`）。改文件用 `edit` 工具或 Python 显式 `encoding="utf-8"`。

> `docs/report/fig2_game_fsm.*`、`fig3_puzzle_core.*`（状态机图与引擎图）也随设计方案交付。

**一条命令跑完整条链**（Typst 不在 PATH 也没关系，脚本会下载固定版本到 `.tmp/tools/typst/`）：

```powershell
python scripts/build_report.py            # 编译 PDF + 生成 md + 同步 docx
python scripts/build_report.py --check    # 只校验四件套是否同步（不写盘、不下载）
```

### 个人上交版（封面只留 姓名 / 学号 / 报告日期）

真实姓名和学号**只作为命令行参数**，不会写进仓库任何文件；产物**必须**写到仓库外
（`--out` 必填），脚本会**拒绝**把产物写进仓库目录：

```powershell
python scripts/build_report.py --submission --name 张三 --id 2024000000 `
    --out "C:\Users\me\Desktop\上交\张三_实验报告.pdf"
```

实现方式：`docs/report/template.typ` 的 `minimal_cover` 参数控制封面显示哪几项，
`.typ` 顶部用 `sys.inputs` 读取 `--input` 传入的值；不带 `--input` 编译时，
封面就是入库版的 8 字段占位符（`课题组成员 / 202300000000 / 实验指导教师组 / 【评定中】`）。

> ⚠️ **仓库里只留占位符版本**。`.gitignore` 已加 `*个人上交版*` / `docs/report/_submission*`
> 等第二道防线，但真正的保障是"产物写在仓库外"这条约定。

---

## 10. 已知取舍

| 取舍 | 原因 |
|:---|:---|
| `docs/图/SIM-*.svg` 不在站内使用 | 是脚本按跳变画出的示意图，多数信号在整段时基上是平线，读不出信息；站内统一用 Quartus 截图（`GUI-*.png`）作为证据 |
| `docs/assets/images/GUI-*.png` 是裁过的 | 裁掉了窗口标题栏、工具条、左侧工具栏和空白行，只留时间轴 + 信号名 + 波形；**原始截图仍在 `docs/图/`**（`GUI-build-area` / `GUI-build-timing` 两张的原始图在 `docs/report/GUI-编译-*.png`） |
| 首页放的是规则模型重放 GIF | 不是板子实录，图注里已明确标注；用来让人 3 秒明白这游戏长什么样 |
| `docs/` 下保留 MkDocs 时代的证据 md 与报告四件套 | 被 `extract_facts.py` / `audit_evidence.py` 读取，删了会破坏事实模型对账；它们不发布，所以不影响线上 |
| 站内目前没有代码块 | 仍保留了 `prism-vhdl` 与 copy-code 插件（合计约 5 KB），硬件文档后续补 VHDL 片段时直接可用 |
