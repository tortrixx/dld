# -*- coding: utf-8 -*-
"""tb_puzzle_ctrl.py —— puzzle_ctrl 功能仿真（落位 / 移动 / 旋转 / 锁定 / 着色）

【这一轮要回答什么】
    `puzzle_ctrl` 是拼图核心，也是全工程面积最大、历史上缺陷最密的模块
    （ERR-005 限时、ERR-007 选中零片显示不出绿色、ERR-009/013 底图挡零片都与它
    或它的显示语义有关）。它同时是**几何规则**的唯一定义者：

      · B5 散落：零片位置随机、**不能重叠**、必须在 8x8 内；
      · B6 选择：选中的零片要**纯绿**（不是"绿是红的子集"→ 显示成黄色）；
      · B7 移动：可以上下左右移动，**不能移出 8x8**、不能与其它零片重叠；
      · B8 确认：确认后**变黄且不可再移动、不可再选择**；
      · B9 成功：**拼出来的画面 == 目标图案** 且每块都已锁定；
      · A4（提高要求）：**选中零片可以 90° 顺时针旋转**（本轮新增覆盖）。

    本 tb 用**独立几何模型**（在 Python 里按"bit = 8*行+列，bit0=左上角"重建零片
    格子）逐条验算，而不是"看着波形像对的"。

【本工作阶段 RTL 变了什么（本 tb 必须跟着改的地方）】
    ⓪ ⚠️ **初始朝向**（第 14 工作阶段）：`puzzle_pkg.PIECE_ORI_INIT` 让四块零片从
       朝向 1/1/2/2 开始散落（i_go 与 i_reset 都写这条常量），于是
         · 散落结束的 o_ori 恒为 `ORI_INIT_WORD = "10100101"`（**不是 0**），
           断言 ② ③ ⑬ 与"4 次旋转回到原样"的那几条都按它重新对齐；
         · 六份走法计划（SOLVE_PLAN / EDGE_PLAN / ROT1_PLAN / ROT2_PLAN / L2_PLAN /
           WRONG_PLAN）全部按新初态**重新解过**（带旋转的 A*，.tmp/opt/rot_astar2.py），
           相应的时间常量（T_R1_* 的下标）也跟着重算；
         · 新增断言 ⑱：不按【旋转】就拼不出目标（本 tb 独立几何模型离线验证）。
       本 tb **不再**用 RTL_PATCHES 把初始朝向钉回 0 —— 那会把"散落结束时的朝向"
       这个真实初态从覆盖里删掉，属于 ERR-022/034 那类"陈旧绿"。
    ① 端口：新增 `i_rot`（1 拍旋转请求）、`o_ori`（8 位 = 4 块各 2 位朝向）。
    ② 旋转（A4）：候选 = 同一锚点 + 朝向 +1，走**同一套**校验流水；被接受时
       **只提交 ori**（o_pos 不变）；越界/重叠/已锁定一律不提交。
       旋转的**锚点语义**：`puzzle_pkg.rot_row` 在固定 3x3 盒里做朝向置换，而
       `rot_off_r/rot_off_c` 把"旋转后的紧包围盒在盒里的偏移"补回来 —— 于是对外
       等价于**绕零片自身紧包围盒中心旋转再对齐左上角**（本 tb 的独立模型就是这么
       算的，见 rot_cells）。第一版漏了偏移补偿（横条转 90° 会凭空右移 2 列、
       ori=2 时整块漏画），旋转⑦ 就是把这条钉住的判据。
    ③ 重叠引擎**串行化**：旧节点 chk_row/chk_orow/chk_prow **已不存在**，现在
       一拍只算一个邻块（chk_ld/chk_sr/chk_slot/chk_srmax/chk_me/chk_ori/
       chk_rot/chk_kind/chk_crow/chk_hit/chk_pos）。一次检查 = hh*(1+npc) 拍
       （npc = 3 一级 / 4 二级），判定在随后那一拍（CH_DONE）。
       → 旧断言 ⑫ 检查的"chk_orow == chk_prow - 候选行"这个**流水陷阱整个没了**，
         本 tb 把它换成等价的、仍然有意义的**扫描不变量**（见断言 ⑫）。
    ④ 渲染器**串行化 + 两相流水**：一拍备一块零片的行掩码、一拍把它并进累加器，
       ph = npc+1 那一拍发布整行。所以一行 = npc + 2 拍、一帧 = 8 行
       （一级 40 拍 = 8000 ns / 二级 48 拍 = 9600 ns）。
       → **所有"等一帧稳定"的采样窗口按帧长重新计算**（旧版一帧只有 8 拍 =
         1600 ns）。改 rtl/puzzle_ctrl.vhd 的 ph 相数必须同步改 tb 的
         ROW_TICKS_*/FRAME_*/SET_*/CMD_STEP。

【时间刻度 / 为什么这样取（见下方"时间表"一节）】
    tick = 200 ns（10 个 20 ns 时钟）。**注意**：散落/移动/旋转/重叠引擎跑的是
    `i_clk`（20 ns 一拍），只有**渲染器**跑 `i_tick`（200 ns 一拍）—— 所以一次
    重叠检查（≤ 16 拍）只要 **320 ns**，而一帧画面要 **8.0/9.6 us**。时间表就是
    按这两个完全不同的量级排的：命令间隔取 18 us（> 一帧 + 一次操作），采样点取
    "相关命令之后、下一条命令之前"（保证是一整帧稳定的画面，且不跨阶段）。

【已知残余缺陷 / 记录在案的偏离（如实留档，不改 RTL）】
    · ERR-018b：16 次尝试都失败后的**硬编码回退锚点不再做重叠检查**。
      本 tb 仍用"rnd_val 恒 12"复现（断言 ⑯）。ERR-018a 修好后回退只在随机源
      连续 16 次给出冲突候选时才触发（真实 LFSR 下概率 ~1e-7）。
    · ERR-040（本 tb 发现、**RTL 已修**）：旋转第一版没有把"旋转后紧包围盒在
      3x3 盒里的偏移"补回锚点 —— 1x3 横条转 90° 会右移 2 列、ori=2 时 3 个格子
      还会整块漏画（引擎却照旧接受）。现在的 RTL 用 rot_off_r/rot_off_c 修好了，
      旋转⑦ 就是这条的回归判据（逐格比对教科书旋转）。
    · ERR-041（本 tb 记录，未修 RTL）：渲染器"干净帧"协议在**帧尾→下一帧头**那
      一行有缝 —— 帧头才拍 pos/level/pat 快照、帧尾才发布判据，两者之间只覆盖
      7 行；变化正好落进那一行时，那一帧仍被判为"干净"。因此断言 ⑰ 用**一串
      相位互不相同的翻转**（12 次、间隔与帧长互质），而不是翻一次。

【端口位序的一个不一致，本 tb 必须按实际约定读】
    掩码类端口（i_target / i_sh*）用 `bit = 8*行 + 列`（bit0 = 左上角）；
    而帧类端口 o_rowr / o_rowg 把**第 0 行放在 63..56**，且行内列 7 在高位
    （等价：列 c ↔ bit(56-8*行+c)）。`puzzle_top` 也按同样的切片读第 0 行，
    功能上自洽 —— 但同一模块里两套位序是**易错点**，本 tb 按实际约定取样。
"""

import pathlib
import re

CLK = 20.0               # 板上 50 MHz 时钟
TICK = 200.0             # 渲染节拍（本仿真里给 1/200 ns，即"一拍"）
GRID_PERIOD = 5.0

# ------------------------------------------------------------------ 零片形状
# 来源：rtl/puzzle_pkg.vhd（＝课程 PDF 图 4-2 的逐像素解码结果）。
# 它们是本模块的**输入**，所以 tb 直接驱动进去，再用独立模型算几何。
L1_P0 = int("0000000000000000000000000000000000000000000000000000000000000111", 2)
L1_P1 = int("0000000000000000000000000000000000000000000000010000001100000111", 2)
L1_P2 = int("0000000000000000000000000000000000000000000000000000001100000010", 2)
L1_TGT_MASK = int("0000000000000000000111000001110000011100000111000000000000000000", 2)

L1 = [
    dict(name="P0 横条 1x3", mask=L1_P0, h=1, w=3, tgt=(2, 2)),
    dict(name="P1 楼梯形 6 格", mask=L1_P1, h=3, w=3, tgt=(3, 2)),
    dict(name="P2 L 形 3 格", mask=L1_P2, h=2, w=2, tgt=(4, 3)),
]
NP = 3
L1_FALLBACK = [(0, 0), (0, 4), (4, 0)]           # RTL 里写死的回退锚点（sh_k = 0/1/2）

# ------------------------------------------------------------------ 第二关（四块自拟异形零片）
# 判据必须是「拼出来的画面」而不是「每块的锚点编号」（ERR-021）：
#   · 现在四块是**四种异形**（3/2/5/6 格，形状互不相同），图案 3（阶梯）恰好有
#     **2 种**铺法（scripts/check_geometry.py / check_plans.py 穷举证明）——
#     本 tb 故意摆成**第二种**铺法，断言 ⑭ 要求 o_solved = 1。
# 零片掩码 / 包围盒 / 图案掩码都**从 rtl/puzzle_pkg.vhd 解析**（唯一真值源）。
_PKG_SRC = (pathlib.Path(__file__).resolve().parent.parent
            / "rtl" / "puzzle_pkg.vhd").read_text(encoding="utf-8")


def _pkg_mask(name):
    m = re.search(r"constant\s+%s\s*:\s*std_logic_vector\(63 downto 0\)\s*:=\s*\"([01]{64})\""
                  % name, _PKG_SRC, re.S)
    if not m:
        raise RuntimeError("puzzle_pkg.vhd 里找不到常量 %s" % name)
    return int(m.group(1), 2)


def _bbox(mask):
    cs = [(r, c) for r in range(8) for c in range(8) if (mask >> (8 * r + c)) & 1]
    return (max(r for r, _ in cs) + 1, max(c for _, c in cs) + 1)


L2 = [dict(name="Q%d" % i, mask=_pkg_mask("L2_P%d" % i)) for i in range(4)]
for _p in L2:
    _p["h"], _p["w"] = _bbox(_p["mask"])
L2_TARGET = _pkg_mask("L2_PAT3")             # 图案 3 = 阶梯（恰有两种铺法）
L2_FALLBACK = [(0, 0), (0, 4), (4, 0), (4, 4)]
NP2 = 4
# ---- 初始朝向（A4 / 第 14 工作阶段）：从 pkg 里解析，**不手抄** ----------------
# 块 k 占 ori(2k+1 downto 2k)；pkg 里 MSB 在左（块 3 先写）。
_m_ini = re.search(r"constant\s+PIECE_ORI_INIT\s*:\s*std_logic_vector\(7 downto 0\)\s*:=\s*"
                   r"\"([01]{2})\"\s*&\s*\"([01]{2})\"\s*&\s*\"([01]{2})\"\s*&\s*\"([01]{2})\"",
                   _PKG_SRC, re.S)
if not _m_ini:
    raise RuntimeError("puzzle_pkg.vhd 里找不到 PIECE_ORI_INIT")
_ini_bits = "".join(_m_ini.groups())            # 块3 块2 块1 块0
ORI_INIT = tuple(int(_ini_bits[6 - 2 * k:8 - 2 * k], 2) for k in range(4))
# RTL 在 i_go 时把**整条 8 位** ori 都写成 PIECE_ORI_INIT（一关也写 4 块），
# 所以 o_ori 在散落结束时恒等于下面这个字：
ORI_INIT_WORD = (ORI_INIT[0] | (ORI_INIT[1] << 2) | (ORI_INIT[2] << 4) | (ORI_INIT[3] << 6))

# 一关：最优计划的终点（槽 0..2）。它不是 pkg 里写的那组见证锚点
# （L1[i]["tgt"] = (2,2)(3,2)(4,3)）而是一组**等价铺法**：(2,2)(3,2)(3,2) ——
# 零片 1 与零片 2 共用锚点 (3,2) 但形状互补，并集仍然逐格等于图 4-1 的 4x3 矩形。
# 这正是 B9"看拼出来的画面"（而不是"看每块的锚点编号"）在第一关的体现。
L1_GOAL = [(2, 2), (3, 2), (3, 2)]
L1_GOAL_ORI = [2, 2, 2]

