# `docs/图/` —— 图目录索引 + **Quartus GUI 实测仿真图拍摄流程**

> 这份文件是 `docs/图/` 的**唯一清单所有者**：`docs/03-仿真验证方案.md` §3.1 与
> `HANDOFF.md` §4.1 都只写"见 `docs/图/README.md`"，具体文件名与状态以本文件为准。

---

## 0. 先分清两类图（**这一条最容易出错**）

| 类别 | 文件名 | 怎么来的 | 能不能当"实测仿真图"交 |
|---|---|---|---|
| ⭐ **Quartus GUI 实测截图** | `GUI-<模块>.png` | 在 **Quartus II 波形编辑器界面**里打开 `sim/<模块>.vwf` 后截屏 | ✅ **报告里只能用这一组** |
| 脚本渲染的辅助波形 | `SIM-<模块>.svg` | `scripts/sim.py` 解析 `.vwf` 后**用 Python 自己画**的矢量图 | ❌ 不是 Quartus 界面，**不能当实测截图** |
| 板子/画面照片 | `结算画面-预览.png` 等 | 上板实测或设计稿 | 按用途单独说明 |

**为什么必须有 GUI 截图**：`SIM-*.svg` 的像素是脚本画的，别人无法确认它没有被脚本"美化"；
而 Quartus 界面截图里带着**菜单栏、工程名、节点名列表、时间刻度**，是软件本身渲染的，可信度不同。
两者**不是**二选一 —— `SIM-*.svg` 留作"逐点比对"的辅助证据（`sim/rounds/*.md` 会链它），
报告正文的仿真波形图用 `GUI-*.png`。

### 0.1 ⚠️ 截图前必读：**只留波形编辑器那一片，标题栏/菜单栏/各面板一律裁掉**

Quartus 的标题栏写的是**完整工程路径**，里面带**你的 Windows 用户名**：

```
Quartus II - C:/Users/<你的用户名>/Desktop/dld/quartus/puzzle - puzzle - [../sim/clk_gen.vwf]
```

把它截进图里，就等于把**本机绝对路径 + 用户名**发到公开仓库 —— 而本项目的既有纪律是
**"全仓库不出现作者本机绝对路径"** —— 出处是 `PROGRESS.md:85`（第 19 工作阶段的验收口径，
不是 `HANDOFF.md` §0）。⚠️ 那句"文本文件已经 `git grep` 0 命中"**当时并不成立**：2026-10-15 复核
**以本机用户目录前缀**（盘符 + 用户目录那一段，本节一律写成占位符 `<本机用户目录前缀>`、
**不把字面模式抄进来 —— 抄进来就会命中这一行自己**）检索**命中 `refs/README.md`（31 行）**，
已在本轮把那些路径脱敏成 `<本机用户目录>\...` 写法（保留全部文字、表格与事实）。
⭐ **脱敏后文本侧复核 = 0 命中**（⭐ **这个"0 命中"只有"模式里带用户名"才立得住**）：本文**只写占位符
`<本机用户目录前缀>`，不把检索用的字面模式抄进来** —— 实测过：任何**会被自己命中的模式**
（只到"盘符 + 用户目录"这一段）写进本文，`git grep -F` 就会**命中这一行自己**
（2026-10-15 实测：那种写法只输出 `docs/图/README.md` 一条自命中，**不是**真有路径泄漏）。
所以本节给的**可实证判据**是：**带用户名的整体前缀**（本机盘符 + `用户目录那一段` + 用户名，
**本文不写出这个字面串**）`git grep -c -I -F` ⇒ **0 命中**（退出码 1）；配合
`git grep -n -I -F '<本机用户目录>'` 的结果 —— 只有 `refs/README.md`（**31 行**脱敏后的占位符）
与本文这 2 行**命令示例**，**没有一条带盘符、带用户名的真实路径**
⇒ **提交后的树里没有任何一条真实本机路径**
（⚠️ **git 历史里的旧提交仍含这些路径**，历史重写需另行决定，本轮不动历史）。
⚠️ 文本文件查得到，**PNG 是二进制，`git grep -I` 看不见** —— 所以这一条**只能靠人手动保证**。

