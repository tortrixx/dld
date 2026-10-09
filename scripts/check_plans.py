# -*- coding: utf-8 -*-
"""check_plans.py —— 离线复核 `sim/tb_puzzle_top.py` 的走法计划（不跑仿真）

【为什么需要它】
  整机仿真一轮要 **13 分钟以上**（压缩时间、近 10 亿个跳变）。而"按键计划能不能把零片
  走到目标铺法、中途会不会被引擎**拒绝**（越界 / 与别的零片重叠）"完全可以**离线算**：
  本文件复刻 `rtl/puzzle_ctrl.vhd` 的按键语义，把计划逐步走一遍，并独立验证
  "走完之后的并集 == 图案"（而不是相信 tb 里写的期望锚点）。

  ⭐ 第 10 工作阶段（A2/S1 图案库）与第 11 工作阶段（异形零片）都是这么做的：
  先用本脚本复核走法计划 ——**零次被拒、并集与图案逐格一致**——再去跑整机仿真。

【复刻的引擎规则（与 RTL 一一对应）】
  · `i_go`         → `locked=0`、`sel=0`、**`ori = PIECE_ORI_INIT`**，随后散落；
                     `rnd_val` 钉 0 时落到**确定性回退锚点**
                     （一关 (0,0)/(0,4)/(4,0)；二关再补 (4,4)）
  · `i_select`     → `sel` 前进到下一个**未锁定**的零片（一关 0..2 循环、二关 0..3 循环）
  · `i_confirm`    → `locked(sel)=1`，随后 `sel` 前进（**确认只锁定，不判对错**）
  · `i_move`       → 锚点先按方向**逐分量夹紧**到 0..7（RTL 的 mv_clamp），
                     再判 `cr+hh<=8 and cc+ww<=8`；越界或与其它零片**精确逐格重叠**
                     → **整个移动被拒**（贴边时夹紧后原地不动 = 被接受但无位移）
  · `i_rot`（A4）  → **原地**顺时针 90°（锚点不变）：候选 = 同一锚点 + `ori_next`，
                     用**旋转后的**高宽做越界判定、用**旋转后的**形状做重叠判定；
                     越界 / 重叠 / 已锁定 → 不提交（朝向与画面都不变）
  · `puzzle_pkg` 的位序：bit = 8*行 + 列，bit0 = 左上角
  · 朝向编码：块 k 占 `ori(2k+1 downto 2k)`；"01"=顺时针 90°、"10"=180°、"11"=270°；
     `PIECE_ORI_INIT = "10"&"10"&"01"&"01"` → 块 0..3 分别从 1/1/2/2 开始

  ⚠️ 第 11 工作阶段起第二关零片是**四种异形**（3/2/5/6 格），不只是大小变了：
     `play()` 里每一块用的是**各自**的掩码，重叠判定必须逐格算（包围盒判定会误判）。
  ⚠️ 第 14 工作阶段（A4 旋转必需性）起零片**不再从朝向 0 开始**，所以四份走法计划
     里**必须出现【旋转】键** —— 保持初始朝向只许平移时，第一关的矩形与四幅图案
     **都恰好覆盖不了**（scripts/check_geometry.py 的"旋转必需性"一节是独立证明）。

【怎么用】
    python scripts/check_plans.py          # 全过 → 退出码 0
"""
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "rtl" / "puzzle_pkg.vhd"


# ---------------------------------------------------------------- 从 RTL 解析掩码
def const_bits(name, src):
    m = re.search(r"constant\s+" + name +
                  r"\s*:\s*std_logic_vector\(63 downto 0\)\s*:=\s*\"([01]{64})\"", src, re.S)
    if not m:
        raise SystemExit("✗ puzzle_pkg.vhd 里找不到常量 %s" % name)
    return int(m.group(1), 2)


def const_anchor(name, src):
    m = re.search(r"constant\s+" + name +
                  r"\s*:\s*std_logic_vector\(7 downto 0\)\s*:=\s*\"([01]{4})\"\s*&\s*\"([01]{4})\"",
                  src, re.S)
    if not m:
        raise SystemExit("✗ puzzle_pkg.vhd 里找不到锚点常量 %s" % name)
    return int(m.group(1), 2), int(m.group(2), 2)


def const_ori_init(src):
    """PIECE_ORI_INIT -> 块 0..3 的初始朝向（VHDL 里 MSB 在左，块 3 先写）。"""
    m = re.search(r"constant\s+PIECE_ORI_INIT\s*:\s*std_logic_vector\(7 downto 0\)\s*:=\s*"
                  r"\"([01]{2})\"\s*&\s*\"([01]{2})\"\s*&\s*\"([01]{2})\"\s*&\s*\"([01]{2})\"",
                  src, re.S)
    if not m:
        raise SystemExit("✗ puzzle_pkg.vhd 里找不到 PIECE_ORI_INIT")
    s = "".join(m.groups())          # 块3 块2 块1 块0
    return tuple(int(s[6 - 2 * k:8 - 2 * k], 2) for k in range(4))


