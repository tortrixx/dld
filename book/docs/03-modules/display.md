# 显示输出：`disp_format` / `seg_scan` / `dot_matrix_scan`

> 一句话定位：这一页回答"状态怎么变成数码管与点阵上的颜色、位序为什么必须钉死、扫描节拍是多少"。

显示子系统（S6）是**纯输出**：它不做任何游戏决策，只把
`game_fsm.o_state/o_level/o_lvl3/o_time` 与 `puzzle_ctrl.o_rowr/o_rowg` 翻译成
引脚上的电平。三个模块的分工是：

| 模块 | 层次 | 一句话职责 | 是否保存状态 |
|---|---|---|---|
| `disp_format` | 格式 | 状态 → 8 位 BCD ＋ 消隐掩码 | ❌ 纯组合 |
| `seg_scan` | 驱动 | BCD → 七段码，1 kHz 位选 | ✅ 位选计数器 |
| `dot_matrix_scan` | 驱动 | **一行**红/绿位平面 → 16 根列线 ＋ 8 根行线 | ✅ 输出寄存器 |

## 一、模块基本信息

| 项 | `disp_format` | `seg_scan` | `dot_matrix_scan` |
|---|---|---|---|
| 子系统 | S6 显示输出 | S6 | S6 |
| 源码 | {{src:rtl/disp_format.vhd}} | {{src:rtl/seg_scan.vhd}} | {{src:rtl/dot_matrix_scan.vhd}} |
| 端口 | 7 | 10 | 9 |
| 上游 | `game_fsm`（状态/关卡/倒计时/闪烁） | `disp_format`（`o_data`/`o_blank`） | `puzzle_top`（从 `frame_*` 按 `mrow` 切片） |
| 下游 | `seg_scan` | 8 位数码管（段 `PIN_62..51`、位选 `PIN_63..31`） | 8×8 双色点阵（行 `PIN_8..1`、红 `PIN_22..11`、绿 `PIN_45..38`） |
| 核心难点 | ①口径 C（DISP2 全程熄灭）②两位拆分不能用除法器 | 位选要 ≥100 Hz，否则肉眼可见闪 | 行号方向、行数据与行索引必须同拍更新、绿色引脚与板载 LED 冲突 |

## 二、端口契约

--8<-- "_generated/ports/disp_format.md"

--8<-- "_generated/ports/seg_scan.md"

--8<-- "_generated/ports/dot_matrix_scan.md"

!!! warning "`dot_matrix_scan` **不是**扫描器"
    它一次只接收**一行**（`i_row` ＋ `i_colr` ＋ `i_colg`），自己**没有行计数器**
    —— 行推进是顶层 `puzzle_top` 的 `mrow` 计数器在 `tick_1k` 上做的
    （见 [顶层集成](top-level.md)）。本模块的活就是"把这一行点亮"：
    独热译码 ＋ 打拍输出（{{src:rtl/dot_matrix_scan.vhd:27}}）。

## 三、`disp_format`：状态 → 8 位 BCD ＋ 消隐

位序与板上一致：**位 31..28 = DISP7（最左）**，位 3..0 = DISP0（最右）。

| 状态 | DISP7 | DISP6..DISP5 | DISP4:DISP3 | DISP2 | DISP1 | DISP0 |
|---|---|---|---|---|---|---|
| `S_SELF_TEST` | `8` | `8` | `8` `8` | `8` | `8` | `8`（八位全 8，2 Hz 闪） |
| `S_IDLE` | `5` | 灭 | 灭 | **灭** | 灭 | 关卡号 1/2/3 |
| `S_PREVIEW` | 预览倒计时 | 灭 | 灭 | **灭** | 灭 | 关卡号 |
| `S_PLAYING` | 灭 | 灭 | **剩余秒数十位:个位** | **灭** | 灭 | 关卡号 |
| `S_WIN` | `P` `A` `S` `S` | | | 灭 | 灭 | 灭 |
| `S_FAIL` | `F` `A` `I` `L` | | | 灭 | 灭 | 灭 |

!!! quote "口径 C：**DISP2 全程熄灭**（用户 2026-10-12 裁决）"
    题目要求 9「进入第二关，数码管 DISP2 显示 2」与要求 3「游戏关数由 DISP0 显示」
    **互相冲突**。用户裁定要求 9 属笔误、取要求 3 口径：第二关只由 DISP0 显示 `2`，
    DISP2 在**所有**状态下都灭（自检态除外 —— B1 明文要求八位全显 `8`）。
    因此本模块**没有任何 DISP2 的赋值**，`o_blank` 默认全 `1`。
    全过程与三条独立证据见 {{src:docs/00-规范理解与需求.md}} §5 Q2、{{src:docs/06-硬件调试记录.md}} §12。

