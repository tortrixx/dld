# 🧪 184 条断言全覆盖仿真验证体系

> **仿真核心指标**：覆盖 11 个子模块 + 1 个整机顶层 ｜ **断言总数**：**184 / 184 全部通过 (100%)** ｜ **仿真工具**：Quartus II 9.1 原生波形仿真器 + Python 自检闭环

---

## 1. 验证体系设计与“拒绝假通过”哲学

在没有大型商业仿真器（如 ModelSim / VCS / Questasim）的单机教学环境下，许多学生在做波形仿真时容易陷入“肉眼看波形、随手画激励、假绿满天飞”的误区。

本项目自主研发了**“Quartus II 原生波形编辑器 (`.vwf`) + 激励/结果自动回写 + Python 自动化断言判定”**的工业级验证流水线：

```mermaid
flowchart TD
  RTL["RTL 源码 (rtl/*.vhd)"] --> SIM["Quartus II 9.1 原生仿真器"]
  VWF["仿真激励文件 (sim/*.vwf)"] --> SIM
  SIM --> RES["仿真结果波形回写 (*.vwf)"]
  RES --> PY["Python 自动化测试台 (sim/tb_*.py)"]
  PY --> AST["184 条业务与协议断言"]
  AST --> PASS["✅ 184 / 184 断言全部通过 (生成 sim/rounds/*/rNN.json)"]
```

### 为什么能彻底杜绝“假通过（陈旧绿）”？
1. **真实硬件时序回写**：波形不是由 Python 脚本画出来的矢量图，而是由 Quartus II 内置仿真器对网表进行真实功能仿真后写盘的物理波形；
2. **时序与电平精确对账**：Python 脚本通过 `vwf.py` 模块以纳秒级时间切片解析波形跳变沿，对每个输出信号的跳变时刻、高低电平、脉冲宽度执行自动化断言；
3. **哈希指纹闭环**：每一轮仿真的断言结果、输入输出哈希值均被固化在 `sim/rounds/<模块>/rNN.json` 中，任何 RTL 代码改动若未重跑仿真，流水线门禁立即报警阻断。

---

## 2. 12 套模块测试台与 184 条断言全景对账表

下表断言数与最新轮次逐行取自真实工程数据（`sim/rounds/`），与实验报告 §3.1 严格对齐：

| 测试台文件 (`sim/tb_*.py`) | 被测实体 | 最新轮次 | 断言数 | 核心测试激励类型 | 关键验证项与边界覆盖范围 |
|:---|:---|:---:|:---:|:---|:---|
| `tb_clk_gen` | `clk_gen` | `r25` | **10** | 周期计数穷举 | 50 MHz 经级联分频链得到 7 路（1 kHz / 200 Hz / 100 Hz / 40 Hz / 4 Hz / 2 Hz / 1 Hz）单周期使能脉冲的宽度与周期精确性 |
| `tb_keypad_scan` | `keypad_scan` | `r27` | **9** | 按键反弹与抖动 | 40 ms 硬件消抖、矩阵行列反相译码、8 个功能键码的唯一译码、长按单脉冲输出与长按连击抑制 |
| `tb_game_fsm` | `game_fsm` | `r36` | **30** | 主状态全流程穷举 | SELF_TEST → IDLE → PREVIEW → PLAYING → WIN / FAIL 的转换边界、2 s / 5 s / 30 s / 40 s / 60 s 定时边界、连闯三关流转 |
| `tb_puzzle_ctrl` | `puzzle_ctrl` | `r37` | **28** | 几何运算与空间移动 | 零片循环切换、上下左右边界拦截、多块重叠碰撞检测、局部 90° 顺时针旋转、主路径竞态 |
| `tb_rng_lfsr` | `rng_lfsr` | `r23` | **10** | 255 拍序列穷举 | 本原多项式逐拍移位一致性、全零吸收态自锁保护、汉明重分布、复位重演性 |
| `tb_piece_rom` | `piece_rom` | `r23` | **10** | 几何掩码查表 | 第一关（3+6+3=12 格）与第二/三关（3+2+5+6=16 格）零片面积守恒、左上角归一化及旋转空间映射 |
| `tb_pattern_rom` | `pattern_rom` | `r21` | **8** | 图案位图一致性 | 【题】图 4-1 矩形及田/十字/SZ/阶梯图案连通性、格数严格 12 / 16 格 |
| `tb_disp_format` | `disp_format` | `r27` | **16** | 全字符译码映射 | 0～9 数字译码、前导零消隐、PASS/FAIL 拼装字符、倒计时 case 表 t=0..63 逐项穷举 |
| `tb_seg_scan` | `seg_scan` | `r31` | **12** | 动态扫描时序 | 8 位共阴极位选 125 Hz 轮巡、段选与位选同拍寄存（无独立消隐相）、`i_blank` 逐位熄灭、`i_en='0'` 全局静默 |
| `tb_dot_matrix_scan` | `dot_matrix_scan` | `r23` | **7** | 双色点阵驱动 | 8 行独热低电平行选通、红/绿列直通（高电平点亮）、单色内容下红绿列互斥、`i_en='0'` 全灭、+20 ns 早采样点无混合态 |
| `tb_buzzer_ctrl` | `buzzer_ctrl` | `r37` | **16** | 音频数控分频 | E5～G6 音符分频精度（实测误差 0.59%～1.25%，容差 1.5%）、50% 占空比、连奏填音与"只有提示音允许休止"的设计规则自检 |
| `tb_puzzle_top` | `puzzle_top` | `r56/57` | **28** | 真实用户按键全流程 | 模式 A / 模式 B 两轮真实按键序列，完成自检、待机、预览、通关三关、按【开始】重开后失败判定的端到端闭环，校验告急幽灵"在闪且只闪绿色" |
| **全系统合计** | **12 个测试集** | — | **184** | **全维度覆盖** | **184 / 184 全部通过，无一漏检，无一失效** |

