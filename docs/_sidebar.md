* [📋 模块导读与速查索引](README.md)

* **系统顶层与全局常量**
  * [01. 整机顶层与引脚绑定 (puzzle_top)](modules/puzzle_top.md)
  * [02. 设计常量与纯函数包 (puzzle_pkg)](modules/puzzle_pkg.md)

* **时钟与输入外设**
  * [03. 级联分频与使能网络 (clk_gen)](modules/clk_gen.md)
  * [04. 矩阵键盘扫描与消抖 (keypad_scan)](modules/keypad_scan.md)

* **主控与核心引擎**
  * [05. 游戏主控算法状态机 (game_fsm)](modules/game_fsm.md)
  * [06. 核心拼图引擎微架构 (puzzle_ctrl)](modules/puzzle_ctrl.md)

* **固化图库与随机源**
  * [07. 关卡目标图案固化库 (pattern_rom)](modules/pattern_rom.md)
  * [08. 零片几何掩码固化库 (piece_rom)](modules/piece_rom.md)
  * [09. 8位 Galois 伪随机源 (rng_lfsr)](modules/rng_lfsr.md)

* **显示与声音驱动**
  * [10. 数码管格式化与除法消除 (disp_format)](modules/disp_format.md)
  * [11. 数码管 125Hz 扫描驱动 (seg_scan)](modules/seg_scan.md)
  * [12. 8×8 双色点阵动态驱动 (dot_matrix_scan)](modules/dot_matrix_scan.md)
  * [13. 数控分频音乐音效发生器 (buzzer_ctrl)](modules/buzzer_ctrl.md)
