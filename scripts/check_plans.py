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
  · `i_go`         → `locked=0`、`sel=0`，随后散落；`rnd_val` 钉 0 时落到**确定性回退锚点**
                     （一关 (0,0)/(0,4)/(4,0)；二关再补 (4,4)）
  · `i_select`     → `sel` 前进（一关 0..2 循环、二关 0..3 循环）
  · `i_confirm`    → `locked(sel)=1`，随后 `sel` 前进（**确认只锁定，不判对错**）
  · `i_move`       → 对 `sel` 指向的零片：up=行-1 / down=行+1 / left=列-1 / right=列+1；
                     越界（`cr+hh<=8 and cc+ww<=8`）或与其它零片**精确逐格重叠** → **整个移动被拒**
  · `puzzle_pkg` 的位序：bit = 8*行 + 列，bit0 = 左上角

  ⚠️ 第 11 工作阶段起第二关零片是**四种异形**（3/2/5/6 格），不只是大小变了：
     `play()` 里每一块用的是**各自**的掩码，重叠判定必须逐格算（包围盒判定会误判）。

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


SRC = PKG.read_text(encoding="utf-8")
L1_SHAPES = [const_bits("L1_P%d" % i, SRC) for i in range(3)]
L2_SHAPES = [const_bits("L2_P%d" % i, SRC) for i in range(4)]
L2_PAT = {k: const_bits("L2_PAT%d" % k, SRC) for k in range(4)}

L1_TARGET = [(2, 2), (3, 2), (4, 3)]        # 图 4-1 的解（一类等价铺法，见 check_geometry）
L2_WITNESS = [const_anchor("L2_TGT%d" % i, SRC) for i in range(4)]

L1_START = [(0, 0), (0, 4), (4, 0)]
L2_START = [(0, 0), (0, 4), (4, 0), (4, 4)]     # rnd_val 恒 0 -> 确定性回退锚点

PLAN_L1 = (["select"] + ["down"] * 3 + ["left"] * 2 +
           ["select"] + ["down"] * 2 + ["right"] * 3 + ["up"] * 2 +
           ["select"] + ["down"] * 2 + ["right"] * 2 + ["confirm"] * 3)

# 第二关走法（**固定 PAT3 = 阶梯**，D2：2026-10-09 起第二关图案不再随机）
#   解算器/最小化目标 = "按键次数"（每次换零片要按 (k'-k) mod 4 次【选择】），
#   见 .tmp/opt/solve_l2plan.py；PAT3 有 **2 种**等价铺法，计划走第 0 种
#   （槽 0..3 → (2,2) (2,1) (3,3) (3,2)）→ 33 条命令。
PLAN_L2_PAT3 = (["down"] + ["select"] + ["left"] + ["select"] + ["up"] + ["right"] +
                ["up"] + ["select"] + ["down"] + ["left"] * 2 + ["up"] +
                ["select"] * 3 + ["right"] * 2 + ["down"] + ["select"] + ["up"] +
                ["select"] + ["down"] + ["right"] * 2 + ["select"] + ["left"] * 2 +
                ["down"] * 2 + ["confirm"] * 4)

# 第三关走法（A2"增加游戏关数 + 多种拼图图案随机选择"）：图案由 rng 决定，
#   整机 tb 用 DLD_L3PAT 把随机值钉住，于是这里给出两种模式各一份计划：
#     模式 A（图案 0 田）：唯一铺法（槽 0..3 → (5,3) (4,2) (2,3) (2,2)），42 条命令
#     模式 B（图案 2 S/Z）：唯一铺法（槽 0..3 → (5,1) (4,4) (2,1) (2,4)），36 条命令
#   两份计划与 sim/tb_puzzle_top.py 里的必须**逐字一致** —— 本脚本就是它们的守卫。
PLAN_L3_PAT0 = (["select"] + ["left"] + ["down"] * 4 + ["select"] + ["up"] * 3 +
                ["right"] * 3 + ["down"] + ["select"] * 2 + ["down"] * 6 + ["select"] +
                ["left"] * 2 + ["select"] * 2 + ["left"] * 2 + ["up"] * 2 + ["select"] +
                ["right"] * 2 + ["up"] + ["right"] + ["select"] + ["right"] +
                ["confirm"] * 4)
