* **项目导览**
  * [🏠 首页概览与全局微架构](README.md)
  * [🎮 硬件操作指南与玩法手册](guide/gameplay.md)

* **分模块详细解构**
  * [01. 整机顶层与引脚集成 (puzzle_top)](modules/puzzle_top.md)
  * [02. 设计常量与纯函数包 (puzzle_pkg)](modules/puzzle_pkg.md)
  * [03. 级联分频与使能网络 (clk_gen)](modules/clk_gen.md)
  * [04. 矩阵键盘扫描与消抖 (keypad_scan)](modules/keypad_scan.md)
  * [05. 游戏主控算法状态机 (game_fsm)](modules/game_fsm.md)
  * [06. 核心拼图引擎微架构 (puzzle_ctrl)](modules/puzzle_ctrl.md)
  * [07. 关卡目标图案固化库 (pattern_rom)](modules/pattern_rom.md)
  * [08. 零片几何掩码固化库 (piece_rom)](modules/piece_rom.md)
  * [09. 8位 Galois 伪随机发生器 (rng_lfsr)](modules/rng_lfsr.md)
  * [10. 数码管格式化与除法消除 (disp_format)](modules/disp_format.md)
  * [11. 数码管 125Hz 扫描驱动 (seg_scan)](modules/seg_scan.md)
  * [12. 8×8 双色点阵动态驱动 (dot_matrix_scan)](modules/dot_matrix_scan.md)
  * [13. 数控分频与马里奥音效 (buzzer_ctrl)](modules/buzzer_ctrl.md)

* **工程专项与答辩宝典**
  * [🎓 老师答辩抽查冲刺速查宝典](guide/defense_qa.md)
  * [🧪 184条断言仿真验证体系](guide/sim_verification.md)
  * [⚡ 1264/1270 LE 极限优化与时序](guide/resource_timing.md)
  * [🛠️ 典型工程故障与排查剖析](guide/bugs_err.md)