**做法（2026-10-15 定稿口径）**：图里**只保留波形编辑器那一片**：

| 必须保留 | 必须裁掉 |
|---|---|
| `.vwf` 文档标题条/标签栏、`Master Time Bar` 一行、`Name` 节点列表、波形网格 + 时间刻度 | 窗口标题栏、菜单栏、工具栏、左侧 `Project Navigator` 与 `Tasks/Flow`、底部 `Messages` 面板、状态栏 |

实现上**不要用"固定裁掉顶部 N 像素"**：先量出 **MDI 客户区**（`MDIClient` 子窗口）的实际矩形，
把本文档子窗口 `SetWindowPos` 铺满它，再按 `Ctrl+W`（Fit in Window）后按该矩形裁剪主窗口位图。
本机实测：主窗口 `(-8,-8)-(1715,1027)`、`MDIClient (246,74)-(1707,760)`、裁剪起点 `(254,82)`、
成品 **1461×686**（12 张统一）。`docs/图/GUI-*.png` 就是这套口径的成品，可直接对照。
⚠️ 实测坑：传给 MDI 子窗口的 `SetWindowPos` 坐标被 Quartus 当成"**相对 MDI 客户区**"（传 `0,0` 才落在原点）。

---

## 1. 为什么"打开 `.vwf` 就有波形"——不用重跑仿真

本工程没有 ModelSim，只有 Quartus II 9.1 内置仿真器（`scripts/vwf.py` 开头有完整说明）。
它的结果是**回写进激励文件本身**的：

```
quartus_sim <工程> --mode=functional --overwrite_waveform=on
        ↓
把每个节点算出来的波形写回 sim/<模块>.vwf 的 TRANSITION_LIST
```

所以 `sim/<模块>.vwf` **既是激励也是结果**，是入库的交付物之一（12 个模块各一份）。
实测抽查：`sim/buzzer_ctrl.vwf` 里输出 `o_buzz` 有 **1455 次跳变**、
`pre_cnt[0]` 有 **336 466 次**跳变 —— 里面确实是真跑出来的波形，不是空白模板。

⇒ **拍图不需要重新编译、不需要重新仿真**，打开就有。

---

## 2. 清单与当前状态

目标：**12 张** `GUI-<模块>.png`，一张一个模块。

| # | 目标文件名 | 打开的源文件 | 这张图在报告里证明什么 | 状态 |
|---|---|---|---|---|
| 1 | `GUI-clk_gen.png` | `sim/clk_gen.vwf` | 分频链（1 kHz → 200 Hz → 100 Hz → 4 Hz / 2 Hz / 1 Hz / 40 Hz）与按键消抖计数 | ✅ 已拍（2026-10-15，1461×686） |
| 2 | `GUI-keypad_scan.png` | `sim/keypad_scan.vwf` | 4×4 键盘扫描四状态机 + 消抖 + 按键按下/释放 | ✅ 已拍（2026-10-15，1461×686） |
| 3 | `GUI-seg_scan.png` | `sim/seg_scan.vwf` | 数码管位选/段选扫描与 5 个字母的段形 | ✅ 已拍（2026-10-15，1461×686） |
| 4 | `GUI-dot_matrix_scan.png` | `sim/dot_matrix_scan.vwf` | 8×8 点阵行扫描（125 Hz）与行序 | ✅ 已拍（2026-10-15，1461×686） |
| 5 | `GUI-rng_lfsr.png` | `sim/rng_lfsr.vwf` | LFSR 伪随机序列（x⁸+x⁶+x⁵+x⁴+1，周期 255） | ✅ 已拍（2026-10-15，1461×686） |
| 6 | `GUI-pattern_rom.png` | `sim/pattern_rom.vwf` | 图案库按 `i_pat` 查表输出 | ✅ 已拍（2026-10-15，1461×686） |
| 7 | `GUI-piece_rom.png` | `sim/piece_rom.vwf` | 零片形状库按（形状/朝向）查表输出 | ✅ 已拍（2026-10-15，1461×686） |
| 8 | `GUI-disp_format.png` | `sim/disp_format.vwf` | 状态 → 8 位数码管内容 + **熄灭掩码**（`o_data`/`o_blank`）：待机/预览/对局/结算各态、倒计时两位拆分，以及 ⭐ **口径 C：`DISP2` 在所有窗口都熄灭（断言 ⑥c）**；**同一条波形也覆盖自检态的八位全 8** | ✅ 已拍（2026-10-15，1461×686） |
| 9 | `GUI-game_fsm.png` | `sim/game_fsm.vwf` | 主状态机 S_IDLE→预览→对局→胜负 的迁移与计时 | ✅ 已拍（2026-10-15，1461×686） |
| 10 | `GUI-puzzle_ctrl.png` | `sim/puzzle_ctrl.vwf` | 拼图引擎：重叠判定 / 选中锁定 / 旋转 / 整帧判据 | ✅ 已拍（2026-10-15，1461×686） |
| 11 | `GUI-buzzer_ctrl.png` | `sim/buzzer_ctrl.vwf` | 音效：音高表查表 + 方波计数 + 三关 BGM 乐句 | ✅ 已拍（2026-10-15，1461×686） |
| 12 | `GUI-puzzle_top.png` | `sim/puzzle_top.vwf` | 整机：三关流程 + 告急幽灵（绿 + 2 Hz 闪） | ✅ 已拍（2026-10-15，1461×686） |