PLAN_L3_PAT2 = (["right"] + ["down"] * 3 + ["right"] * 2 + ["select"] + ["down"] +
                ["select"] + ["up"] * 4 + ["right"] + ["select"] + ["right"] +
                ["select"] + ["left"] * 2 + ["down"] * 2 + ["select"] + ["down"] * 3 +
                ["select"] + ["down"] * 2 + ["select"] + ["up"] * 2 + ["left"] +
                ["confirm"] * 4)

# tb 里断言 ⑪/⑪b 用的落点期望（槽 0..3 各 (行,列) 打包成 1 字节，pos(31:24) = 槽 0）
L2_EXPECT_POS = 0x22213332                       # PAT3 第 0 种铺法
L3_EXPECT_POS = {0: 0x53422322, 2: 0x51442124}   # 第三关：模式 A / 模式 B


def cells(mask, r0, c0):
    return {(r0 + r, c0 + c) for r in range(8) for c in range(8)
            if (mask >> (8 * r + c)) & 1}


def rows_of(mask):
    """图案掩码 -> 8 行 8 位列掩码（与 tb_puzzle_top.pat_rows 同一约定）。"""
    return [(mask >> (8 * r)) & 0xFF for r in range(8)]


def play(plan, shapes, start, lvl2):
    """按引擎语义走一遍计划，返回 (落点, 锁定, 被拒动作列表)。"""
    n = len(shapes)
    pos, locked, sel, bad = list(start), [False] * n, 0, []
    top = 3 if not lvl2 else 4
    for step, cmd in enumerate(plan, 1):
        if cmd == "select":
            sel = (sel + 1) % top
        elif cmd == "confirm":
            locked[sel] = True
            sel = (sel + 1) % top
        elif cmd in ("up", "down", "left", "right"):
            r, c = pos[sel]
            nr, nc = r, c
            if cmd == "up":
                nr -= 1
            elif cmd == "down":
                nr += 1
            elif cmd == "left":
                nc -= 1
            else:
                nc += 1
            mine = cells(shapes[sel], nr, nc)
            ok = (not locked[sel]) and len(mine) > 0 \
                and min(r_ for r_, _ in mine) >= 0 \
                and min(c_ for _, c_ in mine) >= 0 \
                and max(r_ for r_, _ in mine) <= 7 and max(c_ for _, c_ in mine) <= 7
            if ok:
                for k in range(n):
                    if k != sel and (mine & cells(shapes[k], *pos[k])):
                        ok = False
            if ok:
                pos[sel] = (nr, nc)
            else:
                bad.append("第 %d 步 %s 被拒（P%d @ %s）" % (step, cmd, sel, (r, c)))
        else:
            bad.append("未知命令 %s" % cmd)
    return pos, locked, bad


def union_of(shapes, pos):
    u = set()
    for k, m in enumerate(shapes):
        u |= cells(m, *pos[k])
    return u


def tilings_no_rotation(target_mask, shapes):
    """所有**只许平移**的恰好铺法（返回槽序锚点元组列表）。"""
    T = {c for c in cells(target_mask, 0, 0)}
    shapes_c = []
    for m in shapes:
        rel = [(r, c) for r in range(8) for c in range(8) if (m >> (8 * r + c)) & 1]
        mr, mc = min(r for r, _ in rel), min(c for _, c in rel)
        shapes_c.append(sorted((r - mr, c - mc) for r, c in rel))
    out = []

    def rec(i, used, acc):
        if i == len(shapes_c):
            if used == T:
                out.append(tuple(acc))
            return
        h = max(r for r, _ in shapes_c[i]) + 1
        w = max(c for _, c in shapes_c[i]) + 1
        for r0 in range(0, 9 - h):
            for c0 in range(0, 9 - w):
                p = {(r + r0, c + c0) for r, c in shapes_c[i]}
                if p <= T and not (p & used):
                    acc.append((r0, c0))
                    rec(i + 1, used | p, acc)
                    acc.pop()

    rec(0, set(), [])
    return out


