# 硬件设计

目标器件为 **Altera MAX II EPM1270T144C5**，板载晶振 50 MHz。所有同步逻辑使用同一个时钟，低速工作由单周期使能控制。

## 外设与信号

| 外设 | 顶层信号 | 电气或逻辑约定 |
|---|---|---|
| 晶振与复位 | `clk`、`btn` | 晶振 PIN_18；复位键 PIN_61 |
| 总使能 | `sw7` | PIN_125，关闭时停止交互并消隐 |
| 4×4 矩阵键盘 | `kp_row[3:0]`、`kp_col[3:0]` | 行输入、列扫描；消抖后输出键码与单拍事件 |
| 8×8 双色点阵 | `dot_row`、`dot_colr`、`dot_colg` | 行低有效、红绿列高有效 |
| 八位数码管 | `seg[7:0]`、`cat[7:0]` | 段高有效、位选低有效 |
| 蜂鸣器 | `buzz` | PIN_60；音效码选择乐句，计数器生成方波 |

完整的 **52 根用户信号**均显式锁定，依据为 [QSF 引脚分配](https://github.com/tortrixx/dld/blob/main/quartus/puzzle.qsf) 与[事实模型](https://github.com/tortrixx/dld/blob/main/facts/facts.json)。不凭图片猜测板卡接线，也不把本项目极性直接套到其他开发板。

## 显示扫描

点阵逐行、数码管逐位扫描。1 kHz 使能分配给 8 行或 8 位，每行／位刷新率为 **125 Hz**；它与引擎内容更新率是不同概念。

- 点阵行序与逻辑位序相反，行译码需按实际引脚映射处理。
- 数码管段线和位选在同一个时钟沿寄存更新。
- 当前关号在 DISP0 显示，DISP2 除自检外消隐。

依据：[点阵驱动](https://github.com/tortrixx/dld/blob/main/rtl/dot_matrix_scan.vhd)、[数码管驱动](https://github.com/tortrixx/dld/blob/main/rtl/seg_scan.vhd)、[格式化器](https://github.com/tortrixx/dld/blob/main/rtl/disp_format.vhd)。

## 上板前检查

先确认器件、晶振、供电、引脚和有效电平，再用仓库的 `board_test_top`、`keypad_diag_top` 等诊断顶层检查外设。蜂鸣器无声还需核对板上开关与音量电位器。

[工程操作手册](https://github.com/tortrixx/dld/blob/main/HANDOFF.md) 保存了烧录和诊断步骤；[显示与音效模块](modules/06_display_audio.md) 解释扫描和分频实现。本次网站维护未连接开发板。
