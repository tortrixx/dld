#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe_nodes.py —— **廉价**校验测试台观测点（OBSERVE）的名字是否真的存在

【要解决的问题】
    `sim.py` 的 `OBSERVE` 是一份**硬契约**：名字在综合后网表里不存在就直接报错
    （`docs/03-仿真验证方案.md` §3.1 第 5 条）。观测点写错的后果是**静默的**
    —— 该节点没有跳变，断言看到全 X，很容易被误读成"设计坏了"。
    但校验它的**旧办法很贵**：只有"把整个仿真跑完再看" —— 整机 `puzzle_top` 一轮
    **40~60 分钟**。于是过去每次探节点名都要临时写 `.tmp/xxx_probe.py`（不可复用）。

【本工具怎么做到"廉价"】
    ① `quartus_map --generate_functional_sim_netlist`（模块级约 1 分钟）建出仿真网表；
    ② 跑一次**截断的冒烟仿真**（默认 100 us，几千个时钟，**几秒**）；
    ③ 读 `output_files/puzzle.sim.rpt` 里的 **Coverage Summary 节点表** ——
       那是仿真器自己列出的**全部节点全名**（实测整机 41823 条），
       按 `|puzzle_top|game_fsm:u_fsm|sound_p[3]` 的层次写法给出。
    把全名归一成 tb 的写法（`u_fsm|sound_p`）就得到一份**判定性**的存在性清单。
    ⇒ 合计约 1~2 分钟，比跑整机仿真便宜两个数量级。

【⚠️ 为什么不用 `db/puzzle.hier_info`（走过的弯路，留档）】
    最初用 `db/puzzle.hier_info`（也是纯文本）当节点表，结果它**不完整**：
    它只列"有 CLK/端口连接关系"的对象，**纯组合内部网线不在里面**。
    实测反例：`puzzle_top` 的 `mat_r`（组合信号，喂 `dot_matrix_scan`）在
    `hier_info` 里**一条都没有**，但它**确实**是仿真器认的节点
    （`sim/puzzle_top.vwf` 里 `SIGNAL("mat_r")` + 8 条位线，且整机 r33 用了它）。
    ⇒ 用 `hier_info` 会**把正确的观测点误判成缺失**，所以改成读 `sim.rpt` 的节点表。

【用法】
    python scripts/probe_nodes.py <模块>              # 冒烟仿真 → 逐条校验 OBSERVE
    python scripts/probe_nodes.py <模块> --reuse      # 复用已有 sim.rpt（不重跑）
    python scripts/probe_nodes.py <模块> --grep 正则  # 在节点表里搜名字（找观测点时用）
    python scripts/probe_nodes.py <模块> --list       # 打印全部节点名（很大，慎用）

【安全】仓库全程只读（复用 sim.py 的隔离工程机制）；冒烟激励写在
    `.tmp/probe_<模块>/probe_smoke.vwf`，**绝不碰 `sim/<模块>.vwf`** ——
    那份文件既是激励又是结果，覆盖它就等于毁掉正在被复核的证据（ERR-052 同类）。
