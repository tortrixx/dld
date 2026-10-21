# 《简易拼图游戏》Docsify 站点与答辩文档交接手册 (Handover Document)

---

## 1. 任务背景与目标定位

- **课题名称**：《数字电路与逻辑设计实验（下）》题目4：简易拼图游戏设计与实现
- **硬件平台**：Altera MAX II EPM1270T144C5 CPLD（无嵌入式 RAM，无微处理器软核）
- **核心逻辑指标**：
  - 逻辑单元：**1,264 / 1,270 LE (99.53%)**
  - 逻辑阵列块：**127 / 127 LAB (100.00%)**
  - 物理引脚：**52 / 116 Pins (44.83%)**
  - 静态时序：**Fmax = 54.27 MHz**（基准时钟 50.000 MHz，Setup 余量 +1.572 ns）
  - 验证覆盖：12 套测试台、**184 条断言** 100% 自动化通过
- **交付目标**：
  基于 Docsify 构建一套纯静态、极简清新绿色风格的技术文档，部署在 GitHub Pages（`https://tortrixx.github.io/dld/`）。文档用于深入理解各硬件大模块原理、仿真波形分析，并专门辅助学生在实验答辩时应对老师的随机抽检提问。

---

## 2. 用户核心诉求与历史反馈复盘

接手本任务的 Agent 请务必**仔细研读以下用户真实诉求与批评**，避免重蹈覆辙：

### 第 1 轮反馈：基础框架与答辩要求
- **用户要求**：按实验报告分模块撰写 Docsify，结合仿真图、信号传输、代码原理，语言必须能让自己理解，能在答辩时借助网页回答老师随机挑模块提出的问题。配色简约好看。
- **前期操作**：清理了旧版 MkDocs（73 个文件），切换为 Docsify，但当时按 13 个小底层实体（`clk_gen`、`keypad_scan` 等）碎片化划分，且加入了常规网站的首页、故障排查、源码等内容。

### 第 2 轮反馈：内容繁杂批评
- **用户批评**：“内容种类太多、太杂了，完全没必要加上‘首页’、‘故障排查’、‘源码’等内容，你只需要给出分模块依据仿真、代码等数据写的文档！同时配色改为简洁的绿色。一切简洁明了，不要把其他杂内容写上，最重要的是分模块讲解，其中的内容需要让我以及每个人看到后能理解！”

### 第 3 轮反馈：形式与模块粒度严肃批评
- **用户批评**：“目前感受还是不行，内容中小图标太多、AI味太重，你去搜索并参考几个优质的使用 Docsify 搭建的网页，看看他们的设计。还有一个问题：我说的分模块是指报告中的大模块，不是那十多个小模块！你需要进行全面改进，不需要项目导览和工程专项这几个没有啥用的内容，你只需要给出每个‘大模块’的设计、原理、仿真分析等内容，明白了吗？”
- **执行动作**：重新按照《实验报告》§2.2 的大模块架构重构为 6 篇文档，清除 Emoji，切换翡翠绿配色。

### 第 4 轮反馈（当前）：用户仍不满意
- **用户反馈**：“目前修改还是不行，你把交接文档写好，我换一个agent继续这份任务”

---

## 3. 深度复盘：当前修改仍被判“不行”的潜在原因

接手 Agent 在着手修改前，请重点从以下三个维度反思与突破：

### 原因一：视觉审美与“Docsify 优质感”仍有差距
- 虽然修改为绿色配色并删除了 Emoji，但界面可能仍显得单调或平铺直叙，缺乏优质开源文档（如 Vue、Tailwind、Stripe 风格或使用 `docsify-themeable` 的现代文档）的高级留白感、现代字体排印（Typography）与精美卡片感。
- 建议接手 Agent 可以尝试接入 **`docsify-themeable` (Simple Light)** 或更精致的主题包，重新设计侧边栏呼吸感、内容区最大宽度与波形图画廊展示效果。

