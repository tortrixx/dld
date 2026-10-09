# -*- coding: utf-8 -*-
"""tb_puzzle_ctrl.py —— puzzle_ctrl 功能仿真（落位 / 移动 / 锁定 / 着色）

【这一轮要回答什么】
    `puzzle_ctrl` 是拼图核心，也是全工程面积最大、历史上缺陷最密的模块
    （ERR-005 限时、ERR-007 选中零片显示不出绿色、ERR-009/013 底图挡零片都与它
    或它的显示语义有关）。它同时是**几何规则**的唯一定义者：

      · B5 散落：三块零片位置随机、**不能重叠**、必须在 8x8 内；
      · B6 选择：选中的零片要**纯绿**（不是"绿是红的子集"→ 显示成黄色）；
      · B7 移动：可以上下左右移动，**不能移出 8x8**、不能与其它零片重叠；
      · B8 确认：确认后**变黄且不可再移动**；
      · B9 成功：**每块都回到目标锚点且都已锁定**。

    本 tb 用**独立几何模型**（在 Python 里按"bit = 8*行+列，bit0=左上角"重建零片
    格子）逐条验算，而不是"看着波形像对的"。

【本轮实测到并修复的四个真缺陷（见 docs/06 ERR-016 / ERR-017 / ERR-018a / ERR-019）】
    · ERR-016：重叠检查的**行号流水没对齐** —— 候选零片的行是寄存的（晚一拍），
      却拿当前行去和别的零片比 → 候选的第 r 行被拿去比别人第 r+1 行；
      既漏判真重叠、又误拒合法落位（实测：本该落在 (0,0) 的第 1 块被误拒 → 走了回退）。
    · ERR-017：散落时「自己」的掩码用了 `sel` 而不是「正在摆放的那一块」 `sh_k` ——
      散落期间 sel 恒 0，于是**候选永远不和第 0 块比**（两块可以叠在同一格里），
      同时又会拿候选和它**自己散落前的位置**比（误拒）。
    · ERR-018a：散落**重试时不再回 SH_TRY 抽新候选** —— SH_CHK 里重复检查同一个
      寄存候选，16 次「尝试」其实是同一个位置，于是首候选一冲突就必然走回退。
    · ERR-019：`srl8` 把整行往**左**移，而「按锚点列摆放零片」要求往**右**移 ——
      锚点列 > 0 的零片全部画错列、并从左边界丢格子（1x3 横条 @ 列 2 只画出一个点）。
      同一条函数也供重叠判定用，所以碰撞检测一并错了。
    本 tb 的 ②③④⑤⑧⑫ 就是这四条的回归判据。

【已知残余缺陷 ERR-018b（本轮**如实记录、未修**）】
    16 次尝试都失败后走的**硬编码回退锚点不再做重叠检查**。ERR-018a 修好后，回退只
    在「随机源连续 16 次都给出冲突候选」时才可能触发（真实 LFSR 每次尝试都会翻新，
    概率约 1e-7 量级）；但一旦触发，回退锚点可能与别的零片的随机落位重叠。断言 ⑯ 用
    「rnd_val 恒 12」的极端激励把它复现出来并留档。

【⚠️ 端口位序的一个不一致，本 tb 必须按实际约定读】
    掩码类端口（i_target / i_sh*）用 `bit = 8*行 + 列`（bit0 = 左上角）；
    而帧类端口 o_rowr / o_rowg 把**第 0 行放在 63..56**，且行内列 7 在高位
    （等价：列 c ↔ bit(56-8*行+c)）。`puzzle_top` 也按同样的切片读第 0 行，
    功能上自洽 —— 但同一模块里两套位序是**易错点**，本 tb 按实际约定取样，
    并在 docs/02 / docs/06 里如实记录这一条。

【时间刻度】tick = 200 ns（10 个 20 ns 时钟）。模块只把 tick 当"推进拍"用，
    所以可以用远高于 200 Hz 的节拍把整场对局压进几百微秒。
"""

import pathlib

CLK = 20.0
TICK = 200.0
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
FALLBACK = [(0, 0), (0, 4), (4, 0), (4, 4)]      # RTL 里写死的回退锚点

