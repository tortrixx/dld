# 项目介绍（3 分钟）

> 一句话定位：这一页给**答辩用的讲稿骨架**——8 节 PPT 结构（含每节展示哪张图、讲多久），
> 外加一段可以直接背的"3 分钟版项目介绍"。

先说清答辩形式（来自课程幻灯片）：**验收答辩占 50%**，
老师会**从总体框图里随机挑一个模块**，就**代码、仿真波形、设计及实现方法**提问
（依据：`refs/pdf/数字系统设计2026.pdf` 的"9-10 验收答辩"一节、`refs/pdf/…课程说明.pdf` 的评分表）。
所以本页最后给了一张"**每个模块一句话 + 一张图**"的应对表。

## 〇、讲解路径与时间预算

```mermaid
flowchart LR
  S1["1 背景与要求<br/>0:30"] --> S2["2 总体架构<br/>1:00"]
  S2 --> S3["3 核心模块<br/>1:00"]
  S3 --> S4["4 接口与数据流<br/>0:45"]
  S4 --> S5["5 难点与解决<br/>1:30 ⭐"]
  S5 --> S6["6 仿真与硬件演示<br/>1:00"]
  S6 --> S7["7 资源与时序<br/>0:45"]
  S7 --> S8["8 取舍与总结<br/>0:30 ⭐"]
```

**总计 7:00**（留 1 分钟机动 ⇒ 落在要求的 5~8 分钟内）。
⭐ 的两节**不要砍**：第 5 节讲"解决了什么真问题"，第 8 节决定诚实度印象。

## 一、8 节结构（5~8 分钟）

| # | 小节 | 建议展示 | 要强调的结论 | 时长 |
|---|---|---|---|---|
| 1 | **背景与要求** | 题目原文截图 / `docs/00` §1 的 11+5 条表 | 题目 4 的 11 条基本要求 + 5 条提高要求；本设计**基本 11/11、提高 4/4 + A3 半做** | 0:30 |
| 2 | **总体架构** | [系统总体架构](../02-architecture/system-overview.md) 的 Mermaid（或 `../assets/diagrams/dld-架构.drawio`） | 11 个游戏子模块、**单时钟域 + 节拍使能**、`puzzle_pkg` 是设计包不是模块 | 1:00 |
| 3 | **核心模块** | [模块总览](../03-modules/index.md) 的分区表 | 按子系统 S1~S7 分工：时钟/键盘/控制/引擎/图案/显示/音效 | 1:00 |
| 4 | **接口与数据流** | [数据通路与控制通路](../02-architecture/dataflow.md) 的图 | 64 位帧 `o_rowr`/`o_rowg` 怎么经 `eng_fr` → `mrow` 切片 → 点阵；**没有软件 API/总线** | 0:45 |
| 5 | **难点与解决** | [移动与旋转](../05-gameplay/movement-rotation.md) 的四朝向演算表 | 旋转在 **3×3 盒**里做、偏移在一处补回（+6 LE vs **+229 LE**）；"不旋转就拼不出来"是**穷举证明** | 1:30 |
| 6 | **仿真与硬件演示** | `GUI-puzzle_top.png`（整机波形）+ 现场演示（[现场演示脚本](demo-script.md)） | {{fact:sim.totals.assertions}} 条断言 / {{fact:sim.totals.modules}} 个模块；**真实 Quartus 截图 12 张**；板级只有文字记录（**无实拍**） | 1:00 |
| 7 | **资源与时序** | `GUI-clk_gen.png` 或 [资源报告](../07-implementation/resource-report.md) 的表 | **{{fact:build.fit.le}} LE、{{fact:build.fit.lab}} LAB**、50 MHz 约束下 slack +{{fact:build.sta.setup_slack}} ns ⇒ 54.27 MHz | 0:45 |
| 8 | **取舍与总结** | [已知限制与取舍](../01-project/limitations.md) 的总表 | LAB 满载、A3 半做、内容率 25/21 Hz、**无硬件照片**——**主动说出来** | 0:30 |

!!! tip "时间不够时的砍法"
    砍第 3、4 节（改为"细节见文档站"），**不要砍第 5、8 节**：
    第 5 节是"你解决了什么真问题"，第 8 节决定老师对你**诚实度**的印象。

## 二、3 分钟版项目介绍（可直接背）

> 我做的是题目 4「简易拼图游戏」。硬件是 MAX II **EPM1270T144C5**，
> 纯 VHDL-93 手写，**没有用任何 IP 核**，Quartus II 9.1 综合。
>
> **功能上**：11 条基本要求全部实现，5 条提高要求里 A1/A2/A4/A5 实现、**A3 只做了一半**——
> 零片位置随机做了，**初始朝向随机我有意不做**，因为它会让 37% 的牌局"不旋转也能拼出来"，
> 那样 A4 的旋转键就成了摆设；这条性质我用 `check_geometry.py` **穷举证明**过。
>
> **结构上**：`puzzle_top` 下面 11 个游戏子模块，按 S1~S7 分七个子系统，
> **只有一路 50 MHz 时钟**，其余全是**节拍使能**，没有异步时钟域、没有跨时钟握手。
> 拼图引擎 `puzzle_ctrl` 一拍只算一行，输出两套 64 位帧（红/绿），顶层按行切片送给点阵驱动。
>
> **资源上**：**{{fact:build.fit.le}} LE、LAB {{fact:build.fit.lab}} 满占用**，Fmax 实测 54.27 MHz。
> 这颗器件**真正的瓶颈是 LAB**——LE 只能按每 LAB 10 个成组分配，
> 所以"再加一个计数器"经常直接装不下：我有一版幽灵提示是编译过的，**1278 LE，报错**。
>
> **验证上**：12 个模块/场景、**184 条断言**全部通过，
> 12 张 Quartus 波形编辑器截图；固件已烧录并**独立读回校验**（0 error）。
> ⚠️ 但我要说明：**真实硬件照片一张都没有**，音效"好不好听"也只有人的判断、没有录音——
> 这些是本项目**缺的证据**，我列了补拍清单。

