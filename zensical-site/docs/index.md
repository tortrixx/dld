# 在 CPLD 上实现一款拼图游戏

**没有 CPU，没有片上 RAM，只有 VHDL 描述的硬件逻辑。**

本项目在 Altera MAX II EPM1270T144C5 CPLD 上实现 8×8 双色点阵拼图游戏。玩家通过 4×4 矩阵键盘选择、移动和旋转零片，完成三关拼图挑战。整个系统包括输入消抖、游戏状态机、碰撞检测、图案查找表、显示扫描和蜂鸣器音效。

![规则模型重放](assets/images/demo-run.gif)

*软件规则模型生成的演示动画，不是开发板实拍。*

<div class="project-metrics">
  <div><strong>1,264 / 1,270</strong><span>逻辑单元 LE</span></div>
  <div><strong>127 / 127</strong><span>逻辑阵列块 LAB</span></div>
  <div><strong>54.27 MHz</strong><span>Fmax</span></div>
  <div><strong>184</strong><span>验证断言</span></div>
</div>

以上为仓库 README 记录的已验证基线；变更 RTL 后以 [构建证据](https://github.com/tortrixx/dld/blob/main/quartus/build_provenance.json) 和实际报告为准。

## 从哪里开始

<div class="grid cards" markdown>

- :material-chip: **系统架构**

    从时钟、键盘到状态机、拼图引擎和显示输出，理解硬件数据流。

    [阅读架构](architecture.md)

- :material-puzzle: **模块设计**

    阅读 6 组子系统说明，结合真实信号及波形理解实现细节。

    [查看拼图引擎](modules/04_puzzle_engine.md)

- :material-chart-timeline: **工程验证**

    查看 Quartus GUI 波形、仿真断言、资源和时序报告的证据边界。

    [查看验证方案](verification.md)

- :material-tools: **复现项目**

    了解 VHDL、Quartus II 工程生成、编译、测试和环境要求。

    [构建指南](reproducibility.md)

</div>

## 项目的关键设计挑战

1. **资源极限**：127 个 LAB 全部占用，优化重点不只是 LE 数量，更是逻辑装箱与时序收敛。
2. **无片上 RAM**：图案数据通过逻辑查找表生成，不使用软核处理器。
3. **时序与交互**：单时钟域组织多个使能节拍，完成输入、显示、游戏控制与音效协同。
4. **可追溯验证**：仿真断言、截图、构建报告与固件记录共同描述可验证的工程结果。

[:octicons-mark-github-16: 浏览源代码](https://github.com/tortrixx/dld){ .md-button .md-button--primary }