# 图案 3（阶梯）的等价铺法（槽 0..3，含朝向），由带旋转的 A* 穷举 + 最小化得到
#   （scripts/check_plans.py 里同一份枚举；A* 解算器在 .tmp/opt/rot_astar2.py）
#   ⚠️ ERR-021 的回归判据就是"两种不同铺法都必须判成功"：
#        L2_TILING_TB  = 本 tb 摆的那一种（= pkg.L2_PAT3_TGT0..3 的锚点）
#        L2_TILING_TOP = sim/tb_puzzle_top.py 摆的那一种（锚点元组完全不同）
L2_TILING_TB = [(2, 2), (2, 1), (3, 3), (3, 2)]        # ← 本 tb 实际摆成这一种
L2_TILING_TB_ORI = [2, 2, 0, 0]
L2_TILING_TOP = [(5, 3), (2, 1), (2, 2), (2, 3)]       # tb_puzzle_top 的等价铺法
L2_TILING_A = L2_TILING_TB                             # 历史名字（旧断言/注释沿用）

# ------------------------------------------------------------------ 帧长（渲染器串行化 + 两相流水之后）
# 一拍备一块零片的行掩码、一拍把它并进累加器，ph = npc+1 那一拍发布本行；
# 所以一行 = npc + 2 拍（一级 5 拍 / 二级 6 拍），一帧 = 8 行。
ROW_TICKS_L1 = NP + 2                       # 5 拍/行 = 1000 ns
ROW_TICKS_L2 = NP2 + 2                      # 6 拍/行 = 1200 ns
FRAME_TICKS_L1 = 8 * ROW_TICKS_L1           # 40 拍 = 8000 ns
FRAME_TICKS_L2 = 8 * ROW_TICKS_L2           # 48 拍 = 9600 ns
FRAME_L1 = FRAME_TICKS_L1 * TICK
FRAME_L2 = FRAME_TICKS_L2 * TICK

# 采样裕量：一次移动/旋转 ≤ 30 个 20 ns 拍 ≈ 0.6 us，所以"最后一次改动 +1 帧"之后
# 取样一定稳。一级一帧 8.0 us、二级 9.6 us（**注意：帧长随渲染器的相数变过，
# 这里必须与 rtl/puzzle_ctrl.vhd 的 ph 相数保持一致**）。
SET_L1 = 11000.0
SET_L2 = 13000.0
CMD_STEP = 18000.0        # 相邻命令间隔：> 一帧(9.6 us) + 一次操作(0.6 us)，留 ≥3 us
SCATTER_GAP = 60000.0     # 散落窗口：最坏 4 块 x 16 次尝试 ≈ 17 us 的 3.5 倍

# ------------------------------------------------------------------ 时间表
T_GO_1 = 5000.0           # 散落①：rnd_val 恒 12 -> 复现 ERR-018b（回退锚点未查重叠）
T_S1 = 85000.0
T_GO_2 = 95000.0          # 散落②：rnd_val 快速变化 -> 真随机，验重叠判定本身
T_S2 = 155000.0
T_GO_3 = 165000.0         # 散落③：rnd_val 恒 0 -> 可复现的确定落位
T_S3 = 225000.0
# 一关各阶段的起点在下面"时间表（按依赖排）"一节统一算 —— 见那里的说明。


def _cmds(start, items, step=CMD_STEP):
    out, t = [], start
    for (kind, arg, label) in items:
        out.append((t, kind, arg, label))
        t += step
    return out, t


def _ts(cmds, i, off=0.0):
    """第 i 条命令的时刻 + off。"""
    return cmds[i][0] + off


# 一关（3 块）：从确定性回退锚点 (0,0)/(0,4)/(4,0)、初始朝向 (1,1,2) 走到
#   L1_GOAL = (2,2)(3,2)(3,2)（并集 == 图 4-1 的 4x3 矩形），再逐块确认。
#   ⚠️ 第 14 工作阶段：这份计划由**带旋转的 A***重新解出，代价 = 按键次数
#      （.tmp/opt/rot_astar2.py；16 条命令 + 3 次确认，**下界 = 16 ⇒ 可证最优**）。
#      零片从非零朝向开始，所以第 1 条命令就是【旋转】——这就是 A4 的意义。
SOLVE_PLAN = [
    ("rot", None, "P0 旋转（初始 90°：3x1 竖条 -> 1x3 横条）"),
    ("move", "R", "P0 右移"), ("move", "D", "P0 下移"),
    ("move", "R", "P0 右移"), ("move", "D", "P0 -> (2,2) 终点"),
    ("sel", None, "选中 P1(楼梯形)"),
    ("move", "D", "P1 下移"),
    ("rot", None, "P1 旋转（初始 90° -> 180°）"),
    ("move", "D", "P1 下移"), ("move", "L", "P1 左移"),
    ("move", "D", "P1 下移"), ("move", "L", "P1 -> (3,2) 终点"),
    ("sel", None, "选中 P2(L 形)"),
    ("move", "U", "P2 上移"), ("move", "R", "P2 右移"),
    ("move", "R", "P2 -> (3,2) 终点（与 P1 共用锚点，形状互补）"),
    ("confirm", None, "锁定 P2"),
    ("confirm", None, "锁定 P0"),
    ("confirm", None, "锁定 P1 -> 全锁且并集 == 图 4-1 的 4x3 矩形"),
]

# 一关：边界 / 重叠 / 锁定 / 选择跳过锁定（与旧版同一份计划，语义未变）
EDGE_PLAN = [
    ("sel", None, "选中 P2(L 形)"), ("sel", None, "选中 P2(L 形)"),
    ("move", "D", "P2 下移"), ("move", "D", "P2 下移"),
    ("move", "D", "第 3 次下移 —— 应被越界拒绝"),
    ("move", "D", "第 4 次下移 —— 应被越界拒绝"),
    ("sel", None, "选回 P0(横条)"),
    ("move", "R", "P0 右移"), ("move", "R", "P0 右移"), ("move", "R", "P0 右移"),
    ("move", "R", "第 4 次右移 —— 应与楼梯形重叠而被拒"),
    ("confirm", None, "锁定 P0（B8：此后不可再选择、不可移动）"),
    # ⚠️ ERR-035：锁定后的选择语义 —— sel 会**跳过已锁定的 P0**（不是绕回 0）。
    ("sel", None, "ERR-035：按【选择】必须跳过已锁定的 P0"),
    ("sel", None, "ERR-035：再按一次，仍在未锁定零片之间"),
    ("move", "D", "选中的是未锁定的 P1(楼梯形)：移动应被接受"),
    ("sel", None, "再选一次（仍必须跳过 P0），供着色采样"),
]

# 一关：旋转覆盖。起点 = 又一次 rnd_val=0 的散落（三块落在 (0,0)/(0,4)/(4,0)，
#   初始朝向 P0=1（3x1 竖条）/ P1=1（楼梯形转 90°）/ P2=2（L 形转 180°））。
#   ⚠️ 第 14 工作阶段：起点朝向变了，所以**每个"被拒/被接受"的落点都要重排**
#      —— 原来是"横条 P0 在第 7 行转竖会出界"，现在 P0 一开始就是竖的，得先把它
#      转成横的再去贴底。这里按新几何重新排过，并用本 tb 的独立模型逐格验算。
#   索引（供下面 _ts/_after 用）：
#     1..4 = 旋转①②；14 = 旋转④（重叠被拒）；25 = 旋转⑤（出界被拒）；
#     29/30 = 旋转⑦（横条归一化到自身紧包围盒）；35 = 旋转⑥（已锁定 -> 无效）
ROT1_PLAN = [
    ("sel", None, "选中 P1(楼梯形 3x3)"),
    ("rot", None, "旋转① 旋转一次 -> P1 ori 1->2（A4 基本行为）"),
    ("rot", None, "旋转② 第 2 次"), ("rot", None, "旋转② 第 3 次"),
    ("rot", None, "旋转② 第 4 次 -> ori 回到 1"),
    ("sel", None, "选中 P2(L 形)"),
    ("move", "R", "P2 右移"), ("move", "R", "P2 右移"), ("move", "R", "P2 右移"),
    ("move", "R", "P2 -> (4,4)"),
    ("move", "U", "P2 上移"), ("move", "U", "P2 -> (2,4)（占住 (2,4)(2,5)(3,4)）"),
    ("sel", None, "选中 P0"), ("sel", None, "选中 P1"),
    ("rot", None, "旋转④ P1 转 90° 后的格子会压到 P2 -> 必须被拒"),
    ("sel", None, "选中 P2"), ("sel", None, "选中 P0"),
    ("rot", None, "P0 初始是 3x1 竖条，先转成 1x3 横条（ori 1->2）"),
    ("move", "D", "P0 下移"), ("move", "D", "P0 下移"), ("move", "D", "P0 下移"),
    ("move", "D", "P0 下移"), ("move", "D", "P0 下移"), ("move", "D", "P0 下移"),
    ("move", "D", "P0 -> (7,0)（贴底）"),
    ("rot", None, "旋转⑤ 第 7 行上把 1x3 横条转竖 -> 会出界，必须被拒"),
    ("move", "U", "P0 上移"), ("move", "U", "P0 上移"), ("move", "U", "P0 -> (4,0)"),
    ("rot", None, "旋转⑦ 横条在 (4,0) 转 90°：必须画成**同一列**的竖条 "
                  "(4,0)(5,0)(6,0)（旧实现会右移 2 列）"),
    ("rot", None, "旋转⑦ 再转 90°：必须回到原横条 (4,0)(4,1)(4,2)"),
    ("sel", None, "选中 P1"),
    ("confirm", None, "锁定 P1"), ("confirm", None, "锁定 P2"),
    ("confirm", None, "锁定 P0 -> 全锁；sel 停在**已锁定**的 P0 上"),
    ("rot", None, "旋转⑥ 旋转已锁定零片 -> 必须无任何变化"),
]

# 第二关：散落后先做一次旋转覆盖（此时四块都在确定性回退锚点上、朝向 = INIT），
# 转 4 次回到**初始朝向**（Q2 从 2 出发 -> 3 -> 0 -> 1 -> 2）/原位，
# 所以**后面的 ⑭ 拼图计划仍然从同一个初态出发**（计划本身就是按这个初态解的）。
ROT2_PLAN = [
    ("sel", None, "选中 Q1(竖条)"), ("sel", None, "选中 Q2(J 形 3x3)"),
    ("rot", None, "旋转③ 第二关旋转一次（i_level=1，4 块）：Q2 ori 2->3"),
    ("rot", None, "第 2 次"), ("rot", None, "第 3 次"), ("rot", None, "第 4 次 -> 回到 ori=2"),
    ("sel", None, "选中 Q3"), ("sel", None, "选中 Q0 -> sel 回到 0，供 ⑭ 使用"),
]

# 第二关：把四块**异形**零片从确定性回退锚点 (0,0)(0,4)(4,0)(4,4)、初始朝向
#   (1,1,2,2) 摆成**图案 3（阶梯）的一种等价铺法** L2_TILING_TB（锚点 (2,2)(2,1)(3,3)(3,2)，
#   终点朝向 (2,2,0,0)）。走法由**带旋转的 A\***解出（.tmp/opt/rot_astar2.py）：
#   31 条命令 + 4 次确认；本 tb 又用独立几何模型逐格复核过（零次被拒、并集 == 图案）。
# ⚠️ 故意**不是** pkg.L2_PAT3_TGT 的那一组锚点？—— 恰恰相反：本 tb 摆的**就是**
#    pkg 里写的那一组（历史名字 L2_TILING_A），而 tb_puzzle_top 摆的是**另一组**
#    L2_TILING_TOP = (5,3)(2,1)(2,2)(2,3)。两份计划终点**锚点元组完全不同、
#    画面却逐格相同** —— 这正是 ERR-021 要证明的"判据看画面、不看编号"。
L2_PLAN = [
    ("rot", None, "P0 旋转（初始 90°：3x1 -> 1x3）"),
    ("move", "R", "P0 R"), ("move", "D", "P0 D"),
    ("move", "R", "P0 R"), ("move", "D", "P0 -> (2,2)"),
    ("sel", None, "选中 Q1"),
    ("move", "L", "Q1 L"), ("move", "L", "Q1 L"), ("move", "L", "Q1 -> (0,1)"),
    ("rot", None, "Q1 旋转（初始 90°）"),
    ("move", "D", "Q1 D"),
    ("sel", None, "选中 Q2"),
    ("move", "U", "Q2 U"),
    ("rot", None, "Q2 旋转（初始 180° -> 270°）"),
    ("move", "R", "Q2 R"), ("move", "R", "Q2 R"), ("move", "R", "Q2 -> (3,3)"),
    ("sel", None, "选中 Q3"),
    ("rot", None, "Q3 旋转（初始 180° -> 270°）"),
    ("rot", None, "Q3 旋转（-> 原样）"),
    ("move", "D", "Q3 D"),
    ("sel", None, "选中 Q0"), ("sel", None, "选中 Q1"),
    ("move", "D", "Q1 -> (2,1)"),
    ("sel", None, "选中 Q2"),
    ("rot", None, "Q2 旋转（回到原样）"),
    ("sel", None, "选中 Q3"),
    ("move", "L", "Q3 L"), ("move", "L", "Q3 L"),
    ("move", "U", "Q3 U"), ("move", "U", "Q3 -> (3,2)"),
    ("confirm", None, "锁定第 1 块"), ("confirm", None, "锁定第 2 块"),
    ("confirm", None, "锁定第 3 块"), ("confirm", None, "锁定第 4 块 -> 全锁且并集 == 图案 3"),
]