## 三、随机模块问答的应对（老师会挑一个）

| 模块 | 一句话 | 一张图 / 源码 |
|---|---|---|
| `clk_gen` | POR 10 ms + BTN0 20 ms 非对称消抖；7 路节拍使能，`o_tick_2hz` 的实读者是 `board_test_top` | `GUI-clk_gen.png`、{{src:rtl/clk_gen.vhd:51}} |
| `keypad_scan` | 200 Hz 四状态扫描、4 次一致性消抖（≈40 ms）、一次按下只发一个 `o_press` | `GUI-keypad_scan.png`、{{src:rtl/keypad_scan.vhd:72}} |
| `game_fsm` | 6 态状态机；只有对局态响应选择/移动/旋转/确认；【开始】任何状态都可重开 | `GUI-game_fsm.png`、{{src:rtl/game_fsm.vhd:262}} |
| `puzzle_ctrl` | 一拍算一行 `row_mask`；整帧快照判据 `frm_ok`；散落=有界候选+拒绝采样 | `GUI-puzzle_ctrl.png`、{{src:rtl/puzzle_ctrl.vhd:254}} |
| `piece_rom` / `pattern_rom` | 编译期常量表，**0 LE / 4 LE** | `GUI-piece_rom.png`、{{src:rtl/puzzle_pkg.vhd:160}} |
| `rng_lfsr` | 8 位最大长度 LFSR（x⁸+x⁶+x⁵+x⁴+1），周期 255，只在 `i_step` 时推进 | `GUI-rng_lfsr.png`、{{src:rtl/rng_lfsr.vhd:5}} |
| `disp_format` | 纯组合：状态 → 8 位数码管内容 + 熄灭掩码；**DISP2 全程熄灭**（口径 C） | `GUI-disp_format.png`、{{src:rtl/disp_format.vhd:25}} |
| `seg_scan` | 125 Hz 位选、5 个字母的字形 | `GUI-seg_scan.png`、{{src:rtl/seg_scan.vhd}} |
| `dot_matrix_scan` | 行低电平选通、红绿两列；行号顺序是**实测**得出的 | `GUI-dot_matrix_scan.png`、{{src:rtl/dot_matrix_scan.vhd:41}} |
| `buzzer_ctrl` | 4 位码 → 16 步乐句；÷256 预分频、8 位半周期；三关 BGM 靠音区/换音速率区分 | `GUI-buzzer_ctrl.png`、{{src:rtl/buzzer_ctrl.vhd:143}} |
| `puzzle_top` | 顶层：11 个实例、按 `mrow` 切帧、告急幽灵（绿 2 Hz） | `GUI-puzzle_top.png`、{{src:rtl/puzzle_top.vhd:775}} |
| `puzzle_pkg` | 设计包：常量/类型/**24 个纯函数**，综合时展开 | {{src:rtl/puzzle_pkg.vhd:40}} |

!!! note "被问"某个信号为什么留着"时的通用答法"
    先讲**它属于哪个顶层**，再讲**有没有实读者**。
    例：`o_tick_2hz` 在 `puzzle_top` 里接 `open`，但它**不是死逻辑**——
    `board_test_top` 是它唯一的实读者；说"这个信号没人用"必须限定到具体顶层。

## 证据与出处

| 结论 | 依据 |
|---|---|
| 答辩形式与评分表 | `refs/pdf/数字系统设计2026.pdf`（"9-10 验收答辩"）、`refs/pdf/2026秋数字电路与逻辑设计实验（下）课程说明.pdf` §2 |
| 各节引用的图与表 | [系统总体架构](../02-architecture/system-overview.md)、[模块总览](../03-modules/index.md)、[移动与旋转](../05-gameplay/movement-rotation.md)、[已知限制与取舍](../01-project/limitations.md) |
| 关键指标 | {{src:docs/05-资源利用与编译报告.md}}、`facts/facts.json` |
| 断言规模 | {{tree:sim/rounds}} |
| 1278 LE 失败实测 | {{src:docs/06-硬件调试记录.md}} §22.3 |
| 模块级"一句话"的源码出处 | {{tree:rtl}} 各文件（见上表） |

!!! warning "待核实"
    上表的**建议时长**是经验分配，没有排练记录。
    核实路径：按本页顺序**实际掐表**走一遍（8 节 + 3 分钟版），
    把每节超时情况记在 `book/docs/09-defense/` 下的排练笔记里。
