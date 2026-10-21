# 简易拼图游戏设计与实现

> 《数字电路与逻辑设计实验（下）》课程设计 · 题目4  
> 芯片型号：**Altera MAX II EPM1270T144C5** ｜ 综合环境：**Quartus II 9.1** ｜ 时钟基准：**50.000 MHz**

---

## 📌 项目工程速览与极限指标

本项目基于 Altera MAX II EPM1270T144C5 CPLD 芯片，完整实现了一款集**伪随机图案散落**、**多零片平移/90°旋转**、**刚性碰撞越界拦截**、**三关连闯与随机图库**、**超临界无频闪双色点阵渲染**以及**分场景马里奥连奏音效**于一体的硬件纯逻辑拼图游戏机。

在没有任何片上 RAM 块、仅有 1,270 个逻辑单元 (LE) 的极端受限芯片上，本项目实现了极限压榨与严苛时序收敛：

<div class="card-grid">
  <div class="card">
    <div class="card-icon">⚡</div>
    <div class="card-title">极限逻辑利用</div>
    <div class="card-desc"><strong>1,264 / 1,270 LE (99.5%)</strong><br>127 / 127 LAB 全部占满，无任何状态机膨胀与冗余逻辑</div>
  </div>
  <div class="card">
    <div class="card-icon">⏱️</div>
    <div class="card-title">严格时序收敛</div>
    <div class="card-desc"><strong>Fmax = 54.27 MHz</strong><br>主时钟 50 MHz 约束下 Setup Slack 达 <strong>+1.572 ns</strong>，全同步单时钟域</div>
  </div>
  <div class="card">
    <div class="card-icon">🧪</div>
    <div class="card-title">全覆盖仿真验证</div>
    <div class="card-desc"><strong>184 / 184 断言全部通过</strong><br>覆盖 11 个子模块与 1 个整机顶层，Python 自检闭环杜绝假绿</div>
  </div>
  <div class="card">
    <div class="card-icon">🎯</div>
    <div class="card-title">硬件引脚全锁定</div>
    <div class="card-desc"><strong>52 / 116 引脚物理锁定</strong><br>行/列扫描、键盘、数码管、蜂鸣器全部与实验箱引脚精准绑定</div>
  </div>
</div>

---

## 🎮 真实硬件一局演示

整机系统在上电复位后执行开机自检，待机选择关卡，经过 5 秒图案预览后自动将零片伪随机打散并开启倒计时。玩家通过 4×4 矩阵键盘操作零片上下左右移动、90° 顺时针旋转与块切换。倒计时小于等于 10 秒时自动触发**绿色 2 Hz 告急幽灵**辅助指引。拼合成功瞬间判定过关并奏响通关号角！

<p align="center">
  <img src="assets/images/demo-run.gif" alt="真实硬件操作完整一局演示动画" style="max-width: 480px; width: 100%;">
  <br>
  <em>图 0-1 完整游戏流程实录：开机自检 → 待机 → 5s 预览 → 零片散落 → 键盘移动与旋转 → 告急幽灵 → 成功过关结算</em>
</p>

---

## 🏗️ 全局微架构与五大子系统划分

整机严格遵循**同步单时钟域 + 单周期使能脉冲节拍驱动**的设计原则，全工程仅在 PIN_18 50 MHz 主时钟上升沿翻转，坚决不在任何分频信号上挂载触发器。

系统划分为 5 大高层级子系统、共 11 个 VHDL 实体模块与 1 个引脚绑定顶层：

![图 1 系统总体架构与大模块信息交互框图](assets/images/fig1_system_architecture.png)

### 五大子系统职责分工

| 子系统编号 | 子系统名称 | 包含模块 | 驱动节拍 | 核心职责 |
|:---|:---|:---|:---|:---|
| **S1** | **时钟与使能网络** | `clk_gen` | 50 MHz 主频 | 级联分频生成 1 kHz / 200 Hz / 100 Hz / 40 Hz / 4 Hz / 2 Hz / 1 Hz 七路单周期使能脉冲；对复位键进行 20 ms 消抖 |
| **S2** | **人机交互输入** | `keypad_scan` | 200 Hz 脉冲 | 4×4 矩阵键盘行/列双相轮巡；40 ms 滞回消抖；按键边缘提取单周期按键码 |
| **S3** | **主控与规则仲裁** | `game_fsm` | 1 Hz / 4 Hz | 6 状态主状态机（自检、待机、预览、对局、过关、失败）；倒计时管理；模式切换与音效触发 |
| **S4** | **拼图核心运算** | `puzzle_ctrl` | 1 kHz 脉冲 | 64 位并行位运算；行扫描渲染管线；邻块串行碰撞检测；全图 100% 重合判据；仅占 36 个触发器 |
| **S5** | **固化图库与随机源** | `piece_rom`<br>`pattern_rom`<br>`rng_lfsr` | 组合 / 使能 | 关卡目标图案库（5 幅，全连通 12/16 格）；零片几何掩码库；8 位 Galois LFSR 满周期 255 伪随机发生器 |
| **S6** | **多通道音画输出** | `disp_format`<br>`seg_scan`<br>`dot_matrix_scan`<br>`buzzer_ctrl` | 1 kHz / 50 MHz | 8 位数码管无除法译码与 125 Hz 无频闪轮巡；8×8 双色点阵低电平行选通；数控分频与 16 步马里奥连奏音效 |

