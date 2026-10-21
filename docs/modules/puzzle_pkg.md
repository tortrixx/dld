# 02 · 设计常量与纯函数包 (`puzzle_pkg`)

> **所属子系统**：全局真值基础 ｜ **源文件**：[`rtl/puzzle_pkg.vhd`](file:///c:/Users/sznnn/Desktop/dld/rtl/puzzle_pkg.vhd) ｜ **性质**：纯函数与常量包（不生成任何独立硬件实体）

---

## 1. 模块职责与在系统中的定位

<div class="plain-explain-box">
  💡 <strong>大白话一句话理解本模块</strong>：<br>
  它是全设计的<strong>“标准数据字典与常量手册”</strong>。它在物理芯片上不生成任何独立电路（0 个 LE 消耗），但它规定了全工程的统一标准：比如矩阵键盘各个键号定义、点阵屏 64 个点对应的编号、关卡图案几何掩码与音符分频常数。所有子模块都查阅这本标准字典，保证了全局数据绝对一致。
</div>

在大型数字系统工程中，“多头定义”和“魔法数字（Magic Numbers）”是导致时序混乱和逻辑矛盾的罪魁祸首。`puzzle_pkg` 是整个工程的**唯一事实真值源（Single Source of Truth）**。

其核心职责包括：
1. **全局统一类型定义**：定义跨模块传递的自定义数组类型（如 4 块零片掩码数组 `mask_arr_t` 与尺寸数组 `dim_arr_t`）；
2. **全局硬件常量固化**：固化 90 项全局时序常数、按键码映射、关卡几何图案掩码、零片形状掩码与数码管字符段码；
3. **空间运算纯函数库**：提供 24 个无状态、无副作用的纯函数（Pure Functions），在编译时展开为最优组合逻辑或常量，不产生任何触发器或状态机。

---

## 2. 核心数据类型与位序约定

### 2.1 8×8 点阵 64 位扁平位图位序约定

全工程对 8×8 二维平面的表达采用了高度统一的扁平化一维向量映射：
$$\text{Bit Index} = 8 \times \text{row} + \text{col}$$

* **坐标原点 $(0,0)$**：对应向量的最低位 `bit 0`（屏幕物理左上角）；
* **水平向右移动（`col + 1`）**：在同一行内位索引递增；
* **垂直向下移动（`row + 1`）**：位索引增加 8。

```
       col 0   col 1   col 2   col 3   col 4   col 5   col 6   col 7
row 0 [bit 0] [bit 1] [bit 2] [bit 3] [bit 4] [bit 5] [bit 6] [bit 7]
row 1 [bit 8] [bit 9] [bit 10] ...
...
row 7 [bit 56] ...                                            [bit 63]
```

### 2.2 全局数组类型声明
```vhdl
type mask_arr_t is array (0 to 3) of std_logic_vector(63 downto 0);
type dim_arr_t  is array (0 to 3) of std_logic_vector(2 downto 0);
```
由于 VHDL-93 标准禁止在实体端口声明中使用匿名数组（Anonymous Array），这两个类型在包中一次声明，供 `piece_rom`、`puzzle_ctrl` 和 `puzzle_top` 统一调用。

---

## 3. 核心常量分类一览

| 常量类别 | 代表性常量名 | 数值 / 定义 | 物理含义与工程用途 |
|:---|:---|:---|:---|
| **时钟分频基准** | `CLK_FREQ_HZ` | `50_000_000` | 50 MHz 主时钟基准 |
| | `C1_MAX` | `49_999` (16位) | 50 MHz → 1 kHz 分频上限计数值 |
| | `DEBOUNCE_MAX` | `3` (4 轮) | 键盘 40 ms 消抖判稳轮次 |
| **按键编码映射** | `K_UP`, `K_DOWN` | `KEY2` (13), `KEY10` (5) | 上下移动物理键号 |
| | `K_LEFT`, `K_RIGHT`| `KEY5` (8), `KEY7` (10) | 左右移动物理键号 |
| | `K_START`, `K_CONF`| `KEY14` (1), `KEY6` (9) | 开局与确认锁定物理键号 |
| | `K_SEL`, `K_ROT` | `KEY16` (3), `KEY15` (2) | 切换零片与顺时针 90° 旋转物理键号 |
| **关卡目标图案** | `L1_TARGET_MASK` | 64 位常量 | 第一关 12 格矩形图案（图 4-1） |
| | `L2_PATS(0..3)` | 4×64 位常量 | 第二/三关图库：田、十字、SZ、阶梯（各 16 格） |
| **数码管段码** | `DIG_P, DIG_A` | `0x0C, 0x0A` | 字符 'P' 与 'A' 的 7 段共阴极段码 |
| | `DIG_S, DIG_L` | `0x05, 0x0E` | 字符 'S'（同5）与 'L' 的 7 段共阴极段码 |
| **音频分频常数** | `HALF_E5 .. HALF_G6`| `147 .. 61` | 8 个标准音符的 ÷256 预分频半周期计数值 |

---

## 4. 空间几何纯函数设计

### 4.1 8 位窄行移位函数 `srl8`
```vhdl
function srl8(r : std_logic_vector(7 downto 0); dc : integer range -2 to 7)
    return std_logic_vector;
```
* **为什么不直接对 64 位向量做 `sll` 或 `srl`？**
  1. 64 位直接移位会发生“跨行穿墙”——第 $r$ 行最右边的位会溢出并环绕到第 $r+1$ 行最左边；
  2. 64 位可变距离移位器在硬件上等价于巨大的 $64 \times 6$ 交叉开关，综合会消耗数千个 LE。
* `srl8` 仅对 8 位窄行进行移位，且支持负偏移（适应旋转补偿），硬件开销微乎其微。

### 4.2 局部正交 90° 顺时针旋转函数 `rot_mask`
零片在局部 $3 \times 3$ 包围盒内的 90° 顺时针正交映射：
$$(r', c') = (c, \quad h - 1 - r)$$
函数在编译时展开，对 9 种可能的相对偏移位置进行重排，无任何算术乘除法，保证了零延时。

---

## 5. 🎓 老师答辩必问与标准回答（核心快问快答）

<div class="defense-box">
  <div class="defense-title">💡 老师随机抽查：设计包与真值源核心答辩点</div>

  <div class="defense-q">Q1：你们的 puzzle_pkg 在芯片里生成了什么硬件电路？占用了多少逻辑单元？</div>
  <div class="defense-a">
    <strong>标准回答：</strong><br>
    老师，<strong>puzzle_pkg 在物理芯片中不生成任何独立的实体或逻辑单元（0 LE 消耗）</strong>。<br>
    在 VHDL 语法中，package 只包含常量定义（<code>constant</code>）、自定义数据类型（<code>type</code>）和纯函数（<code>pure function</code>）。<br>
    它相当于 C 语言中的头文件 <code>.h</code>。当其他模块调用包中的常量或纯函数时，Quartus 综合器会在编译前将它们就地内联展开。纯函数全是无状态的组合运算，会被综合器直接优化吸收到调用模块的 LUT 中，因此它本身是一个零硬件成本的软件工程抽象。
  </div>

  <div class="defense-q">Q2：为什么要专门建立这个 package，而不是直接在各个模块里写数字？</div>
  <div class="defense-a">
    <strong>标准回答：</strong><br>
    主要是为了遵循<strong>“单一事实真值源（Single Source of Truth）”</strong>的严谨工程规范。<br>
    整机有 11 个子模块，如果分频常数、按键码、图案掩码分别散落在不同的 <code>.vhd</code> 文件中，一旦发生需求变更（例如消抖时间调整或键位重新映射），就必须在十几处代码里手动同步，极易发生“一处改了、另一处漏了”的隐蔽缺陷。<br>
    通过 <code>puzzle_pkg</code> 集中管理，全工程只要修改包内的一处常量，所有子模块和测试台自动同步生效，极大提升了工程的可维护性与架构严密性。
  </div>
</div>