SRC = PKG.read_text(encoding="utf-8")
L1_SHAPES = [const_bits("L1_P%d" % i, SRC) for i in range(3)]
L2_SHAPES = [const_bits("L2_P%d" % i, SRC) for i in range(4)]
L2_PAT = {k: const_bits("L2_PAT%d" % k, SRC) for k in range(4)}
L1_TARGET_MASK = const_bits("L1_TARGET_MASK", SRC)
PIECE_ORI_INIT = const_ori_init(SRC)

L2_WITNESS = [const_anchor("L2_TGT%d" % i, SRC) for i in range(4)]

L1_START = [(0, 0), (0, 4), (4, 0)]
L2_START = [(0, 0), (0, 4), (4, 0), (4, 4)]     # rnd_val 恒 0 -> 确定性回退锚点

# ============================================================================
#  四份走法计划（**必须同时**与 sim/tb_puzzle_top.py 里的逐字一致 —— 见文件末尾守卫）
#
#  ⚠️ 第 14 工作阶段（A4 旋转必需性）起这些计划由"带旋转的 A*"重新解出：
#     状态 = (四块锚点, 四块朝向, sel)，动作 = 移动 / **旋转** / 换零片，
#     代价 = **按键次数**（换零片要按 (k'-k) mod n 次【选择】），
#     终点 = 某个**精确铺法**（锚点 + 朝向）且并集逐格等于图案，
#     取"所有精确铺法里最短的那条"。解算器与最优性证据在 `.tmp/opt/rot_astar2.py`：
#       一关   16 条命令（LB=16 ⇒ **可证最优**）
#       二关   30 条命令（PAT3 铺法 #0 的下界是 29，用"代价上界 29 的有界搜索"
#                          穷尽证明它**无解** ⇒ 30 是最优）
#       三关 0 20 条命令 / 三关 2 26 条命令（下界 ≥ 已找到代价的铺法全部跳过，
#                                            所以这两个也是最优）
# ============================================================================
PLAN_L1 = (["rot"] + ["right"] + ["down"] + ["right"] + ["down"] + ["select"] +
           ["down"] + ["rot"] + ["down"] + ["left"] + ["down"] + ["left"] +
           ["select"] + ["up"] + ["right"] * 2 + ["confirm"] * 3)

# 第二关走法（**固定 PAT3 = 阶梯**，D2：2026-10-09 起第二关图案不再随机）
#   终点 = PAT3 的**第 21 种**精确铺法（含旋转）：槽 0..3 → (5,3) (2,1) (2,2) (2,3)，
#   四块朝向都回到 2（== 初始朝向，所以每块被转过的次数是 4 的倍数）
PLAN_L2_PAT3 = (["down"] + ["select"] + ["left"] * 3 + ["rot"] + ["down"] * 2 +
                ["select"] + ["right"] * 2 + ["select"] + ["up"] * 2 + ["left"] +
                ["select"] + ["down"] * 3 + ["right"] + ["down"] + ["select"] * 2 +
                ["up"] * 2 + ["select"] * 2 + ["rot"] + ["right"] * 2 +
                ["confirm"] * 4)

# 第三关走法（A2"增加游戏关数 + 多种拼图图案随机选择"）：图案由 rng 决定，
#   整机 tb 用 DLD_L3PAT 把随机值钉住，于是这里给出两种模式各一份计划：
#     模式 A（图案 0 田）：20 条命令；终点 = 槽 0..3 → (2,2) (2,5) (3,2) (3,3)，朝向全 2
#     模式 B（图案 2 S/Z）：26 条命令；终点 = 槽 0..3 → (2,1) (4,4) (3,1) (2,4)，
#                            朝向 (2,2,1,0)
PLAN_L3_PAT0 = (["rot"] + ["right"] + ["down"] + ["right"] + ["down"] + ["select"] +
                ["rot"] + ["right"] + ["down"] * 2 + ["select"] + ["right"] * 2 +
                ["select"] + ["left"] + ["up"] + ["select"] * 3 + ["up"] +
                ["confirm"] * 4)
PLAN_L3_PAT2 = (["rot"] + ["right"] + ["down"] * 2 + ["select"] + ["down"] * 3 +
                ["left"] + ["rot"] + ["down"] + ["select"] + ["up"] + ["rot"] * 3 +
                ["select"] + ["up"] * 2 + ["rot"] * 2 + ["select"] * 2 + ["right"] +
                ["select"] + ["right"] + ["confirm"] * 4)