> 每张图对应的**断言明细**在 `sim/rounds/<模块>/rNN.json`（机读）与 `rNN.md`（人看），
> 逐模块的"当前轮次 + 条数"总表在 `docs/03-仿真验证方案.md` §2 / §4。

### 2.1 拍图前自检：12 个 `.vwf` 里都真的有波形吗？

⭐ **本仓库里的 12 个 `.vwf` 都是 2026-10-15 那一轮全量重跑时由 Quartus 回写的**
（对应当前固件：口径 C / `SEED 8` / 1264 LE），**打开就是最新波形**，不需要重新仿真。
`.vwf` 的回写格式是嵌套的 `TRANSITION_LIST { NODE { REPEAT=n; LEVEL … FOR …; } }`，
所以"内容很多"会体现为**段数（`TRANSITION_LIST` 块）**，而不是行数。实测：

| 模块 | `.vwf` 大小 | `TRANSITION_LIST` 段数 | 模块 | `.vwf` 大小 | `TRANSITION_LIST` 段数 |
|---|---|---|---|---|---|
| `clk_gen` | 20 737 B | 40 | `disp_format` | 36 959 B | 60 |
| `keypad_scan` | 42 842 B | 47 | `game_fsm` | 66 611 B | 54 |
| `seg_scan` | 66 190 B | 88 | `puzzle_ctrl` | 1 038 407 B | 592 |
| `dot_matrix_scan` | 28 079 B | 51 | `buzzer_ctrl` | 388 246 B | 34 |
| `rng_lfsr` | 54 549 B | 20 | `puzzle_top` | 646 571 B | 1271（⚠️ **8 段子仿真拼接**，见下注） |
| `pattern_rom` | 29 540 B | 67 | `piece_rom` | 123 855 B | 284 |

> ⚠️ **"段数"要分两种读**：**不含子仿真的 `.vwf`**（如 `puzzle_ctrl`：592 段 = 592 个观测节点）里，**一个 `TRANSITION_LIST` 段就是一个被观察节点的完整波形**；
> 但 **`puzzle_top.vwf` 是 8 段子仿真拼接的**（注释 `/*transitions from sub-simulation number 2..8*/`，连同第 1 段共 **8 段**）——
> **第 1 段 165 个节点、其余 7 段各 158 个节点**（多出的 7 个是只在第 1 段出现的激励：`clk` / `sw7` / `btn` / `kp_row[0..3]`）
> ⇒ **1271 段 = 158 × 8 + 7**，而**唯一节点名只有 165 个** ⇒ **在这个文件上"段数 ≠ 节点数"**。
> 另外，`REPEAT` 会把重复段压紧，
> 所以段数不多不代表内容少 —— 例如 `i_clk` 只有 1 段，但里面是 `REPEAT = 23000` 的 10 ns 翻转）。
> 想自己复核：`Select-String -Path sim\*.vwf -Pattern "TRANSITION_LIST" | Group-Object Filename`。