# ------------------------------------------------------------------ 第二关（4 块 2x2）
# 【本阶段要回答什么】"第二关拼对了却出叉"（ERR-021）。
#
# 第二关的四块零片**形状完全相同**（都是 2x2 方块），而玩家在屏幕上只看得到
# 「四块零片的并集」：把 4 个方块填满 4x4 方块的 24 种摆法，**画面完全一样**。
# 修复前的成功判据却是"每一块的锚点分别等于写死的 L2_TGT0..3"，于是 24 种等价
# 摆法里有 23 种被判失败（`.tmp/analyze_win.py` 枚举出来的；一关的 2 种等价铺法
# 同理，命中率只有 1/2 —— 只是"能不能过一关"更像运气，没被察觉）。
#
# 所以本阶段故意摆成 L2_TGT 的一个**置换**（P0 与 P2 交换锚点），画面仍是目标图案：
#     目标锚点集 {(2,2),(2,4),(4,2),(4,4)}，实测锚点 ((4,2),(2,4),(2,2),(4,4))
# 断言 ⑭ 要求 o_solved = 1（修复前为 0）；断言 ⑮ 是反例：全锁定但画面不对时必须为 0。
L2_P = int("0000000000000000000000000000000000000000000000000000001100000011", 2)
L2_TARGET = int("0000000000000000001111000011110000111100001111000000000000000000", 2)
L2_TGT = [(2, 2), (2, 4), (4, 2), (4, 4)]        # puzzle_pkg.L2_TGT0..3
L2_FALLBACK = [(0, 0), (0, 4), (4, 0), (4, 4)]   # rnd_val 恒 0 -> 确定性回退锚点
NP2 = 4
# 置换后的落位（P0 与 P2 交换）：并集 == L2_TARGET，锚点元组 != L2_TGT
L2_PERM = [(4, 2), (2, 4), (2, 2), (4, 4)]

# ------------------------------------------------------------------ 时间表
T_GO_1 = 1000.0          # 散落①：rnd_val 恒 12 -> 复现 ERR-018b（回退锚点未查重叠）
T_S1 = 90000.0
T_GO_2 = 95000.0         # 散落②：rnd_val 快速变化 -> 真随机，用来验证重叠判定本身
T_S2 = 250000.0
T_GO_3 = 255000.0        # 散落③：rnd_val 恒 0 -> 可复现的确定落位（后续判据的基准）
T_S3 = 320000.0
CMD_C = 330000.0         # 第三阶段（复现拼图）命令起点
CMD_STEP = 3000.0


def _cmds(start, items):
    out, t = [], start
    for (kind, arg, label) in items:
        out.append((t, kind, arg, label))
        t += CMD_STEP
    return out, t


# 第三阶段：把三块零片从 (0,0)/(0,4)/(4,0) 搬到各自目标锚点，再逐块确认。
# 顺序（离线用独立模型校验过，见 .tmp/plan_ctrl2.py）：
#   楼梯形 D,D,D,L,L -> (3,2)；L 形 D,D,R,R,R,U,U -> (4,3)；横条 D,D,R,R -> (2,2)
SOLVE_PLAN = [
    ("sel", None, "选中 P1(楼梯形)"),
    ("move", "D", "P1 下移"), ("move", "D", "P1 下移"), ("move", "D", "P1 下移"),
    ("move", "L", "P1 左移"), ("move", "L", "P1 左移到目标"),
    ("sel", None, "选中 P2(L 形)"),
    ("move", "D", "P2 下移"), ("move", "D", "P2 下移"),
    ("move", "R", "P2 右移"), ("move", "R", "P2 右移"), ("move", "R", "P2 右移"),
    ("move", "U", "P2 上移"), ("move", "U", "P2 上移到目标"),
    ("sel", None, "选中 P0(横条)"),
    ("move", "D", "P0 下移"), ("move", "D", "P0 下移"),
    ("move", "R", "P0 右移"), ("move", "R", "P0 右移到目标"),
    ("confirm", None, "锁定 P0"),
    ("confirm", None, "锁定 P1"),
    ("confirm", None, "锁定 P2 -> 全部锁定且都在目标"),
]
CMDS_C, T_AFTER_C = _cmds(CMD_C, SOLVE_PLAN)

# 第四阶段：边界 / 重叠 / 锁定 / 着色
T_GO_D = T_AFTER_C + 10000.0
T_CMD_D = T_GO_D + 75000.0          # 回退散落要 16 次尝试 x 3 块，留足时间
EDGE_PLAN = [
    ("sel", None, "选中 P2(L 形)"), ("sel", None, "选中 P2(L 形)"),
    ("move", "D", "P2 下移"), ("move", "D", "P2 下移"),
    ("move", "D", "第 3 次下移 —— 应被越界拒绝"),
    ("move", "D", "第 4 次下移 —— 应被越界拒绝"),
    ("sel", None, "选回 P0(横条)"),
    ("move", "R", "P0 右移"), ("move", "R", "P0 右移"), ("move", "R", "P0 右移"),
    ("move", "R", "第 4 次右移 —— 应与楼梯形重叠而被拒"),
    ("confirm", None, "锁定 P0"),
    ("sel", None, "选回 P0(横条)"), ("sel", None, "选回 P0(横条)"),
    ("move", "R", "锁定后再移动 —— 应被拒绝"),
    ("sel", None, "选中 P1(楼梯形) 以便看着色"),
]
CMDS_D, T_AFTER_D = _cmds(T_CMD_D, EDGE_PLAN)
T_EDGE_DONE = T_AFTER_D + 2000.0        # 最后一次 move 之后的稳定采样点

