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
DURATION = T_SAMPLE_COLOR + 5000.0

OBSERVE = ["i_clk", "i_rst", "i_tick", "i_level", "i_go", "i_select", "i_move",
           "i_confirm", "i_up", "i_down", "i_left", "i_right", "rnd_val",
           "o_busy", "o_sel_idx", "o_pos", "o_lock", "o_scanrow",
           "o_solved", "o_all_lock", "o_rowr", "o_rowg",
           "chk_row", "chk_orow", "chk_prow", "chk_pos", "chk_hit", "frow",
           "mv", "mv_pend"]


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

    b.clock("i_clk", CLK)
    b.segments("i_rst", [(500.0, 1), (DURATION - 500.0, 0)])
    b.segments("i_tick", _tl(DURATION, [(t, t + CLK, 1)
                                        for t in _ticks(DURATION, TICK)], 0))
    b.segments("i_level", [(DURATION, 0)])            # 一关（3 块）

    # 形状 / 目标
    for i, sh in enumerate(L1):
        b.bus_segments("i_sh%d" % i, [(DURATION, sh["mask"])])
        b.bus_segments("i_h%d" % i, [(DURATION, sh["h"])])
        b.bus_segments("i_w%d" % i, [(DURATION, sh["w"])])
    b.bus_segments("i_sh3", [(DURATION, 0)])
    b.bus_segments("i_h3", [(DURATION, 0)])
    b.bus_segments("i_w3", [(DURATION, 0)])
    b.bus_segments("i_target", [(DURATION, L1_TGT_MASK)])

    # rnd_val：① 恒 12（复现 ERR-018b）② 每 100 ns 换一个值（真随机）③ 恒 0（可复现）
    rnd = [(T_GO_2, 12)]
    t, v = T_GO_2, 1
    while t < T_GO_3:
        rnd.append((100.0, (v * 97) % 256))
        v += 1
        t += 100.0
    rnd.append((DURATION - t, 0))
    b.bus_segments("rnd_val", rnd)

    # 命令
    b.segments("i_go", _tl(DURATION, _pulse_spans([T_GO_1, T_GO_2, T_GO_3, T_GO_D]), 0))
    b.segments("i_select", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in (CMDS_C + CMDS_D) if k == "sel"]), 0))
    b.segments("i_confirm", _tl(DURATION, _pulse_spans(
        [t for (t, k, _a, _l) in (CMDS_C + CMDS_D) if k == "confirm"]), 0))
    moves = [(t, a) for (t, k, a, _l) in (CMDS_C + CMDS_D) if k == "move"]
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
    sel_vals, t = set(), T_GO_3
    while t < DURATION:
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
        tgt = set((r, c) for r in range(8) for c in range(8)
                  if (L1_TGT_MASK >> (8 * r + c)) & 1)
        badc = []
        for r in range(8):
            for c in range(8):
                cell = (r, c)
                want_r = 1 if ((cell in cov and cell not in selr)
                               or (cell in tgt and cell not in cov)) else 0
                want_g = 1 if (cell in kc or cell in selr) else 0
                if (frame_cell(fr, r, c), frame_cell(fg, r, c)) != (want_r, want_g):
                    badc.append("(%d,%d) 实测红%d绿%d 期望红%d绿%d"
                                % (r, c, frame_cell(fr, r, c), frame_cell(fg, r, c),
                                   want_r, want_g))
        sel_on = all(frame_cell(fr, r, c) == 0 and frame_cell(fg, r, c) == 1
                     for (r, c) in selr)
        res.append((
            "⑧ 着色逐格与模型一致：选中零片=**纯绿**（红必须为 0，ERR-007 回归）、"
            "已锁定零片=黄(红=绿=1)、其余零片=红、目标鬼影=红（B6/B8）",
            (not badc) and sel_on,
            "全部 64 格一致；选中零片 %d 格全部红0绿1；锁定零片 %d 格 红1绿1"
            % (len(selr), len(kc)) if not badc else "；".join(badc[:6]),
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

    return res