---

## 3. 核心测试用例深度解构

### 3.1 拼图引擎越界与碰撞拦截断言 (`tb_puzzle_ctrl`)
在 `sim/tb_puzzle_ctrl.py` 中，针对刚性碰撞设计了严密的反向断言：
```python
# 验证左边界越界拦截：零片在 x=0 处再次向左移动
stimulus.send_key(KEY_LEFT)
run_simulation_step()
# 断言：坐标必须仍然等于 0，且内部碰撞标志 chk_hit 必须在该拍拉高
assert dut.pos_col == 0, "Left boundary interception failed: piece slipped through border!"
assert dut.chk_hit == 1, "Collision flag chk_hit was not asserted on boundary impact!"
```

### 3.2 告急幽灵双色不冲突断言 (`tb_puzzle_top`)
在整机对局仿真中，专门设立了幽灵颜色的互斥性校验断言：
```python
# 当倒计时为 10 秒时
if countdown <= 10:
    # 断言 1：告急幽灵必须且仅能出现在绿色通道，绝对不能污染红色通道
    assert dut.dot_colr & ghost_mask == 0, "Ghost leaked into RED channel causing piece color confusion!"
    # 断言 2：幽灵必须随 2 Hz 方波交替闪烁，禁止常亮
    assert dut.ghost_is_blinking == True, "Ghost must blink at 2 Hz, static ghost is illegal!"
```

---

## 4. 🎓 老师答辩必问与标准回答（核心快问快答）

<div class="defense-box">
  <div class="defense-title">💡 老师随机抽查：仿真验证体系核心答辩点</div>

  <div class="defense-q">Q1：你们没有安装 ModelSim，平时是怎么验证 VHDL 代码正确性的？</div>
  <div class="defense-a">
    <strong>标准回答：</strong><br>
    老师，我们充分利用了 Quartus II 9.1 自带的<strong>内置波形仿真器（Simulator Tool）</strong>与 <code>.vwf</code> 向量波形文件。<br>
    为了避免人工用肉眼检查波形容易遗漏的问题，我们用 Python 编写了自动化测试台调度器：由 Python 解析 <code>.vwf</code> 文件中的激励，调用 Quartus 仿真内核执行硬件网表仿真并回写物理结果；随后 Python 逐拍扫描每个信号的跳变沿和电平值，执行自动化断言。<br>
    全工程累计建立了 <strong>12 套自动化测试台与 184 条断言</strong>，每次改动代码都会一键回归，保证了逻辑的绝对正确。
  </div>

  <div class="defense-q">Q2：你们是怎么防止测试激励出现“假通过”（假绿）的？</div>
  <div class="defense-a">
    <strong>标准回答：</strong><br>
    我们在开发中总结过 <strong>ERR-022 假通过教训</strong>（当时激励使用了陈旧的常量，导致非法分支根本没被激发，测试却误报 100% 通过）。<br>
    为根治假绿，我们确立了两大防御原则：<br>
    1. <strong>反向异常激发</strong>：每个模块必须专门注入非法操作（如故意撞墙、重叠放置、长按不放、输入全 0 等），并断言硬件必须给出拦截；<br>
    2. <strong>事实模型自动核对</strong>：所有断言期望值全部从 <code>facts/facts.json</code> 真值源中机械提取，禁止测试人员手写魔法数字，从源头上杜绝了陈旧假通过。
  </div>
</div>