T_SAMPLE_COLOR = T_AFTER_D + 3000.0

# ------------------------------------------------------------------ 第二关时间表
T_L2 = T_SAMPLE_COLOR + 6000.0          # 切到第二关：i_level / 形状 / 目标一起换
T_GO_L2 = T_L2 + 20000.0                # 第二关散落（rnd_val 恒 0 → 16 次失败 → 回退锚点）
T_CMD_L2 = T_GO_L2 + 20000.0            # 回退散落最坏 ~16x3 次尝试 ≈ 14 us，留 20 us 余量

# 把四块 2x2 摆成 L2_TGT 的**置换**（P0 与 P2 交换）：
#   P0 (0,0) -R R-> (0,2) -D D D D-> (4,2)
#   P1 (0,4) -------- D D --------> (2,4)
#   P2 (4,0) -U U-> (2,0) -R R----> (2,2)
#   P3 (4,4) 原地不动               (4,4)
# 每一步的中间位置都用独立几何模型验过不重叠（见 overlap_report 的复用）。
L2_PLAN = [
    ("move", "R", "P0 右移"), ("move", "R", "P0 右移到第 2 列"),
    ("move", "D", "P0 下移"), ("move", "D", "P0 下移"),
    ("move", "D", "P0 下移"), ("move", "D", "P0 下移到 (4,2)"),
    ("sel", None, "选中 P1"),
    ("move", "D", "P1 下移"), ("move", "D", "P1 下移到 (2,4)"),
    ("sel", None, "选中 P2"),
    ("move", "U", "P2 上移"), ("move", "U", "P2 上移"),
    ("move", "R", "P2 右移"), ("move", "R", "P2 右移到 (2,2)"),
    ("sel", None, "选中 P3"),
    ("confirm", None, "锁定 P3"),
    ("confirm", None, "锁定 P0"),
    ("confirm", None, "锁定 P1"),
    ("confirm", None, "锁定 P2 -> 四块全锁、并集 == 目标图案"),
]
CMDS_L2, T_AFTER_L2 = _cmds(T_CMD_L2, L2_PLAN)
T_L2_SETTLE = T_AFTER_L2 + 4000.0       # 一次整帧渲染 8 个 tick = 1600 ns，留 4 us

# 反例：再散落一次，四块**原地**全锁定 —— 画面（并集）不等于目标图案 → 必须判失败
T_GO_L2B = T_L2_SETTLE + 20000.0
T_CMD_L2B = T_GO_L2B + 20000.0
WRONG_PLAN = [
    ("confirm", None, "锁定第 1 块"), ("confirm", None, "锁定第 2 块"),
    ("confirm", None, "锁定第 3 块"), ("confirm", None, "锁定第 4 块 -> 全锁但画面错"),
]
CMDS_L2B, T_AFTER_L2B = _cmds(T_CMD_L2B, WRONG_PLAN)
T_L2B_SETTLE = T_AFTER_L2B + 4000.0

# A2/S1：故意在第 ⑰ 条断言处翻一次图案库下标（i_pat 0 → 1）。
# 本 tb 是**直接驱动 i_target** 的单元测试，所以 i_pat 只影响 puzzle_ctrl 里
# "整帧判据是否干净"的快照（pat_frm）：图案切换时，在途的那一帧必须作废
# （frm_valid → 0，o_all_lock/o_solved 复位），等下一整帧干净渲染完再重新发布。
T_PAT_CHG = T_L2_SETTLE + 4000.0

DURATION = T_L2B_SETTLE + 5000.0

OBSERVE = ["i_clk", "i_rst", "i_tick", "i_level", "i_pat", "i_go", "i_select", "i_move",
           "i_confirm", "i_up", "i_down", "i_left", "i_right", "rnd_val",
           "o_busy", "o_sel_idx", "o_pos", "o_lock", "o_scanrow",
           "o_solved", "o_all_lock", "o_rowr", "o_rowg",
           "chk_row", "chk_orow", "chk_prow", "chk_pos", "chk_hit", "frow",
           "mv", "mv_pend"]