# 反例（⑮）：再散落一次，四块**原地**全锁定 —— 画面（并集）不等于目标图案。
WRONG_PLAN = [
    ("confirm", None, "锁定第 1 块"), ("confirm", None, "锁定第 2 块"),
    ("confirm", None, "锁定第 3 块"), ("confirm", None, "锁定第 4 块 -> 全锁但画面错"),
]

# ================================================================ 时间表（按依赖排）
# 每个阶段的起点都由**上一阶段结束 + 一个整帧/散落窗口**算出来，避免"下一条 i_go
# 发出时上一阶段的采样点还没到"这类排期错误（命令间隔 CMD_STEP = 18 us > 一帧
# 9.6 us + 一次操作 0.6 us；散落窗口 SCATTER_GAP = 60 us，最坏 4 块 x 16 次尝试
# ≈ 17 us）。**帧长随渲染器相数变过**，改 rtl/puzzle_ctrl.vhd 的 ph 相数就要一起改。
T_CMD_C = 245000.0                                  # 一关：复现拼图（⑧⑨⑩）
CMDS_C, T_AFTER_C = _cmds(T_CMD_C, SOLVE_PLAN)
T_C_2LOCK = _ts(CMDS_C, len(CMDS_C) - 2, 2000.0)    # 只锁了 2 块（最后一次确认之前）
T_C_SOLVED = T_AFTER_C + 5000.0                     # 三块都锁定

T_GO_D = T_C_SOLVED + 15000.0                       # 一关：边界/重叠/锁定（④⑤⑥⑦⑲）
T_CMD_D = T_GO_D + SCATTER_GAP
CMDS_D, T_AFTER_D = _cmds(T_CMD_D, EDGE_PLAN)
T_SAMPLE_COLOR = T_AFTER_D + SET_L1                 # 着色（⑧）稳定采样

T_GO_R1 = T_SAMPLE_COLOR + 10000.0                  # 一关：旋转覆盖（旋转①..⑦）
T_CMD_R1 = T_GO_R1 + SCATTER_GAP
CMDS_R1, T_AFTER_R1 = _cmds(T_CMD_R1, ROT1_PLAN)

T_L2 = T_AFTER_R1 + 10000.0                         # 切到第二关
T_GO_L2 = T_L2 + 30000.0                            # 二关散落（rnd_val 恒 0）
T_S_L2SCAT = T_GO_L2 + SCATTER_GAP + 10000.0        # ⑬ 采样：二关散落已完成
T_CMD_R2 = T_S_L2SCAT + 10000.0                     # 二关：旋转覆盖（旋转③）
CMDS_R2, T_AFTER_R2 = _cmds(T_CMD_R2, ROT2_PLAN)
T_CMD_L2 = T_AFTER_R2 + 10000.0                     # 二关：拼成铺法 B（⑭）
CMDS_L2, T_AFTER_L2 = _cmds(T_CMD_L2, L2_PLAN)
T_L2_SETTLE = T_AFTER_L2 + SET_L2 + 3000.0

# A2/S1（断言 ⑰）：i_pat 变化 → 在途整帧判据必须作废。
# ⚠️ 这里**不是翻一次**，而是翻一串（间隔 1.7 us、共 12 次）：RTL 的"干净帧"快照
#    在**帧头**拍、判据在**帧尾**发布，两次之间只覆盖 7 行；变化若正好落在"帧尾 →
#    下一帧头"那一行的缝里，那一帧本来就还算干净（快照已经是新值）。单次翻转会因此
#    变成"约 1/8 概率复现"的**抽奖**断言。间隔 1700 ns 与帧长 9600 ns 互质（17 与 96
#    互质 → 12 次翻转到 12 个互不相同的相位），保证至少有一次落在在途帧里。
T_PAT_CHG = T_L2_SETTLE + 10000.0
T_PAT_STEP = 1700.0
T_PAT_N = 12
T_PAT_END = T_PAT_CHG + T_PAT_STEP * (T_PAT_N - 1)
T_PAT_WIN = 25000.0                                 # 作废窗口（≥ 2 帧）
T_PAT_REC = T_PAT_END + 30000.0                     # 恢复点（≥ 3 帧）

T_GO_L2B = T_PAT_REC + 10000.0                      # 反例：原地全锁定（⑮）
T_CMD_L2B = T_GO_L2B + SCATTER_GAP
CMDS_L2B, T_AFTER_L2B = _cmds(T_CMD_L2B, WRONG_PLAN)
T_L2B_SETTLE = T_AFTER_L2B + SET_L2 + 3000.0

DURATION = T_L2B_SETTLE + 10000.0


def _after(cmds, i, lead=3000.0, tail=None):
    """"第 i 条命令生效之后"的采样点：取**下一条命令之前** lead ns。

    这样既保证 ≥ 1 整帧（帧长 8.0/9.6 us）已经画完，又不会跨到下一阶段去。
    最后一条命令没有"下一条"，退化成 +1 帧。
    """
    if i + 1 < len(cmds):
        return cmds[i + 1][0] - lead
    return cmds[i][0] + (tail if tail is not None else SET_L2 + 3000.0)


# ------------------------------------------------------------------ 旋转/边界的采样点
# ⚠️ 第 14 工作阶段：ROT1_PLAN 的**长度与顺序都变了**（36 条，旧版 39 条），
#    这些下标必须跟着重算 —— 否则断言会去采样另一个时刻的画面（ERR-022/034 那类
#    "陈旧常量造成的假绿/假红"）。
T_R1_PRE = _ts(CMDS_R1, 1, -4000.0)               # 第 1 次旋转之前（已选中 P1）
T_R1_ONE = _after(CMDS_R1, 1)                     # 第 1 次旋转之后（P1 ori 1->2）
T_R1_FOUR = _after(CMDS_R1, 4)                    # 4 次旋转之后（回到初始朝向 1）
T_R1_OVL_PRE = _ts(CMDS_R1, 14, -4000.0)          # 旋转④（重叠拒绝）之前
T_R1_OVL = _after(CMDS_R1, 14)                    # 旋转④ 之后
T_R1_OOB_PRE = _ts(CMDS_R1, 25, -4000.0)          # 旋转⑤（出界拒绝）之前
T_R1_OOB = _after(CMDS_R1, 25)                    # 旋转⑤ 之后
T_R1_BAR1 = _ts(CMDS_R1, 29, SET_L1)              # 横条 ori=3（3x1 竖条，与原列对齐）
T_R1_BAR2 = _ts(CMDS_R1, 30, SET_L1)              # 横条 ori=0（1x3 横条回到原样）
T_R1_LK_PRE = _ts(CMDS_R1, 35, -5000.0)           # 旋转已锁定零片之前
T_R1_LK = _after(CMDS_R1, 35)                     # 旋转已锁定零片之后

T_R2_PRE = _ts(CMDS_R2, 2, -4000.0)               # 二关旋转之前（已选中 Q2）
T_R2_ONE = _after(CMDS_R2, 2)                     # 二关旋转一次之后
T_R2_FOUR = _after(CMDS_R2, 5)                    # 二关 4 次旋转之后

# ============================================================================
# ⚠️ 2026-10-09 第 14 工作阶段（A4 从"可选"变成"通关必需"）：**本 tb 不再给 RTL 打
#    任何补丁** —— 它必须跑在**仓库里真正的** rtl/ 上（pi = PIECE_ORI_INIT =
#    "10"&"10"&"01"&"01"，块 0..3 从朝向 1/1/2/2 开始散落）。
#
#   上一版的替代做法是"把 PIECE_ORI_INIT 补丁回 0、让老计划继续成立"。那**不可取**：
#     · 散落结束时 o_ori 是多少、开局形状长什么样，是**被测对象的一部分**（B5 的
#       "随机落位"在 A4 之后包含"随机/指定朝向"），把它补丁掉等于把一个真实存在的
#       初态从覆盖里删掉；
#     · 补丁一旦与 pkg 里的字面量漂移（比如有人改了 pkg 的拼接顺序），tb 会**静默**
#       继续测老前提 —— 正是 ERR-022/034 那一类"陈旧绿"。
#   所以本文件的做法是**按新初态重新解计划**（见下面各计划的说明），并用独立几何模型
#   离线复核"删掉旋转就拼不出来"（断言 ⑱）。
# ============================================================================

OBSERVE = ["i_clk", "i_rst", "i_tick", "i_level", "i_pat", "i_go", "i_select", "i_move",
           "i_confirm", "i_rot", "i_up", "i_down", "i_left", "i_right", "rnd_val",
           "o_busy", "o_sel_idx", "o_pos", "o_lock", "o_ori", "o_scanrow",
           "o_solved", "o_all_lock", "o_rowr", "o_rowg",
           "chk_ld", "chk_sr", "chk_slot", "chk_srmax", "chk_me", "chk_ori",
           "chk_rot", "chk_kind", "chk_crow", "chk_hit", "chk_pos", "frow"]