"""
import argparse
import difflib
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import sim   # noqa: E402  —— 复用隔离工程 / quartus 调用 / tb 装载
import vwf   # noqa: E402

# Coverage Summary 的节点表行：`; |a|b:c|d[3]  ; |a|b:c|d[3]  ; regout ;`
RE_NODE_ROW = re.compile(r"^;\s*(\|[^;]*?)\s*;\s*\|[^;]*?;\s*(\w+)\s*;\s*$")
# ⚠️ 只去掉**位选** `[n]`：tb 是按**总线基名**声明观测点的。
#    `~n` **不能**去掉 —— 那是 Quartus 给中间节点起的名字的一部分，是一个**独立节点**
#    （实测反例：`rng_lfsr` 的 tb 观测 `fb~0`，而节点表里就是 `fb~0`；
#      误删 `~0` 会把一个正确观测点判成缺失）。
RE_BITINDEX = re.compile(r"\[\d+\]$")


def short_name(full):
    """`|puzzle_top|game_fsm:u_fsm|sound_p[3]` -> `u_fsm|sound_p`（= tb 的 OBSERVE 写法）。

    规则：去掉顶层段；每个 `实体类型:实例标签` 段只留**实例标签**；去掉位选 `[n]`。
    """
    segs = [s for s in full.strip("|").split("|")][1:]      # 去掉 |puzzle_top
    out = []
    for s in segs:
        if ":" in s:
            s = s.split(":", 1)[1]
        out.append(RE_BITINDEX.sub("", s))
    return "|".join(out)


def load_node_table(rpt_path):
    """解析 sim.rpt 的节点表 -> (短名集合, 全名集合)。"""
    short, full = set(), set()
    for line in rpt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RE_NODE_ROW.match(line)
        if m:
            full.add(m.group(1))
            short.add(short_name(m.group(1)))
    return short, full


def smoke_sim(module, tb):
    """建隔离工程 + 截断冒烟仿真；返回 sim.rpt 路径。仓库只读。"""
    proj = sim._make_isolated_project(module, getattr(tb, "RTL_PATCHES", []))
    if sim._quartus(proj, "quartus_map", sim.PROJ_NAME,
                    "--generate_functional_sim_netlist"):
        raise SystemExit("✗ 生成仿真网表失败")

    # ⚠️ 冒烟激励写到隔离工程里，**不碰 sim/<模块>.vwf**
    probe = proj / "probe_smoke.vwf"
    b = vwf.Builder(duration=SMOKE_NS, grid_period=getattr(tb, "GRID_PERIOD", 10.0))
    tb.build(b)
    b.write(str(probe))
    print("  · 冒烟激励 %s（%.4g ns，仅用于让仿真器列出节点表）"
          % (probe.relative_to(sim.ROOT), SMOKE_NS))

    if sim._quartus(proj, "quartus_sim", sim.PROJ_NAME, "--mode=functional",
                    "--overwrite_waveform=on",
                    "--vector_source=" + probe.as_posix()):
        raise SystemExit("✗ 冒烟仿真失败（可试 --reuse 复用已有 sim.rpt）")
    rpt = proj / "output_files" / (sim.PROJ_NAME + ".sim.rpt")
    if not rpt.exists():
        raise SystemExit("✗ 没找到 %s" % rpt)
    return rpt


SMOKE_NS = 100_000.0        # 100 us：几千个时钟，几秒跑完


def main():
    ap = argparse.ArgumentParser(description="廉价校验 tb 的 OBSERVE 观测点名字")
    ap.add_argument("module")
    ap.add_argument("--reuse", action="store_true", help="复用已有 sim.rpt（不重跑仿真）")
    ap.add_argument("--grep", default=None, help="在节点表里按正则搜名字")
    ap.add_argument("--list", action="store_true", help="打印全部节点名")
    args = ap.parse_args()

    tb = sim.load_tb(args.module)
    proj = sim.TMP_DIR / ("sim_" + args.module)
    rpt = proj / "output_files" / (sim.PROJ_NAME + ".sim.rpt")

    if args.reuse and rpt.exists():
        print("  · 复用已有仿真报告 %s" % rpt.relative_to(sim.ROOT))
    else:
        print("== 冒烟仿真（map + 100 us 仿真；仓库只读）==")
        rpt = smoke_sim(args.module, tb)

    short, full = load_node_table(rpt)
    if not short:
        raise SystemExit("✗ 节点表为空 —— sim.rpt 的格式可能与本工具的正则不符")
    print("  · 仿真器节点表：%d 条全名 / %d 个去位选短名" % (len(full), len(short)))

    if args.grep:
        rx = re.compile(args.grep, re.I)
        hits = sorted(n for n in short if rx.search(n))
        print("\n== 匹配 /%s/ 的节点（%d 个）==" % (args.grep, len(hits)))
        for h in hits:
            print("  %s" % h)
        return 0

    if args.list:
        for n in sorted(short):
            print(n)
        return 0

    obs = list(getattr(tb, "OBSERVE", []))
    if not obs:
        print("  ⚠️ %s 没有声明 OBSERVE" % args.module)
        return 0

    print("\n== 校验 %s 的 OBSERVE（%d 个）==" % (args.module, len(obs)))
    missing = [n for n in obs if n not in short]
    for n in obs:
        line = "  %s %s" % ("✓" if n in short else "✗", n)
        if n not in short:
            near = difflib.get_close_matches(n, short, n=3, cutoff=0.6)
            if near:
                line += "   ← 最接近的现有节点：%s" % "、".join(near)
        print(line)
    print("-" * 66)
    if missing:
        print("✗ %d / %d 个观测点不在仿真器节点表里 —— 跑仿真前先改 tb："
              % (len(missing), len(obs)))
        for n in missing:
            print("    %s" % n)
        print("  提示：`--grep <正则>` 找正确名字；写**总线基名**即可（位选/后缀不用写）")
        return 1
    print("✅ %d / %d 个观测点都存在 —— 可以放心跑仿真" % (len(obs), len(obs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
