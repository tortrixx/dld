<p class="eyebrow">MAX II · VHDL-93 · DIGITAL LOGIC</p>

# 在 CPLD 上实现一款拼图游戏

从矩阵键盘到双色点阵，从游戏状态机到逐行碰撞检测：在 **EPM1270T144C5** 上，以纯 VHDL 实现完整的三关拼图交互。没有 CPU 和片上 RAM，输入、运算、显示与音效都由硬件逻辑完成。

[观看演示](demo.md){ .md-button .md-button--primary }
[理解系统架构](architecture.md){ .md-button }

<figure class="hero-demo" markdown="span">

![软件规则模型重放](assets/images/demo-run.gif)

<figcaption>软件规则模型重放，不是真实硬件录像。用于说明操作与画面规则，不能证明 RTL 或板卡运行结果。</figcaption>

</figure>

## 已有工程基线

<div class="project-metrics">
  <a href="resources/"><strong>{{LE}}</strong><span>逻辑单元 · LE</span></a>
  <a href="resources/"><strong>{{LAB}}</strong><span>逻辑阵列块 · LAB</span></a>
  <a href="resources/"><strong>{{FMAX}} MHz</strong><span>静态时序分析 · Fmax</span></a>
  <a href="verification/"><strong>{{ASSERTIONS}} 条</strong><span>历史验证断言通过</span></a>
</div>

编译记录：**{{BUILD_DATE}}**。读数来自 [构建溯源记录](https://github.com/tortrixx/dld/blob/main/quartus/build_provenance.json)，测试明细见[验证与测试](verification.md)。本次网站迁移不重跑 Quartus，也不新增上板结论。

## 从系统到实现

<div class="grid cards" markdown>

- :material-chip: **系统架构**

    单时钟域、使能节拍与 11 个子模块如何协作。

    [沿信号流阅读](architecture.md)

- :material-puzzle: **六组模块**

    接口、设计实现与原始仿真波形，按功能组织。

    [从顶层集成开始](modules/01_system_top.md)

- :material-chart-timeline: **验证与测试**

    区分软件演示、仿真断言、时序报告与上板记录。

    [检查证据与限制](verification.md)

- :material-tools: **构建复现**

    配置工程、运行仿真，以及安全地修改 RTL。

    [复现工程](reproducibility.md)

</div>

## 这个项目值得拆解的地方

- **在面积约束下串行化计算**：逐行生成掩码、逐块检查碰撞，让运算单元跨周期复用。[资源优化](resources.md)
- **让判据与画面一致**：完成条件看逐格覆盖和锁定状态，允许等价铺法。[拼图引擎](modules/04_puzzle_engine.md)
- **保留明确的工程边界**：初始方向固定、被拒操作无音效，功能取舍有记录可查。[工程取舍](decisions.md)
