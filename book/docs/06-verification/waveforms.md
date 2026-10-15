# 波形与图注

> 这一页回答：**12 张真实的 Quartus 仿真截图分别证明了什么** —— 以及"脚本渲染的波形"为什么不能当截图用。

## 一、两类图不是一回事

| 类别 | 路径 | 数量 | 怎么来的 | 能不能当仿真证据 |
|---|---|---|---|---|
| **Quartus GUI 实测截图** | `../assets/waveforms/quartus/GUI-<模块>.png` | 12 | 在 **Quartus II 9.1 波形编辑器界面**里打开 `sim/<模块>.vwf`，按 `Ctrl+W`（Fit in Window）后截取**波形编辑器区域** | ✅ **能**：这是工具界面里的真实截图 |
| 脚本渲染波形 | `../assets/waveforms/scripted/SIM-<模块>.svg` | 12 | 站点脚本从 `.vwf` 解析翻转后**自己画**的 SVG | ❌ **不能**：它是辅助阅读用的重绘图，**不是** Quartus 截图 |
| 演示动画 / 渲染图 | `../assets/figures/*.gif`、`演示-首帧.png`、`结算画面-预览.png` | 3 | 由网页引擎渲染 | ❌ **不是**硬件实拍，也不是 Quartus 截图 |
| **真实开发板实拍照片** | `../assets/hardware/` | **0** | —— | ⚠️ **缺失**，见 [上板验证](board-validation.md) |

!!! danger "两条不能混的说法"
    1. 把 `SIM-*.svg` 说成"Quartus 截图" —— 图标少了菜单栏与工程名，看着像，但它是重绘的；
    2. 把 `演示-*.gif` 说成"硬件实测" —— 那是浏览器里的引擎渲染，**本仓库没有一张真实硬件照片**。

## 二、本项目的截图规范：只留波形编辑器区域

| 要求 | 原因 |
|---|---|
| **必须**裁掉窗口标题栏 | 标题栏写的是**本机绝对路径 + Windows 用户名**（`Quartus II - C:/Users/<用户名>/…`），贴进公开仓库等于泄露本机路径 |
| 只保留：`.vwf` 标题条、`Master Time Bar`、`Name` 列表、波形网格、时间刻度 | 报告里只需要"哪些信号、什么时刻、什么电平"；菜单栏/工具栏/Project Navigator/Tasks/Messages/状态栏都是噪声 |
| 裁法：量出 **MDI 客户区**（`MDIClient`）矩形再裁，**不要**用"固定裁掉顶部 N 像素" | 固定偏移会随窗口大小/停靠面板变化而错位；本项目 12 张统一为 **1461 × 686** |
| 一律先按 `Ctrl+W`（Fit in Window） | 否则波形挤在左侧一小条、右边大片空白，周期看不出来 |

口径出处与操作步骤见 {{src:docs/图/README.md}}（§0.1 是定稿口径）。

## 三、逐张图注（12 张 GUI 截图）

图注统一给五件事：**测试场景 / 观察信号 / 预期 / 实测（引轮次）/ 证据**，并写清**能证明 / 不能证明**。
"实测"一律指向该模块最新一轮的 `rNN.json`，不另抄数字。

<figure markdown="span">
  ![clk_gen：7 档 tick 的分频链](../assets/waveforms/quartus/GUI-clk_gen.png){ loading=lazy }
  <figcaption>
  **图 6.1** `clk_gen` 的 7 档 tick 与按键消抖。
  测试场景：`tb_clk_gen` 断言 ①③⑥⑧；观察信号 `o_tick_1k/200/100/40/4hz/2hz/1hz`、`o_rst`、`por_cnt`、`bcnt`；
  预期：每档 tick 都是 1 个 `clk` 周期的单拍脉冲，消抖窗 19~20 个标称 ms；
  实测：见 {{src:sim/rounds/clk_gen/r25.json}}（① 全部 3094 个脉冲宽度 = 20 ns）。
  **能证明**：分频计数器与消抖计数器的时序关系正确。**不能证明**：板子上 50 MHz 晶振的绝对频率。
  </figcaption>
</figure>

<figure markdown="span">
  ![keypad_scan：扫描与按下/释放脉冲](../assets/waveforms/quartus/GUI-keypad_scan.png){ loading=lazy }
  <figcaption>
  **图 6.2** `keypad_scan` 的 4×4 扫描与消抖。
  测试场景：`tb_keypad_scan` 断言 ⑨；观察信号 `i_kp_row`、`o_key`、`o_press`、内部状态；
  预期：按下与释放各产生一次单拍 `o_press`，消抖 4 个连续相同样（40 ms 板上）；
  实测：见 {{src:sim/rounds/keypad_scan/r27.json}}（`press = ['88010','824010']`）。
  **能证明**：扫描状态机与消抖逻辑对。**不能证明**：真实机械按键的抖动时长与手感。
  </figcaption>
