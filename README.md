# 简易拼图游戏（FPGA 课程设计 · 选题 4）

MAX II **EPM1270T144C5**（MAXII 数字逻辑实验开发板，LCM12864 扩展板）上的 8×8 点阵拼图游戏，
VHDL-93 + Quartus II 9.1，纯 RTL（无 Nios、无软核）。

**本文件是仓库入口。** 刚接手（人或 AI）请按 §5 的顺序读文档，再按 [`HANDOFF.md`](HANDOFF.md) 顶部的
**「下一轮开工清单」**继续。

---

## 1. 游戏规则（对应课程要求 B1~B11）

| 关卡 | 目标图案 | 零片 | 限时 |
|---|---|---|---|
| 第一关 | 4×3 矩形（12 格） | 3 块**完全相同的 4×3 矩形** | 30 s |
| 第二关 | 4×4 方块（16 格） | 4 块**完全相同的 2×2 方块** | 40 s |

- 待机：点阵全灭、数码管显示「5____1」（B2）；
- 按【开始】→ 预览阶段：点阵显示完整目标图案并**从 5 倒数**，数码管同步（B4）；
- 对局：移动/选择/确认、零片散落、选中绿、锁定黄（B5~B9）；
- 全部锁定且**零片并集 == 目标图案** → 胜利；超时或"锁满但画面不对" → 失败（B9/B10）；
- 胜利 = 点阵**红色粗对勾**、失败 = **红色叉**；结算画面**先闪 2 个 2 Hz 周期再常亮**，
  数码管最左四位拼 **PASS / FAIL**；
- 【开始】可随时重开一轮（对局中、失败后、胜利后，B11）；
- 拨动 SW7 到 0 → 立刻回到自检（8 位数码管全亮 8、2 Hz 闪）并清空状态（B1）。

按键（板子手册附图 26）：**开始** KEY14、**选择** KEY16、**上/下/左/右** KEY7/KEY15/KEY10/KEY12、
**确认** KEY11（KEY13 在本板上不可用）。

---

## 2. 当前状态（固件时间戳 **2026-10-09 00:28:17**）

| 项 | 实测值 |
|---|---|
| 逻辑单元 | **1195 / 1270 LE（94%）**，余量 75 |
| Fmax | **41.39 MHz**（关键路径 = 散落的 `mod` 运算，属人机接口域，见 HANDOFF §6 残余） |
| 引脚 / 未约束引脚 | 52 / **0** |
| 仿真 | 12 个模块 / **132 条断言全部通过**（最新轮次见 [`docs/03`](docs/03-仿真验证方案.md) §2） |
| 显示刷新 | 点阵与数码管均 **125 Hz**（扫描走 1 kHz 节拍，肉眼不再闪） |
| 烧录 | `quartus/output_files/puzzle.pof`，USB-Blaster，Verify 全过 0 errors / 0 warnings |
| 缺陷记录 | **ERR-001 ~ ERR-030**，见 [`docs/06-硬件调试记录.md`](docs/06-硬件调试记录.md) |

**只有"上板复测"这一步是人做的**，清单在 [`HANDOFF.md`](HANDOFF.md) §7⓪；其余全部有脚本/仿真证据。

---

## 3. 目录结构

```
rtl/          16 个 VHDL 文件 = **11 个功能实体**（clk_gen、keypad_scan、dot_matrix_scan、
              seg_scan、disp_format、buzzer_ctrl、pattern_rom、piece_rom、rng_lfsr、
              puzzle_ctrl、game_fsm）+ 主顶层 **puzzle_top** + 板级自检顶层 board_test_top
              + 2 个按键诊断顶层（keypad_diag_top / keypad_raw_top）+ 公共包 **puzzle_pkg**
sim/          12 个 Python 测试台（tb_*.py）+ .vwf 向量 + rounds/（每轮断言记录 rNN.md/json）
scripts/      gen_project.py（生成 Quartus 工程）、build.tcl 的入口、
              sim.py（跑仿真/校验/出图）、vwf.py（波形解析）、sim_summary.py（汇总）、
              check_geometry.py（图案与功耗几何静态检查）、check_keypad_pins.py（管脚一致性）
quartus/      Quartus II 9.1 工程与报告（output_files/puzzle.{fit,sta,map}.rpt）
docs/         00 规范理解与需求 / 02 模块详细设计 / 03 仿真验证方案 /
              05 资源利用与编译报告 / 06 硬件调试记录 + 图/（每模块波形 SVG + 结算画面预览 PNG）
```

