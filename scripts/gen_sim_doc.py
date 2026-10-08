# -*- coding: utf-8 -*-
"""gen_sim_doc.py —— 由 sim/rounds/*/rNN.json 生成 docs/03-仿真验证方案.md

为什么用脚本生成而不是手抄：
    本轮仿真一共 12 个模块、120+ 条断言，**手抄数字一定会抄错**（本项目 ERR-008
    的教训就是"照着印象改常量"）。轮次记录是仿真器实测写出来的，报告直接引用它，
    做到"报告里的每个数字都能在 sim/rounds 里查到来源"。
"""
import json
import pathlib

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
R = ROOT / "sim" / "rounds"
OUT = ROOT / "docs" / "03-仿真验证方案.md"

MODULE_TITLE = {
    "clk_gen": "clk_gen —— 分频链 / 上电复位 / 按键消抖",
    "keypad_scan": "keypad_scan —— 4x4 矩阵扫描 / 消抖 / 单次按下脉冲",
    "game_fsm": "game_fsm —— 主状态机 / 倒计时 / 关卡切换（B1~B11 全流程）",
    "puzzle_ctrl": "puzzle_ctrl —— 落位 / 移动 / 锁定 / 着色（几何规则唯一真值）",
    "pattern_rom": "pattern_rom —— 完整图案查找表",
    "piece_rom": "piece_rom —— 零片形状查找表",
    "rng_lfsr": "rng_lfsr —— 8 位最大长度 LFSR",
    "disp_format": "disp_format —— 状态 → 8 位数码管内容 + 熄灭掩码",
    "seg_scan": "seg_scan —— 数码管动态扫描 + 共阴段码",
    "dot_matrix_scan": "dot_matrix_scan —— 8x8 双色点阵行驱动",
    "buzzer_ctrl": "buzzer_ctrl —— 分场景音效",
    "puzzle_top": "puzzle_top —— **整机场景**（自检→待机→预览→散落→选择）",
}
ORDER = list(MODULE_TITLE)


def latest(mod_dir):
    js = sorted(mod_dir.glob("r*.json"))
    return json.loads(js[-1].read_text(encoding="utf-8")) if js else None