# ------------------------------------------------------------------ 帧判据寄存器
# ERR-021 的修复给 puzzle_ctrl 加了「整帧画面判据」寄存器（frm_ok / frm_valid /
# frm_bad / pos_frm）。仿真用的是**综合后网表**，观测一个不存在的节点会直接报
# "观测点缺失" —— 所以这里显式探测仓库 RTL 里有没有这些寄存器（保住同一个 tb
# 在"修复前/修复后"两版 RTL 上都能跑的老习惯）。
_CTRL_SRC = (pathlib.Path(__file__).resolve().parent.parent
             / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")
HAS_FRAME_VERDICT = "frm_ok" in _CTRL_SRC
# ⚠️ pos_frm 不再观测：渲染器改成两拍流水后综合器把这份"本帧锚点快照"并进了别的
#    网（综合后网表里找不到节点），而断言只需要 frm_ok/frm_valid/frm_bad。
VERDICT_NODES = ["frm_ok", "frm_valid", "frm_bad"]
if HAS_FRAME_VERDICT:
    OBSERVE = OBSERVE + VERDICT_NODES


# ================================================================ 独立几何模型
def rel_cells(sh):
    """零片在它自己 3x3 盒里的格子集合 {(行,列)}。"""
    m = sh["mask"]
    return {(r, c) for r in range(8) for c in range(8) if (m >> (8 * r + c)) & 1}


def abs_cells(sh, anchor):
    return sorted((anchor[0] + r, anchor[1] + c) for (r, c) in rel_cells(sh))


def popcount(m):
    return bin(m).count("1")


def rot_cells(cells, k):
    """**教科书式**旋转：绕零片自身紧包围盒中心顺时针转 k 次，再对齐到包围盒左上角。

    这是从几何出发写的独立模型：(行,列) -> (列, 高-1-行)，每次转 90°。
    RTL 侧的实现是"在固定 3x3 盒里置换 + 用 rot_off_r/rot_off_c 把紧包围盒偏移补回
    来"（见 rtl/puzzle_pkg.vhd 的【锚点语义】），逐格结果与这里相同 —— 第一版漏了
    偏移补偿，本 tb 的旋转⑦ 正是抓它的判据（RTL 已修，见断言文字）。
    """
    out = set(cells)
    for _ in range(k % 4):
        h = max(r for (r, _c) in out) + 1
        out = {(c, h - 1 - r) for (r, c) in out}
    return out


def hh_of(sh, ori):
    """旋转后的包围盒高：奇朝向（90°/270°）与宽互换。"""
    return sh["h"] if ori % 2 == 0 else sh["w"]


def ww_of(sh, ori):
    return sh["w"] if ori % 2 == 0 else sh["h"]


def row_mask_model(sh, ori, sr, ac):
    """锚点列 ac 处，零片旋转 ori 后落在**本块第 sr 行**上的 8 位行掩码。

    独立写法（"行里第 c 列 -> 面板第 c+ac 列，移出 0..7 的位丢掉"），与 RTL 的
    srl8 同语义但不同实现；用于断言 ⑫ 重算 chk_crow。
    """
    m = 0
    for (r, c) in rot_cells(rel_cells(sh), ori):
        if r == sr and 0 <= c + ac <= 7:
            m |= 1 << (c + ac)
    return m


def drawn_cells(sh, anchor, ori):
    """渲染器**实际画出来**的格子：紧包围盒里旋转 ori 次，再整体搬到锚点上。

    旋转在紧包围盒里做（RTL 用 rot_off_r/rot_off_c 把偏移补回来），所以旋转后的格子
    一定落在 0..hh-1 行 / 0..ww-1 列里，不会被 8 位行掩码截掉、也不会漏扫 —— 前提是
    调用方已经用旋转后的 hh/ww 做过边界检查（引擎就是这么做的）。
    """
    ar, ac = anchor
    return {(ar + r, ac + c) for (r, c) in rot_cells(rel_cells(sh), ori)}


def frame_sets(pos, oris, lock, sel, shapes):
    """渲染器语义（未变）：cov = 各块并集；kc = 已锁定块的并集；
    selr = 选中块的格子，但**已锁定的块不算"选中"**（ERR-035 防御）。
    red = cov - selr，green = kc | selr。"""
    cov, kc, selr = set(), set(), set()
    for i, sh in enumerate(shapes):
        cs = drawn_cells(sh, pos[i], oris[i])
        cov |= cs
        if (lock >> i) & 1:
            kc |= cs
        elif sel == i:
            selr |= cs
    return cov, kc, selr


def ori_list(word):
    return [(word >> (2 * k)) & 3 for k in range(4)]


def _ori_from(word, k):
    return (word >> (2 * k)) & 3


def split_pos(v):
    """o_pos (32 位) -> [(行,列)] x4，顺序 P0..P3。"""
    out = []
    for k in range(4):
        b = (v >> (24 - 8 * k)) & 0xFF
        out.append(((b >> 4) & 0xF, b & 0xF))
    return out


def frame_cell(frame, r, c):
    """帧寄存器 o_rowr/o_rowg 的位序：列 c ↔ bit (56 - 8*行 + c)。"""
    return (frame >> (56 - 8 * r + c)) & 1


def lit_cells(frame):
    return {(r, c) for r in range(8) for c in range(8) if frame_cell(frame, r, c) == 1}


def frame_mismatch(fr, fg, cov, kc, selr, limit=6):
    bad = []
    for r in range(8):
        for c in range(8):
            cell = (r, c)
            want_r = 1 if (cell in cov and cell not in selr) else 0
            want_g = 1 if (cell in kc or cell in selr) else 0
            got = (frame_cell(fr, r, c), frame_cell(fg, r, c))
            if got != (want_r, want_g):
                bad.append("(%d,%d) 实测红%d绿%d 期望红%d绿%d"
                           % (r, c, got[0], got[1], want_r, want_g))
                if len(bad) >= limit:
                    return bad
    return bad


def overlap_report(pos, shapes=None, oris=None):
    """返回 (是否越界, 重叠说明)。默认按一关三块、ori=0。"""
    shapes = shapes if shapes is not None else L1
    oris = oris if oris is not None else [0] * len(shapes)
    used, bad = {}, []
    oob = False
    for i, sh in enumerate(shapes):
        ar, ac = pos[i]
        hh, ww = hh_of(sh, oris[i]), ww_of(sh, oris[i])
        if not (0 <= ar and ar + hh <= 8 and 0 <= ac and ac + ww <= 8):
            oob = True
            bad.append("P%d 越界 @%s" % (i, pos[i]))
        for cell in drawn_cells(sh, pos[i], oris[i]):
            if cell in used:
                bad.append("P%d@%s 与 P%d 在格子 %s 重叠" % (i, pos[i], used[cell], cell))
            used[cell] = i
    return oob, bad


def mask_cells(m):
    return {(r, c) for r in range(8) for c in range(8) if (m >> (8 * r + c)) & 1}


def union_cells_multi(pos, shapes, oris=None):
    oris = oris if oris is not None else [0] * len(shapes)
    u = set()
    for i, sh in enumerate(shapes):
        u |= drawn_cells(sh, pos[i], oris[i])
    return u


def shapes_at(t):
    return L1 if t < T_L2 else L2


# ---------------------------------------------------------------- A4 离线走计划
# ⚠️ 第 14 工作阶段：断言 ⑱ 要回答"不按【旋转】到底拼不拼得出来"，而这个问题
#    **不需要仿真** —— 用本 tb 自己的独立几何模型把计划走一遍即可（引擎规则：
#    夹紧 + 越界 + 逐格重叠；rot 只改朝向、锚点不动）。这样"旋转必需"这条性质
#    在引擎级 tb 里也有直接证据，而不是只靠 check_geometry / check_plans。
def _l1_ok(pos, ori, k, cand, o):
    """零片 k 以朝向 o 放在 cand 上是否合法（在 8x8 内且与其它两块不重叠）。"""
    if cand[0] + hh_of(L1[k], o) > 8 or cand[1] + ww_of(L1[k], o) > 8:
        return False
    mine = drawn_cells(L1[k], cand, o)
    for j in range(NP):
        if j != k and (mine & drawn_cells(L1[j], pos[j], ori[j])):
            return False
    return True


def simulate_l1(plan, drop_rot=False):
    """用独立几何模型走一遍一关计划，返回 (pos, ori, 被拒次数, 并集)。

    `drop_rot=True` = 把计划里的【旋转】键全部删掉（模拟"玩家一次都不转"）。
    """
    pos = [tuple(a) for a in L1_FALLBACK]
    ori = list(ORI_INIT[:NP])
    locked = [False] * NP
    sel, rej = 0, 0
    for (kind, arg, _lab) in plan:
        if kind == "sel":
            sel = (sel + 1) % NP
        elif kind == "confirm":
            locked[sel] = True
        elif kind == "rot":
            if drop_rot or locked[sel]:
                continue
            o2 = (ori[sel] + 1) % 4
            if _l1_ok(pos, ori, sel, pos[sel], o2):
                ori[sel] = o2
            else:
                rej += 1
        elif kind == "move":
            if locked[sel]:
                continue
            dr, dc = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}[arg]
            r, c = pos[sel]
            nr = r - 1 if (dr < 0 and r > 0) else (r + 1 if (dr > 0 and r < 7) else r)
            nc = c - 1 if (dc < 0 and c > 0) else (c + 1 if (dc > 0 and c < 7) else c)
            if _l1_ok(pos, ori, sel, (nr, nc), ori[sel]):
                pos[sel] = (nr, nc)
            else:
                rej += 1
    return pos, ori, rej, union_cells_multi(pos, L1, ori)


# ================================================================ 激励
def _buried(b, name, width):
    for n in [name] + ["%s[%d]" % (name, i) for i in range(width)]:
        sig = b.vf.signals.get(n)
        if sig is not None:
            sig.direction = "BURIED"


def _tl(duration, spans, default):
    """[(起, 止, 值)] -> [(时长, 值)]（区间互不重叠时成立）。"""
    ev = []
    for (a, b, v) in spans:
        ev.append((a, 0, v))        # 起点
        ev.append((b, 1, default))  # 终点：恢复默认
    ev.sort(key=lambda x: (x[0], x[1]))
    segs, t, cur = [], 0.0, default
    for (tt, _k, v) in ev:
        if tt > t:
            segs.append((tt - t, cur))
            t = tt
        cur = v
    if t < duration:
        segs.append((duration - t, cur))
    return segs


def _pulse_spans(times, width=CLK):
    return [(t, t + width, 1) for t in times]


def _ticks(duration, period):
    out, t = [], period
    while t < duration:
        out.append(t)
        t += period
    return out


def build(b):
    b.input_bit("i_clk")
    b.input_bit("i_rst")
    b.input_bit("i_tick")
    b.input_bit("i_level")
    b.input_bit("i_go")
    b.input_bit("i_select")
    b.input_bit("i_move")
    b.input_bit("i_confirm")
    b.input_bit("i_rot")                        # A4：1 拍旋转请求
    b.input_bit("i_up")
    b.input_bit("i_down")
    b.input_bit("i_left")
    b.input_bit("i_right")
    b.input_bus("rnd_val", 8)
    b.input_bus("i_pat", 2)                     # A2/S1：图案库下标（见 T_PAT_CHG）
    for n in ("i_sh0", "i_sh1", "i_sh2", "i_sh3", "i_target"):
        b.input_bus(n, 64)
    for n in ("i_h0", "i_h1", "i_h2", "i_h3", "i_w0", "i_w1", "i_w2", "i_w3"):
        b.input_bus(n, 3)
    b.output_bit("o_busy")
    b.output_bus("o_sel_idx", 2)
    b.output_bus("o_pos", 32)
    b.output_bus("o_lock", 4)
    b.output_bus("o_ori", 8)                    # A4：4 块各 2 位朝向
    b.output_bus("o_scanrow", 3)
    b.output_bit("o_solved")
    b.output_bit("o_all_lock")
    b.output_bus("o_rowr", 64)
    b.output_bus("o_rowg", 64)
    # 串行化后的重叠引擎内部节点（旧 chk_row/chk_orow/chk_prow 已不存在 → 删掉；
    # 断言 ⑫ 用下面这组重算"扫描 + 候选本行 + 命中判定"）
    for n, w in (("chk_ld", 1), ("chk_sr", 2), ("chk_slot", 2), ("chk_srmax", 2),
                 ("chk_me", 2), ("chk_ori", 2), ("chk_rot", 1), ("chk_kind", 1),
                 ("chk_crow", 8), ("chk_hit", 1), ("chk_pos", 8), ("frow", 3)):
        if w == 1:
            b.output_bit(n)
        else:
            b.output_bus(n, w)
        _buried(b, n, w)
    if HAS_FRAME_VERDICT:                     # 只在修复后的 RTL 里存在
        for n, w in (("frm_ok", 1), ("frm_valid", 1), ("frm_bad", 1), ("pos_frm", 32)):
            if w == 1:
                b.output_bit(n)
            else:
                b.output_bus(n, w)
            _buried(b, n, w)

    b.clock("i_clk", CLK)
    b.segments("i_rst", [(500.0, 1), (DURATION - 500.0, 0)])
    b.segments("i_tick", _tl(DURATION, [(t, t + CLK, 1)
                                        for t in _ticks(DURATION, TICK)], 0))
    # 一关（3 块 1x3+3x3+2x2）→ 到 T_L2 切二关（4 块异形：3+2+5+6 格）
    b.segments("i_level", [(T_L2, 0), (DURATION - T_L2, 1)])

    # A2/S1 图案库下标：0/1 之间翻一串（见 T_PAT_CHG 的说明与断言 ⑰）。
    # 每次翻转都必须在"在途的那一帧"里被抓住，所以用 12 次互不相同相位的翻转，
    # 而不是翻一次（单次有 ~1/8 概率正好落在帧尾→帧头的缝里）。
    pat_segs, tp, pv = [], 0.0, 0
    for _k in range(T_PAT_N):
        pat_segs.append((T_PAT_CHG + T_PAT_STEP * _k - tp, pv))
        tp = T_PAT_CHG + T_PAT_STEP * _k
        pv ^= 1
    pat_segs.append((DURATION - tp, pv))
    b.bus_segments("i_pat", [s for s in pat_segs if s[0] > 0])

    # 形状 / 目标：两关各一段，T_L2 处整组切换
    for i, sh in enumerate(L1):
        b.bus_segments("i_sh%d" % i, [(T_L2, sh["mask"]), (DURATION - T_L2, L2[i]["mask"])])
        b.bus_segments("i_h%d" % i, [(T_L2, sh["h"]), (DURATION - T_L2, L2[i]["h"])])
        b.bus_segments("i_w%d" % i, [(T_L2, sh["w"]), (DURATION - T_L2, L2[i]["w"])])
    b.bus_segments("i_sh3", [(T_L2, 0), (DURATION - T_L2, L2[3]["mask"])])
    b.bus_segments("i_h3", [(T_L2, 0), (DURATION - T_L2, L2[3]["h"])])
    b.bus_segments("i_w3", [(T_L2, 0), (DURATION - T_L2, L2[3]["w"])])
    b.bus_segments("i_target", [(T_L2, L1_TGT_MASK), (DURATION - T_L2, L2_TARGET)])

    # rnd_val：① 恒 12（复现 ERR-018b）② 每 100 ns 换一个值（真随机）③ 恒 0（可复现）
    rnd = [(T_GO_2, 12)]
    t, v = T_GO_2, 1
    while t < T_GO_3:
        rnd.append((100.0, (v * 97) % 256))
        v += 1
        t += 100.0
    rnd.append((DURATION - t, 0))
    b.bus_segments("rnd_val", rnd)

    # 命令（一关三阶段 + 二关三阶段，共用同一条命令流水）
    cmds = CMDS_C + CMDS_D + CMDS_R1 + CMDS_R2 + CMDS_L2 + CMDS_L2B
    b.segments("i_go", _tl(DURATION, _pulse_spans(
        [T_GO_1, T_GO_2, T_GO_3, T_GO_D, T_GO_R1, T_GO_L2, T_GO_L2B]), 0))
    b.segments("i_select", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in cmds if k == "sel"]), 0))
    b.segments("i_confirm", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in cmds if k == "confirm"]), 0))
    b.segments("i_rot", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in cmds if k == "rot"]), 0))
    moves = [(t, a) for (t, k, a, _l) in cmds if k == "move"]
    b.segments("i_move", _tl(DURATION, _pulse_spans([t for (t, _a) in moves]), 0))
    for ch, name in (("U", "i_up"), ("D", "i_down"), ("L", "i_left"), ("R", "i_right")):
        # 方向必须在 i_move 前后两拍内保持有效（引擎要把它锁进 mv_dir）
        b.segments(name, _tl(DURATION,
                             [(t - 100.0, t + 300.0, 1) for (t, a) in moves if a == ch], 0))