# ---- 计划终点（锚点 + 朝向）：check 里逐条核对 ----
# 打包方式与 tb 的 o_pos 一致：槽 k 的 (行,列) 占一个字节，槽 0 在最高字节。
L1_EXPECT_POS = 0x22323200                       # 一关只用槽 0..2，槽 3 恒 0
L2_EXPECT_POS = 0x53212223                       # PAT3 第 21 种铺法
L3_EXPECT_POS = {0: 0x22253233, 2: 0x21443124}   # 第三关：模式 A / 模式 B
L1_EXPECT_ORI = (2, 2, 2)
L2_EXPECT_ORI = (2, 2, 2, 2)
L3_EXPECT_ORI = {0: (2, 2, 2, 2), 2: (2, 2, 1, 0)}

DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


# ---------------------------------------------------------------- 几何
def cells(mask, r0=0, c0=0):
    return {(r0 + r, c0 + c) for r in range(8) for c in range(8)
            if (mask >> (8 * r + c)) & 1}


def rows_of(mask):
    """图案掩码 -> 8 行 8 位列掩码（与 tb_puzzle_top.pat_rows 同一约定）。"""
    return [(mask >> (8 * r)) & 0xFF for r in range(8)]


def bbox_of(mask):
    cs = [(r, c) for r in range(8) for c in range(8) if (mask >> (8 * r + c)) & 1]
    return max(r for r, _ in cs) + 1, max(c for _, c in cs) + 1


def bbox(cs):
    return max(r for r, _ in cs) + 1, max(c for _, c in cs) + 1


def rot_cells(cs, ori):
    """**教科书式**旋转：绕零片自身紧包围盒顺时针转 ori 次再对齐左上角。

    与 RTL 的 `rot_row` + `rot_off_r/rot_off_c`（在固定 3x3 盒里转 + 补锚点偏移）
    逐格等价 —— 这条等价性由 scripts/check_geometry.py 用**独立参考模型**证明过。
    """
    h, w = bbox(cs)
    if ori == 0:
        return frozenset(cs)
    if ori == 1:
        return frozenset((c, h - 1 - r) for r, c in cs)      # 顺时针 90°
    if ori == 2:
        return frozenset((h - 1 - r, w - 1 - c) for r, c in cs)
    return frozenset((w - 1 - c, r) for r, c in cs)


def shaped_cells(mask, ori):
    return rot_cells(cells(mask), ori)


def placed(mask, anchor, ori):
    ar, ac = anchor
    return {(ar + r, ac + c) for (r, c) in shaped_cells(mask, ori)}


def mask_of(cs):
    m = 0
    for (r, c) in cs:
        m |= (1 << (8 * r + c)) & ((1 << 64) - 1)
    return m


# ------------------------------------------------------------------- 引擎模型
def play(plan, shapes, start, lvl2, ori0=None):
    """按引擎语义走一遍计划，返回 (落点, 朝向, 锁定, 被拒动作列表)。

    `shapes` = 本关各块的掩码（一关 3 块 / 二关 4 块）。
    """
    n = len(shapes)
    ori = list(ori0 if ori0 is not None else PIECE_ORI_INIT[:n])
    pos, locked, sel, bad = list(start), [False] * n, 0, []
    for step, cmd in enumerate(plan, 1):

        def clash(cand, k, o):
            mine = placed(shapes[k], cand, o)
            for j in range(n):
                if j != k and (mine & placed(shapes[j], pos[j], ori[j])):
                    return sorted(mine & placed(shapes[j], pos[j], ori[j]))
            return None

        def oob(cand, k, o):
            h, w = bbox(shaped_cells(shapes[k], o))
            return not (cand[0] + h <= 8 and cand[1] + w <= 8)

        if cmd == "select":
            for _i in range(n):
                sel = (sel + 1) % n
                if not locked[sel]:
                    break
        elif cmd == "confirm":
            locked[sel] = True
            for _i in range(n):
                sel = (sel + 1) % n
                if not locked[sel]:
                    break
        elif cmd == "rot":
            if locked[sel]:
                bad.append("第 %d 步 rot 作用在已锁定的槽 %d 上（RTL 静默无效）"
                           % (step, sel))
                continue
            o2 = (ori[sel] + 1) % 4
            if oob(pos[sel], sel, o2):
                bad.append("第 %d 步 rot 被拒（越界）：槽 %d @ %s 朝向 %d->%d"
                           % (step, sel, pos[sel], ori[sel], o2))
            elif clash(pos[sel], sel, o2):
                bad.append("第 %d 步 rot 被拒（重叠 %s）：槽 %d @ %s"
                           % (step, clash(pos[sel], sel, o2), sel, pos[sel]))
            else:
                ori[sel] = o2
        elif cmd in DIRS:
            if locked[sel]:
                bad.append("第 %d 步 %s 作用在已锁定的槽 %d 上（RTL 静默无效）"
                           % (step, cmd, sel))
                continue
            r, c = pos[sel]
            dr, dc = DIRS[cmd]
            nr = r - 1 if (dr < 0 and r > 0) else (r + 1 if (dr > 0 and r < 7) else r)
            nc = c - 1 if (dc < 0 and c > 0) else (c + 1 if (dc > 0 and c < 7) else c)
            cand = (nr, nc)
            if oob(cand, sel, ori[sel]):
                bad.append("第 %d 步 %s 被拒（越界）：槽 %d @ %s"
                           % (step, cmd, sel, pos[sel]))
            elif clash(cand, sel, ori[sel]):
                bad.append("第 %d 步 %s 被拒（重叠 %s）：槽 %d @ %s"
                           % (step, cmd, clash(cand, sel, ori[sel]), sel, pos[sel]))
            else:
                pos[sel] = cand
        else:
            bad.append("未知命令 %s" % cmd)
    return pos, ori, locked, bad


