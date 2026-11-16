# 工程验证

文档中的结论必须区分**自动化仿真、软件演示、Quartus 编译报告**与**实际开发板复测**，它们不能互相替代。

## 证据分类

| 类别 | 仓库中的来源 | 能证明什么 |
|---|---|---|
| 仿真断言 | `sim/rounds/` | 已定义输入与场景下的逻辑行为 |
| GUI 波形截图 | `docs/图/GUI-*.png` | Quartus 波形查看器中的仿真结果 |
| 资源与时序 | `quartus/build_provenance.json` 与报告 | 目标器件上综合、布局布线及时序结果 |
| 软件演示 GIF | `docs/assets/images/demo-run.gif` | 规则模型的可视化，不等同于板卡运行录像 |
| 上板复测 | `README.md` 与工程记录 | 仓库记录的实际硬件验收结论；没有板卡实拍 |

![游戏状态机波形](assets/images/GUI-game_fsm.png)

*Quartus GUI 仿真截图，不能作为硬件实拍或实际工作频率的直接证据。*

## 关键验证结果

仓库 README 记录 **12 个模块/场景与 184 条断言通过**、**Fmax 54.27 MHz**、**1264 / 1270 LE**、**127 / 127 LAB**。这些是已有构建记录的基线，不代表后续任意 RTL 修改后仍然成立。

!!! warning "关于仿真时间"
    部分测试台为了缩短验证时间会压缩时钟参数，因此波形时间轴不能直接视作板卡真实秒数。详见各模块说明及原始测试台。

## 深入核对

- [仿真原始轮次](https://github.com/tortrixx/dld/tree/main/sim/rounds)
- [资源报告与工程记录](https://github.com/tortrixx/dld/blob/main/docs/05-%E8%B5%84%E6%BA%90%E5%88%A9%E7%94%A8%E4%B8%8E%E7%BC%96%E8%AF%91%E6%8A%A5%E5%91%8A.md)
- [硬件调试记录](https://github.com/tortrixx/dld/blob/main/docs/06-%E7%A1%AC%E4%BB%B6%E8%B0%83%E8%AF%95%E8%AE%B0%E5%BD%95.md)