</figure>

<figure markdown="span">
  ![game_fsm：三关状态机的限时与闪烁](../assets/waveforms/quartus/GUI-game_fsm.png){ loading=lazy }
  <figcaption>
  **图 6.3** `game_fsm` 的三关推进。
  测试场景：`tb_game_fsm` 断言 ③⑥⑪b⑮；观察信号 `o_state`、`o_time`、`o_level`、`o_lvl3`、`o_go`、`o_blink`；
  预期：一/二/三关限时 30 / 40 / 60 s，`o_go` 每局仅一次，`o_blink` 是 2 Hz 方波；
  实测：见 {{src:sim/rounds/game_fsm/r36.json}}（进对局时 `o_time=30`；第三关 `o_time=60`、`o_lvl3=1`）。
  **能证明**：状态迁移、限时加载与闪烁波形。**不能证明**：玩家实际操作下的状态序列（那由整机测试覆盖）。
  </figcaption>
</figure>

<figure markdown="span">
  ![puzzle_ctrl：散落、选中、旋转与整帧判据](../assets/waveforms/quartus/GUI-puzzle_ctrl.png){ loading=lazy }
  <figcaption>
  **图 6.4** `puzzle_ctrl` 的引擎行为。
  测试场景：`tb_puzzle_ctrl` 断言 ⑤⑫⑳；观察信号 `o_piece_pos`、`o_piece_ori`、`o_sel`、`o_lock`、`o_all_lock`、`o_solved`；
  预期：重叠被拒、扫描账目守恒、整帧判据在提交之后重算；
  实测：见 {{src:sim/rounds/puzzle_ctrl/r37.json}}（⑳：18 763 个采样拍里 `o_all_lock=1` 的误判 0 次）。
  **能证明**：引擎的几何判定与主路径竞态保护。**不能证明**：算法在有限 LE 下是否还有别的边界组合（见 ⑫ 的扫描覆盖）。
  </figcaption>
</figure>

<figure markdown="span">
  ![pattern_rom：图案库查表](../assets/waveforms/quartus/GUI-pattern_rom.png){ loading=lazy }
  <figcaption>
  **图 6.5** `pattern_rom` 的图案查表。
  测试场景：`tb_pattern_rom` 断言 ②（及其余 8 条）；观察信号 `i_pat`、`i_level`、`o_rows`；
  预期：第一关恒为图 4-1（忽略图案库），第二关 PAT3、第三关随机；
  实测：见 {{src:sim/rounds/pattern_rom/r21.json}}（`i_pat=3, i_level=0` 输出 `0x00001C1C1C1C0000`）。
  **能证明**：查表内容与关卡选择逻辑。**不能证明**：随机源本身的周期（由 `rng_lfsr` 负责）。
  </figcaption>
</figure>

<figure markdown="span">
  ![piece_rom：四块异形零片](../assets/waveforms/quartus/GUI-piece_rom.png){ loading=lazy }
  <figcaption>
  **图 6.6** `piece_rom` 的零片形状库。
  测试场景：`tb_piece_rom` 断言 ③（及其余 10 条）；观察信号 `i_shape`、`i_ori`、`o_rows`；
  预期：第二关四块异形零片格数 `[3,2,5,6]`、形状互不相同，合计 16 格 = 目标图案格数；
  实测：见 {{src:sim/rounds/piece_rom/r23.json}}。
  **能证明**：形状/朝向查表与零片集合自洽。**不能证明**：这四块真的能拼成目标图案（由整机 ⑪ 证明）。
  </figcaption>
</figure>

<figure markdown="span">
  ![rng_lfsr：255 周期的伪随机序列](../assets/waveforms/quartus/GUI-rng_lfsr.png){ loading=lazy }
  <figcaption>
  **图 6.7** `rng_lfsr` 的最大长度序列。
  测试场景：`tb_rng_lfsr` 断言 ③⑩；观察信号 `o_val`、内部 `sr`、抽头 `fb`；
  预期：周期恰 255、状态不重复、复位分支真的被激励；
  实测：见 {{src:sim/rounds/rng_lfsr/r23.json}}（第 255 拍回到 `0x5A`，1~254 拍无提前回初值）。
  **能证明**：多项式是最大长度序列，复位通路有效。**不能证明**：这个"随机"在游戏性上够不够随机。
  </figcaption>