### 原因二：文字叙述的“通俗性与人话感”依然不足
- 用户反复强调：**“语言一定要能让我自身能理解”、“让我以及每个人看到后能理解”**。
- 当前文档虽然技术细节极度严密，但可能充斥过多硬核理论、公式与长段落，学生在答辩现场紧张时，难以在 3 秒内一眼扫到“最直白、最容易脱口而出的一句话核心结论”。
- 建议接手 Agent：在每个模块开头和每个问答中，**先用 1~2 句大白话讲透原理（例如‘为什么不用门控时钟？因为门控时钟像用开关切断水管会产生水锤震荡一样，会产生纳秒级毛刺导致芯片误动作’）**，再辅以专业参数，兼顾通俗度与专业度。

### 原因三：答辩针对性与波形图结合形式待深化
- 老师现场随机抽一个模块提问时，学生对着网页需要的是：
  1. 这个大模块一句话概括是干嘛的？
  2. 核心波形图里，哪个尖峰/哪个跳变点代表什么动作？（在图中或图文对照中极为直观标注）
  3. 老师最喜欢问的“坑”在哪里？（防被问懵）
- 如果文档缺乏视觉引导，学生依然不知道怎么借助网页来回答问题。

---

## 4. 当前代码库与站点资产现状

### 4.1 Git 状态
- **分支**：`main`（已同步至远程 `origin/main`）
- **最新 Commit**：`7574cf5 feat(docs): restructure docsify into 6 major subsystems aligned with report §2.2, refine minimalist green theme, remove emojis and ai jargon`
- **在线站点**：`https://tortrixx.github.io/dld/`（已通过 GitHub Actions 自动化构建部署，HTTP 200 OK）

### 4.2 目录树结构
```
dld/
├── .github/workflows/pages.yml   # Docsify 自动化部署工作流
├── facts/facts.json              # 硬件事实模型（唯一真值源，184 条断言）
├── scripts/extract_facts.py      # 事实模型对账脚本（运行 python scripts/extract_facts.py --check）
├── vhd/                          # 11 个 VHDL 源码文件 + 1 个 package
├── docs/
│   ├── index.html                # Docsify 入口与插件配置
│   ├── _sidebar.md               # 侧边栏结构
│   ├── README.md                 # 首页索引与全景对账表
│   ├── assets/
│   │   ├── custom.css            # 当前绿色自定义样式表
│   │   └── images/               # 40+ 张原生仿真截图与系统架构图
│   ├── report/
│   │   └── 实验报告_题目4_简易拼图游戏.md  # 课程实验报告原文（文字核心参考）
│   └── subsystems/               # 6 大硬件子系统文档
│       ├── 01_system_top.md      # 系统顶层集成与全局架构 (puzzle_top & puzzle_pkg)
│       ├── 02_clock_keypad.md    # 时钟使能与键盘输入子系统 (clk_gen & keypad_scan)
│       ├── 03_game_fsm.md        # 游戏主控与规则状态机子系统 (game_fsm)
│       ├── 04_puzzle_engine.md   # 核心拼图引擎微架构子系统 (puzzle_ctrl)
│       ├── 05_rom_random.md      # 关卡目标图案与零片数据子系统 (pattern_rom, piece_rom, rng_lfsr)
│       └── 06_display_audio.md   # 显示与音效输出驱动子系统 (disp_format, seg_scan, dot_matrix_scan, buzzer_ctrl)
```

---

## 5. 核心大模块对照与事实真值表

接手 Agent 在重写或调整任何文档内容时，**切勿篡改或胡编硬件数据**，所有数据严格与以下真值表对齐：