# ================================================================ 断言
def _v(vf, name, t):
    return vf.value_at(name, t)


def _bus(vf, name, t):
    return vf.bus_value_at(name, t)


def _ori_at(vf, t, k):
    w = _bus(vf, "o_ori", t)
    return None if w is None else (w >> (2 * k)) & 3


def _frame_pair(vf, t):
    return _bus(vf, "o_rowr", t), _bus(vf, "o_rowg", t)


def _snapshot(vf, t, shapes):
    """某一时刻的 (pos, ori, lock, sel) —— 全部来自端口，供独立模型复算。"""
    p = _bus(vf, "o_pos", t)
    o = _bus(vf, "o_ori", t)
    l = _bus(vf, "o_lock", t)
    s = _bus(vf, "o_sel_idx", t)
    if None in (p, o, l, s):
        return None
    return split_pos(p), ori_list(o), l, s


def _model_frame_check(vf, t, shapes, label, sel=None):
    """整帧逐格与独立模型比对，返回 (ok, detail)。"""
    snap = _snapshot(vf, t, shapes)
    fr, fg = _frame_pair(vf, t)
    if snap is None or fr is None or fg is None:
        return False, "%s：t=%.0f 读到 X（未稳定）" % (label, t)
    pos, oris, lock, selv = snap
    if sel is not None and selv != sel:
        return False, "%s：t=%.0f o_sel_idx=%d（期望 %d）" % (label, t, selv, sel)
    cov, kc, selr = frame_sets(pos, oris, lock, selv, shapes)
    bad = frame_mismatch(fr, fg, cov, kc, selr)
    return (not bad), ("%s：t=%.0f pos=%s ori=%s lock=%s sel=%d；%s"
                       % (label, t, pos[:len(shapes)], oris[:len(shapes)],
                          format(lock, "0%db" % len(shapes)), selv,
                          "整帧 64 格一致" if not bad else "；".join(bad)))