!!! bug "两位拆分**不能用除法器**"
    原来用 `t / 10` 与 `t mod 10`，Quartus 推断出 `lpm_divide`，
    而报告的关键路径（**26 ns ≈ 39 MHz**）正好穿过它的进位链 —— 连 50 MHz 都到不了。
    现在写成一张 **64 项查找表**（`case t is`），把除法器从设计里彻底去掉
    （{{src:rtl/disp_format.vhd:145}}）。

!!! note "`o_blank` 是"每位一个开关"，不是"整体开关""
    `o_blank(k) = '1'` 表示第 k 位**这一位**熄灭。`seg_scan` 用它把该位的所有段一起拉黑
    —— 这样"DISP7~DISP4 全灭"这类要求就不会把**共用的**阴极线驱动错。

## 四、`seg_scan`：段位序必须钉死

| 项 | 值 |
|---|---|
| 段线（并联） | `AA..AG` ＋ `AP`（小数点）→ `o_seg(0..7)` = `PIN_62,59,58,57,55,53,52,51`；**高电平点亮** |
| 位选（独立共阴） | `CAT0..CAT7` → `o_cat(0..7)` = `PIN_63,66,67,68,69,70,30,31`；**低电平选通** |
| 位选节拍 | `i_tick = tick_1k`（1 kHz）⇒ **每位 125 Hz** |
| 小数点 `AP` | **恒为 `0`**：本设计不用它，且该引脚与板上其它外设共用 |
| 诊断旁路 | `i_raw_en='1'` 时 BCD 译码器被旁路，`i_raw` 直通段线 |

!!! bug "历史缺陷（文件头要求**保留**这段说明）：段位序曾经是反的"
    第一版把 `AA` 放在第 7 位、`AP` 放在第 0 位。结合引脚映射，
    就等于**逻辑段 `a` 物理上接到了 `PIN_51`（小数点）**。
    现象是"`2` 显示时顶横缺一截，点亮的却是小数点"。
    这个 bug **在波形上看不出来**（RTL 自洽），只在真板上暴露 ——
    所以现在译码表**每个位的每一段都直接写字面量**，不靠移位凑
    （{{src:rtl/seg_scan.vhd:22}}）。

!!! bug "位选频率：25 Hz 会闪（用户实测反馈）"
    原注释写"200 Hz / 8 = 25 Hz，舒适地高于闪烁融合频率"——**是错的**：
    用户 2026-10-08 反馈"数码管闪得比较明显"。顶层因此把 `i_tick` 从 `tick_200`
    改成 `tick_1k` ⇒ **125 Hz/位**。本模块与节拍无关，只改正了注释口径
    （{{src:rtl/seg_scan.vhd:74}}）。

**输入输出示例（待机画面，信号名与 `sim/*.vwf` 一致）**

1. `game_fsm` 报 `o_state = S_IDLE("001")`、`o_level='0'`、`o_lvl3='0'`、`o_time=0`。
2. `disp_format` 算出 `lvlv = 1` ⇒ `d(31 downto 28) = bcd(5) = "0101"`、`bl(7) = '0'`；
   `d(3 downto 0) = bcd(1) = "0001"`、`bl(0) = '0'`；其余保持默认（数据 0、`bl='1'`）。
   ⇒ **`o_data = 0x50000001`、`o_blank = "0111_1110"`**。
3. `seg_scan` 的 `idx` 在 `tick_1k` 上 0→7 循环：
   * `idx=7` ⇒ `nib = i_data(31 downto 28) = "0101"` ⇒ 译码 `"0" & "1101101"`（a c d f g）
     ⇒ `o_seg = 0x6D`、`cat_r = "0111_1111"`（CAT7 低）⇒ **DISP7 显示 `5`**；
   * `idx=1..6` ⇒ `i_blank(idx)='1'` ⇒ `seg_r = 0`（**所有段拉黑**）⇒ 这 6 位不亮；
   * `idx=0` ⇒ `nib = "0001"` ⇒ b c 两段 ⇒ **DISP0 显示 `1`**（这个字形同时是字母 `I`，
     `S_FAIL` 画面就用它当 `I`）。
4. 每位每 1 ms 亮一次 ⇒ **125 Hz/位**，8 位一轮 8 ms。