| 子系统文档 | 对应底层实体 | 资源 / 时钟节拍 | 对应仿真图资产 | 答辩核心关键词 |
|:---|:---|:---|:---|:---|
| **01. 系统顶层** (`01_system_top.md`) | `puzzle_top`<br>`puzzle_pkg` | 52 引脚 / 50 MHz 主时钟 / 0 LE (package 纯函数静态展开) | `fig1_system_architecture.png`<br>`GUI-puzzle_top.png` | 52 引脚对齐、点阵红绿空间混黄色、10s 告急幽灵闪烁、127 LAB 极限饱和 |
| **02. 时钟与键盘** (`02_clock_keypad.md`) | `clk_gen`<br>`keypad_scan` | 7 路使能脉冲 / 单时钟域 / 40 ms 滞回消抖 | `GUI-clk_gen.png`<br>`GUI-keypad_scan.png` | 严禁门控时钟、级联计数省触发器、40ms 判稳消除触点弹跳、单拍脉冲防连击 |
| **03. 游戏主控** (`03_game_fsm.md`) | `game_fsm` | 6 状态 ASM / 1Hz 秒递减 / 4Hz 窗口 / 单进程 | `fig2_game_fsm.png`<br>`GUI-game_fsm.png` | 2.0s 自检、5.0s 预览、倒计时防下溢保护、单拍散落握手、非法状态安全回退 |
| **04. 拼图引擎** (`04_puzzle_engine.md`) | `puzzle_ctrl` | **4690 LE → 1264 LE 面积战役** / 仅 36 触发器 / 1kHz 扫描 | `fig3_puzzle_core.png`<br>`GUI-puzzle_ctrl.png` | 行流式实时渲染、串行分时碰撞检测、包围盒越界截断、等效多解性判定 |
| **05. 图库与随机** (`05_rom_random.md`) | `pattern_rom`<br>`piece_rom`<br>`rng_lfsr` | 纯组合 LUT 查表（零 RAM 芯片）/ 8 位 Galois LFSR / 255 周期 | `GUI-pattern_rom.png`<br>`GUI-piece_rom.png`<br>`GUI-rng_lfsr.png` | CPLD 零嵌入式 RAM、面积守恒证明 (12格/16格)、Galois 优于 Fibonacci 的时序、全零防死锁 |
| **06. 显示与音效** (`06_display_audio.md`) | `disp_format`<br>`seg_scan`<br>`dot_matrix_scan`<br>`buzzer_ctrl` | 64 项查表消灭除法器（26ns → 4.2ns）/ 125 Hz 超临界无频闪 / NCO 音准 < 1.25% | `GUI-disp_format.png`<br>`GUI-seg_scan.png`<br>`GUI-dot_matrix_scan.png`<br>`GUI-buzzer_ctrl.png` | 为什么坚决不用 `/ 10`、125Hz 物理依据 (CFF)、同拍锁存消重影、双色混光、马里奥三曲 |

---

## 6. 接手 Agent 的关键行动建议 (Action Plan)

1. **第一步：重新审视设计风格（Design Polish）**
   - 深入调研优秀的开源 Docsify 文档。可考虑引入 `docsify-themeable` 或重构 `docs/assets/custom.css`，使用更具现代质感的翡翠绿配色、优雅卡片、高质感代码块、波形对照排版。
2. **第二步：优化文字表达的“通俗可读性”**
   - 检查 6 篇大模块文档的语言，避免冷冰冰的教条式文字。
   - 增加**“一句话大白话直击本质”**与**“答辩场景对话式应对”**，确保学生在答辩现场紧张时，一眼看过去就能立刻开口说给老师听。
3. **第三步：波形深度图解与交互引导**
   - 对波形图的核心时间节点（如 0~2s 自检、20ns 单周期脉冲、40ms 消抖稳态、碰撞发生的瞬间）做更加清晰明了的图文锚定。
4. **第四步：本地与远端持续验证**
   - 任何改动后必须运行：
     ```powershell
     python scripts/extract_facts.py --check
     ```
   - 验证无死链、无缺失图片后推送到 GitHub：
     ```powershell
     git add docs/
     git commit -m "style/docs: ..."
     git push origin main
     ```
   - 使用 `gh run watch <run-id>` 观察 GitHub Pages 部署状态并验证上线结果。

---

> **给下一任 Agent 的特别寄语**：
> 本工程底层硬件实现极其优秀（1264 LE 极限收敛、184 条断言全绿、波形完备）。用户当前的根本痛点在于**文档网站的质感与内容表达依然无法达到其心目中的理想效果**。请放下任何形式主义，真正站在一个即将参加硬件课程设计答辩的本科生角度，打磨出一份既赏心悦目、又通俗易懂、能真正帮其在答辩中拿高分的极简硬件文档！
