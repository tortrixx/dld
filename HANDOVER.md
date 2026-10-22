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
| `.pdf` | `typst compile`（交付主件，28 页） |
| `.md` | `scripts/gen_report_md.py`（封面与正文都从 `.typ` 派生） |
| `.docx` | `scripts/sync_report_docx.py`（幂等同步，收敛后重跑是 0 变更） |

### 另外两个交付件：平台「实际设计方案」的作答稿与三张设计图

课程平台除了报告，还有一步「实际设计方案（10 分）」，要求**框图与实现电路(代码)一致**。
老师两次反馈过这张图：先是"更像流程图、缺模块间信号"，重画后又指出"**渲染出来的架构图不好**" ——
所以最终版把这件事拆成**三层**，每层只干一件事：

| 层 | 文件 | 职责 |
|:---|:---|:---|
| **数据（唯一事实源）** | `scripts/arch_data.py` | 方框集合（11 entity + 7 板载 + 2 顶层胶合）、35 组连线 / 60 个 `(源,目标,网名)` 三元组、每个模块消费的全局网络 —— 全部从 `facts/facts.json` 与 `rtl/puzzle_top.vhd` 现算，人工只能读不能改 |
| **布局（只管画）** | `scripts/fig1_layout.py` | 六列分层 + 空通道正交走线 + 顶部干线带 + 标签自动避让；产出 SVG **和** 一份 `layout.json` 供对账 |
| **裁判（客观体检）** | `scripts/audit_diagram.py` | 读 `layout.json` 做 16 项几何检查：线穿框、标签压框/互压、端点是否落在框边、越界、交叉数、空白率、对齐…；`--fidelity` 再和 `arch_data` 逐条对账 |

`gen_design_diagram.py` 只是个壳：**写盘之前必须连过三关**（① 数据对账 ② 几何体检 ③ 端口名核对），
过不了就不写盘。

| 交付件 | 怎么来 |
|:---|:---|
| `docs/report/fig1_system_architecture.svg/.png` | `scripts/gen_design_diagram.py`：**方框 = entity**，箭头 = 顶层端口连接（网名[位宽]），全局网络用角标。报告 §2.2 与站点 `docs/assets/images/` 用同一张 |
| `docs/report/fig_game_flow.svg/.png` | `scripts/gen_flow_diagram.py`：**规范流程图**（圆角=起止 / 矩形=处理 / 菱形=判断），对局循环用容器框 + 「回循环」总线 |
| `docs/report/实际设计方案-模块设计一览.svg/.png` | 同上（11 格，逐模块给端口与设计要点） |
| `docs/report/实际设计方案.md` | **手写**：游戏流程 → 设计方法 → 总体框图 → 各模块设计 → 信号传递表 |

这三张图的**方框集合、文件名、网名、位宽、端口名**全部从 `facts/facts.json` 与
`rtl/puzzle_top.vhd` 现算，`--check` 会逐条对账 ⇒ "与代码一致"是按构造保证的；
流程图的六个状态、三个判据信号、四个限时常量也与 `game_fsm.vhd` / `puzzle_ctrl.vhd` /
`puzzle_pkg.vhd` 对账。改完 RTL 记得重跑这两个脚本（它们还会顺手刷新
`docs/assets/images/` 下的站点副本）。

**量化记录（改造前后，同一把尺子）**：旧版 `fig1` 跑 `audit_diagram` 得到 **35 个 ERROR**
（32 处线穿方框 + 3 处标签重叠）、16 处交叉、55% 空白、`SCORE 4156`；
新版 **0 ERROR / 0 穿框 / 0 标签冲突**，80 处交叉、40% 空白、`SCORE 958`。
数字与命令见 `.tmp/cand/BASELINE.md`。

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
