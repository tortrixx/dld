# 系统架构

这不是一段在 CPU 上运行的游戏软件。每一次按键、每一帧点阵显示与每一个状态转移都由 CPLD 里的逻辑电路完成。

![系统架构图](assets/images/fig1_system_architecture.png)

*原仓库已有的系统架构图；以 RTL 顶层连接和实际设计说明为准。*

## 信号流与模块边界

| 子系统 | 代表模块 | 职责 |
|---|---|---|
| 时钟与输入 | `clk_gen`、`keypad_scan` | 产生使能节拍并处理键盘按键 |
| 游戏控制 | `game_fsm` | 管理待机、预览、游玩和胜负状态 |
| 拼图计算 | `puzzle_ctrl` | 位置、方向、碰撞、完成条件 |
| 图案与随机 | `pattern_rom`、`piece_rom`、`rng_lfsr` | 提供图案和伪随机位置 |
| 显示与音效 | `disp_format`、`seg_scan`、`dot_matrix_scan`、`buzzer_ctrl` | 驱动数码管、双色点阵与蜂鸣器 |
| 系统集成 | `puzzle_top`、`puzzle_pkg` | 顶层连接和共用类型、常量、函数 |

## 设计取舍

- **统一时钟域**：将频率分配表达为节拍使能，而不是随意创建独立时钟域。
- **面积与行为之间的约束**：在已占满的 LAB 下，功能增强需要重新评估综合装箱。
- **随机性与旋转玩法的取舍**：仓库明确记录了初始方向随机性未完全实现的原因，不能将它描述为完整实现。

从 [系统顶层](modules/01_system_top.md) 开始逐步阅读，或直接进入 [拼图引擎](modules/04_puzzle_engine.md)。

> 原始数据与真实实现以 [RTL 源码](https://github.com/tortrixx/dld/tree/main/rtl) 和 [facts.json](https://github.com/tortrixx/dld/blob/main/facts/facts.json) 为准。

## 源码中的使能推进

下面的 VHDL 片段在构建时直接从 `rtl/rng_lfsr.vhd` 抽取，展示反馈计算与全零保护。寄存器只在 `i_step` 有效时推进，不能将它描述为自由运行的随机源。

```vhdl
{{RNG_CODE}}
```

[阅读完整 LFSR 源码](https://github.com/tortrixx/dld/blob/main/rtl/rng_lfsr.vhd) · [图案与随机数模块](modules/05_rom_random.md)