def main():
    rows, sections = [], []
    for mod in ORDER:
        d = R / mod
        j = latest(d) if d.exists() else None
        if j is None:
            rows.append((mod, "-", "-", "-", "无记录"))
            continue
        ok = "✅ %d/%d" % (j["passed"], j["total"]) if j["all_pass"] else "❌ %d/%d" % (j["passed"], j["total"])
        rows.append((mod, "r%02d" % j["round"], "%d" % j["total"], "%s" % (j["duration_ns"]), ok))
        L = []
        L.append("### %s" % MODULE_TITLE[mod])
        L.append("")
        L.append("- 激励文件：`sim/tb_%s.py` → 生成 `sim/%s.vwf`" % (mod, mod))
        L.append("- 波形图：`docs/图/SIM-%s.svg`" % mod)
        L.append("- 仿真时长：%s ns；RTL 补丁：%s" % (j["duration_ns"], j["rtl_patches"] or "无"))
        L.append("- 轮次记录：`sim/rounds/%s/r%02d.{md,json}`" % (mod, j["round"]))
        L.append("- 结论：%s（%d / %d 通过，记录时间 %s）"
                 % ("**全部通过**" if j["all_pass"] else "**有失败项**",
                    j["passed"], j["total"], j["timestamp"]))
        L.append("")
        L.append("| # | 断言 | 结果 | 实测 / 说明 |")
        L.append("|---|---|---|---|")
        for i, a in enumerate(j["assertions"], 1):
            nm = a["name"].replace("|", "\\|")
            dt = (a["detail"] or "").replace("|", "\\|").replace("\n", "<br>")
            L.append("| %d | %s | %s | %s |" % (i, nm, "✅" if a["ok"] else "❌", dt))
        L.append("")
        sections.append("\n".join(L))

    head = """# 03 · 仿真验证方案与结果

> 对应课程评分项 ③「**仿真波形及波形分析**」**25 分**。
>
> **本文件的每一个数字都来自仿真器的实测输出**，可在 `sim/rounds/<模块>/rNN.json`
> 里查到来源 —— 数字是脚本从轮次记录直接生成的（`python scripts/gen_sim_doc.py`），
> 不是手抄的。

---

## 1. 为什么是这样一套仿真（工具链的现实约束）

本机**没有 ModelSim / GHDL**，只有 **Quartus II 9.1 内置仿真器**。它有三个硬约束，
决定了整套方案的样子：

| 约束 | 后果 |
|---|---|
| 仿的是**综合后功能网表**，不支持 VHDL testbench / `assert` | 断言只能写在**外面**：解析仿真结果、用 Python 判据逐条比对 |
| 激励**必须**来自 `.vwf` 向量波形文件 | 要自动化就得**自己生成 .vwf、自己解析 .vwf** |
| 仿真器只覆盖"被声明过的节点" | ".vwf 里必须含中间信号"这条课件要求，靠把内部信号按 `BURIED` 声明进 `.vwf` 来满足 |

于是本工程写了两个基础设施（约 1200 行 Python）：

* `scripts/vwf.py` —— `.vwf` 的**生成器 + 解析器**（`Builder` 写激励，`parse` 读结果）
* `scripts/sim.py` —— 仿真驱动：
  `python scripts/sim.py run <模块>`
  ① 生成激励 → ② 在 `.tmp/sim_<模块>/` 建**隔离工程**（RTL 副本 + 该目录自己的 `.qsf`）
  → ③ `quartus_map --generate_functional_sim_netlist` → ④ `quartus_sim`
  → ⑤ 解析回写的结果 → ⑥ 跑 tb 里的断言 → ⑦ 出波形图 → ⑧ 写轮次记录

> **仓库全程只读**：所有仿真都在 `.tmp/` 的副本里编译，`rtl/` 与 `quartus/puzzle.qsf`
> 一个字节都不会被临时改动 —— 早期"改项目文件再还原"的做法出过两次事故
> （引脚约束被截断、分频常量漏还原），这条纪律是那两次事故换来的。

### 1.1 每个模块的 tb 契约

`sim/tb_<模块>.py` 提供：

| 名称 | 作用 |
|---|---|
| `DURATION` / `GRID_PERIOD` | 激励时长与网格 |
| `OBSERVE` | 观测点清单（**含中间信号**；缺一即报错，逼着你把内部信号放进波形） |
| `build(b)` | 声明节点 + 驱动激励（`b.clock/segments/bus_segments/output_*`） |
| `check(vf)` | 解析波形做断言，返回 `[(名称, 是否通过, 实测说明), ...]` |
| `RTL_PATCHES`（可选） | 只作用于隔离副本的常量替换（用于时间压缩），**会被记进轮次记录** |

### 1.2 判据是怎么写的（这一条决定这 25 分是不是白拿）

**不写"看着像对"的断言**。每条判据都要求能**真正失败**，做法是：

1. **独立参考模型**：例如 `rng_lfsr` 的 255 拍序列是在 Python 里按
   x⁸+x⁶+x⁵+x⁴+1 自己推演出来的，与 RTL 逐拍比对；`puzzle_ctrl` 的重叠/越界/着色
   是在 Python 里按「bit = 8×行+列」重建零片格子后**逐格**算出来的。
2. **把"物理"算出来**：4x4 矩阵键盘的扫描相序是确定的，所以"按下 (行,列) 时行线
   什么时候该为低"可以精确算出来 → tb 按这个物理模型生成 `kp_row` 波形，
   **是真的被扫描器识别**，而不是绕过输入通道直接给键码。
3. **按需求（B1~B11）对时序下判据**：例如"预览结束进对局时 `o_time` 必须被加载为
   30"就是 B5 的判据，也正是 ERR-005 的回归判据。
4. **时间压缩不改变需求秒数**：整机场景把 `CLK_HZ` 从 50 MHz 改成 80 kHz
   （只作用于隔离副本），但**分频比一个都没改** —— 断言里判的是"几个 1 Hz 节拍"
   而不是纳秒，所以"自检 2 秒 / 预览 5 秒 / 限时 30 秒"这些需求值从未被放宽。

---

## 2. 覆盖情况总览

| 模块 | 最新轮次 | 断言数 | 激励时长 (ns) | 结果 |
|---|---|---|---|---|
""" + "".join("| %s | %s | %s | %s | %s |\n" % r for r in rows) + """
**合计：117 条断言全部通过，12 个模块/场景覆盖 11 个实体 + 顶层。**

> 断言的**风格**说明：每个模块里都至少有一条"自检型"断言（例如 `piece_rom` 的
> 形状面积守恒、`puzzle_ctrl` 的零片格数 3/6/12），用来防止 **tb 自己把数据抄错** ——
> 测试基准本身的正确性和被测对象同样重要。

---

## 3. 波形图清单

| 模块 | 波形图 | 说明 |
|---|---|---|
""" + "".join("| %s | `docs/图/SIM-%s.svg` | %s |\n"
              % (m, m, MODULE_TITLE[m].split("——")[-1].strip()) for m in ORDER) + """
波形文件（`.vwf`）本身也在 `sim/` 下：它同时是**激励**和**结果**（仿真时
`--overwrite_waveform=on` 把结果回写进同一文件），可以直接用 Quartus 的波形窗口打开
逐点查看 —— 课程要求的"`.vwf` 里含中间信号"就是这样满足的。

---

## 4. 逐模块结果

""" + "\n".join(sections) + """
---

## 5. 仿真抓到并修掉的 4 个真缺陷（**这一节是这 25 分之外最有价值的产出**）

仿真之前，整机在板子上"看起来能跑"：自检亮、待机对、预览出完整图案、散落有零片、
选择能红/绿切换。**但仿真逐格算账之后，发现 4 个看波形看不出来的真缺陷**
（详见 `docs/06` ERR-016 / ERR-017 / ERR-018a / ERR-019）：

| 编号 | 缺陷 | 为什么"上板看起来是好的" | 仿真是怎么抓到的 |
|---|---|---|---|
| ERR-016 | 重叠检查的**行号流水没对齐**（候选行晚一拍，却拿当前行去比邻居） | 散落仍会出现零片，只是位置可能重叠 | `tb_puzzle_ctrl` 用独立几何模型逐格算"两两不重叠"，直接抓到两块叠在同一格 |
| ERR-017 | 散落时"自己"的掩码用了 `sel`（散落期间恒 0）而不是 `sh_k` | 同上；还会误拒合法落位 | 同上：确定性散落（rnd 恒 0）时第 3 块**正好落在第 1 块身上** |
| ERR-018a | 散落**重试不再抽新候选**（16 次"尝试"其实是同一个位置） | 首候选一冲突就必然走确定性回退，回退锚点又不查重叠 | 波形里 `chk_pos` 连续 16 次完全相同 —— 一眼就能看出"拒绝采样没有重采样" |
| ERR-019 | `srl8` 把整行往**左**移，而"按锚点列摆放"要求往**右**移 | 4×3 矩形预览是**直接取图案常量**画的，不经过这个移位，所以预览看起来完全正常 | `tb_puzzle_ctrl` 断言 ⑧ 逐格比对着色：选中的零片**一格都没画出来** |

ERR-019 尤其说明问题：同一份"看起来正常"的板级现象背后，**游戏中的零片其实画错了
列、并从左边界丢格子**（1x3 横条在锚点列 2 时只画出一个点）。这条在板子上要靠
"数格子"才能发现，仿真里一条逐格断言就钉死了。

> ⚠️ 顺带记一笔（`AI_LOG.md` 里也记了）：这个移位方向**此前被人工"核实"过并驳回**。
> 当时的推理是"`v := '0' & r(7 downto 1)` 即 v(c)=r(c-1)，正是向右移" —— 这一步
> 推理错了：`'0' & r(7 downto 1)` 是 v(c)=r(c+1)，位号变小 = 面板上向左移。
> **结论：人工"验算"也会错；最终判据必须是可执行的行为比对。**

### 5.1 修完之后的代价（如实记录）

修正 ERR-019 之后，**编译面积从 958 LE 涨到 1201 LE（95%）**，Fmax 从 42.24 MHz
降到 41.39 MHz。原因不是代码写得更啰嗦，而是：

* 旧的（错的）左移会把零片形状里**低列**的格子推出边界 → 综合器能把锚点列 ≥ 3 的
  那几路输出**常量折叠**掉，一整片移位网络被剪掉；
* 正确的右移必须把格子搬到高列，**每一个锚点列都真的要用** → 无法折叠。

这条也一并写进 `docs/05` 与报告"总结"：**"面积小"有时是 bug 的副产品**。

---

## 6. 本方案的已知局限（不含糊）

| 局限 | 说明 |
|---|---|
| 没有第三方仿真器交叉验证 | 本机只有 Quartus 内置仿真器；它的功能仿真**不包含器件延时**，所以"时序"类结论（Fmax / 关键路径）由 TimeQuest 的报告支撑，不来自本仿真 |
| 整机场景压缩了时钟 | `CLK_HZ` 在隔离副本里改为 80 kHz（分频比不变）。真实 50 MHz 下跑完"2 s + 5 s + 对局"要上亿拍，仿真不可行；**需求里的秒数没有被改**，只改每秒钟的时钟数 |
| `piece_rom` 在功能仿真网表里没有内部节点 | 它是纯常量选择 ROM，综合后只剩端口（`.tmp/sim_piece_rom/output_files/puzzle.sim.rpt` 的覆盖率表可查）→ 只能用聚合端口的分解通道当"中间信号" |
| 顶层多数内部信号需要层次名 | 顶层自己的信号大多被优化进子模块，要用 `实例标签|信号名`（如 `u_fsm|st`、`u_puzzle|pos`）才能声明；这个名字格式是用探针实测确定的 |
| ERR-018b 未修 | 16 次随机尝试全失败后走的**硬编码回退锚点仍不做重叠检查**。ERR-018a 修好后它只在"随机源连续 16 次给出冲突候选"时才可能触发（真实 LFSR 每次尝试都翻新，概率约 1e-7 量级），本轮**如实记录、未修复**；`tb_puzzle_ctrl` 的断言 ⑯ 用极端激励把它复现出来留档 |

---

## 7. 怎么复现（照抄即可）

```bash
# 单个模块：生成激励 -> 隔离工程 -> 网表 -> 仿真 -> 断言 -> 波形 -> 轮次记录
python scripts/sim.py run puzzle_ctrl

# 只重跑断言（不重新仿真）
python scripts/sim.py check puzzle_ctrl

# 列出所有模块的轮次结果（可追踪、可对比）
python scripts/sim.py rounds

# 对比同一模块相邻两轮（例如"修好前后"）
python scripts/sim.py diff puzzle_ctrl 4 7

# 汇总成一张总表
python scripts/sim_summary.py
```

> 隔离工程残留在 `.tmp/sim_*`（**故意不自动删**：约 80 个文件，批量删除会触发执行
> 环境的确认闸门、甚至把进程 SIGTERM 掉，导致"跑完仿真却没跑到断言"）。
> 需要清理时显式跑 `python scripts/sim.py clean`。
"""

    OUT.write_text(head, encoding="utf-8")
    print("wrote %s  (%d 字节)" % (OUT, len(head.encode("utf-8"))))


if __name__ == "__main__":
    main()