</figure>

<figure markdown="span">
  ![dot_matrix_scan：8 行扫描与红绿列](../assets/waveforms/quartus/GUI-dot_matrix_scan.png){ loading=lazy }
  <figcaption>
  **图 6.8** `dot_matrix_scan` 的行扫描。
  测试场景：`tb_dot_matrix_scan` 断言 ①②⑤b；观察信号 `o_row`、`o_colr`、`o_colg`、`i_en`；
  预期：每次恰一位为低且等于 `7-row`、红绿列互斥、早采样点无鬼影；
  实测：见 {{src:sim/rounds/dot_matrix_scan/r23.json}}（144 点行序正确；180 个早采样点全为本窗口期望）。
  **能证明**：行序、消隐与红绿互斥。**不能证明**：LED 的实际亮度与余辉（观感）。
  </figcaption>
</figure>

<figure markdown="span">
  ![seg_scan：位选、段码与结算拼字](../assets/waveforms/quartus/GUI-seg_scan.png){ loading=lazy }
  <figcaption>
  **图 6.9** `seg_scan` 的数码管扫描。
  测试场景：`tb_seg_scan` 断言 ③⑧b⑪；观察信号 `o_seg`、`o_cat`、`i_raw_en`、`i_en`；
  预期：位选低有效且互不重叠、位选与段码同源、`i_en` 压过 `i_raw_en`、结算拼出 PASS/FAIL；
  实测：见 {{src:sim/rounds/seg_scan/r31.json}}（108 个显示状态段码一致；W12 的 `o_seg` 恒 `0x00`）。
  **能证明**：扫描与熄灭掩码逻辑。**不能证明**：真实数码管的亮度均匀性。
  </figcaption>
</figure>

<figure markdown="span">
  ![disp_format：各状态下的 8 位数码管内容](../assets/waveforms/quartus/GUI-disp_format.png){ loading=lazy }
  <figcaption>
  **图 6.10** `disp_format` 的状态 → 内容映射。
  测试场景：`tb_disp_format` 断言 ⑥c⑦b；观察信号 `o_data`、`o_blank`、内部 `tens`/`ones`；
  预期：自检八位全 8、倒计时两位拆分、口径 C 下 `DISP2` 恒熄灭；
  实测：见 {{src:sim/rounds/disp_format/r27.json}}（76 个窗口 `DISP2` 全灭；`t=0..63` 逐项一致）。
  **能证明**：显示内容与消隐掩码。**不能证明**：这条口径本身是否满足题目要求（需求裁定问题）。
  </figcaption>
</figure>

<figure markdown="span">
  ![buzzer_ctrl：乐句、音高与占空比](../assets/waveforms/quartus/GUI-buzzer_ctrl.png){ loading=lazy }
  <figcaption>
  **图 6.11** `buzzer_ctrl` 的乐句与方波。
  测试场景：`tb_buzzer_ctrl` 断言 ⑥⑦⑩⑪；观察信号 `o_buzz`、内部 `step`、`cnt`、`tone_sel`；
  预期：8 个音高的翻转间隔 == `(补丁 half+1)×2`、休止步真的静音、占空比 50%；
  实测：见 {{src:sim/rounds/buzzer_ctrl/r37.json}}（高/低各 7520 ns ⇒ 50.0%）。
  **能证明**：音高表、节拍与占空比。**不能证明**：三个提示音"分不分得清"（那是板级听感）。
  </figcaption>
</figure>

<figure markdown="span">
  ![puzzle_top：整机三关流程与结算画面](../assets/waveforms/quartus/GUI-puzzle_top.png){ loading=lazy }
  <figcaption>
  **图 6.12** `puzzle_top` 的整机波形（含 8 段子仿真）。
  测试场景：`tb_puzzle_top` 断言 ①⑤⑧⑬⑱⑲⑳㉒；观察信号点阵三色列、`seg`/`cat`、`buzz`、状态码；
  预期：自检画面全黄 + 八位全亮/全灭都出现、三关连过、胜利绿对勾 + PASS、对局中四键不发声；
  实测：见 {{src:sim/rounds/puzzle_top/r56.json}}（模式 A）与 {{src:sim/rounds/puzzle_top/r57.json}}（模式 B），各 28/28。
  **能证明**：跨模块协议与整机流程。**不能证明**：真实板子上的观感/听感/手感。
  ⚠️ 整机波形是 **8 段子仿真拼接**（`TRANSITION_LIST` 1271 段 ≠ 165 个唯一节点名），读法见 [整机测试](integration-tests.md)。
  </figcaption>