---

## 📋 功能指标达成对照表

| 分类 | 编号 | 规范要求 | 本工程实际达成状态 | 实现模块与依据 |
|:---|:---|:---|:---|:---|
| **基础要求** | **B1** | 游戏开始显示 4×3 矩形（红黄绿任选） | ✅ 完美达成（第一关全红显示目标图案，12 格） | `pattern_rom`, `puzzle_top` |
| | **B2** | 预览 5 秒后散开为 3 个零片 | ✅ 完美达成（`S_PREVIEW` 倒计时 5s，届满自动切入 `S_PLAYING` 散落） | `game_fsm`, `puzzle_ctrl` |
| | **B3** | 倒计时 30 秒游戏时间 | ✅ 完美达成（第一关数码管 DISP1..0 显示 30 秒倒计时，1 Hz 递减） | `game_fsm`, `disp_format` |
| | **B4** | 4×4 矩阵键盘控制上下左右平移 | ✅ 完美达成（8 个功能键单脉冲触发，刚性边界碰撞拦截） | `keypad_scan`, `puzzle_ctrl` |
| | **B5** | 按键切换操作的零片 | ✅ 完美达成（按【切换】键循环轮选活动零片） | `keypad_scan`, `puzzle_ctrl` |
| | **B6** | 选中的零片与未选中的显示不同颜色 | ✅ 完美达成（当前活动零片显示为**亮绿色**，未选中已放置零片显示为**黄色**，底图目标显示为红色） | `puzzle_top` 显示多路器 |
| | **B7** | 零片不可重叠 | ✅ 完美达成（移动与旋转时若与已锁定零片重叠，当拍置高 `chk_hit` 拦截坐标更新） | `puzzle_ctrl` 碰撞检测单元 |
| | **B8** | 正确拼完在倒计时结束前停止倒计时并判定胜利 | ✅ 完美达成（全图整帧 100% 重合瞬间锁定倒计时，进入 `S_WIN`） | `puzzle_ctrl`, `game_fsm` |
| | **B9** | 拼图完成后按确认键显示提示并进入下一关 | ✅ 完美达成（数码管显示 PASS，奏响通关号角，自动升入第 2 关） | `game_fsm`, `disp_format` |
| | **B10** | 第 2 关难度增加，倒计时 40 秒 | ✅ 完美达成（第 2 关 4 块异形零片共 16 格，倒计时 40 秒） | `piece_rom`, `game_fsm` |
| | **B11** | 游戏中或结束后按复位键重新开始 | ✅ 完美达成（按【开始】键随时可重新开局；硬件 BTN0 复位重入自检） | `game_fsm`, `puzzle_top` |
| **提高要求** | **A1** | 游戏各环节增加不同音效（自检/倒计时/成功/失败等） | ✅ 完美达成（三关三首背景音乐 + 6 种事件提示音，马里奥经典乐句） | `buzzer_ctrl` |
| | **A2** | 增加第 3 关，图案从图形库中随机抽取 | ✅ 完美达成（第 3 关 60 秒限时，从田/十字/SZ/阶梯 4 幅 16 格图案库随机抽取） | `pattern_rom`, `rng_lfsr` |
| | **A3** | 零片出现位置随机 | ✅ 完美达成（8 位 LFSR 随机散落锚点，智能防死锁重试与兜底机制） | `rng_lfsr`, `puzzle_ctrl` |
| | **A4** | 零片可旋转 | ✅ 完美达成（按【旋转】键在局部包围盒内 90° 顺时针正交旋转，复用碰撞校验） | `puzzle_ctrl` 旋转处理单元 |
| | **A5** | 其他自拟功能 | ✅ 完美达成（详见下方自拟功能表） | 多个子模块协同 |
| **自拟功能** | **S1** | 第 2/3 关图案库随机抽取机制 | ✅ 预置 4 幅高难度几何图案，随机种子确定性抽取 | `pattern_rom` |
| | **S2** | 125 Hz 超临界无频闪动态扫描 | ✅ 远高于人眼 60 Hz 融合频率，点阵与数码管完全无抖动无重影 | `seg_scan`, `dot_matrix_scan` |
| | **S3** | 无除法器 64 项常量除法与取模 | ✅ 消除 26 ns 运算延时，节约上百 LE 资源 | `disp_format` |
| | **S4** | 非对称 40 ms 滞回消抖与快速响应 | ✅ 连击跟手不吞键，彻底消除机械反弹双击 | `keypad_scan` |
| | **S5** | 结算画面 2 Hz 闪烁 + 常亮停留机制 | ✅ 胜负结算先闪 1 秒引起注意，随后定格等待玩家确认 | `game_fsm`, `puzzle_top` |
| | **S6** | 64 位宽并行位平面空间位移 | ✅ 充分发挥 CPLD 宽互联优势，单拍完成平移与投影 | `puzzle_ctrl` |
| | **S7** | 剩余时间 ≤10 秒**绿色 2 Hz 告急幽灵**闪烁辅助 | ✅ 解决点阵双色混叠问题，临界倒计时动态提示目标轮廓 | `puzzle_top` 告急幽灵单元 |