def union_of(shapes, pos, ori):
    u = set()
    for k, m in enumerate(shapes):
        u |= placed(m, pos[k], ori[k])
    return u


# ------------------------------------------------------------------- 铺法枚举
def _tilings(target_mask, shapes, allow_rot):
    """恰好铺法（返回 [(锚点, 朝向)] 序列的列表）。allow_rot=False = 只许平移。"""
    T = frozenset(cells(target_mask))
    opts = []
    for m in shapes:
        per = []
        for o in (range(4) if allow_rot else (0,)):
            sh = shaped_cells(m, o)
            h, w = bbox(sh)
            for r0 in range(0, 9 - h):
                for c0 in range(0, 9 - w):
                    p = {(r0 + r, c0 + c) for r, c in sh}
                    if p <= T:
                        per.append(((r0, c0), o))
        opts.append(per)
    out = []

    def rec(i, used, acc):
        if i == len(shapes):
            if used == T:
                out.append(tuple(acc))
            return
        for (a, o) in opts[i]:
            p = placed(shapes[i], a, o)
            if not (p & used):
                acc.append((a, o))
                rec(i + 1, used | p, acc)
                acc.pop()

    rec(0, set(), [])
    return out


def tilings_no_rotation(target_mask, shapes):
    """所有**只许平移**的恰好铺法（返回槽序锚点元组列表）。"""
    return [tuple(a for (a, _o) in t)
            for t in _tilings(target_mask, shapes, False)]


# ---- 可达性抽样用的**快速**几何（整数位掩码，避免 Python 集合开销）------------
_OMS = [[mask_of(shaped_cells(L2_SHAPES[k], o)) for o in range(4)] for k in range(4)]
_ODIM = [[bbox(shaped_cells(L2_SHAPES[k], o)) for o in range(4)] for k in range(4)]


def _pmask(k, o, anchor):
    """零片 k 以朝向 o 放在 anchor=(r,c) 时覆盖的 64 位掩码（行距恰为 8）。"""
    return _OMS[k][o] << (8 * anchor[0] + anchor[1])


def _others(st, so, k):
    m = 0
    for j in range(4):
        if j != k:
            m |= _pmask(j, so[j], st[j])
    return m


def _ok(k, anchor, o, st, so):
    h, w = _ODIM[k][o]
    r, c = anchor
    if r < 0 or c < 0 or r + h > 8 or c + w > 8:
        return False
    return (_pmask(k, o, anchor) & _others(st, so, k)) == 0


def _piece_home(k, st, so, goal_a, goal_o):
    """BFS（零片 k 单独走，可平移 + 可旋转）：走到 goal_a/goal_o，其余零片不动。"""
    s0 = (st[k], so[k])
    if s0 == (goal_a, goal_o):
        return True
    seen, q = {s0}, [s0]
    while q:
        a, o = q.pop(0)
        nxt = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            na = (a[0] + dr, a[1] + dc)
            if na != a:
                nxt.append((na, o))
        nxt.append((a, (o + 1) % 4))
        for ns in nxt:
            if ns in seen or not _ok(k, ns[0], ns[1], st, so):
                continue
            if ns == (goal_a, goal_o):
                return True
            seen.add(ns)
            q.append(ns)
    return False


def _plan_sequential(start, sori, gpos, gori):
    """把四块**一块一块**搬回家（24 种顺序都试）。比全状态 A* 快几个数量级。"""
    import itertools
    for perm in itertools.permutations(range(4)):
        st, so, ok = list(start), list(sori), True
        for k in perm:
            if not _piece_home(k, st, so, gpos[k], gori[k]):
                ok = False
                break
            st[k], so[k] = gpos[k], gori[k]
        if ok:
            return True
    return None


