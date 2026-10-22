#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""arch_data.py —— 系统总体框图的**唯一事实源**（数据与布局分离）

【为什么要单独一个文件】
    课程平台原文要求「**总体框图中的模块要求与实现电路(代码)一致**」。
    图好不好看是"布局"问题，图对不对是"数据"问题 —— 这两件事必须分开：
      · 本文件 = 数据（有哪些方框、有哪些连线、每根线叫什么、多少位）——
        **全部从 facts/facts.json 与 rtl/*.vhd 现算**，人工只能读不能改；
      · 各布局脚本 = 布局（坐标、走线、配色）—— 可以随便换、随便比。

    布局脚本 `import arch_data`，只许按 `BOX_IDS` / `WIRE_GROUPS` / `GLOBALS`
    画图；画完把自己的布局写成 JSON，再用 `arch_data.py --verify-layout <json>`
    对账 —— 少画一根线、多画一根线、写错一个网名都会 FAIL。

【用法】
    python scripts/arch_data.py                     # 打印事实源摘要
    python scripts/arch_data.py --verify-layout X.json   # 对账某个布局文件
    python scripts/arch_data.py --json              # 机器可读输出

【事实源】
    · facts/facts.json 的 entities.puzzle_top.instantiations[].port_map
      ⇒ 每个顶层信号的网名与位宽（formal ← actual）
    · rtl/puzzle_top.vhd 的 `signal` 声明 ⇒ 顶层内部信号（eng_fr/mat_r/mrow/pat_sel…）
    · rtl/puzzle_top.vhd 的 port map 原文 ⇒ 每个模块消费哪些全局网络（clk/rst/sw7）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS = os.path.join(ROOT, "facts", "facts.json")

# ---------------------------------------------------------------- 方框集合（固定 20 个）
# 11 个 entity（= puzzle_top.vhd 里 11 个 u_* 例化，一个不多一个不少）
ENTITIES = {
    "clk_gen":         {"file": "rtl/clk_gen.vhd",         "title": "clk_gen"},
    "keypad_scan":     {"file": "rtl/keypad_scan.vhd",     "title": "keypad_scan"},
    "game_fsm":        {"file": "rtl/game_fsm.vhd",        "title": "game_fsm"},
    "piece_rom":       {"file": "rtl/piece_rom.vhd",       "title": "piece_rom"},
    "pattern_rom":     {"file": "rtl/pattern_rom.vhd",     "title": "pattern_rom"},
    "rng_lfsr":        {"file": "rtl/rng_lfsr.vhd",        "title": "rng_lfsr"},
    "puzzle_ctrl":     {"file": "rtl/puzzle_ctrl.vhd",     "title": "puzzle_ctrl"},
    "disp_format":     {"file": "rtl/disp_format.vhd",     "title": "disp_format"},
    "seg_scan":        {"file": "rtl/seg_scan.vhd",        "title": "seg_scan"},
    "dot_matrix_scan": {"file": "rtl/dot_matrix_scan.vhd", "title": "dot_matrix_scan"},
    "buzzer_ctrl":     {"file": "rtl/buzzer_ctrl.vhd",     "title": "buzzer_ctrl"},
}

# 7 个板载外部器件（不是 entity，画成"系统上下文"）
EXTERNAL = {
    "ext_clk":  {"title": "50 MHz 有源晶振", "sub": "PIN_18"},
    "ext_btn":  {"title": "BTN0 复位按键",   "sub": "PIN_61"},
    "ext_sw":   {"title": "SW7 全局使能",    "sub": "PIN_125"},
    "ext_kp":   {"title": "4×4 矩阵键盘",    "sub": "kp_row / kp_col"},
    "ext_seg":  {"title": "8 位共阴数码管",  "sub": "seg / cat"},
    "ext_dot":  {"title": "8×8 双色点阵",    "sub": "ROW / COLR / COLG"},
    "ext_buzz": {"title": "无源蜂鸣器",      "sub": "PIN_60"},
}

# 2 个顶层胶合逻辑（不是 entity，画虚线框）
GLUE = {
    "glue_row": {"title": "行计数器 + 行切片",
                 "sub": "puzzle_top.vhd 内 · 非 entity"},
    "glue_pat": {"title": "图案选择锁存",
                 "sub": "puzzle_top.vhd 内 · 非 entity"},
}

BOX_IDS = list(ENTITIES) + list(EXTERNAL) + list(GLUE)

# ---------------------------------------------------------------- 全局网络（轨道式分配）
# 这三个网络是"一对多"的全局分配（clk 8 个消费者、rst 8 个、sw7 4 个）。
# 逐根画箭头会得到 20 根长线、必然穿框 ⇒ 图上用**全局轨道 / 角标**表达，
# 不进入 WIRE_GROUPS（否则 fidelity 对账会要求画 20 根线）。
RAILS = {
    "clk": {"from": "ext_clk", "text": "clk 50 MHz"},
    "rst": {"from": "clk_gen", "text": "rst 同步复位"},
    "sw7": {"from": "ext_sw",  "text": "sw7 使能"},
}
# 每个方框消费的全局网络（从 rtl/puzzle_top.vhd 的 port map 逐条读出：i_clk / i_rst / i_en）
GLOBALS = {
    "clk_gen":         ["clk"],
    "keypad_scan":     ["clk", "rst"],
    "game_fsm":        ["clk", "rst", "sw7"],
    "piece_rom":       [],
    "pattern_rom":     [],
    "rng_lfsr":        ["clk", "rst"],
    "puzzle_ctrl":     ["clk", "rst"],
    "disp_format":     [],
    "seg_scan":        ["clk", "rst", "sw7"],
    "dot_matrix_scan": ["clk", "rst", "sw7"],
    "buzzer_ctrl":     ["clk", "rst", "sw7"],
    "glue_row":        ["clk"],
    "glue_pat":        ["clk", "rst"],
}

# ---------------------------------------------------------------- 连线（逻辑图，与坐标无关）
# (源方框, 目标方框, [网名…])
#   · 一根"线"可以携带多个网名（同向、同目的地的一组信号画成一根箭头）；
#   · 同一个网名**可以出现在多根线里**（扇出：state 既去 disp_format 又去胶合逻辑）；
#   · 对账口径 = 展开后的 (源,目标,网名) 三元组集合必须**完全相等**。
WIRE_GROUPS = [
    # 板级输入
    ("ext_btn",  "clk_gen",  ["btn"]),
    ("ext_kp",   "keypad_scan", ["kp_row"]),
    ("keypad_scan", "ext_kp", ["kp_col"]),
    # 时钟节拍分发（clk_gen 的 7 路 tick 里 4 路有人用）
    ("clk_gen",  "keypad_scan",  ["t_200"]),
    ("clk_gen",  "game_fsm",     ["t_1hz", "t_4hz"]),
    ("clk_gen",  "buzzer_ctrl",  ["t_4hz"]),
    ("clk_gen",  "puzzle_ctrl",  ["t_1k"]),
    ("clk_gen",  "seg_scan",     ["t_1k"]),
    ("clk_gen",  "glue_row",     ["t_1k"]),
    # 键盘 → 主控
    ("keypad_scan", "game_fsm", ["key", "press"]),
    # 主控 → 存储器 / 引擎
    ("game_fsm", "piece_rom",   ["level"]),
    ("game_fsm", "pattern_rom", ["level"]),
    ("game_fsm", "puzzle_ctrl", ["go", "sel", "move", "conf"]),
    ("game_fsm", "puzzle_ctrl", ["mv_up", "mv_dn", "mv_lf", "mv_rt", "mv_rot"]),
    ("game_fsm", "puzzle_ctrl", ["level"]),
    ("puzzle_ctrl", "game_fsm", ["solved", "all_lock", "shuf_busy"]),
    # 存储器 / 随机源 → 引擎
    ("piece_rom",   "puzzle_ctrl", ["shapes", "shape_h", "shape_w"]),
    ("pattern_rom", "puzzle_ctrl", ["tgt_mask"]),
    ("rng_lfsr",    "puzzle_ctrl", ["rnd_val"]),
    ("puzzle_ctrl", "rng_lfsr",    ["rnd_step"]),
    # 主控 → 显示 / 音频
    ("game_fsm", "disp_format", ["state", "gtime", "gblink"]),
    ("game_fsm", "disp_format", ["level", "lvl3"]),
    ("disp_format", "seg_scan", ["disp_data", "disp_blank"]),
    ("seg_scan", "ext_seg",     ["seg", "cat"]),
    ("game_fsm", "buzzer_ctrl", ["sound"]),
    ("buzzer_ctrl", "ext_buzz", ["buzz"]),
    # 引擎 → 顶层胶合（行切片）
    ("puzzle_ctrl", "glue_row", ["eng_fr", "eng_fg"]),
    ("game_fsm",    "glue_row", ["state", "gblink"]),
    ("pattern_rom", "glue_row", ["tgt_mask"]),
    ("glue_row", "dot_matrix_scan", ["mat_r", "mat_g", "mrow"]),
    ("dot_matrix_scan", "ext_dot", ["dot_row", "dot_colr", "dot_colg"]),
    # 顶层胶合（图案选择锁存）
    ("game_fsm", "glue_pat", ["state", "lvl3"]),
    ("rng_lfsr", "glue_pat", ["rnd_val"]),
    ("glue_pat", "pattern_rom", ["pat_sel"]),
    ("glue_pat", "puzzle_ctrl", ["pat_sel"]),
]

# 数组型端口在 facts.json 里宽度记为 1，这里给人可读口径
ARRAY_WIDTH = {"shapes": "4×64", "shape_h": "4×3", "shape_w": "4×3"}

# 如实说明（画在图的脚注里，或写进正文）
NOTES = [
    "clk_gen 另有 t_100 / t_40 / o_tick_2hz 三路输出，在 puzzle_top 里无人消费"
    "（仅板级诊断顶层 board_test_top / keypad_diag_top 使用），本图未画。",
    "piece_rom.o_n（piece_n）在顶层未被消费，与编译报告 “assigned a value but never read” 一致。",
    "另有 3 个板级诊断顶层（board_test_top / keypad_diag_top / keypad_raw_top）不属于本数据通路。",
]


def load_facts():
    with open(FACTS, encoding="utf-8") as fh:
        return json.load(fh)


def top_signals() -> dict:
    """解析 rtl/puzzle_top.vhd 里声明的顶层内部信号 → (位宽, 出处)。"""
    src = open(os.path.join(ROOT, "rtl", "puzzle_top.vhd"), encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"^\s*signal\s+(\w+)\s*:\s*([^;]+);", src, re.M):
        name, typ = m.group(1), m.group(2)
        rng = re.search(r"(\d+)\s+downto\s+(\d+)", typ)
        if rng:
            out[name] = (abs(int(rng.group(1)) - int(rng.group(2))) + 1, "puzzle_top.vhd signal")
        elif re.search(r"\bstd_logic\b|\bunsigned\b|\bsigned\b", typ):
            out[name] = (1, "puzzle_top.vhd signal")
    return out


def net_widths(facts=None) -> dict:
    """网名 → (位宽, 出处)。全部来自端口映射与顶层 signal 声明。"""
    facts = facts or load_facts()
    ent = facts["entities"]
    widths: dict = {}
    for inst in ent["puzzle_top"]["instantiations"]:
        pmap = {p["name"]: p for p in ent[inst["entity"]].get("ports", [])}
        for m in inst["port_map"]:
            actual, formal = m.get("actual"), m.get("formal")
            if not actual or actual == "open" or actual in widths:
                continue
            p = pmap.get(formal)
            if p:
                widths[actual] = (int(p.get("width") or 1), "%s.%s" % (inst["entity"], formal))
    for p in ent["puzzle_top"].get("ports", []):
        widths.setdefault(p["name"], (int(p.get("width") or 1), "puzzle_top.%s" % p["name"]))
    for k, v in top_signals().items():
        widths.setdefault(k, v)
    return widths


def width_of(net: str, widths: dict | None = None) -> int:
    widths = widths if widths is not None else net_widths()
    if net in ARRAY_WIDTH:
        return 1
    return widths.get(net, (1, "?"))[0]


def net_label(net: str, widths: dict | None = None) -> str:
    """单个网名的标注文本（带位宽口径 [MSB:LSB]）。"""
    if net in ARRAY_WIDTH:
        return "%s[%s]" % (net, ARRAY_WIDTH[net])
    w = width_of(net, widths)
    return net if w <= 1 else "%s[%d:0]" % (net, w - 1)


def wire_label(nets, widths: dict | None = None) -> str:
    return "/".join(net_label(n, widths) for n in nets)


def wire_triples():
    """展开成 (源, 目标, 网名) 三元组的**有序去重**列表。"""
    seen, out = set(), []
    for frm, to, nets in WIRE_GROUPS:
        for n in nets:
            t = (frm, to, n)
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def all_nets():
    return sorted({n for _f, _t, nets in WIRE_GROUPS for n in nets})


# ---------------------------------------------------------------- 布局对账
def verify_layout(path: str) -> int:
    """校验某个布局 JSON 是否与事实源一致。

    只认这几件事：
      · kind=="entity" 的方框集合 == ENTITIES；"ext" == EXTERNAL；"glue" == GLUE
      · 每根线展开出的 (源,目标,网名) 三元组集合 == WIRE_GROUPS 展开的集合
      · 每个方框的 globals == GLOBALS
      · 用到的网名都真的存在（位宽可查）
    坐标是否好看不在这里管 —— 那是 scripts/audit_diagram.py 的事。
    """
    with open(path, encoding="utf-8") as fh:
        lay = json.load(fh)
    bad = []
    widths = net_widths()

    boxes = {b["id"]: b for b in lay.get("boxes", [])}
    for kind, want in (("entity", ENTITIES), ("ext", EXTERNAL), ("glue", GLUE)):
        got = {b["id"] for b in lay.get("boxes", []) if b.get("kind") == kind}
        if got != set(want):
            bad.append("%s 方框集合不符：缺 %s / 多 %s"
                       % (kind, sorted(set(want) - got), sorted(got - set(want))))
    for bid, b in boxes.items():
        if bid in GLOBALS:
            g = list(b.get("globals") or [])
            if sorted(g) != sorted(GLOBALS[bid]):
                bad.append("%s 的全局网络标注 %s ≠ 事实源 %s" % (bid, g, GLOBALS[bid]))
        if bid in ENTITIES:
            f = b.get("file")
            if f and f != ENTITIES[bid]["file"]:
                bad.append("%s 的文件名 %s ≠ %s" % (bid, f, ENTITIES[bid]["file"]))

    got_triples, unknown = set(), []
    for w in lay.get("wires", []):
        frm, to = w.get("from"), w.get("to")
        for n in w.get("nets", []):
            if n not in widths:
                unknown.append(n)
            got_triples.add((frm, to, n))
    want_triples = set(wire_triples())
    if got_triples != want_triples:
        miss = sorted(want_triples - got_triples)
        extra = sorted(got_triples - want_triples)
        if miss:
            bad.append("漏画 %d 根：%s" % (len(miss), miss[:8]))
        if extra:
            bad.append("多画 %d 根：%s" % (len(extra), extra[:8]))
    if unknown:
        bad.append("用了不存在的网名：%s" % sorted(set(unknown)))

    print("== 布局 vs 事实源：%s ==" % os.path.relpath(path, ROOT))
    print("  方框：entity %d / ext %d / glue %d"
          % (sum(1 for b in boxes.values() if b.get("kind") == "entity"),
             sum(1 for b in boxes.values() if b.get("kind") == "ext"),
             sum(1 for b in boxes.values() if b.get("kind") == "glue")))
    print("  连线：布局 %d 根 / 三元组 %d 个；事实源三元组 %d 个"
          % (len(lay.get("wires", [])), len(got_triples), len(want_triples)))
    if bad:
        for b in bad:
            print("  [FAIL] %s" % b)
        return 1
    print("  OK：方框集合 / 文件名 / 连线三元组 / 全局网络 全部与事实源一致")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="系统总体框图的事实源（数据与布局分离）")
    ap.add_argument("--verify-layout", metavar="JSON", help="对账某个布局文件")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    if args.verify_layout:
        return verify_layout(args.verify_layout)

    widths = net_widths()
    if args.json:
        print(json.dumps({
            "entities": ENTITIES, "external": EXTERNAL, "glue": GLUE,
            "globals": GLOBALS, "rails": RAILS,
            "wire_groups": [{"from": f, "to": t, "nets": n} for f, t, n in WIRE_GROUPS],
            "net_widths": {k: v[0] for k, v in widths.items()},
            "notes": NOTES,
        }, ensure_ascii=False, indent=2))
        return 0

    print("方框：%d 个 entity + %d 个外部器件 + %d 个顶层胶合 = %d"
          % (len(ENTITIES), len(EXTERNAL), len(GLUE), len(BOX_IDS)))
    print("全局轨道：%s" % "、".join("%s(←%s)" % (k, v["from"]) for k, v in RAILS.items()))
    print("连线分组：%d 根，展开三元组 %d 个，涉及网名 %d 个"
          % (len(WIRE_GROUPS), len(wire_triples()), len(all_nets())))
    for f, t, nets in WIRE_GROUPS:
        print("  %-14s → %-16s %s" % (f, t, wire_label(nets, widths)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
