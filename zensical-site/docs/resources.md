# 资源优化

约束不是单独的“LE 数量越少越好”。设计需要同时满足 **LAB 容量、逻辑装箱和 50 MHz 时序**。

## 整机编译基线

| 项目 | 已记录结果 | 来源 |
|---|---|---|
| 逻辑单元 | {{LE}} LE | 构建记录 `fit.le` |
| 逻辑阵列块 | {{LAB}} LAB | 构建记录 `fit.lab` |
| Fmax | {{FMAX}} MHz | 构建记录 `sta.fmax_mhz` |
| Setup slack | +{{SETUP}} ns | 构建记录 `sta.setup_slack` |
| Hold slack | +{{HOLD}} ns | 构建记录 `sta.hold_slack` |

以上由事实模型生成。原始[构建溯源记录](https://github.com/tortrixx/dld/blob/main/quartus/build_provenance.json)的时间为 **{{BUILD_DATE}}**，记录了源文件哈希及固件 SHA-256。原始工作区 `git_dirty=true`，因此不能只凭其中 `git_head` 就断言整个工作区等同于那个提交。

![Quartus 资源报告](assets/images/GUI-build-area.png)
*历史 Quartus 资源报告裁图；原始报告读数由构建溯源记录保存。*

![Quartus 时序报告](assets/images/GUI-build-timing.png)
*历史 Fmax Summary 截图。54.27 MHz 是静态时序分析结果，设计约束与板载晶振均为 50 MHz。*

## 把并行逻辑改成时间复用

`puzzle_ctrl` 的历史版本从整帧并行计算逐步改成逐行生成掩码，再逐块检查碰撞。每次只保留当前候选行和当前邻块，复用组合逻辑。

| 历史版本 | 单独综合 LE | 变化 |
|---|---|---|
| v1 | 4,690 | 早期全帧实现 |
| v5 | 3,751 | 仍并行计算多份行掩码 |
| v6 | 994 | 逐块串行检查 |

这些是 **`puzzle_ctrl` 单独综合的历史读数**，不能与整机 1,264 LE 直接比较。整机 Fitter 层次表中 `puzzle_ctrl` 为 760 LE。版本过程与报告出处见[资源记录](https://github.com/tortrixx/dld/blob/main/docs/05-资源利用与编译报告.md)及[引擎说明](modules/04_puzzle_engine.md)。

## 优化付出的代价

- 碰撞检查跨多个时钟周期，需要状态、候选坐标和忙信号。
- 行扫描刷新与内容更新分开：内容更新约为 25 / 21 Hz，行扫描为 125 Hz。
- LAB 已满，剩余 LE 不意味着新逻辑一定能装入；必须重新跑 Fitter 才能判断。
- Fitter seed 会影响装箱与时序。已有基线使用 seed 8，不能把它当作修改 RTL 后仍最优的配置。

这类优化保留了功能，却增加了调度复杂度。详见[工程取舍](decisions.md)和[验证记录](verification.md)。