# ------------------------------------------------------------------ 修复前/后的同一个 tb
# ERR-021 的修复给 puzzle_ctrl 加了「整帧画面判据」寄存器（frm_ok / frm_valid /
# frm_bad / pos_frm）。仿真用的是**综合后网表**，观测一个不存在的节点会直接报
# "观测点缺失" —— 那样就没法用**同一个 tb** 分别在修复前/修复后各跑一轮做 A/B 对照。
# 所以这里显式探测仓库 RTL 里有没有这些寄存器：
#   · 修复前的 RTL：不观测（断言 ⑭ 会因为 o_solved = 0 直接失败 → 复现缺陷）
#   · 修复后的 RTL：观测（额外断言帧判据本身）
_CTRL_SRC = (pathlib.Path(__file__).resolve().parent.parent
             / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")
HAS_FRAME_VERDICT = "frm_ok" in _CTRL_SRC
VERDICT_NODES = ["frm_ok", "frm_valid", "frm_bad", "pos_frm"]
if HAS_FRAME_VERDICT:
    OBSERVE = OBSERVE + VERDICT_NODES


# ---------------------------------------------------------------- 独立几何模型
def rel_cells(sh):
    m = sh["mask"]
    return [(r, c) for r in range(8) for c in range(8) if (m >> (8 * r + c)) & 1]


def abs_cells(sh, anchor):
    ar, ac = anchor
    return sorted((ar + r, ac + c) for (r, c) in rel_cells(sh))


def popcount(m):
    return bin(m).count("1")


def split_pos(v):
    """o_pos (32 位) -> [(行,列)] x4，顺序 P0..P3。"""
    out = []
    for k in range(4):
        b = (v >> (24 - 8 * k)) & 0xFF
        out.append(((b >> 4) & 0xF, b & 0xF))
    return out


def frame_cell(frame, r, c):
    """帧寄存器 o_rowr/o_rowg 的位序。

    RTL 把第 r 行写在 bit (63-8r) .. (56-8r)，且行内 redrow(7) 落在高那一位，
    即列 c 对应 bit (56 - 8*r + c)。（等价说法：帧整字是掩码的"行序倒置"，
    行 0 在高位；同一行内列 7 在高位。）
    """
    return (frame >> (56 - 8 * r + c)) & 1


def overlap_report(pos, npc=NP):
    """返回 (是否越界, 重叠说明)。"""
    used, bad = {}, []
    oob = False
    for i in range(npc):
        ar, ac = pos[i]
        if not (0 <= ar and ar + L1[i]["h"] <= 8 and 0 <= ac and ac + L1[i]["w"] <= 8):
            oob = True
            bad.append("P%d 越界 @%s" % (i, pos[i]))
        for cell in abs_cells(L1[i], pos[i]):
            if cell in used:
                bad.append("P%d@%s 与 P%d 在格子 %s 重叠" % (i, pos[i], used[cell], cell))
            used[cell] = i
    return oob, bad


# ---------------------------------------------------------------- 二关用几何模型
# 二关四块形状完全相同（2x2 方块），所以模型直接按 (mask, h, w) 算格子，不按块编号。
def mask_cells(m):
    """64 位掩码 -> {(行,列)}（bit = 8*行 + 列，bit0 = 左上角）。"""
    return {(r, c) for r in range(8) for c in range(8) if (m >> (8 * r + c)) & 1}


def union_cells(pos, npc, mask, hw):
    """npc 块同形状零片放在 pos 上时，它们覆盖的格子并集。"""
    h, w = hw
    u = set()
    for i in range(npc):
        ar, ac = pos[i]
        for (r, c) in mask_cells(mask):
            if r < h and c < w:
                u.add((ar + r, ac + c))
    return u


# ---------------------------------------------------------------- 激励
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
    b.output_bus("o_scanrow", 3)
    b.output_bit("o_solved")
    b.output_bit("o_all_lock")
    b.output_bus("o_rowr", 64)
    b.output_bus("o_rowg", 64)
    for n, w in (("chk_row", 4), ("chk_orow", 4), ("chk_prow", 4), ("chk_pos", 8),
                 ("chk_hit", 1), ("frow", 3), ("mv", 1), ("mv_pend", 1)):
        if w == 1:
            b.output_bit(n)
        else:
            b.output_bus(n, w)
        _buried(b, n, w)
    if HAS_FRAME_VERDICT:                     # 只在修复后的 RTL 里存在（见文件上方说明）
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
    # 一关（3 块 1x3+3x3+2x2）→ 到 T_L2 切二关（4 块 2x2）
    b.segments("i_level", [(T_L2, 0), (DURATION - T_L2, 1)])

    # A2/S1 图案库下标：0 → 1 翻一次（见 T_PAT_CHG 的说明与断言 ⑰）
    b.bus_segments("i_pat", [(T_PAT_CHG, 0), (DURATION - T_PAT_CHG, 1)])

    # 形状 / 目标：两关各一段，T_L2 处整组切换（与 puzzle_top 里 piece_rom/pattern_rom
    # 受同一个 level 选择的行为一致）
    for i, sh in enumerate(L1):
        b.bus_segments("i_sh%d" % i, [(T_L2, sh["mask"]), (DURATION - T_L2, L2_P)])
        b.bus_segments("i_h%d" % i, [(T_L2, sh["h"]), (DURATION - T_L2, 2)])
        b.bus_segments("i_w%d" % i, [(T_L2, sh["w"]), (DURATION - T_L2, 2)])
    b.bus_segments("i_sh3", [(T_L2, 0), (DURATION - T_L2, L2_P)])
    b.bus_segments("i_h3", [(T_L2, 0), (DURATION - T_L2, 2)])
    b.bus_segments("i_w3", [(T_L2, 0), (DURATION - T_L2, 2)])
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

    # 命令（一关的三/四阶段 + 二关的两阶段，共用同一条命令流水）
    cmds = CMDS_C + CMDS_D + CMDS_L2 + CMDS_L2B
    b.segments("i_go", _tl(DURATION, _pulse_spans(
        [T_GO_1, T_GO_2, T_GO_3, T_GO_D, T_GO_L2, T_GO_L2B]), 0))
    b.segments("i_select", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in cmds if k == "sel"]), 0))
    b.segments("i_confirm", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in cmds if k == "confirm"]), 0))
    moves = [(t, a) for (t, k, a, _l) in cmds if k == "move"]
    b.segments("i_move", _tl(DURATION, _pulse_spans([t for (t, _a) in moves]), 0))
    for ch, name in (("U", "i_up"), ("D", "i_down"), ("L", "i_left"), ("R", "i_right")):
        # 方向必须在 i_move 之后的两拍内保持有效（引擎要把它锁进 mv_dir）
        b.segments(name, _tl(DURATION,
                             [(t - 100.0, t + 300.0, 1) for (t, a) in moves if a == ch], 0))