def reachable(start, sori, goals, cap=60000):
    """从 (start, sori) 能不能走到某个恰好铺法（**允许旋转**）。

    先试顺序搬运（快，覆盖绝大多数样本），再退回全状态 A*（启发式 = 每块零片到
    "任一铺法里它可能待的 (锚点, 朝向)" 的最短距离之和，可采纳且每次只需 O(4)）。
    返回 True/False/None（None = 上限内未判定，**不是**证否）。
    """
    import heapq
    start = tuple(start)
    sori = tuple(sori)
    goalset = {(tuple(gp), tuple(go)) for (gp, go) in goals}
    if (start, sori) in goalset:
        return True
    for (gp, go) in goals:
        if _plan_sequential(start, sori, gp, go):
            return True

    htab = []
    for k in range(4):
        places = {(tuple(gp[k]), go[k]) for (gp, go) in goals}
        tab = {}
        for r in range(8):
            for c in range(8):
                for o in range(4):
                    tab[(r, c, o)] = min(
                        abs(r - a[0]) + abs(c - a[1]) + min((o - oo) % 4, (oo - o) % 4)
                        for (a, oo) in places)
        htab.append(tab)

    def h(st, so):
        return sum(htab[k][(st[k][0], st[k][1], so[k])] for k in range(4))

    openq = [(h(start, sori), 0, start, sori)]
    seen = {(start, sori)}
    n = 0
    while openq:
        n += 1
        if n > cap:
            return None                      # 未判定（不是"证否"，如实记录）
        _, g, st, so = heapq.heappop(openq)
        for k in range(4):
            cands = []
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                na = (st[k][0] + dr, st[k][1] + dc)
                if na != st[k]:
                    cands.append((na, so[k]))
            cands.append((st[k], (so[k] + 1) % 4))
            for (na, no) in cands:
                if not _ok(k, na, no, st, so):
                    continue
                ns = st[:k] + (na,) + st[k + 1:]
                nso = so[:k] + (no,) + so[k + 1:]
                if (ns, nso) in seen:
                    continue
                if (ns, nso) in goalset:
                    return True
                seen.add((ns, nso))
                heapq.heappush(openq, (g + 1 + h(ns, nso), g + 1, ns, nso))
    return False


def sample_scatter(rng, dims):
    """按引擎的散落规则抽一个初始布局：逐块随机候选（最多 16 次，拒绝重叠），
    全失败才用硬编码回退锚点 (0,0)/(0,4)/(4,0)/(4,4)（ERR-018b 的已知残余）。

    ⚠️ 候选范围用**当前朝向**（散落时 = PIECE_ORI_INIT）下的高宽 —— RTL 就是这么算的
    （`oh/ow(h, w, ori)`），所以 `dims` 必须传"初始朝向下的包围盒"。
    """
    pos = []
    used = 0
    for k in range(4):
        h, w = dims[k]
        placed = False
        for _ in range(16):
            ar = rng.randrange(0, 9 - h)
            ac = rng.randrange(0, 9 - w)
            m = _pmask(k, PIECE_ORI_INIT[k], (ar, ac))
            if not (m & used):
                pos.append((ar, ac))
                used |= m
                placed = True
                break
        if not placed:
            ar, ac = [(0, 0), (0, 4), (4, 0), (4, 4)][k]
            pos.append((ar, ac))
            used |= _pmask(k, PIECE_ORI_INIT[k], (ar, ac))
    return tuple(pos)


def pack_pos(pos):
    """锚点元组 -> **完整 32 位 o_pos**：槽 k 占字节 (3-k)（与 RTL 的 o_pos 一致）。

    ⚠️ 一关只有 3 块零片，但槽号仍然是 0..2（槽 3 恒 0），所以**不能**左对齐打包：
    槽 k 永远在 `8*(3-k)` 位上（第一关的期望值因此是 0x22323200）。
    """
    out = 0
    for k in range(len(pos)):
        out |= ((pos[k][0] << 4) | pos[k][1]) << (8 * (3 - k))
    return out