---

## 4. 常用命令（Windows · PowerShell）

```powershell
# 0) 依赖：Quartus II 9.1 装在 C:\QuartusII91\QuartusII91\；Python 用仓库脚本即可
# 1) 生成/更新 Quartus 工程（改过 RTL 的文件列表或顶层时）
python scripts/gen_project.py puzzle_top

# 2) 编译（结果看 quartus/output_files/puzzle.fit.rpt 与 .sta.rpt）
& "C:/QuartusII91/QuartusII91/quartus/bin/quartus_sh.exe" -t scripts/build.tcl

# 3) 烧录（在 quartus/output_files 目录下执行）
& "C:/QuartusII91/QuartusII91/quartus/bin/quartus_pgm.exe" -c "USB-Blaster [USB-0]" -m jtag -o "p;puzzle.pof"

# 4) 仿真：只跑一个模块（⚠️ 同一个模块不能并发跑！见 docs/06 ERR-028）
python scripts/sim.py run game_fsm            # 自动分配轮次 rNN
python scripts/sim.py check puzzle_top --round 22   # 只重跑校验（复用已有波形）
python scripts/sim_summary.py                 # 汇总所有模块最新轮次

# 5) 静态检查
python scripts/check_geometry.py              # 图案/结算画面几何 + 功耗
python scripts/check_keypad_pins.py           # 按键管脚 vs 手册
```

仿真用**压缩时钟**（`sim/tb_puzzle_top.py` 的 `RTL_PATCHES`：50 MHz → 80 kHz，随机源钉 0），
所以 96 ms 的仿真等价于板上的 60 s 对局；断言里的 ns 要按 **625 倍**换算成板上时间。

---

## 5. 建议阅读顺序

1. [`HANDOFF.md`](HANDOFF.md) —— **先读顶部「下一轮开工清单」**，再看 §0 状态、§5 错误索引、§7⓪ 上板清单；
2. [`docs/00-规范理解与需求.md`](docs/00-规范理解与需求.md) —— 需求逐条对照（含"基本要求 ✅ / 提高要求 🔶❌"的诚实状态）；
3. [`docs/02-模块详细设计.md`](docs/02-模块详细设计.md) —— 各模块接口、时钟节拍表、按键映射；
4. [`docs/03-仿真验证方案.md`](docs/03-仿真验证方案.md) —— 每个断言在验什么、参考模型怎么独立算；
5. [`docs/06-硬件调试记录.md`](docs/06-硬件调试记录.md) —— **ERR-001~030 的完整教训**（含"注释里的假设是错的""测试台陈旧常量""同模块仿真不能并发"等）；
6. [`PROGRESS.md`](PROGRESS.md) / [`AI_LOG.md`](AI_LOG.md) —— 阶段进展与每轮的证据链。

## 6. 下一步（摘要）

1. 上板复测当前固件（红色粗对勾 + PASS/FAIL + 125 Hz 扫描）；
2. **A2/S1「图案库随机选择」**（提高要求里唯一明确未实现的项，实现要点见 HANDOFF 开工清单）；
3. 再评估 A3 方向随机 / A4 90° 旋转（代价大，属可选）；
4. 已知残余见 HANDOFF §6.2（ERR-018b、随机散落恰好等于目标摆法 ~1e-5、Fmax 41.39 MHz < 50 MHz、内容更新 25 Hz）。