# ---------------------------------------------------------------- 断言
def _v(vf, name, t):
    return vf.value_at(name, t)


def _bus(vf, name, t):
    return vf.bus_value_at(name, t)


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
        "o_busy 见到=%s，回到 0 的时刻=%s（须早于 %.0f ns）"
        % (busy_seen, "%.0f" % busy_end if busy_end else "从未", T_S1),
    ))

    # ② ★ 真随机散落后：两两不重叠 + 都在 8x8 内（B5）
    posA = split_pos(_bus(vf, "o_pos", T_S2))
    oob, bad = overlap_report(posA)
    res.append((
        "② ★ 随机散落后三块零片**两两不重叠**且都在 8x8 内（B5：位置随机但不能重叠）"
        " —— 独立几何模型逐格验算（ERR-016/017 的回归判据）",
        (not oob) and (not bad),
        "实测锚点 P0=%s P1=%s P2=%s；%s"
        % (posA[0], posA[1], posA[2], "；".join(bad) if bad else "无重叠、无越界"),
    ))

    # ③ 确定性散落（rnd_val=0）复现出三个回退锚点
    posB = split_pos(_bus(vf, "o_pos", T_S3))
    expect_B = [(0, 0), (0, 4), (4, 0)]
    res.append((
        "③ rnd_val 恒 0（候选恒为 (0,0)，必然 16 次失败）时落到三个确定性回退锚点 —— "
        "后续边界/重叠/锁定/拼合判据的基准",
        posB[:NP] == expect_B,
        "实测 P0=%s P1=%s P2=%s（期望 %s）" % (posB[0], posB[1], posB[2], expect_B),
    ))

    # ④ 越界拒绝：2 行高零片到第 6 行后不能再下移
    t_edge = T_CMD_D + 6 * CMD_STEP          # 第 4 次下移（索引 5）之后
    posEdge = split_pos(_bus(vf, "o_pos", t_edge))
    res.append((
        "④ 越界被拒：P2(2x2) 从第 4 行下移到第 6 行为止，第 3/4 次下移被拒（B7 不能移出 8x8）",
        posEdge[2] == (6, 0),
        "P2 最终锚点 = %s（期望 (6,0)：第 7 行放不下 2 行高的零片）" % (posEdge[2],),
    ))

    # ⑤ 重叠拒绝：横条右移撞上楼梯形
    t_ov = T_CMD_D + 11 * CMD_STEP           # 第 4 次右移（索引 10）之后
    posOv = split_pos(_bus(vf, "o_pos", t_ov))
    res.append((
        "⑤ 重叠被拒：P0(1x3 横条) 从 (0,0) 右移一格到 (0,1) 合法，"
        "再右移就压到 P1(楼梯形, (0,4)) 上而被拒（B7；几何按「列 = 位号」独立算出）",
        posOv[0] == (0, 1),
        "P0 最终锚点 = %s（期望 (0,1)：横条占列 0~2，锚点列 2 时占列 2~4，与楼梯形冲突）"
        % (posOv[0],),
    ))

    # ⑥ 锁定后不可再移动
    t_lk = T_CMD_D + 15 * CMD_STEP           # 锁定后那次右移（索引 14）之后
    posLk = split_pos(_bus(vf, "o_pos", t_lk))
    lockv = _bus(vf, "o_lock", t_lk)
    res.append((
        "⑥ 确认锁定后该零片不能再移动（B8：确认后不可再选择及移动）",
        posLk[0] == (0, 1) and (lockv & 1) == 1,
        "锁定后再按右移：P0 仍为 %s；o_lock = %s" % (posLk[0], format(lockv, "04b")),
    ))

    # ⑦ 一关只有 3 块 -> 选择索引不出现 3
    #    ⚠️ 只在**一关**的时间窗内统计：T_L2 之后是二关（4 块），sel 会出现 3
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

    # ⑧ 着色：逐格与模型比对
    fr = _bus(vf, "o_rowr", T_SAMPLE_COLOR)
    fg = _bus(vf, "o_rowg", T_SAMPLE_COLOR)
    posCol = split_pos(_bus(vf, "o_pos", T_SAMPLE_COLOR))
    lockCol = _bus(vf, "o_lock", T_SAMPLE_COLOR)
    selCol = _bus(vf, "o_sel_idx", T_SAMPLE_COLOR)
    if None in (fr, fg, lockCol, selCol):
        res.append(("⑧ 着色逐格比对", False, "帧寄存器/锁定读到 X（未稳定）"))
    else:
        cov, kc, selr = set(), set(), set()
        for i in range(NP):
            cs = set(abs_cells(L1[i], posCol[i]))
            cov |= cs
            if (lockCol >> i) & 1:
                kc |= cs
            if selCol == i:
                selr |= cs
        tgt = mask_cells(L1_TGT_MASK)
        badc = []
        for r in range(8):
            for c in range(8):
                cell = (r, c)
                # ⚠️ ERR-023：**不再画目标鬼影**。引擎帧只在 S_PLAYING 显示（顶层状态
                # 多路器只在别的状态显示图案/胜利/失败图），而对局态又不该用红色虚影
                # 盖住零片（ERR-013）；原来靠顶层把 i_target 置零来实现"不画鬼影"，
                # 结果把成功判据也一起废掉了。现在改为引擎内直接不画鬼影、
                # i_target 始终是真实目标图案（判据要用）。
                want_r = 1 if (cell in cov and cell not in selr) else 0
                want_g = 1 if (cell in kc or cell in selr) else 0
                if (frame_cell(fr, r, c), frame_cell(fg, r, c)) != (want_r, want_g):
                    badc.append("(%d,%d) 实测红%d绿%d 期望红%d绿%d"
                                % (r, c, frame_cell(fr, r, c), frame_cell(fg, r, c),
                                   want_r, want_g))
        # 未覆盖的目标格子必须**不亮**（这正是"不画鬼影"的可执行判据：
        # 旧实现把 i_target 置零是为了这个，现在由引擎自己保证）
        ghost_lit = [(r, c) for (r, c) in (tgt - cov)
                     if frame_cell(fr, r, c) == 1 or frame_cell(fg, r, c) == 1]
        sel_on = all(frame_cell(fr, r, c) == 0 and frame_cell(fg, r, c) == 1
                     for (r, c) in selr)
        res.append((
            "⑧ 着色逐格与模型一致：选中零片=**纯绿**（红必须为 0，ERR-007 回归）、"
            "已锁定零片=黄(红=绿=1)、其余零片=红，且**不画目标鬼影**"
            "（未覆盖的目标格子不亮 —— ERR-023 的引擎侧判据；旧实现靠顶层把 "
            "i_target 置零来消鬼影，代价是成功判据永远不成立）",
            (not badc) and (not ghost_lit) and sel_on,
            "全部 64 格一致；选中零片 %d 格全部红0绿1；锁定零片 %d 格 红1绿1；"
            "未覆盖目标格 %d 个、其中被点亮的 %d 个"
            % (len(selr), len(kc), len(tgt - cov), len(ghost_lit))
            if not badc else "；".join(badc[:6]),
        ))

    # ⑨ 三块全部到位并锁定 -> o_solved = 1
    t_solved = T_AFTER_C - CMD_STEP + 2000.0
    posS = split_pos(_bus(vf, "o_pos", t_solved))
    at_tgt = all(posS[i] == L1[i]["tgt"] for i in range(NP))
    res.append((
        "⑨ 三块零片全部回到目标锚点后逐块确认 → o_solved = 1（B9：位置和形状与初始拼图一致）",
        at_tgt and _v(vf, "o_solved", t_solved) == "1"
        and _bus(vf, "o_lock", t_solved) == 0x7,
        "锚点 P0=%s(目标%s) P1=%s(目标%s) P2=%s(目标%s)；o_solved=%s；o_lock=%s"
        % (posS[0], L1[0]["tgt"], posS[1], L1[1]["tgt"], posS[2], L1[2]["tgt"],
           _v(vf, "o_solved", t_solved), format(_bus(vf, "o_lock", t_solved), "04b")),
    ))

    # ⑩ 只锁 2 块时 o_solved=0
    t_2lock = T_AFTER_C - 2 * CMD_STEP + 2000.0
    res.append((
        "⑩ 只锁定 2 块时 o_solved = 0、o_all_lock = 0（成功判据必须是「全部锁定」）",
        _v(vf, "o_solved", t_2lock) == "0" and _v(vf, "o_all_lock", t_2lock) == "0"
        and _v(vf, "o_all_lock", t_solved) == "1",
        "锁 2 块时 o_solved=%s o_all_lock=%s；锁 3 块后 o_all_lock=%s"
        % (_v(vf, "o_solved", t_2lock), _v(vf, "o_all_lock", t_2lock),
           _v(vf, "o_all_lock", t_solved)),
    ))

    # ⑪ 行扫描
    rows, t = set(), 20000.0
    while t < 40000.0:
        v = _bus(vf, "o_scanrow", t)
        if v is not None:
            rows.add(v)
        t += 20.0
    res.append((
        "⑪ 行扫描渲染：o_scanrow 在 0..7 之间轮转（整帧由 8 个 tick 拼出，不是一次性写入）",
        rows == set(range(8)),
        "20~40 us 内出现过的行号 = %s" % sorted(rows),
    ))

    # ⑫ 重叠引擎的行号对齐（ERR-016 的结构性判据）
    #   不变量：同一拍内 chk_orow == (chk_prow - 候选锚点行) mod 16。
    #   修复前两者相差 1 行（候选晚一拍却用当前行去比邻居），正是 ②⑤ 失败的根因。
    bad_align, n_align = [], 0
    t, row_prev = T_GO_3, None
    while t < T_GO_3 + 40000.0:
        crow = _bus(vf, "chk_row", t)
        cp = _bus(vf, "chk_prow", t)
        co = _bus(vf, "chk_orow", t)
        cpos = _bus(vf, "chk_pos", t)
        if None not in (crow, cp, co, cpos):
            if row_prev is not None and crow != row_prev and cp != 0xF:
                n_align += 1
                want = (cp - ((cpos >> 4) & 0xF)) & 0xF
                if want != co and len(bad_align) < 5:
                    bad_align.append("t=%.0f chk_prow=%d chk_orow=%d 应为 %d"
                                     % (t, cp, co, want))
            row_prev = crow
        t += CLK
    res.append((
        "⑫ 重叠检查的行号流水**对齐**：同一拍内 chk_orow == chk_prow - 候选锚点行"
        "（ERR-016 的结构性判据；修复前相差 1 行）",
        n_align > 50 and not bad_align,
        "检查了 %d 个比对拍；%s" % (n_align, "；".join(bad_align) if bad_align else "全部对齐"),
    ))

    # ⑯ 已知残余缺陷 ERR-018b：硬编码回退锚点不做重叠检查
    posErr = split_pos(_bus(vf, "o_pos", T_S1))
    _, badE = overlap_report(posErr)
    used_fallback = [i for i in range(NP) if posErr[i] == FALLBACK[i]]
    res.append((
        "⑯【已知残余缺陷 ERR-018b，本轮如实记录、未修复】16 次尝试都失败后启用硬编码"
        "回退锚点，而回退锚点**不再做重叠检查** → 与别的零片的随机落位重叠",
        len(badE) > 0 and len(used_fallback) >= 1,
        "散落①(rnd_val 恒 12) 实测 P0=%s P1=%s P2=%s；命中回退锚点的零片=%s；%s"
        % (posErr[0], posErr[1], posErr[2], used_fallback,
           "；".join(badE) if badE else "未复现重叠（若已修复请更新本条）"),
    ))

    # ================================================================
    # 第二关（ERR-021）：成功判据必须是「拼出来的画面」而不是「每块的锚点编号」
    # ================================================================
    tQ = mask_cells(L2_TARGET)

    # ⑬ 二关散落：4 块 2x2 落在确定性回退锚点，未锁定时不许判成功
    tQ0 = T_GO_L2 + 18000.0
    posQ = split_pos(_bus(vf, "o_pos", tQ0))
    uQ = union_cells(posQ, NP2, L2_P, (2, 2))
    res.append((
        "⑬ 第二关（i_level=1，4 块 2x2）散落完成：四块落在确定性回退锚点、互不重叠"
        "（16 格），且未锁定时 o_solved = 0",
        tuple(posQ[:NP2]) == tuple(L2_FALLBACK) and len(uQ) == 16 and uQ != tQ
        and _v(vf, "o_solved", tQ0) == "0",
        "锚点 = %s（期望 %s）；并集 %d 格；并集==目标 = %s；o_solved = %s"
        % (posQ[:NP2], L2_FALLBACK, len(uQ), uQ == tQ, _v(vf, "o_solved", tQ0)),
    ))

    # ⑭ ★ ERR-021 的回归判据
    posP = split_pos(_bus(vf, "o_pos", T_L2_SETTLE))
    uP = union_cells(posP, NP2, L2_P, (2, 2))
    lockP = _bus(vf, "o_lock", T_L2_SETTLE)
    solP = _v(vf, "o_solved", T_L2_SETTLE)
    okP = (tuple(posP[:NP2]) == tuple(L2_PERM) and uP == tQ and lockP == 0xF
           and solP == "1")
    detailP = ("锚点 = %s；写死的 L2_TGT = %s（本阶段故意摆成它的置换 %s）；"
               "并集==目标图案 = %s（%d 格）；o_lock = %s；o_solved = %s"
               % (posP[:NP2], L2_TGT, L2_PERM, uP == tQ, len(uP), format(lockP, "04b"), solP))
    if HAS_FRAME_VERDICT:
        fok = _v(vf, "frm_ok", T_L2_SETTLE)
        fva = _v(vf, "frm_valid", T_L2_SETTLE)
        okP = okP and fok == "1" and fva == "1"
        detailP += "；frm_ok = %s、frm_valid = %s（整帧画面判据）" % (fok, fva)
    res.append((
        "⑭ ★【ERR-021 回归判据】第二关把四块摆成目标锚点集的**一个置换**"
        "（画面与目标图案逐格一致、四块全锁）→ o_solved = 1。"
        "修复前判据是「第 k 块的锚点 == 写死的 L2_TGT[k]」，四块形状完全相同、"
        "24 种等价摆法里只认 1 种 → 玩家拼对了也出叉",
        okP, detailP,
    ))

    # ⑮ 反例：别把判据放宽成"永远成功"
    posW = split_pos(_bus(vf, "o_pos", T_L2B_SETTLE))
    uW = union_cells(posW, NP2, L2_P, (2, 2))
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
    #    puzzle_ctrl 的"干净帧"条件是 pos、level **和 pat** 三者在整帧内都没变
    #    （只跟踪 level 是不够的：i_target 现在由 (level, pat) 一起决定，
    #     图案切换那一拍可能让一帧里混着两幅图案的行）。
    #    时窗按帧长取：一帧 = 8 个 i_tick = 1600 ns，所以翻转后 0~3200 ns 内
    #    一定命中"作废"窗口，再往后一整帧渲染完又会重新发布判据。
    inval, fv0 = [], 0
    t = T_PAT_CHG
    while t < T_PAT_CHG + 3400.0:
        if _v(vf, "o_all_lock", t) == "0" or _v(vf, "o_solved", t) == "0":
            inval.append(t)
        if HAS_FRAME_VERDICT and _v(vf, "frm_valid", t) == "0":
            fv0 += 1
        t += CLK
    t_rec = T_PAT_CHG + 4200.0
    rec_ok = (_v(vf, "o_all_lock", t_rec) == "1" and _v(vf, "o_solved", t_rec) == "1")
    ok_pat = bool(inval) and rec_ok
    detail_pat = ("i_pat 翻转后 3.4 us 内 o_all_lock/o_solved 归 0 的采样数 = %d"
                  "（必须 > 0）；再遍历一整帧（t=%.0f ns）后 o_all_lock=%s、o_solved=%s"
                  % (len(inval), t_rec, _v(vf, "o_all_lock", t_rec),
                     _v(vf, "o_solved", t_rec)))
    if HAS_FRAME_VERDICT:
        detail_pat += "；同期 frm_valid = 0 的采样数 = %d（必须 > 0）" % fv0
        ok_pat = ok_pat and fv0 > 0
    res.append((
        "⑰ ★【A2/S1】图案库下标 i_pat 变化 → 在途整帧判据立即作废"
        "（o_all_lock/o_solved 归 0），再渲染一整帧干净画面后重新发布 —— "
        "「干净帧」必须同时跟踪 pos / level / **pat**，否则图案切换时可能拿混了"
        "两幅图案的帧发布判据",
        ok_pat, detail_pat,
    ))

    return res