## 五、`dot_matrix_scan`：三种颜色只由两个位平面产生

| 行 | 红平面 | 绿平面 | 显示 |
|---|---|---|---|
| 低（选通） | 高 | 低 | **红** |
| 低 | 低 | 高 | **绿** |
| 低 | 高 | 高 | **黄**（两个 LED 同时亮） |
| 低 | 低 | 低 | 灭 |
| 高 | — | — | 整行不选通 |

!!! bug "这条"两列都为高 = 熄灭"曾写错，且只在板级测试中暴露"
    早期注释写成"两列都为高电平 = 该点熄灭"，与板级测试矛盾
    —— 板级把自检画面画成了**全黄**。2026-10-08 更正为
    "两列都为高 = 黄"（{{src:rtl/dot_matrix_scan.vhd:13}}）。
    这也是 [诊断顶层](diagnostic-tops.md) 里 `board_test_top` 存在的意义之一。

!!! warning "行号方向：逻辑行 0 = 顶部，但物理 `ROW0` 在最下面"
    手册只说 `ROW0..ROW7` 接在 `PIN_8..PIN_1`，**从没说过 `ROW0` 是哪个物理边缘**。
    用 `board_test_top` 的测试 2（左上角点为红色的空心方框）实测：
    红色标记出现在**左下角** ⇒ 物理 `ROW0` 是最下面一行。
    所以 RTL 里的译码是**反的**（逻辑行 0 → `ROW7`/`PIN_1`），
    并且**保持 `.qsf` 与手册逐引脚一致**，把"反"留在 RTL 里
    （{{src:rtl/dot_matrix_scan.vhd:41}}）。

!!! danger "绿色引脚 `PIN_38..45` 与板载 LED 复用，**不能挪作他用**"
    `PIN_38..45` 由 `COLG0..COLG7` 与 `LD8..LD15` 共用，`PIN_137..144` 由 `LD8..LD15`
    与 VGA 端口共用。驱动这些 LED 会让点阵**失去绿色**，而要求 B6 依赖绿色
    （锁定 = 黄 = 红＋绿）。题目没有任何要求需要这些 LED，所以刻意不用
    （{{src:rtl/dot_matrix_scan.vhd:35}}）。

!!! note "为什么不会出现"鬼影"（相邻行串扰）"
    行数据（`i_colr`/`i_colg`）与行索引（`i_row`）由**同一个源**在**同一拍**更新，
    并且本模块的输出是**寄存器**（`o_row`/`o_colr`/`o_colg` 同时打拍）
    ⇒ 一行绝不会被另一行的数据驱动（{{src:rtl/dot_matrix_scan.vhd:51}}）。

## 六、验证与证据

--8<-- "_generated/assertions/disp_format.md"

--8<-- "_generated/assertions/seg_scan.md"

--8<-- "_generated/assertions/dot_matrix_scan.md"

<figure markdown="span">
  ![disp_format：状态 → BCD 与消隐掩码](../assets/waveforms/quartus/GUI-disp_format.png){ loading=lazy }
  <figcaption>
  **图 3.7** `disp_format` 的 Quartus 波形编辑器实测截图（`sim/disp_format.vwf`）。
  观察信号：`i_state`、`i_level`、`i_lvl3`、`i_time`、`i_blink`、`o_data`、`o_blank`。
  预期：自检八位全 `8` 且随 `i_blink` 整体亮灭；待机 `o_data = 0x50000001`；对局 `DISP4:DISP3` 是两位倒计时；**DISP2 在所有窗口都灭**。
  实测：`r27` 的 16 条断言全过（{{fact:sim.modules.disp_format.passed}} / {{fact:sim.modules.disp_format.total}}），其中 ⑥c 覆盖 **76 个窗口**。
  证据：{{src:sim/rounds/disp_format/r27.json}}、`sim/disp_format.vwf`。
  **能证明**：各状态的编码、两位拆分、消隐掩码、口径 C。
  **不能证明**：数码管在板上的亮度与对比度 —— 那是【板级实测】。
  </figcaption>
</figure>

