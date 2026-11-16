# 验证与测试

软件演示、RTL 仿真、静态时序分析与硬件验收各有边界。以下是仓库已有证据，不是本次网站维护新产生的硬件测试结果。

## 证据分层

| 类别 | 能支持的结论 | 不能替代 |
|---|---|---|
| 软件规则模型 GIF | 规则与操作流程的可视化 | RTL 正确性、真实板卡效果 |
| Python 测试台与 VWF 断言 | 已定义场景中的信号行为 | 未覆盖输入、硬件电气行为 |
| Quartus GUI 波形 | 所显示观测点的仿真变化 | 截图未捕获的内部信号 |
| 编译与时序记录 | 指定器件和约束下的资源、时序结果 | 实际运行频率测量、修改后的新结果 |
| 上板文字记录 | 历史人工验收结论 | 本次现场复测、硬件照片或录像 |

## 历史仿真明细

表格从 `facts/facts.json` 生成，记录保留了时间、轮次与测试台入口。整机历史测试还有多种场景；下表展示各模块最新记录，总计按事实模型汇总。

| 模块 | 最新轮次 | 通过 / 总数 | 原始记录时间 | 入口 |
|---|---|---|---|---|
{{SIM_TABLE}}

[事实模型](https://github.com/tortrixx/dld/blob/main/facts/facts.json)汇总为 **12 个模块／场景、{{ASSERTIONS}} / {{ASSERTIONS}} 条断言通过**。更新测试后需重新生成事实模型并检查，不能只改这句摘要。

## 波形如何阅读

![游戏状态机仿真波形](assets/images/GUI-game_fsm.png)
*Quartus GUI 波形裁图：截图刻度至 204.8 µs，总长 222.02 µs。仿真中的 1 Hz 节拍被压缩为 2 µs，不代表板卡秒数。*

先核对测试台的时间补丁，再看信号名、触发条件和变化沿。图中没有的信号要回到 VWF 与断言核对。各模块页保留了具体时间窗和波形说明。

- [状态迁移与散落握手](modules/03_game_fsm.md)
- [碰撞、旋转与等价铺法](modules/04_puzzle_engine.md)
- [LFSR 周期与复位](modules/05_rom_random.md)

## 本地证据检查

```bash
python scripts/extract_facts.py --check
python scripts/check_docs.py
python scripts/audit_evidence.py
python scripts/check_geometry.py
python scripts/check_plans.py
```

这些命令检查事实、文档、历史证据或软件模型。重新运行 RTL 仿真仍需要 Quartus，详见[构建复现](reproducibility.md)。本次网站构建与浏览器验收记录单独保存在仓库的 `zensical-site/VALIDATION.md`。

!!! warning "当前源码与历史证据的差异"
    2026-11-16 运行 `audit_evidence.py` 得到 13 FAIL。当前 `puzzle_top.vhd` 的组件声明顺序与历史逻辑指纹不同，仿真和固件指纹门禁未通过。检查差异显示该文件的去注释内容变化集中于声明重排，但本次没有 Quartus 环境，不能据此补签仿真或固件一致性。资源与测试结果均按历史记录展示，后续需在工具环境中重跑完整验证。