def check(label, plan, shapes, start, lvl2, pattern_mask, expect_pos=None,
          expect_ori=None, require_rot=True):
    pos, ori, locked, bad = play(plan, shapes, start, lvl2)
    u = union_of(shapes, pos, ori)
    tgt = cells(pattern_mask)
    ok = (not bad) and all(locked) and u == tgt
    packed = pack_pos(pos)
    if expect_pos is not None:
        ok = ok and (packed == expect_pos)
    if expect_ori is not None:
        ok = ok and (tuple(ori) == tuple(expect_ori))
    print("\n  %s %s" % ("[OK]  " if ok else "[FAIL]", label))
    print("    落点 = %s；朝向 = %s" % (pos, ori))
    print("    并集 == 图案 = %s（%d / %d 格）" % (u == tgt, len(u), len(tgt)))
    if expect_pos is not None:
        print("    落点打包 = 0x%08X（期望 0x%08X：%s）"
              % (packed, expect_pos, "一致" if packed == expect_pos else "不一致"))
    if expect_ori is not None:
        print("    朝向 = %s（期望 %s：%s）"
              % (tuple(ori), tuple(expect_ori),
                 "一致" if tuple(ori) == tuple(expect_ori) else "不一致"))
    print("    locked = %s；被拒动作 %d 个%s"
          % (locked, len(bad), ("：" + "；".join(bad)) if bad else ""))

    # ---- A4 旋转必需性回归守卫（第 14 工作阶段）----------------------------
    if require_rot:
        n_rot = plan.count("rot")
        has = n_rot > 0
        # 把计划里的【旋转】全部删掉 -> 必须**走不通**（被拒 或 并集 != 图案）
        nr_plan = [c for c in plan if c != "rot"]
        p2, o2, l2, bad2 = play(nr_plan, shapes, start, lvl2)
        u2 = union_of(shapes, p2, o2)
        fails = bool(bad2) or (u2 != tgt) or (not all(l2))
        ok = ok and has and fails
        print("    A4 旋转必需性：计划里【旋转】%d 次；删掉全部旋转后 被拒 %d 个、"
              "并集==图案 = %s、全锁定 = %s ⇒ 仍然解得出来 = %s（必须 False）"
              % (n_rot, len(bad2), u2 == tgt, all(l2), not fails))
        if bad2:
            print("      （删掉旋转后第一个被拒：%s）" % bad2[0])
    return ok