<figure markdown="span">
  ![seg_scan：位选与七段译码](../assets/waveforms/quartus/GUI-seg_scan.png){ loading=lazy }
  <figcaption>
  **图 3.8** `seg_scan` 的 Quartus 波形编辑器实测截图（`sim/seg_scan.vwf`）。
  观察信号：`i_tick`、`i_data`、`i_blank`、`i_raw_en`、`i_raw`、`idx`、`nib`、`decoded`、`o_seg`、`o_cat`。
  预期：`idx` 每 1 ms 加一（每位 125 Hz）；`o_cat` 恒为独热低有效；`AP`（bit7）恒 `0`；`i_raw_en='1'` 时 `o_seg` 直通 `i_raw`。
  实测：`r31` 的 12 条断言全过（{{fact:sim.modules.seg_scan.passed}} / {{fact:sim.modules.seg_scan.total}}）。
  证据：{{src:sim/rounds/seg_scan/r31.json}}、`sim/seg_scan.vwf`。
  **能证明**：位选计数、独热阴极、七段码表、消隐、调试旁路。
  **不能证明**：真实数码管的段-引脚对应（那只能靠 `i_raw` 在板上逐段实测）。
  </figcaption>
</figure>

<figure markdown="span">
  ![dot_matrix_scan：行选通与双色位平面](../assets/waveforms/quartus/GUI-dot_matrix_scan.png){ loading=lazy }
  <figcaption>
  **图 3.9** `dot_matrix_scan` 的 Quartus 波形编辑器实测截图（`sim/dot_matrix_scan.vwf`）。
  观察信号：`i_en`、`i_row`、`i_colr`、`i_colg`、`row_sel`、`o_row`、`o_colr`、`o_colg`。
  预期：`o_row` 恒为独热低有效且随 `i_row` 移动；`i_en='0'` 时三组输出全灭；红/绿两平面直通打拍（都高 = 黄）。
  实测：`r23` 的 7 条断言全过（{{fact:sim.modules.dot_matrix_scan.passed}} / {{fact:sim.modules.dot_matrix_scan.total}}）。
  证据：{{src:sim/rounds/dot_matrix_scan/r23.json}}、`sim/dot_matrix_scan.vwf`。
  **能证明**：行译码方向、输出寄存、使能语义。**不能证明**：板上的行方向（那是 `board_test_top` 测试 2 的板级实测结论）。
  </figcaption>
</figure>

| 证据类别 | 有什么 | 缺什么 |
|---|---|---|
| 【RTL 仿真】 | `disp_format r27` = {{fact:sim.modules.disp_format.passed}}/{{fact:sim.modules.disp_format.total}}；`seg_scan r31` = {{fact:sim.modules.seg_scan.passed}}/{{fact:sim.modules.seg_scan.total}}；`dot_matrix_scan r23` = {{fact:sim.modules.dot_matrix_scan.passed}}/{{fact:sim.modules.dot_matrix_scan.total}} | — |
| 【编译/STA】 | 去掉除法器后的关键路径改善（26 ns → 见 `docs/05`） | 无模块级独立 STA |
| 【板级实测】 | 段位序（用 `i_raw` 逐段实测）、行方向（`board_test_top` 测试 2）、闪烁反馈（用户"闪得明显"） | 没有亮度/色温测量；"黄色"只有肉眼结论 |

## 证据与出处

| 结论 | 依据 |
|---|---|
| 各状态的显示内容与需求编号（B1~B5/A2） | {{src:rtl/disp_format.vhd:5}} |
| 口径 C（DISP2 全程熄灭）的裁决 | {{src:rtl/disp_format.vhd:25}}、{{src:docs/00-规范理解与需求.md}}、{{src:docs/06-硬件调试记录.md}} |
| 除法器 → 查找表（26 ns 关键路径） | {{src:rtl/disp_format.vhd:145}} |
| `o_data`/`o_blank` 的位序与"每位一个开关" | {{src:rtl/disp_format.vhd:33}}、{{src:rtl/seg_scan.vhd:143}} |
| 段位序历史缺陷（`AA` 曾在第 7 位） | {{src:rtl/seg_scan.vhd:22}} |
| 位选 125 Hz（原 25 Hz 会闪） | {{src:rtl/seg_scan.vhd:74}} |
| 点阵颜色规则与"两列都高 = 黄"的更正 | {{src:rtl/dot_matrix_scan.vhd:10}} |
| 行号方向（逻辑 0 = 顶部，物理 `ROW0` 在最下） | {{src:rtl/dot_matrix_scan.vhd:41}} |
| `PIN_38..45` 与板载 LED 复用（不能用） | {{src:rtl/dot_matrix_scan.vhd:35}} |
| 引脚锁定 | {{src:quartus/puzzle.qsf}}、`book/docs/_generated/pins.md` |
| 实测数值 | {{src:sim/rounds/disp_format/r27.json}}、{{src:sim/rounds/seg_scan/r31.json}}、{{src:sim/rounds/dot_matrix_scan/r23.json}} |
