#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_facts.py —— 从**真实工程文件**抽出「唯一事实模型」 facts/facts.json

为什么要这个东西
----------------
本项目有两个站点（`site/` 工程展示站 与 `book/` Material 技术文档站），
它们必须共用**同一套工程事实**。如果模块清单、端口名、位宽、资源读数
分别手写在两个地方，迟早会互相打脸（这个仓库已经被同类问题咬过：
见 docs/06 的 ERR-022「文档与代码的位宽不一致」）。

所以：**凡是能从文件机械抽出来的，一律不手写。**
本脚本只做「读取 + 解析 + 汇总」，不做任何推断；抽不出来的才由人写，
并在文档里标 `待核实`。

抽取来源（全部是**已入库**的文件）
----------------------------------
    rtl/*.vhd                  实体、端口、component 声明、实例化与 port map、
                               puzzle_pkg 的常量/类型/子类型/函数
    sim/rounds/<mod>/rNN.json  每个模块**最新一轮**仿真的断言与结果
    sim/tb_<mod>.py            测试台文件（存在性）
    sim/<mod>.vwf              波形文件（**既是激励也是结果**，见 ERR-028）
    quartus/build_provenance.json   器件、LE/LAB/引脚、setup/hold slack、POF 指纹
    quartus/puzzle.qsf         引脚锁定
    quartus/puzzle.sdc         时钟约束
    docs/图/**                 图片清单（含 Quartus GUI 截图 / 脚本辅助波形之分）
    docs/06-硬件调试记录.md      ERR-xxx 故障编号与标题

输出
----
    facts/facts.json           机读事实模型（供 book/ 与 site/ 双方消费）

    ⚠️ 有意**不写入任何易变字段**（时间戳 / git HEAD / 主机名）：
       这样 `--check` 才能用「重新生成并逐字节比对」来判断事实是否过期，
       而不会每提交一次就无意义地报脏。

用法
----
    python scripts/extract_facts.py            # 生成/覆盖 facts/facts.json
    python scripts/extract_facts.py --check    # 只校验：过期则退出码 1（CI 门禁用）
    python scripts/extract_facts.py --stdout   # 打到标准输出，不写文件

退出码：0 成功；1 校验失败（事实过期）；2 解析失败（源码里出现了本脚本
看不懂的结构 —— 宁可炸掉也不要静默漏掉一个端口）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

# --------------------------------------------------------------------------
# 仓库根目录（本文件在 scripts/ 下）
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "facts", "facts.json")

# 15 个实体中，哪些不是「游戏运行时数据通路」上的模块。
# ⚠️ 这个分类必须**人工**给定语义，脚本只负责搬运；
#    依据是 rtl/puzzle_top.vhd 文件头 19-31 行的框图编号（S1..S7）。
ENT_TIERS: dict[str, str] = {
    "puzzle_top": "top",
    "board_test_top": "diag_top",
    "keypad_diag_top": "diag_top",
    "keypad_raw_top": "diag_top",
}
# S 编号 → 子系统（来自 puzzle_top.vhd 头注释，逐条可核）
SUB_SYSTEM: dict[str, str] = {
    "clk_gen": "S1 时钟与复位",
    "keypad_scan": "S2 键盘输入",
    "game_fsm": "S3 游戏控制",
    "puzzle_ctrl": "S4 拼图引擎",
    "pattern_rom": "S5 图案与零片数据",
    "piece_rom": "S5 图案与零片数据",
    "rng_lfsr": "S5 图案与零片数据",
    "dot_matrix_scan": "S6 显示输出",
    "seg_scan": "S6 显示输出",
    "disp_format": "S6 显示输出",
    "buzzer_ctrl": "S7 音效",
}


def die(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    print("extract_facts: " + msg, file=sys.stderr)
    raise SystemExit(2)


# ==========================================================================
# 通用：读文件 + 分隔 VHDL 注释
# ==========================================================================
def read_text(rel: str) -> str:
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def split_vhdl_comment(line: str) -> tuple[str, str]:
    """把一行 VHDL 切成 (代码, 注释)。

    `--` 在 VHDL 里是行注释，但**位串字面量** `x"5A"` / `"1010"` 里的
    双引号必须先跟踪，否则 `x"5A" -- 说明` 之外的边角会被切错。
    """
    in_str = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_str = not in_str
        elif ch == "-" and not in_str and i + 1 < len(line) and line[i + 1] == "-":
            return line[:i], line[i + 2:].strip()
        i += 1
    return line, ""


def code_only(text: str) -> str:
    return "\n".join(split_vhdl_comment(ln)[0] for ln in text.splitlines())


def join_logical(text: str, sep: str = ";") -> list[tuple[int, str]]:
    """按**深度 0 的分隔符**把文本切成逻辑语句，返回 [(起始行号 1-based, 语句)]。

    深度只跟踪圆括号：VHDL 的端口/常量声明里唯一会嵌套的就是
    `std_logic_vector(63 downto 0)` 这种子类型指示。
    """
    out: list[tuple[int, str]] = []
    buf: list[str] = []
    depth = 0
    start = 1
    for idx, raw in enumerate(text.splitlines(), start=1):
        code, _ = split_vhdl_comment(raw)
        if not buf:
            start = idx
        depth += code.count("(") - code.count(")")
        if sep in code and depth <= 0:
            head, _, tail = code.rpartition(sep)
            buf.append(head)
            stmt = "\n".join(buf).strip()
            if stmt:
                out.append((start, stmt))
            buf = []
            if tail.strip():
                buf.append(tail)
            depth = 0
            continue
        buf.append(code)
    tail_stmt = "\n".join(buf).strip()
    if tail_stmt:
        out.append((start, tail_stmt))
    return out


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ==========================================================================
# VHDL 解析
# ==========================================================================
RE_ENTITY = re.compile(r"^\s*entity\s+([A-Za-z_]\w*)\s+is\b", re.I)
RE_END_ENTITY = re.compile(r"^\s*end\s+(?:entity\s+)?([A-Za-z_]\w*)\s*;", re.I)
RE_ARCH = re.compile(r"^\s*architecture\s+([A-Za-z_]\w*)\s+of\s+([A-Za-z_]\w*)\s+is\b", re.I)
RE_PACKAGE = re.compile(r"^\s*package\s+([A-Za-z_]\w*)\s+is\b", re.I)
RE_PACKAGE_BODY = re.compile(r"^\s*package\s+body\s+([A-Za-z_]\w*)\s+is\b", re.I)
RE_COMPONENT = re.compile(r"^\s*component\s+([A-Za-z_]\w*)\b", re.I)


def _scan_paren_block(lines: list[str], start_idx: int) -> tuple[str, int]:
    """从 start_idx 行起找第一个 `(` 并返回 (括号内的**原始**文本, 右括号所在行下标)。

    为什么不用"逐行数括号"：VHDL 注释里出现的 `)`（本项目的中文注释里真的有，
    例如 `-- 见 docs/05 §1.2`、`-- （S1..S7）`）会让朴素计数提前闭合。
    这里按字符扫描，同时跟踪**双引号字符串**与 `--` 行注释，只在真正的代码
    括号上计数 —— 返回的原文里保留注释，便于把尾注释贴到对应端口/连接上。
    """
    text = "\n".join(lines[start_idx:])
    depth = 0
    started = False
    in_str = False
    i = 0
    while i < len(text):
        ch = text[i]
        if not in_str and ch == "-" and i + 1 < len(text) and text[i + 1] == "-":
            j = text.find("\n", i)
            if j < 0:
                break
            i = j
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "(":
                if not started:
                    started = True
                    depth = 1
                    inner_start = i + 1
                else:
                    depth += 1
            elif ch == ")":
                depth -= 1
                if started and depth == 0:
                    inner = text[inner_start:i]
                    consumed = lines[start_idx : start_idx + text[:i].count("\n") + 1]
                    end_line = start_idx + len(consumed) - 1
                    return inner, end_line
        i += 1
    die("括号不配对：%r" % lines[start_idx][:80])


def extract_port_block(lines: list[str], start_idx: int) -> tuple[str, int]:
    return _scan_paren_block(lines, start_idx)


def parse_ports(block: str, line0: int) -> list[dict[str, Any]]:
    """解析端口声明块 -> [{name, dir, type, width, default, comment}]"""
    # 逐行保留尾注释，方便把注释贴到对应端口上
    lines = block.splitlines()
    ports: list[dict[str, Any]] = []
    for stmt in join_logical(block):
        _, raw = stmt
        if ":" not in raw:
            continue
        names_part, _, rest = raw.partition(":")
        rest = norm_ws(rest)
        m = re.match(r"(in|out|inout)\b\s*(.*)$", rest, re.I)
        if not m:
            die("端口声明里找不到方向: %r" % raw)
        direction = m.group(1).lower()
        decl = m.group(2).strip()
        default = None
        if ":=" in decl:
            decl, _, default = decl.partition(":=")
            default = norm_ws(default)
        vtype = norm_ws(decl)
        width = 1
        mw = re.search(r"\(\s*(\d+)\s+downto\s+(\d+)\s*\)", vtype)
        if mw:
            width = int(mw.group(1)) - int(mw.group(2)) + 1
        mw = re.search(r"\(\s*(\d+)\s+to\s+(\d+)\s*\)", vtype)
        if mw and width == 1:
            width = int(mw.group(2)) - int(mw.group(1)) + 1
        for nm in names_part.split(","):
            nm = nm.strip()
            if nm:
                ports.append(
                    {
                        "name": nm,
                        "dir": direction,
                        "type": vtype,
                        "width": width,
                        "default": default,
                        "comment": None,
                    }
                )
    # 尾注释：端口名 -> 注释
    cmap: dict[str, str] = {}
    for ln in lines:
        code, com = split_vhdl_comment(ln)
        if not com or ":" not in code:
            continue
        nm = code.split(":", 1)[0].strip().split(",")[0].strip()
        if nm:
            cmap[nm] = com
    for p in ports:
        p["comment"] = cmap.get(p["name"])
    return ports


def parse_port_map(block: str) -> list[dict[str, str]]:
    conns: list[dict[str, str]] = []
    for _, raw in join_logical(block, ","):
        if "=>" not in raw:
            continue
        formal, _, actual = raw.partition("=>")
        conns.append(
            {
                "formal": norm_ws(formal).strip(),
                "actual": norm_ws(actual).strip(),
            }
        )
    return conns


def parse_instantiations(text: str, file_rel: str) -> list[dict[str, Any]]:
    """找 `<label> : <entity|component> [generic map(..)] port map (..)`。"""
    lines = text.splitlines()
    insts: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        code, _ = split_vhdl_comment(lines[i])
        m = re.match(
            r"^\s*([A-Za-z_]\w*)\s*:\s*(?:entity\s+(?:work\.)?([A-Za-z_]\w*)|([A-Za-z_]\w*))\s*$",
            code,
        )
        if not m:
            i += 1
            continue
        label = m.group(1)
        ent = m.group(2) or m.group(3)
        line_no = i + 1
        j = i + 1
        visited: list[str] = []
        got_map = False
        while j < len(lines) and j < i + 12:
            c2, _ = split_vhdl_comment(lines[j])
            visited.append(c2)
            if "generic map" in c2.lower() or "port map" in c2.lower():
                if "port map" in c2.lower():
                    blk, end = extract_port_map_block(lines, j)
                    insts.append(
                        {
                            "instance": label,
                            "entity": ent,
                            "file": file_rel,
                            "line": line_no,
                            "port_map": parse_port_map(blk),
                        }
                    )
                    got_map = True
                    i = end
                    break
                blk, end = extract_port_map_block(lines, j)
                j = end
                continue
            j += 1
        if not got_map:
            i += 1
        else:
            i = max(i, j)
    return insts


def extract_port_map_block(lines: list[str], start_idx: int) -> tuple[str, int]:
    return _scan_paren_block(lines, start_idx)


def parse_entity_file(rel: str) -> dict[str, Any] | None:
    text = read_text(rel)
    lines = text.splitlines()
    ent_line = None
    ent_name = None
    for idx, ln in enumerate(lines):
        m = RE_ENTITY.match(split_vhdl_comment(ln)[0])
        if m:
            ent_line, ent_name = idx + 1, m.group(1)
            break
    if ent_name is None:
        return None
    # 端口块：实体头之后第一个 port (
    ports: list[dict[str, Any]] = []
    for idx in range(ent_line - 1, min(len(lines), ent_line + 200)):
        code, _ = split_vhdl_comment(lines[idx])
        if re.search(r"\bport\s*\(", code, re.I):
            blk, _ = extract_port_block(lines, idx)
            ports = parse_ports(blk, idx + 1)
            break
    arch = None
    for idx, ln in enumerate(lines):
        m = RE_ARCH.match(split_vhdl_comment(ln)[0])
        if m:
            arch = {"name": m.group(1), "line": idx + 1}
            break
    comps: list[str] = []
    for ln in lines:
        m = RE_COMPONENT.match(split_vhdl_comment(ln)[0])
        if m:
            comps.append(m.group(1))
    end_line = None
    for idx, ln in enumerate(lines):
        m = RE_END_ENTITY.match(split_vhdl_comment(ln)[0])
        if m:
            end_line = idx + 1
            break
    return {
        "entity": ent_name,
        "file": rel,
        "entity_line": ent_line,
        "end_entity_line": end_line,
        "architecture": arch,
        "ports": ports,
        "components_declared": comps,
        "instantiations": parse_instantiations(text, rel)
        if arch
        else [],
        "loc": len(lines),
    }


# --------------------------------------------------------------------------
# 设计包 puzzle_pkg.vhd
# --------------------------------------------------------------------------
RE_CONST = re.compile(r"^\s*constant\s+([A-Za-z_]\w*)\s*:\s*(.+?)\s*:=\s*(.+)$", re.S)
RE_TYPE = re.compile(r"^\s*type\s+([A-Za-z_]\w*)\s+is\s+(.+)$", re.S)
RE_SUBTYPE = re.compile(r"^\s*subtype\s+([A-Za-z_]\w*)\s+is\s+(.+)$", re.S)
RE_FUNC = re.compile(r"^\s*function\s+([A-Za-z_]\w*)\s*\(", re.S)


def parse_package(rel: str) -> dict[str, Any]:
    text = read_text(rel)
    lines = text.splitlines()
    code = code_only(text)
    pkg_line = None
    pkg_name = None
    for idx, ln in enumerate(lines):
        m = RE_PACKAGE.match(split_vhdl_comment(ln)[0])
        if m:
            pkg_line, pkg_name = idx + 1, m.group(1)
            break
    if pkg_name is None:
        die("%s 里没找到 package 声明" % rel)
    body_line = None
    for idx, ln in enumerate(lines):
        if RE_PACKAGE_BODY.match(split_vhdl_comment(ln)[0]):
            body_line = idx + 1
            break
    # 声明部分 = package 头到 package body（或 end package）
    decl_end = (body_line - 1) if body_line else len(lines)
    decl = "\n".join(code.splitlines()[pkg_line - 1 : decl_end])

    consts: list[dict[str, Any]] = []
    for start, raw in join_logical(decl):
        m = RE_CONST.match(raw)
        if not m:
            continue
        name, vtype, value = m.group(1), norm_ws(m.group(2)), norm_ws(m.group(3))
        com = None
        for ln in lines[start - 1 : start + len(raw.splitlines())]:
            _, c = split_vhdl_comment(ln)
            if c:
                com = c
        consts.append(
            {"name": name, "type": vtype, "value": value, "comment": com, "line": start + pkg_line - 1}
        )
    types = []
    subtypes = []
    for start, raw in join_logical(decl):
        m = RE_TYPE.match(raw)
        if m:
            types.append({"name": m.group(1), "def": norm_ws(m.group(2)), "line": start + pkg_line - 1})
            continue
        m = RE_SUBTYPE.match(raw)
        if m:
            subtypes.append(
                {"name": m.group(1), "def": norm_ws(m.group(2)), "line": start + pkg_line - 1}
            )
    funcs = []
    for idx, ln in enumerate(lines):
        c, _ = split_vhdl_comment(ln)
        m = RE_FUNC.match(c)
        if m:
            funcs.append({"name": m.group(1), "line": idx + 1})
    return {
        "package": pkg_name,
        "file": rel,
        "line": pkg_line,
        "body_line": body_line,
        "loc": len(lines),
        "constants": consts,
        "types": types,
        "subtypes": subtypes,
        "functions": funcs,
    }


# ==========================================================================
# 仿真轮次
# ==========================================================================
def parse_sim() -> dict[str, Any]:
    base = os.path.join(ROOT, "sim", "rounds")
    mods: dict[str, Any] = {}
    for mod in sorted(os.listdir(base)):
        d = os.path.join(base, mod)
        if not os.path.isdir(d):
            continue
        rounds = sorted(
            int(m.group(1))
            for m in (re.match(r"r(\d+)\.json$", f) for f in os.listdir(d))
            if m
        )
        if not rounds:
            continue
        latest = rounds[-1]
        with open(os.path.join(d, "r%d.json" % latest), "r", encoding="utf-8") as fh:
            rec = json.load(fh)
        tb = "sim/tb_%s.py" % mod
        vwf = "sim/%s.vwf" % mod
        mods[mod] = {
            "module": rec.get("module", mod),
            "round": latest,
            "rounds_total": len(rounds),
            "first_round": rounds[0],
            "timestamp": rec.get("timestamp"),
            "duration_ns": rec.get("duration_ns"),
            "passed": rec.get("passed"),
            "total": rec.get("total"),
            "all_pass": rec.get("all_pass"),
            "record_json": "sim/rounds/%s/r%d.json" % (mod, latest),
            "record_md": "sim/rounds/%s/r%d.md" % (mod, latest),
            "tb": tb if os.path.exists(os.path.join(ROOT, tb)) else None,
            "vwf": vwf if os.path.exists(os.path.join(ROOT, vwf)) else None,
            "assertions": [
                {"name": a.get("name"), "ok": bool(a.get("ok")), "detail": a.get("detail")}
                for a in rec.get("assertions", [])
            ],
        }
    totals = {
        "modules": len(mods),
        "assertions": sum(int(m["total"] or 0) for m in mods.values()),
        "passed": sum(int(m["passed"] or 0) for m in mods.values()),
        "all_pass": all(bool(m["all_pass"]) for m in mods.values()),
    }
    return {"modules": mods, "totals": totals}


# ==========================================================================
# 编译 / 时序 / 引脚
# ==========================================================================
def parse_build() -> dict[str, Any]:
    prov = json.loads(read_text("quartus/build_provenance.json"))
    fit = prov.get("fit", {})
    sta = prov.get("sta", {})
    qsf = read_text("quartus/puzzle.qsf")
    pins = []
    for ln in qsf.splitlines():
        m = re.match(
            r"set_location_assignment\s+(PIN_\d+)\s+-to\s+(\S+)", ln.strip()
        )
        if m:
            pins.append({"pin": m.group(1), "signal": m.group(2)})
    sdc = read_text("quartus/puzzle.sdc")
    period = None
    m = re.search(r"create_clock[^\n]*?-period\s+([\d.]+)", sdc)
    if m:
        period = float(m.group(1))
    fmax = None
    if period:
        fmax = round(1000.0 / period, 2)
    return {
        "device": "EPM1270T144C5",
        "family": "MAX II",
        "provenance": {
            "path": "quartus/build_provenance.json",
            "timestamp": prov.get("timestamp"),
            "pof": prov.get("pof"),
            "sources": prov.get("sources"),
            "sources_logic": prov.get("sources_logic"),
        },
        "fit": fit,
        "sta": sta,
        "constraint": {
            "sdc": "quartus/puzzle.sdc",
            "period_ns": period,
            "fmax_mhz": fmax,
        },
        "pins": pins,
        "pins_locked": len(pins),
    }


# ==========================================================================
# 图片清单
# ==========================================================================
def git_tracked(paths: list[str]) -> set[str]:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", ROOT, "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
    except Exception:
        return set()
    return {p for p in out.split("\0") if p}


def parse_images() -> list[dict[str, Any]]:
    d = os.path.join(ROOT, "docs", "图")
    tracked = git_tracked([])
    out = []
    for fn in sorted(os.listdir(d)):
        full = os.path.join(d, fn)
        if not os.path.isfile(full):
            continue
        rel = "docs/图/" + fn
        ext = os.path.splitext(fn)[1].lower()
        if fn.startswith("GUI-"):
            kind = "quartus_gui_screenshot"
        elif fn.startswith("SIM-"):
            kind = "script_waveform_svg"
        elif ext == ".drawio":
            kind = "editable_diagram_source"
        elif ext == ".gif":
            kind = "demo_animation"
        elif ext == ".png":
            kind = "rendered_figure"
        else:
            kind = "other"
        out.append(
            {
                "path": rel,
                "name": fn,
                "ext": ext,
                "kind": kind,
                "bytes": os.path.getsize(full),
                "module": fn.split("-", 1)[1].rsplit(".", 1)[0] if "-" in fn else None,
                "tracked": rel in tracked,
            }
        )
    return out


# ==========================================================================
# 故障编号（docs/06）
# ==========================================================================
RE_ERR_HEAD = re.compile(r"^#{2,6}\s+(ERR-\d+)\s*(?:·|\s)\s*(.*)$")


def parse_errors() -> list[dict[str, Any]]:
    rel = "docs/06-硬件调试记录.md"
    text = read_text(rel)
    out = []
    for idx, ln in enumerate(text.splitlines(), start=1):
        m = RE_ERR_HEAD.match(ln)
        if m:
            out.append({"id": m.group(1), "title": m.group(2).strip(), "line": idx})
    return out


# ==========================================================================
# 主流程
# ==========================================================================
def build() -> dict[str, Any]:
    rtl_dir = os.path.join(ROOT, "rtl")
    vhd = sorted(f for f in os.listdir(rtl_dir) if f.endswith(".vhd"))

    entities: dict[str, Any] = {}
    packages: dict[str, Any] = {}
    for fn in vhd:
        rel = "rtl/" + fn
        text = read_text(rel)
        # 逐行找 `package <name> is`（`package body` 不匹配，因为 RE_PACKAGE 要求
        # `package` 后紧跟标识符 + is；`package body X is` 中间有 body 一词）
        pkg = any(RE_PACKAGE.match(split_vhdl_comment(ln)[0]) for ln in text.splitlines())
        if pkg:
            parsed = parse_package(rel)
            packages[parsed["package"]] = parsed
            continue
        parsed = parse_entity_file(rel)
        if parsed is None:
            die("%s 既不是 package 也解析不出 entity" % rel)
        parsed["tier"] = ENT_TIERS.get(parsed["entity"], "module")
        parsed["subsystem"] = SUB_SYSTEM.get(parsed["entity"], "—")
        entities[parsed["entity"]] = parsed

    # 实例化 -> 反向索引（谁例化了谁）
    children: dict[str, list[dict[str, Any]]] = {e: [] for e in entities}
    for ent, info in entities.items():
        for inst in info["instantiations"]:
            target = inst["entity"]
            if target not in entities:
                die("%s 例化了未知实体 %s" % (info["file"], target))
            children[ent].append(
                {
                    "instance": inst["instance"],
                    "entity": target,
                    "line": inst["line"],
                    "file": info["file"],
                }
            )

    facts = {
        "schema": 1,
        "generator": "scripts/extract_facts.py",
        "sources": {
            "rtl": ["rtl/" + f for f in vhd],
            "sim_rounds": "sim/rounds/<module>/rNN.json",
            "build": "quartus/build_provenance.json",
            "qsf": "quartus/puzzle.qsf",
            "sdc": "quartus/puzzle.sdc",
            "figures": "docs/图/",
            "errors": "docs/06-硬件调试记录.md",
        },
        "design": {
            "title": "简易拼图游戏",
            "device": "EPM1270T144C5",
            "family": "MAX II",
            "hdl": "VHDL-93",
            "tool": "Quartus II 9.1",
            "games": 3,
            "matrix": "8x8 dual-color",
        },
        "entities": entities,
        "packages": packages,
        "hierarchy": {
            "roots": [
                e for e, i in entities.items() if i["tier"] in ("top", "diag_top")
            ],
            "game_top": "puzzle_top",
            "children": children,
            "counts": {
                "entities": len(entities),
                "modules": sum(1 for i in entities.values() if i["tier"] == "module"),
                "diag_tops": sum(1 for i in entities.values() if i["tier"] == "diag_top"),
                "packages": len(packages),
                "files": len(vhd),
            },
        },
        "sim": parse_sim(),
        "build": parse_build(),
        "images": parse_images(),
        "errors": parse_errors(),
    }
    facts["hierarchy"]["tree"] = [
        {"root": r, "children": children.get(r, [])}
        for r in facts["hierarchy"]["roots"]
    ]
    facts["hierarchy"]["puzzle_top_instances"] = children.get("puzzle_top", [])
    return facts


def dump(facts: dict[str, Any]) -> str:
    return json.dumps(facts, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="抽取工程事实模型 facts/facts.json")
    ap.add_argument("--check", action="store_true", help="只校验是否过期")
    ap.add_argument("--stdout", action="store_true", help="打到标准输出")
    args = ap.parse_args()

    try:
        facts = build()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        die("解析失败: %r" % exc)

    text = dump(facts)

    if args.stdout:
        sys.stdout.write(text)
        return 0

    if args.check:
        if not os.path.exists(OUT_PATH):
            print("extract_facts: 缺少 facts/facts.json（请运行 python scripts/extract_facts.py）", file=sys.stderr)
            return 1
        cur = open(OUT_PATH, "r", encoding="utf-8").read()
        if cur != text:
            print(
                "extract_facts: facts/facts.json 已过期 —— 源码/仿真/编译事实有变，请重新生成",
                file=sys.stderr,
            )
            return 1
        print("extract_facts: OK（facts/facts.json 与源码一致）")
        return 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("extract_facts: 已写入 facts/facts.json")
    print(
        "  实体 %d（模块 %d / 诊断顶层 %d）+ 包 %d / 文件 %d"
        % (
            facts["hierarchy"]["counts"]["entities"],
            facts["hierarchy"]["counts"]["modules"],
            facts["hierarchy"]["counts"]["diag_tops"],
            facts["hierarchy"]["counts"]["packages"],
            facts["hierarchy"]["counts"]["files"],
        )
    )
    print(
        "  仿真 %d 个模块 / %d 条断言（通过 %d）"
        % (
            facts["sim"]["totals"]["modules"],
            facts["sim"]["totals"]["assertions"],
            facts["sim"]["totals"]["passed"],
        )
    )
    print("  引脚 %d / 图片 %d / 故障编号 %d" % (len(facts["build"]["pins"]), len(facts["images"]), len(facts["errors"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