</figure>

## 四、脚本渲染波形（12 张，**不是** Quartus 截图）

这 12 张由站点脚本从 `.vwf` 重绘，用途是网页里放大阅读（SVG 不失真）。**它们不能替代 GUI 截图**：
图里没有 Quartus 的界面元素，也就无法证明"这份数据是在 Quartus 里跑出来的"。

每张 SVG 与上面同模块的 GUI 截图**读的是同一份 `.vwf`**，所以"测试场景 / 观察信号 / 预期 / 实测"
与图 6.x 完全相同（见该图的 `<figcaption>`）；差别只在**证据级别**与**阅读便利性**：

| 模块 | 文件 | 测试场景（= 同一张 GUI 截图） | 能证明 | 不能证明 |
|---|---|---|---|---|
| `clk_gen` | `../assets/waveforms/scripted/SIM-clk_gen.svg` | 图 6.1：`tb_clk_gen` ①③⑥⑧ | 分频比与消抖窗的**数值关系**（便于放大读数） | 这份数据在 Quartus 里跑过（重绘本身不构成证据） |
| `keypad_scan` | `../assets/waveforms/scripted/SIM-keypad_scan.svg` | 图 6.2：断言 ⑨ | 扫描/消抖的时序关系 | 同上 |
| `game_fsm` | `../assets/waveforms/scripted/SIM-game_fsm.svg` | 图 6.3：断言 ③⑥⑪b⑮ | 状态迁移与限时加载 | 同上 |
| `puzzle_ctrl` | `../assets/waveforms/scripted/SIM-puzzle_ctrl.svg` | 图 6.4：断言 ⑤⑫⑳ | 引擎几何判定与整帧判据 | 同上 |
| `pattern_rom` | `../assets/waveforms/scripted/SIM-pattern_rom.svg` | 图 6.5：断言 ② | 图案查表内容 | 同上 |
| `piece_rom` | `../assets/waveforms/scripted/SIM-piece_rom.svg` | 图 6.6：断言 ③ | 零片形状/朝向查表 | 同上 |
| `rng_lfsr` | `../assets/waveforms/scripted/SIM-rng_lfsr.svg` | 图 6.7：断言 ③⑩ | LFSR 周期与复位分支 | 同上 |
| `disp_format` | `../assets/waveforms/scripted/SIM-disp_format.svg` | 图 6.10：断言 ⑥c⑦b | 8 位数码管内容与消隐掩码 | 同上 |
| `seg_scan` | `../assets/waveforms/scripted/SIM-seg_scan.svg` | 图 6.9：断言 ③⑧b⑪ | 位选/段码同源与拼字 | 同上 |
| `dot_matrix_scan` | `../assets/waveforms/scripted/SIM-dot_matrix_scan.svg` | 图 6.8：断言 ①②⑤b | 行序、红绿互斥、早采样点 | 同上 |
| `buzzer_ctrl` | `../assets/waveforms/scripted/SIM-buzzer_ctrl.svg` | 图 6.11：断言 ⑥⑦⑩⑪ | 音高翻转间隔与占空比 | 同上 |
| `puzzle_top` | `../assets/waveforms/scripted/SIM-puzzle_top.svg` | 图 6.12：断言 ①⑤⑧⑬⑱⑲⑳㉒ | 整机跨模块协议 | 同上；且整机 SVG 是 8 段子仿真的重绘，**段数 ≠ 节点数** |

!!! warning "引用规范"
    在报告/答辩里，**优先放 GUI 截图**（它是"在 Quartus 里跑出来的"的唯一证据）；
    SVG 只作为"放大看细节"的补充，并且必须同时保留它的**证据级别标注**。

## 五、图片总清单（机械生成，含证据分级）

--8<-- "_generated/figures.md"

## 证据与出处

| 结论 | 依据 |
|---|---|
| 12 张 GUI 截图与 12 张脚本渲染图 | {{src:docs/图/README.md}}（清单所有者）、`book/docs/_generated/figures.md` |
| 截图口径（只留波形编辑器区域、1461×686） | {{src:docs/图/README.md}} §0.1 |
| 各图对应的轮次与实测值 | {{src:sim/rounds/clk_gen/r25.json}}、{{src:sim/rounds/puzzle_top/r56.json}}、{{src:sim/rounds/puzzle_top/r57.json}} 等（见各图注） |
| 整机波形的分段读法 | {{src:docs/图/README.md}} §2.1 |
| 素材同步到文档站的机制 | {{src:book/scripts/sync_assets.py}} |