def bbox_of(mask):
    cs = [(r, c) for r in range(8) for c in range(8) if (mask >> (8 * r + c)) & 1]
    return max(r for r, _ in cs) + 1, max(c for _, c in cs) + 1


# ---- 可达性抽样用的**快速**几何（整数位掩码，避免 Python 集合开销）------------
_MSK = [m & ((1 << 64) - 1) for m in L2_SHAPES]


def _pmask(k, anchor):
    """零片 k 放在 anchor=(r,c) 时覆盖的 64 位掩码（shape << (8r+c)，行距恰为 8）。"""
    return _MSK[k] << (8 * anchor[0] + anchor[1])


def _others(st, k):
    m = 0
    for j in range(4):
        if j != k:
            m |= _pmask(j, st[j])
    return m


def _ok(k, anchor, st, dims):
    h, w = dims[k]
    r, c = anchor
    if r < 0 or c < 0 or r + h > 8 or c + w > 8:
        return False
    return (_pmask(k, anchor) & _others(st, k)) == 0


def _piece_home(k, st, goal_a, dims):
    """BFS（零片 k 单独走）：把零片 k 从 st[k] 走到 goal_a，其余零片不动。"""
    if st[k] == goal_a:
        return True
    seen, q = {st[k]}, [st[k]]
    while q:
        cur = q.pop(0)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            na = (cur[0] + dr, cur[1] + dc)
            if na in seen or not _ok(k, na, st, dims):
                continue
            if na == goal_a:
                return True
            seen.add(na)
            q.append(na)
    return False


def _plan_sequential(start, goal, dims):
    """把四块**一块一块**搬回家（24 种顺序都试）。比全状态 A* 快几个数量级。"""
    import itertools
    for perm in itertools.permutations(range(4)):
        st = list(start)
        ok = True
        for k in perm:
            if not _piece_home(k, st, goal[k], dims):
                ok = False
                break
            st[k] = goal[k]
        if ok:
            return True
    return None


def reachable(start, goals, dims, cap=200000):
    """从 start 能不能走到某个恰好铺法。先试顺序搬运（快），再退回全状态 A*。"""
    goals = [tuple(g) for g in goals]
    start = tuple(start)
    if start in goals:
        return True
    if any(_plan_sequential(start, g, dims) for g in goals):
        return True

    import heapq

    def h(st):
        return min(sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(st, g))
                   for g in goals)

    openq = [(h(start), 0, start)]
    seen = {start}
    n = 0
    while openq:
        n += 1
        if n > cap:
            return None                      # 未判定（不是"证否"，如实记录）
        _, g, st = heapq.heappop(openq)
        for k in range(4):
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                na = (st[k][0] + dr, st[k][1] + dc)
                if not _ok(k, na, st, dims):
                    continue
                ns = st[:k] + (na,) + st[k + 1:]
                if ns in seen:
                    continue
                if ns in goals:
                    return True
                seen.add(ns)
                heapq.heappush(openq, (g + 1 + h(ns), g + 1, ns))
    return False


def sample_scatter(rng, dims):
    """按引擎的散落规则抽一个初始布局：逐块随机候选（最多 16 次，拒绝重叠），
    全失败才用硬编码回退锚点 (0,0)/(0,4)/(4,0)/(4,4)（ERR-018b 的已知残余）。"""
    pos = []
    used = 0
    for k in range(4):
        h, w = dims[k]
        placed = False
        for _ in range(16):
            ar = rng.randrange(0, 9 - h)
            ac = rng.randrange(0, 9 - w)
            m = _pmask(k, (ar, ac))
            if not (m & used):
                pos.append((ar, ac))
                used |= m
                placed = True
                break
        if not placed:
            ar, ac = [(0, 0), (0, 4), (4, 0), (4, 4)][k]
            pos.append((ar, ac))
            used |= _pmask(k, (ar, ac))
    return tuple(pos)


