# 简易拼图游戏 · 硬件模块与答辩速查

> **一句话**：在一块没有 CPU、也没有片上 RAM 的 CPLD 上，用纯硬件逻辑做了一个能玩的 8×8 双色点阵拼图游戏。

<div class="metrics">
  <div class="metric"><b>1,264 / 1,270</b><span>逻辑单元 LE（99.53%）</span></div>
  <div class="metric"><b>127 / 127</b><span>逻辑阵列块 LAB（100%）</span></div>
  <div class="metric"><b>54.27 MHz</b><span>Fmax（基准时钟 50 MHz）</span></div>
  <div class="metric"><b>52 / 116</b><span>用户 I/O 引脚（44.83%）</span></div>
  <div class="metric"><b>184</b><span>条仿真断言，全部通过</span></div>
</div>

## 这是什么

目标器件是 Altera MAX II EPM1270T144C5，一共 1,270 个逻辑单元，没有 CPU 软核，也没有片上 RAM。键盘扫描、游戏规则、碰撞判断、图案存储、显示扫描、音效，全部由 VHDL 描述成硬件电路，最终占掉 1,264 个逻辑单元。人机接口是 4×4 矩阵键盘，输出是 8×8 双色点阵、8 位数码管和一个蜂鸣器。

![规则模型重放：从开机自检到通关的一局](assets/images/demo-run.gif)
*规则模型重放（软件渲染，不是板子实录）：开机自检 → 预览目标图案 → 零片散落 → 拼装 → 通关*

## 六个大模块

本站按《实验报告》§2.2 的 5 大子系统划分，另加 1 页顶层集成，共 6 页。点任意一张卡片进入。

<div class="mod-grid">
  <a class="mod-card" href="#/subsystems/01_system_top">
    <div class="mod-card-head"><span class="mod-card-idx">01</span><span class="mod-card-title">系统顶层集成</span></div>
    <span class="mod-card-entity">puzzle_top.vhd · puzzle_pkg.vhd</span>
    <div class="mod-card-desc">把 11 个子模块接在一起，管 52 根引脚怎么接、点阵的红绿两色怎么分配。</div>
    <div class="mod-card-tags"><span>52 引脚</span><span>双色仲裁</span><span>127 LAB 打满</span></div>
  </a>
  <a class="mod-card" href="#/subsystems/02_clock_keypad">
    <div class="mod-card-head"><span class="mod-card-idx">02</span><span class="mod-card-title">时钟使能与键盘输入</span></div>
    <span class="mod-card-entity">clk_gen.vhd · keypad_scan.vhd</span>
    <div class="mod-card-desc">把 50 MHz 时钟切成 7 种节拍，再把人手按键变成干净的单击脉冲。</div>
    <div class="mod-card-tags"><span>7 路节拍</span><span>40 ms 消抖</span><span>单拍脉冲</span></div>
  </a>
  <a class="mod-card" href="#/subsystems/03_game_fsm">
    <div class="mod-card-head"><span class="mod-card-idx">03</span><span class="mod-card-title">游戏主控状态机</span></div>
    <span class="mod-card-entity">game_fsm.vhd</span>
    <div class="mod-card-desc">游戏的裁判：管自检、待机、预览、对局、胜负这几步怎么走，以及倒计时。</div>
    <div class="mod-card-tags"><span>6 状态</span><span>2 s 自检</span><span>30 / 40 / 60 s</span></div>
  </a>
  <a class="mod-card" href="#/subsystems/04_puzzle_engine">
    <div class="mod-card-head"><span class="mod-card-idx">04</span><span class="mod-card-title">核心拼图引擎</span></div>
    <span class="mod-card-entity">puzzle_ctrl.vhd</span>
    <div class="mod-card-desc">真正干活的部分：算零片往哪走、会不会撞上、有没有拼对。</div>
    <div class="mod-card-tags"><span>本模块 760 LE</span><span>36 位状态</span><span>行流式渲染</span></div>
  </a>
  <a class="mod-card" href="#/subsystems/05_rom_random">
    <div class="mod-card-head"><span class="mod-card-idx">05</span><span class="mod-card-title">图案库与随机数</span></div>
    <span class="mod-card-entity">pattern_rom.vhd · piece_rom.vhd · rng_lfsr.vhd</span>
    <div class="mod-card-desc">芯片上没有 RAM，就用组合查找表存图案，用 LFSR 造零片的随机位置。</div>
    <div class="mod-card-tags"><span>零 RAM</span><span>8 位 LFSR</span><span>面积守恒</span></div>
  </a>
  <a class="mod-card" href="#/subsystems/06_display_audio">
    <div class="mod-card-head"><span class="mod-card-idx">06</span><span class="mod-card-title">显示与音效驱动</span></div>
    <span class="mod-card-entity">disp_format · seg_scan · dot_matrix_scan · buzzer_ctrl</span>
    <div class="mod-card-desc">把内部数据变成数码管、点阵和蜂鸣器能直接接受的电信号。</div>
    <div class="mod-card-tags"><span>125 Hz 刷新</span><span>红绿混黄</span><span>三关 BGM</span></div>
  </a>
</div>

## 硬件与工具

| 项目 | 内容 |
|:---|:---|
| 目标器件 | Altera MAX II EPM1270T144C5（1,270 LE / 127 LAB，无嵌入式 RAM，无微处理器软核） |
| 开发工具 | Quartus II 9.1 (32-bit)，VHDL-93，单时钟域设计 |
| 基准时钟 | 板载 50.000 MHz 有源晶振，Fmax 54.27 MHz（Setup 余量 +1.572 ns） |
| 验证方式 | 12 套 Quartus 波形仿真测试台、184 条断言，全部自动通过 |

> **数据出处**：以上读数来自 `quartus/output_files/puzzle.fit.rpt` 与 TimeQuest 报告，站内每页引用的数字都可在 `facts/facts.json` 中回溯。