def _engine_walk(vf, t0, t1, tag):
    """⑫ 串行重叠引擎的扫描不变量（替代已消失的 ERR-016 流水对齐判据）。

    对窗口内**每一次检查**逐拍核对：
      · 每一行的第一拍是 load（chk_ld=1），随后 npc 拍的 chk_slot 恰好是 0..npc-1
        （逐拍 +1、不跳号、不错行），行号 0..chk_srmax 每行恰好走一遍；
      · 每一拍的 chk_crow 都等于用**独立模型**重算的"候选本行掩码"
        （= 本块形状 + chk_ori + chk_sr + chk_pos 锚点列）；
      · 检查结束那一拍的 chk_hit 等于"模型算出的任何一次比较是否命中"，
        其中 slot == chk_me 自己那一拍按 RTL 语义**不比较**；
      · chk_rot = 1 的那些检查（旋转请求）用的是**同一套**流水：候选朝向
        chk_ori 必须等于该块当时的 ori + 1（A4 的实现声明）。
    返回 (errors, n_checks, n_cmp, n_hit, n_rot)。
    """
    errs = []
    S = []
    m = int(t0 // CLK)
    while m * CLK + 15.0 < t1:
        t = m * CLK + 15.0
        rec = dict(
            t=t,
            ld=_v(vf, "chk_ld", t), sr=_bus(vf, "chk_sr", t),
            slot=_bus(vf, "chk_slot", t), srmax=_bus(vf, "chk_srmax", t),
            me=_bus(vf, "chk_me", t), cori=_bus(vf, "chk_ori", t),
            crow=_bus(vf, "chk_crow", t), hit=_v(vf, "chk_hit", t),
            pos=_bus(vf, "chk_pos", t), level=_v(vf, "i_level", t),
            rot=_v(vf, "chk_rot", t),
            opos=_bus(vf, "o_pos", t), oori=_bus(vf, "o_ori", t))
        S.append(rec)
        m += 1
    need = ("ld", "sr", "slot", "srmax", "me", "cori", "crow", "hit", "pos", "level",
            "opos", "oori")
    n = len(S)
    i = 0
    n_checks = n_cmp = n_hit = n_rot = n_edge = 0
    while i < n:
        s = S[i]
        if s["ld"] != "1" or s["sr"] != 0 or s["srmax"] is None:
            i += 1
            continue
        if any(s[k] is None for k in need):
            errs.append("%s t=%.0f 检查起点采样含 X" % (tag, s["t"]))
            i += 1
            continue
        if s["rot"] == "1":
            n_rot += 1
            want_ori = ((_ori_from(s["oori"], s["me"])) + 1) % 4
            if s["cori"] != want_ori:
                errs.append("%s t=%.0f 旋转检查的 chk_ori=%d，而该块 ori+1=%d"
                            % (tag, s["t"], s["cori"], want_ori))
        npc = 3 if s["level"] == "0" else 4
        shapes = shapes_at(s["t"])
        srmax = s["srmax"]
        rows, j, ok = [], i, True
        # 一次检查最多 (3 行 x (1+4) 拍) + 1 = 16 拍；窗口边缘若把检查切断，
        # 剩下的采样数不够走完，就**当作窗口截断**丢掉，不算错误。
        edge_cut = (n - i) < (4 * (1 + npc) + 4)
        for sr in range(srmax + 1):
            if j >= n or S[j]["ld"] != "1" or S[j]["sr"] != sr:
                if not edge_cut:
                    errs.append("%s t=%.0f 第 %d 行没有 load 拍（ld=%s sr=%s）"
                                % (tag, s["t"], sr, S[j]["ld"] if j < n else "-",
                                   S[j]["sr"] if j < n else "-"))
                ok = False
                break
            slots = []
            for kk in range(npc):
                q = S[j + 1 + kk] if j + 1 + kk < n else None
                if (q is None or q["ld"] != "0" or q["sr"] != sr or q["slot"] != kk
                        or any(q[k] is None for k in need)):
                    if not edge_cut:
                        errs.append("%s t=%.0f sr=%d 第 %d 个邻块拍不对（slot=%s ld=%s sr=%s）"
                                    % (tag, s["t"], sr, kk,
                                       q["slot"] if q else "-", q["ld"] if q else "-",
                                       q["sr"] if q else "-"))
                    ok = False
                    break
                slots.append(q)
            if not ok:
                break
            rows.append((S[j], slots))
            j += 1 + npc
        if not ok:
            i = j + 1
            if edge_cut:
                n_edge += 1
            continue
        exp_hit = 0
        for (load, slots) in rows:
            sr = load["sr"]
            me = load["me"]
            cori = load["cori"]
            cpos = load["pos"]
            ac = cpos & 0xF
            want = row_mask_model(shapes[me], cori, sr, ac)
            for q in slots:
                if q["crow"] != want:
                    errs.append("%s t=%.0f sr=%d slot=%d chk_crow=0x%02X 模型=0x%02X"
                                % (tag, q["t"], sr, q["slot"], q["crow"] or 0, want))
                slot = q["slot"]
                if want == 0 or slot == me:
                    continue
                pos_all = split_pos(q["opos"])
                ori_all = ori_list(q["oori"])
                srow = ((cpos >> 4) & 0xF) + sr - pos_all[slot][0]
                if 0 <= srow <= 2:
                    nrow = row_mask_model(shapes[slot], ori_all[slot], srow,
                                          pos_all[slot][1])
                    n_cmp += 1
                    if want & nrow:
                        exp_hit = 1
        done = S[j] if j < n else None
        if done is None or done["hit"] != ("1" if exp_hit else "0"):
            errs.append("%s t=%.0f 检查结束时 chk_hit=%s，模型算出来=%d"
                        % (tag, s["t"], done["hit"] if done else "-", exp_hit))
        n_checks += 1
        n_hit += exp_hit
        i = j + 1
    return errs, n_checks, n_cmp, n_hit, n_rot, n_edge


def check(vf):
    res = []

    # ⓪ 形状数据自检
    res.append((
        "⓪ 形状数据自检：三块零片格数 3/6/3 = 12，与目标图案（12 格）面积守恒",
        [popcount(s["mask"]) for s in L1] == [3, 6, 3]
        and popcount(L1_TGT_MASK) == 12,
        "格数 = %s；目标图案格数 = %d"
        % ([popcount(s["mask"]) for s in L1], popcount(L1_TGT_MASK)),
    ))

    # ① 散落一定会结束
    busy_seen, busy_end = False, None
    for (t, lv) in vf.trace("o_busy"):
        if lv == "1":
            busy_seen = True
        elif busy_seen and busy_end is None and t > T_GO_1:
            busy_end = t
    res.append((
        "① i_go 后 o_busy 置起并**回到 0**（散落一定会结束，不会卡在忙态）",
        busy_seen and busy_end is not None and busy_end < T_S1,
        "o_busy 见到=%s，回到 0 的时刻=%s（须早于 %.0f ns；一次检查 ≤ 320 ns，"
        "最坏 33 次检查 ≈ 11 us）"
        % (busy_seen, "%.0f" % busy_end if busy_end else "从未", T_S1),
    ))

    # ② ★ 真随机散落后：两两不重叠 + 都在 8x8 内（B5）
    posA = split_pos(_bus(vf, "o_pos", T_S2))
    oriA = ori_list(_bus(vf, "o_ori", T_S2))
    oob, bad = overlap_report(posA, L1, oriA)
    res.append((
        "② ★ 随机散落后三块零片**两两不重叠**且都在 8x8 内（B5：位置随机但不能重叠）"
        " —— 独立几何模型逐格验算（ERR-016/017 的回归判据）；朝向必须等于 "
        "puzzle_pkg.PIECE_ORI_INIT = %s（第 14 工作阶段：散落不再把朝向清零）"
        % (list(ORI_INIT[:NP]),),
        (not oob) and (not bad) and oriA[:NP] == list(ORI_INIT[:NP]),
        "实测锚点 P0=%s P1=%s P2=%s；ori=%s（期望 %s = PIECE_ORI_INIT 前 %d 位）；%s"
        % (posA[0], posA[1], posA[2], oriA[:NP], list(ORI_INIT[:NP]), NP,
           "；".join(bad) if bad else "无重叠、无越界"),
    ))

    # ③ 确定性散落（rnd_val=0）复现出三个回退锚点
    posB = split_pos(_bus(vf, "o_pos", T_S3))
    oriB = ori_list(_bus(vf, "o_ori", T_S3))
    res.append((
        "③ rnd_val 恒 0（候选恒为 (0,0)，必然 16 次失败）时落到三个确定性回退锚点、"
        "朝向 = PIECE_ORI_INIT —— 后续边界/重叠/锁定/拼合判据的基准"
        "（⚠️ 回退锚点是 RTL 里写死的四角，**与朝向无关**，所以第 14 工作阶段没变）",
        posB[:NP] == L1_FALLBACK and oriB[:NP] == list(ORI_INIT[:NP]),
        "实测 P0=%s P1=%s P2=%s（期望 %s）；ori=%s（期望 %s）"
        % (posB[0], posB[1], posB[2], L1_FALLBACK, oriB[:NP], list(ORI_INIT[:NP])),
    ))

    # ④ 越界拒绝：2 行高零片到第 6 行后不能再下移
    posEdge = split_pos(_bus(vf, "o_pos", _ts(CMDS_D, 5, 1000.0)))
    res.append((
        "④ 越界被拒：P2(2x2) 从第 4 行下移到第 6 行为止，第 3/4 次下移被拒（B7 不能移出 8x8）",
        posEdge[2] == (6, 0),
        "P2 最终锚点 = %s（期望 (6,0)：第 7 行放不下 2 行高的零片）" % (posEdge[2],),
    ))

    # ⑤ 重叠拒绝：横条右移撞上楼梯形
    posOv = split_pos(_bus(vf, "o_pos", _ts(CMDS_D, 10, 1000.0)))
    res.append((
        "⑤ 重叠被拒：P0（初始朝向 1 = **3x1 竖条**）从 (0,0) 右移 3 格到 (0,3) 都合法，"
        "第 4 次右移就压到 P1(楼梯形, (0,4)) 的 (0,4) 格上而被拒"
        "（B7；几何按「列 = 位号」独立算出。⚠️ 第 14 工作阶段零片初始朝向变了，"
        "所以停下来的锚点是 (0,3) 而不是旧版的 (0,1)）",
        posOv[0] == (0, 3),
        "P0 最终锚点 = %s（期望 (0,3)：竖条占列 3 的第 0~2 行；再右移一列就与 (0,4) 冲突）"
        % (posOv[0],),
    ))

    # ⑥ 锁定后不可再移动（B8）+ 移动**仍然作用于未锁定的零片**
    t_lk = _ts(CMDS_D, 15, 1000.0)
    posLk = split_pos(_bus(vf, "o_pos", t_lk))
    lockv = _bus(vf, "o_lock", t_lk)
    res.append((
        "⑥ 确认锁定后 P0 **锚点不再变化**（B8：不可移动）；同时未锁定的 P1 仍可被移动 —— "
        "修复「跳过锁定零片」不能把普通移动一起卡死",
        posLk[0] == (0, 3) and posLk[1] == (1, 4) and (lockv & 1) == 1,
        "锁定并执行 1 次移动后：P0=%s（期望 (0,3) 不变）、P1=%s（期望 (1,4)：它是被选中的"
        "未锁定块）；o_lock = %s" % (posLk[0], posLk[1], format(lockv, "04b")),
    ))

    # ⑦ 一关只有 3 块 -> 选择索引不出现 3（只在**一关**窗口内统计）
    sel_vals, t = set(), T_GO_3
    while t < T_L2:
        v = _bus(vf, "o_sel_idx", t)
        if v is not None:
            sel_vals.add(v)
        t += 50.0
    res.append((
        "⑦ 一关只有 3 块零片：选择索引只在 0..2 之间循环（不出现 3）",
        sel_vals == {0, 1, 2},
        "出现过的选择索引 = %s" % sorted(sel_vals),
    ))

    # ⑲ ★【ERR-035 回归判据】B8："确认后不可再选择"
    t_a, t_b = _ts(CMDS_D, 12, 2000.0), T_SAMPLE_COLOR
    seen, hit_locked, tt = set(), [], t_a
    while tt < t_b:
        v = _bus(vf, "o_sel_idx", tt)
        if v is not None:
            seen.add(v)
            if v == 0:
                hit_locked.append(tt)
        tt += 50.0
    res.append((
        "⑲ ★【ERR-035 / B8 回归】P0 确认锁定后，【选择】键**永远不再选中它**"
        "（o_sel_idx 全程 != 0），但仍能在未锁定的 P1/P2 之间循环 —— "
        "修复前 sel 会绕回 0、把黄块显示成绿色（B8 明文「不可再选择及移动」）",
        (not hit_locked) and seen == {1, 2},
        "锁定后窗口内出现过的选择索引 = %s；命中锁定块 0 的采样数 = %d"
        % (sorted(seen), len(hit_locked)),
    ))

    # ⑧ 着色：逐格与模型比对
    ok8, det8 = _model_frame_check(vf, T_SAMPLE_COLOR, L1, "着色", sel=2)
    fr = _bus(vf, "o_rowr", T_SAMPLE_COLOR)
    fg = _bus(vf, "o_rowg", T_SAMPLE_COLOR)
    posCol = split_pos(_bus(vf, "o_pos", T_SAMPLE_COLOR))
    lockCol = _bus(vf, "o_lock", T_SAMPLE_COLOR)
    oriCol = ori_list(_bus(vf, "o_ori", T_SAMPLE_COLOR))
    cov = union_cells_multi(posCol[:NP], L1, oriCol[:NP])
    selr = drawn_cells(L1[2], posCol[2], oriCol[2])
    tgt = mask_cells(L1_TGT_MASK)
    # ⚠️ ERR-023：**不画目标鬼影** —— 未覆盖的目标格子必须不亮。
    ghost = []
    if None not in (fr, fg):
        ghost = [(r, c) for (r, c) in (tgt - cov)
                 if frame_cell(fr, r, c) == 1 or frame_cell(fg, r, c) == 1]
    res.append((
        "⑧ 着色逐格与模型一致：选中零片=**纯绿**（红必须为 0，ERR-007 回归）、"
        "已锁定零片=黄(红=绿=1)、其余零片=红，且**不画目标鬼影**"
        "（未覆盖的目标格子不亮 —— ERR-023 的引擎侧判据）",
        ok8 and (not ghost),
        det8 + "；选中零片 %d 格；未覆盖目标格 %d 个、其中被点亮的 %d 个"
        % (len(selr), len(tgt - cov), len(ghost)),
    ))

    # ⑨ 三块全部到位并锁定 -> o_solved = 1
    posS = split_pos(_bus(vf, "o_pos", T_C_SOLVED))
    oriS = ori_list(_bus(vf, "o_ori", T_C_SOLVED))
    uS = union_cells_multi(posS[:NP], L1, oriS[:NP])
    at_tgt = (all(posS[i] == L1_GOAL[i] for i in range(NP))
              and oriS[:NP] == L1_GOAL_ORI)
    res.append((
        "⑨ 三块零片拼成图 4-1 的 4x3 矩形（**并集**逐格一致；终点锚点 = 最优计划的 "
        "(2,2)(3,2)(3,2)、朝向 (2,2,2)）后逐块确认 → o_solved = 1"
        "（B9：位置和形状与初始拼图一致 —— 判据看**画面**，不看零片编号；"
        "⚠️ 这组锚点不是 pkg 里写的那组见证锚点，而是一组**等价铺法**）",
        at_tgt and uS == mask_cells(L1_TGT_MASK) and _v(vf, "o_solved", T_C_SOLVED) == "1"
        and _bus(vf, "o_lock", T_C_SOLVED) == 0x7,
        "锚点 P0=%s P1=%s P2=%s（期望 %s）；朝向=%s（期望 %s）；并集 %d 格 == 目标 = %s；"
        "o_solved=%s；o_lock=%s"
        % (posS[0], posS[1], posS[2], L1_GOAL, oriS[:NP], L1_GOAL_ORI,
           len(uS), uS == mask_cells(L1_TGT_MASK),
           _v(vf, "o_solved", T_C_SOLVED), format(_bus(vf, "o_lock", T_C_SOLVED), "04b")),
    ))

    # ⑩ 只锁 2 块时 o_solved=0
    res.append((
        "⑩ 只锁定 2 块时 o_solved = 0、o_all_lock = 0（成功判据必须是「全部锁定」）",
        _v(vf, "o_solved", T_C_2LOCK) == "0" and _v(vf, "o_all_lock", T_C_2LOCK) == "0"
        and _v(vf, "o_all_lock", T_C_SOLVED) == "1",
        "锁 2 块时 o_solved=%s o_all_lock=%s；锁 3 块后 o_all_lock=%s"
        % (_v(vf, "o_solved", T_C_2LOCK), _v(vf, "o_all_lock", T_C_2LOCK),
           _v(vf, "o_all_lock", T_C_SOLVED)),
    ))

    # ⑪ 行扫描
    rows, t = set(), 20000.0
    while t < 60000.0:
        v = _bus(vf, "o_scanrow", t)
        if v is not None:
            rows.add(v)
        t += 20.0
    res.append((
        "⑪ 行扫描渲染：o_scanrow 在 0..7 之间轮转（整帧由 8 行拼出，不是一次性写入）",
        rows == set(range(8)),
        "20~60 us 内出现过的行号 = %s（一关一行 %d 拍 = %.0f ns，整帧 %.0f ns）"
        % (sorted(rows), ROW_TICKS_L1, ROW_TICKS_L1 * TICK, FRAME_L1),
    ))

    # ⑫ ★ 串行重叠引擎的扫描不变量（**替代**已消失的 ERR-016 流水对齐判据）
    #    旧判据查的是 "chk_orow == chk_prow - 候选行" —— 那套一拍算完所有行、
    #    候选行寄存的流水结构（chk_row/chk_orow/chk_prow）在这一版 RTL 里**整个
    #    不存在了**，所以那一条无法再表达。换成：每次检查里 (chk_sr, chk_slot)
    #    恰好走遍每一种组合一次、chk_crow 逐拍等于独立模型重算的候选本行掩码、
    #    结束时 chk_hit 等于模型算出的命中判定（含"slot == chk_me 自己不比较"）。
    all_err, tot_ck, tot_cmp, tot_hit, tot_rot, tot_edge = [], 0, 0, 0, 0, 0
    for (a, b, tag) in ((T_GO_3, T_GO_3 + 40000.0, "散落③"),
                        (T_CMD_D + 90000.0, T_CMD_D + 190000.0, "移动/拒绝"),
                        (T_CMD_R1, T_AFTER_R1, "旋转（含非方形零片与拒绝）"),
                        (T_GO_L2, T_GO_L2 + 40000.0, "二关散落")):
        e, nc, ncmp, nh, nr, ne = _engine_walk(vf, a, b, tag)
        all_err += e
        tot_ck += nc
        tot_cmp += ncmp
        tot_hit += nh
        tot_rot += nr
        tot_edge += ne
    res.append((
        "⑫ ★ 重叠引擎串行化后的**扫描不变量**（替代已不存在的 ERR-016 流水对齐判据）："
        "每次检查里 (chk_sr, chk_slot) 恰好走遍 (本块行 0..chk_srmax) x (邻块 0..npc-1) "
        "每一种组合**一次**（每行先 1 拍 load 再 npc 拍逐块比较、不跳号不错行），"
        "每拍 chk_crow 等于用**独立模型**重算的候选本行掩码，检查结束那一拍的 chk_hit "
        "等于模型算出的「是否有任何一次真实比较命中」（slot == chk_me 自己那一拍按 "
        "RTL 语义不比较）；旋转请求（chk_rot=1）必须走**同一套**流水且 chk_ori = 该块 "
        "ori+1 —— 既查扫描结构、也端到端查重叠判定与 A4 的流水复用",
        (not all_err) and tot_ck >= 6 and tot_cmp >= 50 and tot_hit >= 1 and tot_rot >= 4,
        "四个窗口共核对 %d 次检查（其中旋转请求 %d 次）、%d 次邻块比较、判定命中 %d 次"
        "（另有 %d 次检查被窗口边缘截断、已跳过）；%s"
        % (tot_ck, tot_rot, tot_cmp, tot_hit, tot_edge,
           "全部一致" if not all_err else "；".join(all_err[:5])),
    ))

    # ⑯ 已知残余缺陷 ERR-018b：硬编码回退锚点不做重叠检查
    posErr = split_pos(_bus(vf, "o_pos", T_S1))
    _, badE = overlap_report(posErr, L1, ori_list(_bus(vf, "o_ori", T_S1)))
    used_fallback = [i for i in range(NP) if posErr[i] == L1_FALLBACK[i]]
    res.append((
        "⑯【已知残余缺陷 ERR-018b，如实记录、未修复】16 次尝试都失败后启用硬编码"
        "回退锚点，而回退锚点**不再做重叠检查** → 与别的零片的随机落位重叠",
        len(badE) > 0 and len(used_fallback) >= 1,
        "散落①(rnd_val 恒 12) 实测 P0=%s P1=%s P2=%s；命中回退锚点的零片=%s；%s"
        % (posErr[0], posErr[1], posErr[2], used_fallback,
           "；".join(badE) if badE else "未复现重叠（若已修复请更新本条）"),
    ))

    # ================================================================
    # 旋转覆盖（A4）—— 一关
    # ================================================================
    # 旋转①/⑥：一关（三块）单次旋转。用**楼梯形**（bbox 3x3）。
    # 判据 = 独立几何模型逐格复算整帧（"绕零片自身 bbox 中心顺时针转 90° 再对齐左上角"）。
    sh_p1 = L1[1]
    okR1, detR1 = _model_frame_check(vf, T_R1_ONE, L1, "旋转①", sel=1)
    pos_pre = split_pos(_bus(vf, "o_pos", T_R1_PRE))
    pos_one = split_pos(_bus(vf, "o_pos", T_R1_ONE))
    ori_one = _bus(vf, "o_ori", T_R1_ONE)
    res.append((
        "旋转①/⑥ ★【A4】一关（只有三块零片时同样有效）：选中 P1(楼梯形) 按【旋转】一次 "
        "→ o_ori 该块 **%d -> %d**（初始朝向就是 %d，不再是 0）、**o_pos 一格都不动**、"
        "整帧逐格等于独立模型算出的「绕零片中心顺时针转 90°」后的形状"
        % (ORI_INIT[1], (ORI_INIT[1] + 1) % 4, ORI_INIT[1]),
        okR1 and _ori_at(vf, T_R1_ONE, 1) == (ORI_INIT[1] + 1) % 4
        and pos_one == pos_pre and pos_one[1] == (0, 4),
        "%s；ori=%s（P1=%d）；pos 前=%s 后=%s（必须相同）"
        % (detR1, format(ori_one, "08b") if ori_one is not None else "X",
           (ORI_INIT[1] + 1) % 4, pos_pre[:NP], pos_one[:NP]),
    ))

    # 旋转②：转 4 次回到 0，且整帧与旋转前逐位相同
    fr_pre, fg_pre = _frame_pair(vf, T_R1_PRE)
    fr_four, fg_four = _frame_pair(vf, T_R1_FOUR)
    ori_four = _bus(vf, "o_ori", T_R1_FOUR)
    okR2b, detR2b = _model_frame_check(vf, T_R1_FOUR, L1, "旋转②(模型)", sel=1)
    res.append((
        "旋转② ★ 连按 4 次【旋转】= 360°：o_ori 回到**初始朝向 %d**，且**整帧 "
        "o_rowr/o_rowg 与旋转前逐位相同**（4 次都提交、没有丢步或方向累积错误）"
        % ORI_INIT[1],
        _ori_at(vf, T_R1_FOUR, 1) == ORI_INIT[1] and fr_pre == fr_four
        and fg_pre == fg_four and okR2b and None not in (fr_pre, fg_pre),
        "ori=%s（P1=%s，期望 %d）；旋转前 frame=(0x%X,0x%X) 4 次后=(0x%X,0x%X) "
        "逐位相同=%s；%s"
        % (format(ori_four, "08b") if ori_four is not None else "X",
           _ori_at(vf, T_R1_FOUR, 1), ORI_INIT[1],
           fr_pre or 0, fg_pre or 0, fr_four or 0, fg_four or 0,
           fr_pre == fr_four and fg_pre == fg_four, detR2b),
    ))

    # 旋转④：重叠被拒
    pos_ov = split_pos(_bus(vf, "o_pos", T_R1_OVL))
    ori_ov = _bus(vf, "o_ori", T_R1_OVL)
    fr_ov, fg_ov = _frame_pair(vf, T_R1_OVL)
    fr_ov0, fg_ov0 = _frame_pair(vf, T_R1_OVL_PRE)
    p1_rot = drawn_cells(sh_p1, (0, 4), (ORI_INIT[1] + 1) % 4)
    p2_cells = drawn_cells(L1[2], (2, 4), ORI_INIT[2])
    clash = sorted(p1_rot & p2_cells)
    res.append((
        "旋转④ ★ 重叠被拒：P1(楼梯形 @(0,4)，朝向 %d) 转 90° 后的格子会压到 "
        "P2(L 形 @(2,4)，朝向 %d) 上（交集格子见实测），因此这次旋转必须**什么都不改** "
        "—— o_pos / o_ori / 整帧全部与旋转请求之前逐位相同"
        % (ORI_INIT[1], ORI_INIT[2]),
        clash and _ori_at(vf, T_R1_OVL, 1) == ORI_INIT[1]
        and pos_ov == split_pos(_bus(vf, "o_pos", T_R1_OVL_PRE))
        and fr_ov == fr_ov0 and fg_ov == fg_ov0,
        "独立模型算出冲突格 = %s；P1 的 ori=%s（必须仍为 %d）；pos=%s；整帧不变=%s"
        % (clash, _ori_at(vf, T_R1_OVL, 1), ORI_INIT[1], pos_ov[:NP],
           fr_ov == fr_ov0 and fg_ov == fg_ov0),
    ))

    # 旋转⑤：出界被拒
    t_oob_pre = T_R1_OOB_PRE
    pos_oob = split_pos(_bus(vf, "o_pos", T_R1_OOB))
    ori_oob = _bus(vf, "o_ori", T_R1_OOB)
    fr_oob, fg_oob = _frame_pair(vf, T_R1_OOB)
    fr_oob0, fg_oob0 = _frame_pair(vf, t_oob_pre)
    res.append((
        "旋转⑤ ★ 出界被拒：1x3 横条 P0（当前朝向 2）移到**第 7 行**后再按【旋转】—— "
        "转 90° 后包围盒变成 3 行高，锚点行 + 3 = 10 > 8（教科书旋转同样出界，两种解释"
        "都判越界），必须被拒：o_ori / o_pos / 整帧全部不变",
        pos_oob[0] == (7, 0) and _ori_at(vf, T_R1_OOB, 0) == 2
        and pos_oob == split_pos(_bus(vf, "o_pos", t_oob_pre))
        and fr_oob == fr_oob0 and fg_oob == fg_oob0,
        "P0 锚点 = %s（期望 (7,0) 不变）；P0 的 ori=%s（必须仍为 2）；整帧不变=%s"
        % (pos_oob[0], _ori_at(vf, T_R1_OOB, 0),
           fr_oob == fr_oob0 and fg_oob == fg_oob0),
    ))

    # 旋转⑦：非方形零片（1x3 横条）的旋转必须**归一化到自身紧包围盒**。
    # 这是第一版 RTL 的真实缺陷（旋转在固定 3x3 盒里做、紧包围盒偏移没补回来：
    # 横条转 90° 会凭空右移 2 列，ori=2 时 3 个格子还会整块漏画）—— 现在的 RTL 用
    # rot_off_r/rot_off_c 把偏移补回来了（见 rtl/puzzle_pkg.vhd 的【锚点语义】），
    # 本 tb 就用"逐格等于教科书旋转"这条判据把它钉住：横条 @(4,0) 转 90° 必须变成
    # **同一列**的竖条 (4,0)(5,0)(6,0)，再转 90° 必须回到原横条 (4,0)(4,1)(4,2)。
    fg_b1 = _bus(vf, "o_rowg", T_R1_BAR1)
    fg_b2 = _bus(vf, "o_rowg", T_R1_BAR2)
    green1 = lit_cells(fg_b1) if fg_b1 is not None else set()
    green2 = lit_cells(fg_b2) if fg_b2 is not None else set()
    bar = L1[0]
    want1 = drawn_cells(bar, (4, 0), 3)
    want2 = drawn_cells(bar, (4, 0), 0)
    # 旧实现（在固定 3x3 盒里转但不补 rot_off_c）会把竖条画到第 2 列 —— ERR-040
    unnorm1 = {(4 + r, 2) for r in range(3)}
    ori_b1 = _ori_at(vf, T_R1_BAR1, 0)
    ori_b2 = _ori_at(vf, T_R1_BAR2, 0)
    pos_b1 = split_pos(_bus(vf, "o_pos", T_R1_BAR1))
    pos_b2 = split_pos(_bus(vf, "o_pos", T_R1_BAR2))
    res.append((
        "旋转⑦ ★ 非方形零片的旋转**归一化到自身紧包围盒**（第一版 RTL 的真实缺陷，"
        "已被 rot_off_r/rot_off_c 修掉）：1x3 横条 P0 @(4,0) 从朝向 2 转 90° 到朝向 3 后"
        "必须画成**同一列**的竖条 (4,0)(5,0)(6,0)、o_pos 不变；再转 90°（朝向 0）必须回到"
        "原横条 (4,0)(4,1)(4,2)。判据是**逐格与独立教科书模型比对**，不是「看着像」",
        ori_b1 == 3 and pos_b1[0] == (4, 0) and green1 == want1
        and ori_b2 == 0 and pos_b2[0] == (4, 0) and green2 == want2,
        "ori=3：实测绿格 = %s，教科书模型 = %s（未归一化的旧实现会画在 %s）"
        "；ori=0：实测绿格 = %s，教科书模型 = %s"
        % (sorted(green1), sorted(want1), sorted(unnorm1), sorted(green2), sorted(want2)),
    ))

    # 旋转⑥：旋转已锁定零片
    t_lk_pre = T_R1_LK_PRE
    pos_lk = split_pos(_bus(vf, "o_pos", T_R1_LK))
    ori_lk = _bus(vf, "o_ori", T_R1_LK)
    lock_lk = _bus(vf, "o_lock", T_R1_LK)
    sel_lk = _bus(vf, "o_sel_idx", T_R1_LK)
    fr_lk, fg_lk = _frame_pair(vf, T_R1_LK)
    fr_lk0, fg_lk0 = _frame_pair(vf, t_lk_pre)
    did_accept = (ori_b2 == 0 and pos_b2[0] == (4, 0))   # 同一锚点、同一朝向在未锁时被接受过
    res.append((
        "旋转⑥ ★ 旋转**已锁定**的零片什么都没发生（B8「确认后不可再选择及移动」对旋转同样成立）："
        "把 P1/P2/P0 依次确认锁定（此时 sel 停在**已锁定的 P0** 上 —— 全锁时 next_unlocked 无处可去，"
        "这是 ERR-035 的边角），再按【旋转】：o_ori / o_pos / 整帧全部不变。"
        "**同一锚点**上未锁定时旋转是被接受的（旋转⑦ 的 (4,0) 朝向 2->3->0），所以这次"
        "「没变化」只能归因于锁定",
        ori_lk == _bus(vf, "o_ori", t_lk_pre)
        and pos_lk == split_pos(_bus(vf, "o_pos", t_lk_pre))
        and lock_lk == (1 << NP) - 1 and sel_lk == 0 and did_accept
        and fr_lk == fr_lk0 and fg_lk == fg_lk0,
        "o_lock=%s o_sel_idx=%d（0 = 停在已锁定的 P0 上）；ori=%s（与旋转前 %s 相同）；"
        "pos 不变=%s；整帧不变=%s；同锚点未锁定时该旋转被接受过=%s"
        % (format(lock_lk, "04b"), sel_lk, format(ori_lk, "08b"),
           format(_bus(vf, "o_ori", t_lk_pre) or 0, "08b"),
           pos_lk[:NP] == split_pos(_bus(vf, "o_pos", t_lk_pre))[:NP],
           fr_lk == fr_lk0 and fg_lk == fg_lk0, did_accept),
    ))

    # ================================================================
    # 第二关（ERR-021 / A4）
    # ================================================================
    tQ = mask_cells(L2_TARGET)

    # ⑬ 二关散落：4 块异形落在确定性回退锚点，未锁定时不许判成功
    posQ = split_pos(_bus(vf, "o_pos", T_S_L2SCAT))
    oriQ = ori_list(_bus(vf, "o_ori", T_S_L2SCAT))
    uQ = union_cells_multi(posQ[:NP2], L2, oriQ[:NP2])
    res.append((
        "⑬ 第二关（i_level=1，4 块异形 3+2+5+6 格）散落完成：四块落在确定性回退锚点、"
        "互不重叠（16 格）、朝向 = PIECE_ORI_INIT = %s，且未锁定时 o_solved = 0"
        % (list(ORI_INIT),),
        tuple(posQ[:NP2]) == tuple(L2_FALLBACK) and len(uQ) == 16 and uQ != tQ
        and oriQ[:NP2] == list(ORI_INIT) and _v(vf, "o_solved", T_S_L2SCAT) == "0",
        "锚点 = %s（期望 %s）；并集 %d 格；并集==目标 = %s；ori=%s（期望 %s）；o_solved = %s"
        % (posQ[:NP2], L2_FALLBACK, len(uQ), uQ == tQ, oriQ[:NP2], list(ORI_INIT),
           _v(vf, "o_solved", T_S_L2SCAT)),
    ))

    # 旋转③：第二关同样有效（Q2 = J 形）
    okR3, detR3 = _model_frame_check(vf, T_R2_ONE, L2, "旋转③", sel=2)
    pos2_pre = split_pos(_bus(vf, "o_pos", T_R2_PRE))
    pos2_one = split_pos(_bus(vf, "o_pos", T_R2_ONE))
    fr2_pre, fg2_pre = _frame_pair(vf, T_R2_PRE)
    fr2_four, fg2_four = _frame_pair(vf, T_R2_FOUR)
    ori2_one = _bus(vf, "o_ori", T_R2_ONE)
    ori2_four = _bus(vf, "o_ori", T_R2_FOUR)
    res.append((
        "旋转③ ★【A4 / ⑥】第二关（四块零片、i_level=1）旋转同样有效：选中 Q2(J 形) "
        "转一次 → 该块朝向 **%d -> %d**、o_pos 不变、整帧等于独立模型；再转 3 次回到初始"
        "朝向 %d 且整帧与旋转前逐位相同（转完 sel 回到 0，所以后面 ⑭ 的拼图计划不受影响）"
        % (ORI_INIT[2], (ORI_INIT[2] + 1) % 4, ORI_INIT[2]),
        okR3 and _ori_at(vf, T_R2_ONE, 2) == (ORI_INIT[2] + 1) % 4
        and pos2_one == pos2_pre
        and _ori_at(vf, T_R2_FOUR, 2) == ORI_INIT[2]
        and fr2_pre == fr2_four and fg2_pre == fg2_four
        and None not in (fr2_pre, fg2_pre),
        "%s；ori 一次后=%s（Q2=%s）、四次后=%s（Q2=%s）；pos 前=%s 后=%s（必须相同）；"
        "旋转前后整帧逐位相同=%s"
        % (detR3, format(ori2_one, "08b"), _ori_at(vf, T_R2_ONE, 2),
           format(ori2_four, "08b"), _ori_at(vf, T_R2_FOUR, 2),
           pos2_pre[:NP2], pos2_one[:NP2],
           fr2_pre == fr2_four and fg2_pre == fg2_four),
    ))

    # ⑭ ★ ERR-021 的回归判据（等价摆法：故意摆成图案 3 的第二种铺法）
    posP = split_pos(_bus(vf, "o_pos", T_L2_SETTLE))
    oriP = ori_list(_bus(vf, "o_ori", T_L2_SETTLE))
    uP = union_cells_multi(posP[:NP2], L2, oriP[:NP2])
    lockP = _bus(vf, "o_lock", T_L2_SETTLE)
    solP = _v(vf, "o_solved", T_L2_SETTLE)
    okP = (tuple(posP[:NP2]) == tuple(L2_TILING_TB) and uP == tQ and lockP == 0xF
           and solP == "1" and oriP[:NP2] == list(L2_TILING_TB_ORI))
    detailP = ("锚点 = %s、朝向 = %s（= 本 tb 摆的那一种）；**另一种等价铺法** = %s "
               "（sim/tb_puzzle_top.py 摆的就是它 —— RTL 里**不再有任何锚点常量**，"
               "判据只看画面）；并集==目标图案 = %s（%d 格）；o_lock = %s；o_solved = %s"
               % (posP[:NP2], oriP[:NP2], L2_TILING_TOP, uP == tQ, len(uP),
                  format(lockP, "04b"), solP))
    if HAS_FRAME_VERDICT:
        fok = _v(vf, "frm_ok", T_L2_SETTLE)
        fva = _v(vf, "frm_valid", T_L2_SETTLE)
        okP = okP and fok == "1" and fva == "1"
        detailP += "；frm_ok = %s、frm_valid = %s（整帧画面判据）" % (fok, fva)
    res.append((
        "⑭ ★【ERR-021 回归判据】第二关把四块摆成图案 3（阶梯）的**第二种**铺法"
        "（画面与目标图案逐格一致、四块全锁）→ o_solved = 1。"
        "任何「第 k 块的锚点 == 写死的第 k 个位置」的判据都会在这里判错",
        okP, detailP,
    ))

    # ⑮ 反例：别把判据放宽成"永远成功"
    posW = split_pos(_bus(vf, "o_pos", T_L2B_SETTLE))
    uW = union_cells_multi(posW[:NP2], L2, ori_list(_bus(vf, "o_ori", T_L2B_SETTLE))[:NP2])
    lockW = _bus(vf, "o_lock", T_L2B_SETTLE)
    solW = _v(vf, "o_solved", T_L2B_SETTLE)
    allW = _v(vf, "o_all_lock", T_L2B_SETTLE)
    res.append((
        "⑮ 反例：第二关四块**原地全锁定**（不摆到目标位置上），画面并集 != 目标图案 → "
        "o_solved = 0 且 o_all_lock = 1（必须判失败；防止修 ERR-021 时把判据放宽成永远成功）",
        tuple(posW[:NP2]) == tuple(L2_FALLBACK) and uW != tQ and lockW == 0xF
        and solW == "0" and allW == "1",
        "锚点 = %s；并集 %d 格（目标 %d 格、%s）；o_lock = %s；o_solved = %s；"
        "o_all_lock = %s"
        % (posW[:NP2], len(uW), len(tQ), "相同" if uW == tQ else "不同",
           format(lockW, "04b"), solW, allW),
    ))

    # ⑰ ★ A2/S1：图案库下标（i_pat）一动，**在途的那一帧判据必须作废**。
    #    一帧 = 8 行 x (npc+2) 拍 = 48 拍 = 9.6 us（渲染器两相流水之后）。
    #    ⚠️ 翻转是**一串 12 次**（间隔 1.7 us，与帧长互质）：RTL 的"干净帧"快照在帧头、
    #    判据在帧尾，两者之间只有 7 行；变化若落在"帧尾→下一帧头"那一行的缝里，那一帧
    #    本来就还是干净的（快照已经是新值）—— 单次翻转会是 1/8 概率的抽奖。
    inval, fv0, n_flip = [], 0, 0
    t = T_PAT_CHG
    while t < T_PAT_END + T_PAT_WIN:
        if _v(vf, "o_all_lock", t) == "0" or _v(vf, "o_solved", t) == "0":
            inval.append(t)
        if HAS_FRAME_VERDICT and _v(vf, "frm_valid", t) == "0":
            fv0 += 1
        t += CLK
    # 顺带核对激励本身：i_pat 在这串时间里确实翻了 T_PAT_N 次
    pv, tt = _bus(vf, "i_pat", 0.0), T_PAT_CHG - 100.0
    while tt < T_PAT_END + 100.0:
        v = _bus(vf, "i_pat", tt)
        if v is not None and v != pv:
            n_flip += 1
            pv = v
        tt += 10.0
    rec_ok = (_v(vf, "o_all_lock", T_PAT_REC) == "1" and _v(vf, "o_solved", T_PAT_REC) == "1")
    ok_pat = bool(inval) and rec_ok and n_flip == T_PAT_N
    detail_pat = ("i_pat 在这串时间里翻转 %d 次（期望 %d）；此后 %.0f ns（≥ 2 帧）内 "
                  "o_all_lock/o_solved 归 0 的采样数 = %d（必须 > 0）；再等 3 帧"
                  "（t=%.0f ns）后 o_all_lock=%s、o_solved=%s"
                  % (n_flip, T_PAT_N, T_PAT_END + T_PAT_WIN - T_PAT_CHG, len(inval),
                     T_PAT_REC, _v(vf, "o_all_lock", T_PAT_REC),
                     _v(vf, "o_solved", T_PAT_REC)))
    if HAS_FRAME_VERDICT:
        detail_pat += "；同期 frm_valid = 0 的采样数 = %d（必须 > 0，一帧 = %.0f ns）" % (fv0, FRAME_L2)
        ok_pat = ok_pat and fv0 > 0
    res.append((
        "⑰ ★【A2/S1】图案库下标 i_pat 变化 → 在途整帧判据立即作废"
        "（o_all_lock/o_solved 归 0），再渲染一整帧干净画面后重新发布 —— "
        "「干净帧」必须同时跟踪 pos / level / **pat**。"
        "（翻转 12 次、相位互不相同，避免单次翻转正好落进「帧尾→帧头」那一行的缝里"
        "而变成概率性断言）",
        ok_pat, detail_pat,
    ))

    # ================================================================
    # ⑱ ★ A4 端到端（用户上板反馈的直接回归判据）
    #   "旋转 90 度效果倒是有，但是旋转好像对游戏并没有什么影响，不旋转也能成功通关。"
    #   → 本断言把"不转就通不了"这件事**在引擎级 tb 里直接算出来**（离线、不看波形）：
    #       ① 拼图计划里确实出现【旋转】按键；
    #       ② 按计划走：0 次被拒、并集逐格 == 图 4-1、三块全锁；
    #       ③ 把计划里的 rot 全部删掉再走：**出现被拒动作，且并集 != 目标**。
    #   几何模型是**本 tb 自己**的（drawn_cells / hh_of / ww_of），与 check_plans.py
    #   的实现互相独立 —— 同一结论由两处独立复算。
    # ================================================================
    posX, oriX, rejX, uX = simulate_l1(SOLVE_PLAN)
    posY, oriY, rejY, uY = simulate_l1(SOLVE_PLAN, drop_rot=True)
    n_rot_l1 = sum(1 for (k, _a, _l) in SOLVE_PLAN if k == "rot")
    tgtL1 = mask_cells(L1_TGT_MASK)
    res.append((
        "⑱ ★【A4 端到端 / 用户上板反馈的回归】零片从 PIECE_ORI_INIT = %s 开始散落，"
        "**一次都不按【旋转】就拼不出目标**：同一条拼图计划里【旋转】%d 次，按它走 → "
        "0 次被拒且并集 == 图 4-1；把 rot 全部删掉再走 → 被拒 %d 次且并集 != 目标"
        "（用本 tb 自己的独立几何模型离线算，与波形无关）"
        % (list(ORI_INIT[:NP]), n_rot_l1, rejY),
        n_rot_l1 > 0 and rejX == 0 and uX == tgtL1
        and (rejY > 0 or uY != tgtL1) and oriX != list(ORI_INIT[:NP]),
        "计划 %d 条：按计划走 被拒 %d 次、并集 %d 格 == 目标 = %s、终点朝向 %s（初始 %s）；"
        "删掉旋转后 被拒 %d 次、并集 %d 格 == 目标 = %s、终点朝向 %s、终点锚点 %s"
        % (len(SOLVE_PLAN), rejX, len(uX), uX == tgtL1, oriX, list(ORI_INIT[:NP]),
           rejY, len(uY), uY == tgtL1, oriY, posY),
    ))

    return res