### 2.2 ⭐ 评分项④「资源利用」要的**编译报告截图**（1~3 张，另一类图）

评分项 ④ 原文是"实际实现功能说明及**资源利用情况（编译报告截图）**"——它要的不是仿真波形，
而是 **Quartus 编译报告**的截图。建议拍 **2 张**（文件名自定，别和 `GUI-*.png` 混）：

| 建议文件名 | 在哪拍 | 要截到的关键行 |
|---|---|---|
| `GUI-编译-面积.png` | Quartus `Processing → Compilation Report` → `Fitter → Summary`（或直接打开 `quartus/output_files/puzzle.fit.rpt` 的 `Fitter Summary` 段） | **Total logic elements 1,264 / 1,270 ( 100 % )**、**Total LABs 127 / 127 ( 100 % )**、Total pins 52 / 116 |
| `GUI-编译-时序.png` | `Compilation Report → Timing Analyzer → Summary`（TimeQuest；或 `quartus/output_files/puzzle.sta.rpt` 的 Fmax Summary 段） | **Fmax Summary = 54.27 MHz**、**Clock Setup 'clk' 的 slack +1.572 ns**（hold +1.078 ns）、违例 **0 条** |

> ⚠️ 截图同样**要裁掉标题栏**（含本机用户名，见 §0.1）。
> ⚠️ **浏览器/文本编辑器里截 `.rpt` 也能用，但 Quartus 界面里的更稳**（报告名、工程名都在图里）。
> ⭐ 数字的唯一真值源是 `quartus/build_provenance.json` 与 `docs/05` §1A'''''（**1264 LE / 54.27 MHz / +1.572 ns**）；
> 截图前先扫一眼那两个地方，避免拍到旧报告（`output_files` 里只会有一份当前的 `fit.rpt` / `sta.rpt`）。

---

## 3. 操作流程 A：手动拍（**推荐**，12 张约 20 分钟）

### 3.1 准备（只做一次）

1. **打开 Quartus II 9.1**
   - 开始菜单 → `Quartus II 9.1`；或直接运行
     `C:\QuartusII91\QuartusII91\quartus\bin\quartus.exe`
2. **打开本工程**：`File → Open Project…`（快捷键 **Ctrl+J**）→ 选
   `<仓库>\quartus\puzzle.qpf`（也可以直接在资源管理器里双击这个 `.qpf`）
3. **关掉 `Tips & Tricks` 浮窗**（右上角 `×`），否则它挡住半个屏幕
4. **把 Quartus 窗口最大化**
5. **让波形编辑器占满主区**（关键，能让一屏多显示 3 倍信号）
   - 第一次打开任意 `.vwf` 之后，波形编辑器是**浮动的**小窗；
   - **双击它的标题栏**，它会停靠（dock）进主区，成为一大块；
   - 之后每次打开别的 `.vwf` 都复用这块位置。
6. （可选）**多腾出 ~200 像素高度**：`View → Utility Windows → Messages` 取消勾选，
   把底部消息窗关掉。

### 3.2 每个模块重复这 6 步

1. **`File → Open…`（Ctrl+O）**
2. 定位到 `<仓库>\sim\`，双击 **`<模块>.vwf`**
   - ⚠️ 第一次打开任意 `.vwf` 时 Quartus 会弹一条提示：
     *"Future versions of the Quartus II software will not support the Quartus II Simulator…"*
     → 勾上 **`Don't show this again`** → 点 **OK**。之后不再弹。
3. **`View → Fit in Window`（快捷键 `Ctrl+W`）** ← **最容易漏的一步**
   - 不按它，时间轴默认只显示最前面**几十纳秒**，波形挤成一片黑，什么也看不出来；
   - 按完之后整段仿真时间（如 `buzzer_ctrl` 的 0 ~ 6.7 ms）铺满窗口。
4. （可选）在左侧**信号名列表**里上下滚动，把你报告里要讲的那几行滚进可视区
   - 总线是**折叠**的（如 `i_sel`、`pre_cnt`）；点名字左边的小方块可以展开看每一位。
   - **不需要手动添加节点**：测试台要观察的中间信号（`OBSERVE` 里那些 `BURIED` 节点，
     如 `buzzer_ctrl` 的 `pre_cnt` / `cnt` / `tone_sel` / `on_now`）**已经写进 `.vwf` 的
     节点表**，打开就在列表里。
5. **截图**（抓活动窗口，别抓全屏；**按 §0.1 只留 `MDIClient` 那一片**，本机实测成品 **1461×686**）
   - 先按 §0.1 量出波形编辑器所在的 **MDI 客户区**矩形（本机实测 `MDIClient (246,74)-(1707,760)`）
   - 推荐：**`Alt + PrintScreen`** → 打开"画图" → `Ctrl+V` → **用选择框按上面那个矩形框住波形编辑器那一片**
     （⚠️ **不是"只框菜单栏以下"** —— 菜单栏、工具栏、左侧 `Project Navigator` 与 `Tasks/Flow`、
     底部 `Messages`、状态栏**都不进框**；要保留的只有 `.vwf` 文档标题条/标签栏、`Master Time Bar` 一行、
     `Name` 节点列表、波形网格 + 时间刻度）→ `Ctrl+Shift+X` 裁剪 → 另存为 PNG
   - 或：**`Win + Shift + S`** 框选（**框 §0.1 说的 `MDIClient` 那一片**，**别从菜单栏上沿开始** ——
     菜单栏本身就要裁掉）→ 到画图里 `Ctrl+V` → 另存为 PNG
   - ❌ 不要用单独的 `PrintScreen`（全屏）：会把桌面、浏览器窗口一起拍进去。
6. **另存为 `<仓库>\docs\图\GUI-<模块>.png`** —— 文件名必须与 §2 表里一致
   （模块名、下划线都要对；`docs/03` §3.1 是按 `GUI-*.png` 通配引用的）

### 3.3 想只拍某一段时间（可选）

`View → Zoom…` 会弹一个对话框，可以直接填 **Start / End** 时间；填完点 OK，
时间轴就固定到那一段。适合"只想证明幽灵 2 Hz 闪烁周期"这类细节图。

---

## 4. 操作流程 B：一键脚本（可选，12 张约 2 分钟）

仓库里已经带了一个把上面流程自动化掉的脚本：

```powershell
# 在仓库根目录
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\shoot_vwf.ps1
```

它会：启动（或复用已开着的）Quartus GUI → 逐个打开 `sim/<模块>.vwf` →
按 `Ctrl+W` → 用 `PrintWindow` 抓**主窗口位图** → 存成 `docs\图\GUI-<模块>.png`。

常用参数：

```powershell
# 只拍两个模块
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\shoot_vwf.ps1 -Modules buzzer_ctrl,clk_gen
# 拍完把 Quartus 关掉
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\shoot_vwf.ps1 -CloseQuartus
```

**为什么它比手点更稳**：抓的是**窗口位图**（`PrintWindow`）而不是屏幕像素 ——
窗口被别的窗口挡住、甚至被拖到屏幕外都不影响结果，也绝不会把桌面上的东西拍进去。

⚠️ **已知缺陷（2026-10-15 实测，尚未合并修正）**：本机跑它 **12/12 都报「打开对话框没出现」**，根因两条 ——
① 它只用 `SetForegroundWindow` 抢前台，当别的进程占着前台时**不生效**（`Ctrl+O` 打飞）⇒ 需改用
`AttachThreadInput` 强抢；② `Ctrl+O` 之后只固定等 2.5 s，**没有轮询**等对话框 ⇒ 需改成轮询。
另外它默认只裁顶部 33 px，**已不符合 §0.1 的新口径**（要裁到只剩 MDI 客户区那一片）。
2026-10-15 的 12 张成品不是它拍的，而是用修正版脚本（当时放在 `.tmp/shoot_gui_v27.ps1`，`.tmp/` 不入库）：
强抢前台 → `Ctrl+O` 轮询 → 枚举 `MDIClient` 与本文档子窗口 → `SetWindowPos` 铺满 → `Ctrl+W`
→ `PrintWindow` → 按 `MDIClient` 矩形裁剪。要长期可用，应把这套修正并回 `scripts/shoot_vwf.ps1`。

**其它已知的两点**（不是故障）：

* 脚本可能打印 `!! <模块>：波形编辑器没有切到该文件` —— 这是**误报**：Quartus 把多个 `.vwf`
  开成**标签页**，而脚本比的是面板标题（停留在第一个标签的名字），实际已经切过去了。
  拍完自己扫一眼图确认即可。
* 脚本会把 Quartus 窗口挪到屏幕左上角并调整大小，拍完恢复；运行期间会**抢桌面焦点**，
  建议别在它跑的时候打字。

---

## 5. 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 波形挤成一片黑，看不出周期 | 漏了 `Ctrl+W`（Fit in Window） | 补按 `Ctrl+W` |
| 图里出现桌面/浏览器 | 用了全屏 `PrintScreen` | 改用 `Alt+PrintScreen` 或 `Win+Shift+S` |
| 图里出现 `C:/Users/<你的用户名>/...` | 标题栏没裁掉（**会泄露本机路径与用户名**） | 按 §0.1 只留波形编辑器那一片；⚠️ `scripts/shoot_vwf.ps1` 默认只裁 33 px，**不够** |
| 图里波形只占右下 2/3，左侧/底部一堆面板 | 只裁了标题栏、没裁到 MDI 客户区 | 按 §0.1：量出 `MDIClient` 矩形再裁（成品 1461×686），或先 `View → Utility Windows` 关掉各停靠面板 |
| `docs/03` §3.1 的通配匹配不到图 | 文件名写错（大小写/下划线/模块名） | 严格按 §2 表的文件名 |
| 想看的内部信号找不到 | 总线折叠，或该模块节点太多需滚动 | 点小方块展开；或在信号列表里滚动 |
| 打开 `.vwf` 后提示"不支持内置仿真器" | Quartus 9.1 的固定提示 | 勾 `Don't show this again` → OK |
| 想重拍某个模块 | —— | 重复 §3.2 的 6 步，直接覆盖同名 PNG |

---

## 6. 拍完之后

1. 把 §2 表格里的状态从 `✅ 已拍（2026-10-15，1461×686）` 改成 `✅`（**本文件是清单所有者，只在这里改**）；
2. 确认 12 个文件名一个不缺：
   ```powershell
   Get-ChildItem docs\图\GUI-*.png | Select-Object Name, Length
   ```
3. 提交：
   ```powershell
   git add docs/图/GUI-*.png docs/图/README.md
   git commit -m "docs(fig): 补 12 张 Quartus GUI 实测仿真波形截图"
   ```
   ⚠️ 图是二进制，`.gitattributes` 里已有 `*.png binary`，不会被行尾转换。

---

## 附录 A · 站点用的两个"非 Quartus"素材

上面 §2 的 12 张 `GUI-*.png` 是**Quartus 界面实测截图**清单。展示站还用到两个不由 Quartus 产出的素材，
它们的"清单所有者"也是本文件，所以在这里一并登记：

| 文件 | 规格 | 怎么来的 | 性质 |
|---|---|---|---|
| `演示-跑一局.gif` | 640×420 · 48 帧 · 14.1 s · 290 KiB · 循环 | 由已退役的站点生成脚本产出（`site/scripts/gen-demo-frames.ts` → `render-demo-gif.py`，该目录已随站点重做删除；素材本身保留） | **规则模型渲染，不是板子实录** |
| `dld-架构.drawio` | 纯文本 XML · 56 个元素（31 框 / 25 连线） | 由已退役的 `site/scripts/gen-architecture-drawio.mjs` 生成（目录已删除，此后请直接手改本文件） | 架构与数据通路图，可在 app.diagrams.net 打开编辑 |

⚠️ 口径提醒（同 §0）：这两个素材都**不能**当作"Quartus 实测仿真图"引用。
演示 GIF 的图注在站点上也明确写了"非板子实录"。