def check(label, plan, shapes, start, lvl2, pattern_mask, expect_pos=None):
    pos, locked, bad = play(plan, shapes, start, lvl2)
    u = union_of(shapes, pos)
    tgt = cells(pattern_mask, 0, 0)
    ok = (not bad) and all(locked) and u == tgt
    packed = None
    if expect_pos is not None:
        packed = 0
        for k in range(len(shapes)):
            packed |= ((pos[k][0] << 4) | pos[k][1]) << (8 * (len(shapes) - 1 - k))
        ok = ok and (packed == expect_pos)
    print("\n  %s %s" % ("[OK]  " if ok else "[FAIL]", label))
    print("    落点 = %s" % (pos,))
    print("    并集 == 图案 = %s（%d / %d 格）" % (u == tgt, len(u), len(tgt)))
    if packed is not None:
        print("    落点打包 = 0x%08X（期望 0x%08X：%s）"
              % (packed, expect_pos, "一致" if packed == expect_pos else "不一致"))
    print("    locked = %s；被拒动作 %d 个%s"
          % (locked, len(bad), ("：" + "；".join(bad)) if bad else ""))
    return ok


def main():
    print("-- 走法计划离线复核（引擎规则：越界 + 精确逐格重叠；按键语义 select/confirm/move）")
    ok = True

    # ① 先核对 tb 用的零片掩码与 pkg 一致（计划是照 pkg 的形状算出来的）
    print("\n-- 零片掩码与 puzzle_pkg.vhd 一致")
    print("   一关 3 块：%s" % [len([1 for r in range(8) for c in range(8)
                                    if (m >> (8 * r + c)) & 1]) for m in L1_SHAPES])
    print("   二关 4 块格数：%s" % [len([1 for r in range(8) for c in range(8)
                                        if (m >> (8 * r + c)) & 1]) for m in L2_SHAPES])

    print("\n-- 图案库可铺性（只许平移；与 scripts/check_geometry.py 互为独立复核）")
    for k in range(4):
        ts = tilings_no_rotation(L2_PAT[k], L2_SHAPES)
        good = len(ts) > 0
        ok &= good
        print("  %s 图案 %d（L2_PAT%d）：恰好铺法 %d 种%s"
              % ("[OK]  " if good else "[FAIL]", k, k, len(ts),
                 ("，见证 = %s" % (ts[0],)) if ts else ""))
    ts0 = tilings_no_rotation(L2_PAT[0], L2_SHAPES)
    good = len(ts0) == 1 and ts0[0] == tuple(L2_WITNESS)
    ok &= good
    print("  %s 图案 0（田）的解唯一，且 == pkg.L2_TGT0..3 = %s"
          % ("[OK]  " if good else "[FAIL]", L2_WITNESS))

    # ---- ERR-037 守卫：散落的候选锚点必须覆盖**完整合法域** 0..(8-零片尺寸) ----
    # 原实现写 `ch := 8 - hh`，候选只到 7-hh ⇒ **最后一行/最后一列永远抽不到**，
    # 而且 0..7 mod 7 让锚点 0 的概率翻倍。这里直接读 RTL 的公式并与合法域对账。
    print("\n-- ERR-037 守卫：散落候选范围（合法域 = 0..8-尺寸）")
    ctrl = (ROOT / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")
    formula_ok = ("ch := 9 - hh;" in ctrl) and ("cw := 9 - ww;" in ctrl)
    ok &= formula_ok
    print("  %s RTL 里的除数公式 = `ch := 9 - hh` / `cw := 9 - ww`（覆盖 0..8-尺寸）"
          % ("[OK]  " if formula_ok else "[FAIL]"))
    bad_pc = []
    for k, m in enumerate(L2_SHAPES):
        h, w = bbox_of(m)
        for dim, n in ((h, "行"), (w, "列")):
            ch = 9 - dim
            cand = sorted({x if x < ch else x - ch for x in range(8)})
            if cand != list(range(0, 9 - dim)):
                bad_pc.append("零片 %d 的%s：候选 %s ≠ 合法域 %s"
                              % (k, n, cand, list(range(0, 9 - dim))))
    ok &= not bad_pc
    print("  %s 四块零片 × (行/列)：候选集合 == 合法域（含最后一行/列）%s"
          % ("[OK]  " if not bad_pc else "[FAIL]", "" if not bad_pc else "：" + "；".join(bad_pc)))

    print("\n-- 三份走法计划（第二关固定 PAT3 + 第三关两种模式）")
    ok &= check("一关（3 块异形：1x3 横条 + 6 格阶梯 + L 三格）→ 拼回图 4-1",
                PLAN_L1, L1_SHAPES, L1_START, False,
                const_bits("L1_TARGET_MASK", SRC))
    ok &= check("二关 · **固定** 图案 3（阶梯，D2；有 2 种铺法，走第 0 种）"
                "→ 画面逐格 == 图案（判据只看画面，不看锚点常量）",
                PLAN_L2_PAT3, L2_SHAPES, L2_START, True, L2_PAT[3],
                expect_pos=L2_EXPECT_POS)
    ok &= check("三关 · 图案 0（田，模式 A；第三关图案由 rng 决定，tb 钉在 0）"
                "→ 拼成唯一铺法",
                PLAN_L3_PAT0, L2_SHAPES, L2_START, True, L2_PAT[0],
                expect_pos=L3_EXPECT_POS[0])
    ok &= check("三关 · 图案 2（S/Z 锯齿，模式 B）→ 拼成唯一铺法（端到端出绿对勾）",
                PLAN_L3_PAT2, L2_SHAPES, L2_START, True, L2_PAT[2],
                expect_pos=L3_EXPECT_POS[2])

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
            and tb.pat_rows(0) == rows_of(L2_PAT[0])
            and tb.pat_rows(2) == rows_of(L2_PAT[2])
            and tb.pat_rows(3) == rows_of(L2_PAT[3])
            and (tbf.T_PREVIEW, tbf.T_L1, tbf.T_L2, tbf.T_L3)
                == (pkg_t["T_PREVIEW"], pkg_t["T_LEVEL1"],
                    pkg_t["T_LEVEL2"], pkg_t["T_LEVEL3"]))
    ok &= same
    print("  %s 走法计划 / 落点期望 / pat_rows(0,2,3) / tb_game_fsm 的关卡限时 全部一致：%s"
          % ("[OK]  " if same else "[FAIL]",
             "PLAN_L1 + PLAN_L2_PAT3 + PLAN_L3_PAT0/PAT2 + 两组落点期望 + 图案掩码 + 关卡限时"
             if same else "有不一致项，请同步两份文件"))

    # ---- 随机散落可达性抽样（"会不会死局"的实证，不是证明）----
    print("\n-- 随机散落可达性抽样（按引擎散落规则抽 60 个布局/幅，逐个找一条合法走法）")
    import random
    dims = [bbox_of(m) for m in L2_SHAPES]
    rng = random.Random(20261009)
    for k in range(4):
        tl = tilings_no_rotation(L2_PAT[k], L2_SHAPES)
        sol, stuck, unc = 0, 0, 0
        for _ in range(60):
            st = sample_scatter(rng, dims)
            r = reachable(st, tl, dims)
            if r is None:                       # 探索上限内没找到 → 加大上限再试一次
                r = reachable(st, tl, dims, cap=900000)
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
                 "" if unc == 0 else "（未判定 ≠ 死局：只是搜素上限内没找到路，"
                                     "记为本验证器的已知残余）"))

    print("\n%s" % ("ALL PLAN CHECKS PASSED" if ok else "*** SOME CHECKS FAILED ***"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