def main():
    print("-- 走法计划离线复核（引擎规则：夹紧 + 越界 + **旋转后的**精确逐格重叠；"
          "按键语义 select/confirm/move/**rot**）")
    ok = True

    print("\n-- 零片掩码与 puzzle_pkg.vhd 一致")
    print("   PIECE_ORI_INIT（块 0..3 的初始朝向）= %s（编码："
          "0=原样 1=顺 90° 2=180° 3=顺 270°）" % (PIECE_ORI_INIT,))
    print("   一关 3 块格数：%s" % [len(cells(m)) for m in L1_SHAPES])
    print("   二关 4 块格数：%s" % [len(cells(m)) for m in L2_SHAPES])

    # ---- 参考事实：**只许平移**的可铺性（第 14 工作阶段之后只是历史事实）----
    print("\n-- 参考：图案库**只许平移**的恰好铺法（历史事实；第 14 工作阶段起"
          "零片不再从朝向 0 开始，这些铺法已经**用不上**了 —— 见每份计划下面的"
          "『A4 旋转必需性』守卫）")
    for k in range(4):
        ts = tilings_no_rotation(L2_PAT[k], L2_SHAPES)
        good = len(ts) > 0
        ok &= good
        print("  %s 图案 %d（L2_PAT%d）：只许平移的恰好铺法 %d 种%s"
              % ("[OK]  " if good else "[FAIL]", k, k, len(ts),
                 ("，见证 = %s" % (ts[0],)) if ts else ""))
    ts0 = tilings_no_rotation(L2_PAT[0], L2_SHAPES)
    good = len(ts0) == 1 and ts0[0] == tuple(L2_WITNESS)
    ok &= good
    print("  %s 图案 0（田）的平移解唯一，且 == pkg.L2_TGT0..3 = %s"
          % ("[OK]  " if good else "[FAIL]", L2_WITNESS))

    # ---- A4 守卫：**允许旋转**时四幅图案仍然全都有恰好铺法（不是死局）--------
    print("\n-- A4 守卫：允许旋转时，第一关与四幅图案**都仍然可铺**（旋转是必需的一步，"
          "但不是死局）")
    n_l1 = len(_tilings(L1_TARGET_MASK, L1_SHAPES, True))
    ok &= n_l1 > 0
    print("  %s 第一关 4x3 矩形：含旋转的恰好铺法 %d 种"
          % ("[OK]  " if n_l1 > 0 else "[FAIL]", n_l1))
    for k in range(4):
        n = len(_tilings(L2_PAT[k], L2_SHAPES, True))
        ok &= n > 0
        print("  %s 图案 %d：含旋转的恰好铺法 %d 种"
              % ("[OK]  " if n > 0 else "[FAIL]", k, n))

    # ---- ERR-037 守卫：散落的候选锚点必须覆盖**完整合法域** 0..(8-零片尺寸) ----
    # 原实现写 `ch := 8 - hh`，候选只到 7-hh ⇒ **最后一行/最后一列永远抽不到**，
    # 而且 0..7 mod 7 让锚点 0 的概率翻倍。这里直接读 RTL 的公式并与合法域对账。
    print("\n-- ERR-037 守卫：散落候选范围（合法域 = 0..8-尺寸；尺寸取**初始朝向**）")
    ctrl = (ROOT / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")
    formula_ok = ("ch := 9 - hh;" in ctrl) and ("cw := 9 - ww;" in ctrl)
    ok &= formula_ok
    print("  %s RTL 里的除数公式 = `ch := 9 - hh` / `cw := 9 - ww`（覆盖 0..8-尺寸）"
          % ("[OK]  " if formula_ok else "[FAIL]"))
    bad_pc = []
    for k, m in enumerate(L2_SHAPES):
        h, w = bbox(shaped_cells(m, PIECE_ORI_INIT[k]))
        for dim, n in ((h, "行"), (w, "列")):
            ch = 9 - dim
            cand = sorted({x if x < ch else x - ch for x in range(8)})
            if cand != list(range(0, 9 - dim)):
                bad_pc.append("零片 %d 的%s：候选 %s ≠ 合法域 %s"
                              % (k, n, cand, list(range(0, 9 - dim))))
    ok &= not bad_pc
    print("  %s 四块零片 × (行/列)：候选集合 == 合法域（含最后一行/列）%s"
          % ("[OK]  " if not bad_pc else "[FAIL]", "" if not bad_pc else "：" + "；".join(bad_pc)))

    print("\n-- 四份走法计划（第二关固定 PAT3 + 第三关两种模式）"
          "：每份都必须**用旋转**才解得出来")
    ok &= check("一关（3 块异形：1x3 横条 + 6 格阶梯 + L 三格）→ 拼回图 4-1 的 4x3 矩形",
                PLAN_L1, L1_SHAPES, L1_START, False,
                L1_TARGET_MASK, expect_pos=L1_EXPECT_POS, expect_ori=L1_EXPECT_ORI)
    ok &= check("二关 · **固定** 图案 3（阶梯，D2；含旋转时有 24 种等价铺法，走最短的那一种）"
                "→ 画面逐格 == 图案（判据只看画面，不看锚点常量）",
                PLAN_L2_PAT3, L2_SHAPES, L2_START, True, L2_PAT[3],
                expect_pos=L2_EXPECT_POS, expect_ori=L2_EXPECT_ORI)
    ok &= check("三关 · 图案 0（田，模式 A；第三关图案由 rng 决定，tb 钉在 0）→ 铺满",
                PLAN_L3_PAT0, L2_SHAPES, L2_START, True, L2_PAT[0],
                expect_pos=L3_EXPECT_POS[0], expect_ori=L3_EXPECT_ORI[0])
    ok &= check("三关 · 图案 2（S/Z 锯齿，模式 B）→ 铺满（端到端出绿对勾）",
                PLAN_L3_PAT2, L2_SHAPES, L2_START, True, L2_PAT[2],
                expect_pos=L3_EXPECT_POS[2], expect_ori=L3_EXPECT_ORI[2])

    # ---- 守卫：RTL 里的"第二关固定图案"必须就是第二关计划解的那一幅 --------------
    print("\n-- D2 守卫：RTL 的 L2_FIXED_PAT ↔ 第二关计划 ↔ 图案库")
    mf = re.search(r"constant\s+L2_FIXED_PAT\s*:\s*std_logic_vector\(1 downto 0\)\s*:=\s*\"([01]{2})\"",
                   SRC, re.S)
    fixed = int(mf.group(1), 2) if mf else None
    ok &= (fixed == 3)
    print("  %s RTL 的 L2_FIXED_PAT = %s（期望 3 == PAT3 阶梯）；第二关计划解的就是 PAT3"
          % ("[OK]  " if fixed == 3 else "[FAIL]", fixed))

    # ---- 守卫：关卡限时常量（题目值 + 自拟的第三关）必须两边一致 ------------------
    #    ERR-031/034/038 这一类"时间/轮数算错"的缺陷全都出在常量漂移上，所以这里
    #    直接把 pkg 与 tb 的关卡限时对账（第三关是自拟值，更容易写着写着就漂）。
    print("\n-- 守卫：关卡限时常量（pkg ↔ tb_game_fsm）")
    pkg_t = {}
    for n in ("T_PREVIEW", "T_LEVEL1", "T_LEVEL2", "T_LEVEL3"):
        m = re.search(r"constant\s+%s\s*:\s*integer\s*:=\s*(\d+)" % n, SRC)
        pkg_t[n] = int(m.group(1)) if m else None
    want_t = {"T_PREVIEW": 5, "T_LEVEL1": 30, "T_LEVEL2": 40, "T_LEVEL3": 40}
    ok &= (pkg_t == want_t)
    print("  %s pkg: T_PREVIEW/LEVEL1/2/3 = %s（B4 预览 5 s、B5 30 s、B10 40 s；"
          "第三关 40 s 为自拟）" % ("[OK]  " if pkg_t == want_t else "[FAIL]", pkg_t))

    # ---- 守卫：本文件里的计划必须与 sim/tb_puzzle_top.py 里的**逐字一致** ----
    print("\n-- 计划一致性守卫（本文件 vs sim/tb_puzzle_top.py）")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "tb_top_for_guard", str(ROOT / "sim" / "tb_puzzle_top.py"))
    tb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tb)
    spec_f = importlib.util.spec_from_file_location(
        "tb_fsm_for_guard", str(ROOT / "sim" / "tb_game_fsm.py"))
    tbf = importlib.util.module_from_spec(spec_f)
    spec_f.loader.exec_module(tbf)
    same = (list(tb.PLAN_L1) == PLAN_L1
            and list(tb.PLAN_L2_PAT3) == PLAN_L2_PAT3
            and list(tb.PLAN_L3_PAT0) == PLAN_L3_PAT0
            and list(tb.PLAN_L3_PAT2) == PLAN_L3_PAT2
            and tb.PLAN_L2 == PLAN_L2_PAT3
            and tb.L2_EXPECT_POS == L2_EXPECT_POS
            and tb.L3_EXPECT_POS == L3_EXPECT_POS[tb.FORCE_PAT]
            and tb.L1_EXPECT_POS == L1_EXPECT_POS
            and tb.pat_rows(0) == rows_of(L2_PAT[0])
            and tb.pat_rows(2) == rows_of(L2_PAT[2])
            and tb.pat_rows(3) == rows_of(L2_PAT[3])
            and (tbf.T_PREVIEW, tbf.T_L1, tbf.T_L2, tbf.T_L3)
                == (pkg_t["T_PREVIEW"], pkg_t["T_LEVEL1"],
                    pkg_t["T_LEVEL2"], pkg_t["T_LEVEL3"]))
    ok &= same
    print("  %s 走法计划 / 落点期望 / pat_rows(0,2,3) / tb_game_fsm 的关卡限时 全部一致：%s"
          % ("[OK]  " if same else "[FAIL]",
             "PLAN_L1 + PLAN_L2_PAT3 + PLAN_L3_PAT0/PAT2 + 三组落点期望 + 图案掩码 + 关卡限时"
             if same else "有不一致项，请同步两份文件"))

    # ---- A4 守卫（**第 14 工作阶段起与旧版相反**）：四份解谜计划**都必须**含旋转 ----
    # 零片从 PIECE_ORI_INIT（1/1/2/2）开始散落，而"保持初始朝向只许平移"时第一关的
    # 矩形与四幅图案**都恰好覆盖不了**（scripts/check_geometry.py 独立证明）。所以
    # "计划里一次都不转"在现在这个 RTL 上**根本走不通** —— 计划里必须出现【旋转】。
    has_rot = all("rot" in getattr(tb, nm)
                  for nm in ("PLAN_L1", "PLAN_L2_PAT3", "PLAN_L3_PAT0", "PLAN_L3_PAT2"))
    ok &= has_rot
    print("  %s A4 守卫：四份解谜计划**都含【旋转】命令**（旧版这条守卫是反过来的："
          "那时零片从朝向 0 开始、计划只许平移）"
          % ("[OK]  " if has_rot else "[FAIL]"))

    # ---- 随机散落可达性抽样（"会不会死局"的实证，不是证明）----
    print("\n-- 随机散落可达性抽样（按引擎散落规则抽 60 个布局/幅，逐个找一条合法走法；"
          "零片带**初始朝向**，走法可以平移也可以旋转）")
    import random
    dims = [bbox(shaped_cells(L2_SHAPES[k], PIECE_ORI_INIT[k])) for k in range(4)]
    rng = random.Random(20261009)
    for k in range(4):
        tl = _tilings(L2_PAT[k], L2_SHAPES, True)
        goals = [(tuple(a for (a, _o) in t), tuple(o for (_a, o) in t)) for t in tl]
        sol, stuck, unc = 0, 0, 0
        for _ in range(60):
            st = sample_scatter(rng, dims)
            r = reachable(st, PIECE_ORI_INIT, goals)
            if r is None:                       # 探索上限内没找到 → 加大上限再试一次
                r = reachable(st, PIECE_ORI_INIT, goals, cap=200000)
            if r is True:
                sol += 1
            elif r is False:
                stuck += 1                      # 状态空间**穷尽**仍未到达 → 真死局
            else:
                unc += 1
        good = (stuck == 0)
        ok &= good
        print("  %s 图案 %d：可解 %d/60，**证明死局 %d**，上限内未判定 %d%s"
              % ("[OK]  " if good else "[FAIL]", k, sol, stuck, unc,
                 "" if unc == 0 else "（未判定 ≠ 死局：只是搜索上限内没找到路，"
                                     "记为本验证器的已知残余）"))

    print("\n%s" % ("ALL PLAN CHECKS PASSED" if ok else "*** SOME CHECKS FAILED ***"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