---

## 🧭 模块与专项快速导航

<div class="card-grid">
  <a class="card" href="#/modules/puzzle_top.md">
    <div class="card-icon">👑</div>
    <div class="card-title">01. 整机顶层 (puzzle_top)</div>
    <div class="card-desc">引脚分配绑定、显示多路选择器、告急幽灵与 11 模块信号互联</div>
  </a>
  <a class="card" href="#/modules/clk_gen.md">
    <div class="card-icon">⏰</div>
    <div class="card-title">03. 时钟与使能 (clk_gen)</div>
    <div class="card-desc">50 MHz 级联分频链、7 路单周期无毛刺使能脉冲、复位同步消抖</div>
  </a>
  <a class="card" href="#/modules/keypad_scan.md">
    <div class="card-icon">⌨️</div>
    <div class="card-title">04. 矩阵键盘 (keypad_scan)</div>
    <div class="card-desc">4×4 矩阵扫描、40 ms 滞回消抖、单拍脉冲提取与防吞键机制</div>
  </a>
  <a class="card" href="#/modules/game_fsm.md">
    <div class="card-icon">🕹️</div>
    <div class="card-title">05. 规则状态机 (game_fsm)</div>
    <div class="card-desc">6 状态 ASM 算法状态机、倒计时管理、三关流转与胜负仲裁</div>
  </a>
  <a class="card" href="#/modules/puzzle_ctrl.md">
    <div class="card-icon">🧩</div>
    <div class="card-title">06. 核心拼图引擎 (puzzle_ctrl)</div>
    <div class="card-desc">面积优化主战场（仅36触发器）、64位位运算、串行碰撞、全图判据</div>
  </a>
  <a class="card" href="#/modules/buzzer_ctrl.md">
    <div class="card-icon">🎵</div>
    <div class="card-title">13. 音频发生器 (buzzer_ctrl)</div>
    <div class="card-desc">数控分频精确音高、16步连奏填音消除卡顿、马里奥三曲与提示音</div>
  </a>
  <a class="card" href="#/guide/defense_qa.md">
    <div class="card-icon">🎓</div>
    <div class="card-title">答辩抽查冲刺速查宝典</div>
    <div class="card-desc">老师现场随机抽查模块？大白话原理解释 + 专业术语标准应答汇总</div>
  </a>
  <a class="card" href="#/guide/sim_verification.md">
    <div class="card-icon">🧪</div>
    <div class="card-title">184 条断言仿真体系</div>
    <div class="card-desc">Quartus II 9.1 原生波形回写、逐模块激励断言覆盖与自动化判据</div>
  </a>
  <a class="card" href="#/guide/resource_timing.md">
    <div class="card-icon">📊</div>
    <div class="card-title">1,264 LE 极致优化报告</div>
    <div class="card-desc">99.5% 占满、编译演进史、无嵌入式 RAM 极限压缩与时序收敛秘诀</div>
  </a>
  <a class="card" href="#/guide/bugs_err.md">
    <div class="card-icon">🛠️</div>
    <div class="card-title">典型工程故障深度复盘</div>
    <div class="card-desc">ERR-001 ~ ERR-056 软硬件实战避坑：漏引脚、错坐标、频闪、吞键等</div>
  </a>
</div>
