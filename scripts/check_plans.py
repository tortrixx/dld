# -*- coding: utf-8 -*-
"""check_plans.py —— 离线复核 `sim/tb_puzzle_top.py` 的三份走法计划（不跑仿真）

【为什么需要它】
  整机仿真一轮要 **13 分钟**（96.8 ms 压缩时间、7.9 亿个跳变）。而"按键计划能不能把零片
  走到目标锚点、中途会不会被引擎**拒绝**（越界 / 与别的零片重叠）"完全可以**离线算**：
  本文件复刻 `rtl/puzzle_ctrl.vhd` 的按键语义，把三份计划逐步走一遍。

  ⭐ 第 10 工作阶段（A2/S1 图案库）就是这么做的：先用本脚本复核"图案 3（S/Z）"的走法计划
  ——**零次被拒、落点与期望一致**——再去跑 13 分钟的整机仿真，**一次通过**。

【复刻的引擎规则（与 RTL 一一对应）】
  · `i_go`         → `locked=0`、`sel=0`，随后散落；`rnd_val` 钉 0 时落到**确定性回退锚点**
                     （一关 (0,0)/(0,4)/(4,0)；二关再补 (4,4)）
  · `i_select`     → `sel` 前进（一关 0..2 循环、二关 0..3 循环）
  · `i_confirm`    → `locked(sel)=1`，随后 `sel` 前进（**确认只锁定，不判对错**）
  · `i_move`       → 对 `sel` 指向的零片：up=行-1 / down=行+1 / left=列-1 / right=列+1；
                     越界（`cr+hh<=8 and cc+ww<=8`）或与其它零片**精确逐格重叠** → **整个移动被拒**
  · `puzzle_pkg` 的位序：bit = 8*行 + 列，bit0 = 左上角

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


SRC = PKG.read_text(encoding="utf-8")
L1_P0 = const_bits("L1_P0", SRC)
L1_P1 = const_bits("L1_P1", SRC)
L1_P2 = const_bits("L1_P2", SRC)
L2_P16 = const_bits("L2_P0", SRC)          # 四块 2x2 完全相同
L2_PAT = {k: const_bits("L2_PAT%d" % k, SRC) for k in range(4)}

# 第二关图案库的块坐标（与 puzzle_pkg.vhd 的注释/构造一致）
L2_BLOCKS = {
    0: [(1, 1), (1, 2), (2, 1), (2, 2)],   # 田
    1: [(1, 1), (1, 2), (1, 3), (2, 2)],   # T
    2: [(1, 1), (2, 1), (3, 1), (3, 2)],   # L
    3: [(0, 0), (0, 1), (1, 1), (1, 2)],   # S/Z
}

# tb 里的目标锚点（一关：拼回图 4-1；二关图案 0：ERR-021 的"置换"摆法）
L1_TARGET = [(2, 2), (3, 2), (4, 3)]
L2_PAT0_TARGET = [(4, 2), (2, 4), (2, 2), (4, 4)]
# 二关图案 3：P0..P3 → 块锚点（0,0）(0,2) (2,2) (2,4)
L2_PAT3_TARGET = [(0, 0), (0, 2), (2, 2), (2, 4)]

L1_START = [(0, 0), (0, 4), (4, 0)]
L2_START = [(0, 0), (0, 4), (4, 0), (4, 4)]

PLAN_L1 = (["select"] + ["down"] * 3 + ["left"] * 2 +
           ["select"] + ["down"] * 2 + ["right"] * 3 + ["up"] * 2 +
           ["select"] + ["down"] * 2 + ["right"] * 2 + ["confirm"] * 3)
PLAN_L2_PAT0 = (["right"] * 2 + ["down"] * 4 + ["select"] + ["down"] * 2 +
                ["select"] + ["up"] * 2 + ["right"] * 2 + ["select"] + ["confirm"] * 4)
PLAN_L2_PAT3 = (["confirm"] + ["left"] * 2 + ["confirm"] + ["up"] * 2 +
                ["right"] * 2 + ["confirm"] + ["up"] * 2 + ["confirm"])


def cells(mask, r0, c0):
    return {(r0 + r, c0 + c) for r in range(8) for c in range(8)
            if (mask >> (8 * r + c)) & 1}


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
            ok = (not locked[sel]) and min(r_ for r_, _ in mine) >= 0 \
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


def check(label, plan, shapes, start, lvl2, want, want_union=None):
    pos, locked, bad = play(plan, shapes, start, lvl2)
    ok = (not bad) and pos == want and all(locked)
    if want_union is not None:
        u = set()
        for k, m in enumerate(shapes):
            u |= cells(m, *pos[k])
        ok = ok and (u == want_union)
        print("    并集 == 目标图案 = %s（%d / %d 格）"
              % (u == want_union, len(u), len(want_union)))
    print("  %s %s" % ("[OK]  " if ok else "[FAIL]", label))
    print("    落点 = %s%s" % (pos, "" if pos == want else "   期望 %s" % want))
    print("    locked = %s；被拒动作 %d 个%s"
          % (locked, len(bad), ("：" + "；".join(bad)) if bad else ""))
    return ok


def pat_union(blocks):
    u = set()
    for (b, c) in blocks:
        for dr in (0, 1):
            for dc in (0, 1):
                u.add((2 * b + dr, 2 * c + dc))
    return u


def main():
    print("-- 走法计划离线复核（引擎规则：越界 + 精确逐格重叠；按键语义 select/confirm/move）")
    ok = True
    ok &= check("一关（3 块异形：1x3 横条 + 6 格阶梯 + L 三格）→ 拼回图 4-1",
                PLAN_L1, [L1_P0, L1_P1, L1_P2], L1_START, False, L1_TARGET)
    ok &= check("二关 · 图案 0（田，4x4 方块）→ 摆成目标锚点集的一个**置换**（ERR-021 回归）",
                PLAN_L2_PAT0, [L2_P16] * 4, L2_START, True, L2_PAT0_TARGET)
    ok &= check("二关 · 图案 3（S/Z 锯齿，A2/S1 模式 B）→ 拼成图案 3 的块锚点集",
                PLAN_L2_PAT3, [L2_P16] * 4, L2_START, True, L2_PAT3_TARGET,
                want_union=pat_union(L2_BLOCKS[3]))
    # 顺带核对：图案库的每幅都能用四块 2x2 恰好铺满（与 check_geometry 的穷举互为独立复核）
    for k, blocks in L2_BLOCKS.items():
        m = L2_PAT[k]
        u = pat_union(blocks)
        mk = 0
        for (r, c) in u:
            mk |= 1 << (8 * r + c)
        good = (mk == m)
        ok &= good
        print("  %s 图案 %d 的块并集 == puzzle_pkg.L2_PAT%d"
              % ("[OK]  " if good else "[FAIL]", k, k))

    print("\n%s" % ("ALL PLAN CHECKS PASSED" if ok else "*** SOME CHECKS FAILED ***"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
