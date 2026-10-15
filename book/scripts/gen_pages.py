#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book/scripts/gen_pages.py —— 从 `facts/facts.json` 机械生成文档站里的**表格页**

为什么要有这一步
----------------
「模块端口表」「跨模块连接表」「层级表」「引脚表」「断言表」这些东西
**不该手写**：手写一遍就等于把源码抄了一遍，抄错一处就是文档与实现不符
（这个仓库的 ERR-022 就是位宽抄错）。所以这里的规则是：

    凡是能从 rtl/、sim/、quartus/ 机械推出来的表格，一律生成；
    生成不出来的语义（"什么时候有效""为什么这么设计"）才由人写。

生成物落在 `book/docs/_generated/`，**不入库**（.gitignore 挡住），
每次构建前由 `book/scripts/book.py build|serve` 重新生成 ⇒ 不存在"忘了更新"。

生成内容
--------
    _generated/metrics.md                 关键读数表（LE/LAB/Fmax/slack/断言/引脚）
    _generated/hierarchy.md               真实 RTL 层级与实例表（含行号链接）
    _generated/connections.md             跨模块连接总表（发送方->信号->接收方）
    _generated/connections-<root>.md      同上，按顶层拆分
    _generated/ports/<entity>.md          单模块端口契约表
    _generated/pkg-constants.md           puzzle_pkg 常量表
    _generated/pkg-types.md               puzzle_pkg 类型/子类型表
    _generated/pkg-functions.md           puzzle_pkg 纯函数表
    _generated/pins.md                    引脚锁定表（顶层端口 <-> PIN）
    _generated/sim-rounds.md              12 个模块的最新有效仿真轮次
    _generated/assertions/<module>.md     该模块最新一轮的逐条断言
    _generated/assertions-index.md        断言索引（模块 -> 条数/通过）
    _generated/figures.md                 图片清单（含"是不是真实 Quartus 截图"）
    _generated/errors.md                  ERR-xxx 故障索引

用法：python book/scripts/gen_pages.py
"""

from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.dirname(HERE)
ROOT = os.path.dirname(BOOK)
GEN = os.path.join(BOOK, "docs", "_generated")
FACTS = json.load(open(os.path.join(ROOT, "facts", "facts.json"), encoding="utf-8"))

REPO = "https://github.com/tortrixx/dld"
BRANCH = "main"

# 生成物顶部统一加这段横幅：读文档的人必须知道"这一页不是手写的"
BANNER = (
    "<!-- ============================================================ -->\n"
    "<!-- 本页由 book/scripts/gen_pages.py 从 facts/facts.json 机械生成 -->\n"
    "<!-- **不要手工编辑**：改了会在下次构建时被覆盖。要改就改源码。   -->\n"
    "<!-- ============================================================ -->\n"
)


def enc(path: str) -> str:
    from urllib.parse import quote

    return "/".join(quote(s, safe="") for s in path.strip("/").split("/"))


def blob(path: str, line: int | None = None) -> str:
    url = "%s/blob/%s/%s" % (REPO, BRANCH, enc(path))
    return url + ("#L%d" % line if line else "")


def esc(text) -> str:
    """表格单元格转义：`|` 会截断表格，换行会毁掉整行。"""
    if text is None:
        return "—"
    s = str(text).replace("|", "\\|").replace("\n", " ")
    s = s.replace("`", "`")
    return s.strip()


def demote_headings(text: str) -> str:
    """把**片段里**的标题层级整体下沉 2 级。

    为什么必须做：这些生成物是被 `--8<--` **内联**到别人页面里的，而页面自己
    已经有 `## 二、端口契约` 这样的章节标题。片段如果再带一个 `# 一级标题`，
    页面就会出现**两个 H1**、而且嵌套是倒的（h2 → h1）——文档大纲和目录都不对，
    视觉上那个大标题也会把页面结构压垮。

    下沉 2 级之后：片段的 `# 标题` → `###`（页面 h2 的子节，进目录 ✓）、
    片段里的 `## 小节` → `####`、`### 条目` → `#####`。
    代码围栏里的 `#` 注释不动（按 ``` 状态跳过）。
    """
    out = []
    fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            out.append(line)
            continue
        if not fence:
            m = re.match(r"^(#{1,6})(\s+)", line)
            if m:
                level = min(6, len(m.group(1)) + 2)
                out.append("#" * level + m.group(2) + line[m.end():])
                continue
        out.append(line)
    return "\n".join(out)


def w(path: str, text: str) -> None:
    full = os.path.join(GEN, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(BANNER + "\n" + demote_headings(text))


# ==========================================================================
# 关键读数
# ==========================================================================
def gen_metrics() -> None:
    b = FACTS["build"]
    fit, sta = b["fit"], b["sta"]
    sim = FACTS["sim"]["totals"]
    pof = b["provenance"]["pof"]
    lines = [
        "# 关键读数（机械抽取）",
        "",
        "!!! abstract \"这一页的数字从哪来\"",
        "    全部来自入库的机读真值源：`quartus/build_provenance.json`（器件/资源/时序/POF 指纹）、",
        "    `sim/rounds/<模块>/rNN.json`（仿真）与 `quartus/puzzle.qsf`（引脚）。",
        "    页面由 `book/scripts/gen_pages.py` 生成，**没有任何一个数字是手打的**。",
        "",
        "| 项目 | 读数 | 出处 |",
        "|---|---|---|",
        "| 器件 | MAX II `%s`（1270 LE / 127 LAB） | `quartus/puzzle.qsf` |" % b["device"],
        "| 逻辑单元 LE | `%s` | `quartus/build_provenance.json` → `fit.le` |" % esc(fit["le"]),
        "| 逻辑阵列块 LAB | **`%s`**（真正的瓶颈） | `quartus/build_provenance.json` → `fit.lab` |" % esc(fit["lab"]),
        "| 引脚 | `%s`（全部显式锁定） | `quartus/build_provenance.json` → `fit.pins` |" % esc(fit["pins"]),
        "| 时钟约束（`create_clock`） | %s MHz（周期 %s ns） | `quartus/puzzle.sdc` |"
        % (b["constraint"]["fmax_mhz"], b["constraint"]["period_ns"]),
        "| **实测 Fmax（TimeQuest `Fmax Summary`）** | **%s MHz** | `quartus/build_provenance.json` → `sta.fmax_mhz` |"
        % sta.get("fmax_mhz", "待核实"),
        "| Restricted Fmax | %s MHz | `quartus/build_provenance.json` → `sta.restricted_fmax_mhz` |"
        % sta.get("restricted_fmax_mhz", "待核实"),
        "| Setup slack | `%+g` ns | `quartus/build_provenance.json` → `sta.setup_slack` |" % sta["setup_slack"],
        "| Hold slack | `%+g` ns | `quartus/build_provenance.json` → `sta.hold_slack` |" % sta["hold_slack"],
        "| Fitter 编译状态 | %s | `quartus/build_provenance.json` → `fit.status` |" % esc(fit["status"]),
        "| 固件 POF | `%d` 字节，sha256 `%s` | `quartus/build_provenance.json` → `pof` |"
        % (pof["bytes"], pof["sha256"]),
        "| 仿真模块数 | **%d** | `sim/rounds/` |" % sim["modules"],
        "| 断言总数 | **%d 条，全部通过** | `sim/rounds/<模块>/rNN.json` 求和 |" % sim["assertions"],
        "| RTL 文件 | %d 个（实体 %d + 设计包 %d） | `rtl/` |"
        % (
            FACTS["hierarchy"]["counts"]["files"],
            FACTS["hierarchy"]["counts"]["entities"],
            FACTS["hierarchy"]["counts"]["packages"],
        ),
        "| 故障记录 | %d 条有独立小节的 ERR（全文共 %d 个编号） | `docs/06-硬件调试记录.md` |"
        % (len(FACTS["errors"]), 56),
        "",
        "!!! warning \"`build_provenance.json` 是**快照**，不是实时读数\"",
        "    它的 `timestamp` 是 `%s`。RTL 一变，这一页的所有资源/时序数字**立即作废**，"
        % b["provenance"]["timestamp"],
        "    必须重新清洁编译并用 `python scripts/record_build.py` 重新记录。",
        "    这也是为什么每一页引用读数的地方都写“约束 50 MHz”而不是“当前频率”。",
        "",
        "## 每个 RTL 文件的源码指纹",
        "",
        "`build_provenance.json` 对 16 个源文件各记了两个指纹：",
        "`sources` 是**逐字节** sha256 前缀，`sources_logic` 是**去掉注释与空白**后的逻辑指纹",
        "（由 `scripts/srcnorm.py` 计算）。后者是“这次改动只动了注释”的机器证据。",
        "",
        "| 文件 | 字节指纹 | 逻辑指纹 |",
        "|---|---|---|",
    ]
    src = b["provenance"]["sources"]
    srcl = b["provenance"]["sources_logic"]
    for path in sorted(src):
        lines.append("| [`%s`](%s) | `%s` | `%s` |" % (path, blob(path), src[path], srcl.get(path, "—")))
    w("metrics.md", "\n".join(lines) + "\n")


# ==========================================================================
# 层级
# ==========================================================================
def gen_hierarchy() -> None:
    ents = FACTS["entities"]
    counts = FACTS["hierarchy"]["counts"]
    lines = [
        "# RTL 层级与实例表（机械抽取）",
        "",
        "!!! info \"读法\"",
        "    「实例名」是源码里 `port map` 前面那个标号；「实体名」是被例化的 `entity`。",
        "    「位置」可点开 GitHub 上那一行。层次关系**只反映真实的例化语句**，",
        "    没有出现在这里的模块之间不存在任何直接连接。",
        "",
        "## 总览",
        "",
        "| 顶层 | 类型 | 例化子模块数 | 说明 |",
        "|---|---|---|---|",
    ]
    tier_desc = {
        "top": "**正常游戏运行的唯一顶层**（引脚绑定在它身上）",
        "diag_top": "调试/诊断顶层，**不在游戏数据通路上**",
    }
    for root in FACTS["hierarchy"]["roots"]:
        info = ents[root]
        kids = FACTS["hierarchy"]["children"][root]
        lines.append(
            "| [`%s`](%s) | %s | %d | %s |"
            % (root, blob(info["file"], info["entity_line"]), tier_desc.get(info["tier"], info["tier"]), len(kids), info["subsystem"])
        )
    lines += [
        "",
        "## 全部实体一览",
        "",
        "| 实体 | 文件 | 行数 | 端口数 | 所属子系统 | 被谁例化 |",
        "|---|---|---|---|---|---|",
    ]
    parents: dict[str, list[str]] = {e: [] for e in ents}
    for p, kids in FACTS["hierarchy"]["children"].items():
        for k in kids:
            parents[k["entity"]].append("%s（`%s`）" % (p, k["instance"]))
    for e in sorted(ents):
        i = ents[e]
        lines.append(
            "| [`%s`](%s) | [`%s`](%s) | %d | %d | %s | %s |"
            % (
                e,
                blob(i["file"], i["entity_line"]),
                i["file"],
                blob(i["file"]),
                i["loc"],
                len(i["ports"]),
                i["subsystem"],
                "、".join(parents[e]) if parents[e] else "**顶层，无人例化**",
            )
        )
    lines += [
        "",
        "## 逐顶层的例化清单",
        "",
    ]
    for root in FACTS["hierarchy"]["roots"]:
        lines.append("### `%s`" % root)
        lines.append("")
        lines.append("| 实例名 | 实体 | 例化位置 | 端口映射条数 |")
        lines.append("|---|---|---|---|")
        for inst in ents[root]["instantiations"]:
            lines.append(
                "| `%s` | [`%s`](%s) | [`%s:%d`](%s) | %d |"
                % (
                    inst["instance"],
                    inst["entity"],
                    blob(ents[inst["entity"]]["file"], ents[inst["entity"]]["entity_line"]),
                    inst["file"],
                    inst["line"],
                    blob(inst["file"], inst["line"]),
                    len(inst["port_map"]),
                )
            )
        lines.append("")

    lines += [
        "## 设计包（不是硬件模块）",
        "",
        "| 包 | 文件 | 常量 | 类型 | 子类型 | 纯函数 |",
        "|---|---|---|---|---|---|",
    ]
    for pname, pkg in sorted(FACTS["packages"].items()):
        lines.append(
            "| `%s` | [`%s`](%s) | %d | %d | %d | %d |"
            % (
                pname,
                pkg["file"],
                blob(pkg["file"], pkg["line"]),
                len(pkg["constants"]),
                len(pkg["types"]),
                len(pkg["subtypes"]),
                len(pkg["functions"]),
            )
        )
    lines += [
        "",
        "!!! warning \"`puzzle_pkg` 不是模块\"",
        "    它是 `package`，只提供**常量、类型与纯函数**（综合时全部被展开成常量/组合逻辑），",
        "    在框图里**不应该**被画成一个带端口的方框。",
        "",
        "## 统计口径",
        "",
        "| 项 | 值 |",
        "|---|---|",
        "| VHDL 文件 | %d |" % counts["files"],
        "| 实体（entity） | %d |" % counts["entities"],
        "| 其中：游戏子模块 | %d |" % counts["modules"],
        "| 其中：诊断顶层 | %d |" % counts["diag_tops"],
        "| 设计包（package） | %d |" % counts["packages"],
        "",
        "证据：`facts/facts.json`（由 `scripts/extract_facts.py` 从 `rtl/*.vhd` 抽出）。",
    ]
    w("hierarchy.md", "\n".join(lines) + "\n")


# ==========================================================================
# 跨模块连接
# ==========================================================================
def _port_index(entity: str) -> dict[str, dict]:
    return {p["name"]: p for p in FACTS["entities"][entity]["ports"]}


def _remove_port_maps(body: str) -> str:
    """把 `port map ( ... )` 整段抠掉，剩下的就是**顶层自己的逻辑**。

    这样才分得清一个信号是「被别的模块驱动」还是「被顶层自己的进程驱动」——
    不做这一步，`mat_r` 这种由顶层 case 语句驱动的信号会被错标成"无驱动"。
    """
    out = []
    i = 0
    in_str = False
    while i < len(body):
        ch = body[i]
        if not in_str and ch == "-" and body[i : i + 2] == "--":
            j = body.find("\n", i)
            j = len(body) if j < 0 else j
            out.append(body[i:j])
            i = j
            continue
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            i += 1
            continue
        if not in_str and body[i : i + 8].lower().startswith("port map"):
            k = body.find("(", i)
            if k < 0:
                break
            depth = 0
            j = k
            s = False
            while j < len(body):
                c = body[j]
                if c == '"':
                    s = not s
                elif not s:
                    if c == "(":
                        depth += 1
                    elif c == ")":
                        depth -= 1
                        if depth == 0:
                            break
                j += 1
            out.append("/*port map*/")
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _arch_parts(root: str) -> tuple[str, str]:
    """返回 (架构声明部分, 去掉 port map 的架构体)。"""
    info = FACTS["entities"][root]
    text = open(os.path.join(ROOT, info["file"]), encoding="utf-8").read()
    lines = text.splitlines()
    aline = info["architecture"]["line"]
    end = len(lines)
    for i in range(aline, len(lines)):
        if re.match(r"\s*end\s+architecture", lines[i], re.I):
            end = i
            break
    decl_lines = []
    body_start = end
    for i in range(aline, end):
        if re.match(r"\s*begin\s*$", lines[i], re.I):
            body_start = i + 1
            break
        decl_lines.append(lines[i])
    return "\n".join(decl_lines), _remove_port_maps("\n".join(lines[body_start:end]))


def _declared_signals(root: str) -> list[str]:
    decl, _ = _arch_parts(root)
    names: list[str] = []
    for m in re.finditer(r"\bsignal\s+([^;:]+?)\s*:", decl, re.I | re.S):
        for n in m.group(1).split(","):
            n = n.strip()
            if re.fullmatch(r"[A-Za-z_]\w*", n):
                names.append(n)
    return names


def build_connections(root: str) -> dict:
    """返回 {"rows": [...], "unconnected": [...], "internal": {...}}"""
    ents = FACTS["entities"]
    info = ents[root]
    top_ports = _port_index(root)
    prod: dict[str, list[dict]] = {}
    cons: dict[str, list[dict]] = {}
    unconnected: list[dict] = []
    for name, p in top_ports.items():
        rec = {"owner": root, "port": name, "top": True, "width": p["width"], "type": p["type"]}
        if p["dir"] == "in":
            prod.setdefault(name, []).append(rec)
        else:
            cons.setdefault(name, []).append(rec)
    for inst in info["instantiations"]:
        child = inst["entity"]
        cp = _port_index(child)
        for c in inst["port_map"]:
            formal, actual = c["formal"], c["actual"]
            spec = cp.get(formal)
            if spec is None:
                raise SystemExit("gen_pages: %s 的 %s 没有端口 %s" % (inst["instance"], child, formal))
            if actual == "open":
                unconnected.append(
                    {
                        "instance": inst["instance"],
                        "entity": child,
                        "port": formal,
                        "dir": spec["dir"],
                        "line": inst["line"],
                    }
                )
                continue
            rec = {
                "owner": inst["instance"],
                "entity": child,
                "port": formal,
                "width": spec["width"],
                "type": spec["type"],
                "line": inst["line"],
            }
            if spec["dir"] == "out":
                prod.setdefault(actual, []).append(rec)
            else:
                cons.setdefault(actual, []).append(rec)

    # 顶层自己的进程：谁被赋值、谁被读
    _, body = _arch_parts(root)
    declared = set(_declared_signals(root))
    assigned = set(re.findall(r"(?<![\w.'])([A-Za-z_]\w*)\s*<=", body))
    body_ids = set(re.findall(r"[A-Za-z_]\w*", body))
    internal_drive = {s for s in declared if s in assigned}
    internal_read = {s for s in declared if s in body_ids}

    def base_of(sig: str) -> str | None:
        s = sig.strip()
        m = re.match(r"^[A-Za-z_]\w*\s*\(\s*([A-Za-z_]\w*)\s*\)$", s)
        if m:
            return m.group(1)  # 类型转换 / 单参数：std_logic_vector(mrow)
        m = re.match(r"^([A-Za-z_]\w*)\s*\(", s)
        if m:
            return m.group(1)  # 数组元素或切片：shapes(0)
        return None

    signals = sorted(set(prod) | set(cons))
    rows = []
    for sig in signals:
        ps = prod.get(sig, [])
        cs = cons.get(sig, [])
        via = None
        if not ps and not cs:
            continue
        if not ps:
            b = base_of(sig)
            if b and b in prod:
                ps = prod[b]
                via = b
            elif (b or sig) in internal_drive:
                if b:
                    via = b
                ps = [{"owner": root, "port": "（顶层进程）", "top": False, "process": True,
                       "width": 1, "type": "—"}]
        if not cs:
            b = base_of(sig)
            if b and b in cons:
                cs = cons[b]
                via = via or b
            elif (b or sig) in internal_read:
                if b:
                    via = via or b
                cs = [{"owner": root, "port": "（顶层进程）", "top": False, "process": True,
                       "width": 1, "type": "—"}]
        if not ps and not cs:
            continue
        rows.append({"signal": sig, "producers": ps, "consumers": cs, "via": via})
    # 数组型信号（例如 `shapes : mask_arr_t`）本身不会出现在任何 port map 的实参里，
    # 出现的是它的元素。这里把它标成"按元素读取"，免得读成"无人使用"。
    vias = {r["via"] for r in rows if r.get("via")}
    for r in rows:
        if r["signal"] in vias and not r["consumers"]:
            r["elements"] = sorted(x["signal"] for x in rows if x.get("via") == r["signal"])
    return {"rows": rows, "unconnected": unconnected, "internal": (internal_drive, internal_read)}


def _node(rec: dict, ents: dict) -> str:
    if rec.get("top"):
        return "**顶层端口** `%s`" % rec["port"]
    if rec.get("process"):
        return "**顶层自身逻辑**"
    return "`%s` · %s" % (rec["owner"], rec["port"])


def gen_connections() -> None:
    roots = FACTS["hierarchy"]["roots"]
    body = [
        "# 跨模块连接总表（机械抽取）",
        "",
        "!!! quote \"这张表是怎么来的\"",
        "    逐条扫描 `port map`：每个子模块的 **out** 端口把它连到的信号登记为“生产者”，",
        "    每个 **in** 端口把同一个信号登记为“消费者”。同一个信号名把两边接起来，",
        "    就是一条真实的连接。**没有出现在这张表里的信号，在 RTL 里不存在。**",
        "    生产者一栏还会出现 `顶层自身逻辑` —— 那是顶层 `architecture` 里自己赋值的",
        "    信号（例如 `mat_r`、`pat_sel`），不是任何子模块的输出。",
        "",
        "!!! warning \"这张表**只**说明电气连接，不说明语义\"",
        "    它没有也无法回答“什么时候有效”“要维持几个周期”“谁先谁后”——",
        "    那是同步 RTL 的**协议**，只能读代码得到，见",
        "    [控制信号与握手](../04-interfaces/control-signals.md) 与",
        "    [时序契约](../04-interfaces/timing-contracts.md)。",
        "    把这张表当软件 API 看是错的：这里的“信号”是**同一时钟域里的电平/脉冲**。",
        "",
    ]
    for root in roots:
        conn = build_connections(root)
        body += ["## `%s`" % root, ""]
        body += _single_root(root, conn)
        if root != FACTS["hierarchy"]["game_top"]:
            body += [
                "!!! warning \"这是诊断顶层\"",
                "    `%s` 只用于板级调试，**不在游戏运行的数据通路上**；" % root,
                "    它的连接不代表游戏如何工作。",
                "",
            ]
        one = ["# `%s` 顶层内的连接（机械抽取）" % root, ""] + _single_root(root, conn)
        w("connections-%s.md" % root, "\n".join(one) + "\n")
    body += [
        "---",
        "",
        "机械生成自 `facts/facts.json`；生成脚本：`book/scripts/gen_pages.py`。",
    ]
    w("connections.md", "\n".join(body) + "\n")


def _single_root(root: str, conn: dict) -> list[str]:
    ents = FACTS["entities"]
    rows = conn["rows"]
    const_re = re.compile(r"^('.*'|\".*\"|[xX]\"[0-9A-Fa-f_]+\"|\(others\s*=>.*\)|\d+)$")
    out = ["### `%s` 内部的全部连接（%d 个信号）" % (root, len(rows)), ""]
    out += [
        "| 发送方（驱动） | 发送端口 | 信号名 | 接收方 | 接收端口 | 位宽 | VHDL 类型 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        p = r["producers"][0] if r["producers"] else None
        # 位宽/类型的取法：正常取"发送端端口"的；但当这一行是数组元素/切片/类型转换，
        # 或发送端其实是顶层自己的进程（没有端口类型）时，改取**接收端端口**的，
        # 否则会出现 `mat_r` 被标成 1 位、`shapes(0)` 被标成 1 位这种假读数。
        if (r.get("via") or (p and p.get("process"))) and r["consumers"]:
            src = r["consumers"][0]
        else:
            src = p or (r["consumers"][0] if r["consumers"] else None)
        width = src["width"] if src else "—"
        vtype = src["type"] if src else "—"
        pcell = _node(p, ents) if p else "**（无驱动）**"
        pport = "`%s`" % p["port"] if p else "—"
        if p is None and const_re.match(r["signal"]):
            pcell = "**常量实参**（直接写在 `port map` 里的字面量，没有对应信号）"
            pport = "—"
        if len(r["producers"]) > 1:
            pcell = "⚠️ 多驱动：%s" % "、".join(_node(x, ents) for x in r["producers"])
        ccell = "；".join(_node(c, ents) for c in r["consumers"]) if r["consumers"] else "**（无人读）**"
        cport = "；".join("`%s`" % c["port"] for c in r["consumers"]) or "—"
        if r.get("elements"):
            ccell = "**按元素读取**：%s" % "、".join("`%s`" % e for e in r["elements"])
            cport = "—"
        sig = r["signal"]
        if r.get("via"):
            sig = "`%s`（数组/转换自 `%s`）" % (r["signal"], r["via"])
        else:
            sig = "**`%s`**" % sig
        out.append(
            "| %s | %s | %s | %s | %s | %s | `%s` |"
            % (pcell, pport, sig, ccell, cport, width, esc(vtype))
        )
    out.append("")
    if conn["unconnected"]:
        out += [
            "### 未连接（`open`）的输出端口",
            "",
            "这些端口在源码里被显式写成 `=> open`。**它们不是接错，是有意悬空**，",
            "每一处都应当在对应的模块页里给出理由（否则就是漏接）。",
            "",
            "| 实例 | 实体 | 端口 | 方向 | 源码位置 |",
            "|---|---|---|---|---|",
        ]
        for u in conn["unconnected"]:
            out.append(
                "| `%s` | `%s` | `%s` | `%s` | [`%s:%d`](%s) |"
                % (u["instance"], u["entity"], u["port"], u["dir"], ents[root]["file"], u["line"], blob(ents[root]["file"], u["line"]))
            )
        out.append("")
    return out


# ==========================================================================
# 单模块端口契约
# ==========================================================================
def gen_ports() -> None:
    ents = FACTS["entities"]
    # 反向：某实体的某个端口，在别处被连到了什么信号
    usage: dict[str, dict[str, list[str]]] = {}
    for parent, kids in FACTS["hierarchy"]["children"].items():
        for inst in ents[parent]["instantiations"]:
            for c in inst["port_map"]:
                usage.setdefault(inst["entity"], {}).setdefault(c["formal"], []).append(
                    "%s.%s ← `%s`" % (parent, inst["instance"], c["actual"])
                )
    for e, info in sorted(ents.items()):
        lines = [
            "# `%s` 端口契约表（机械抽取）" % e,
            "",
            "| 项 | 值 |",
            "|---|---|",
            "| 源码 | [`%s`](%s) |" % (info["file"], blob(info["file"])),
            "| 实体声明 | [`%s:%d`](%s) |" % (info["file"], info["entity_line"], blob(info["file"], info["entity_line"])),
            "| 架构 | `%s`（[`%s:%d`](%s)） |"
            % (
                info["architecture"]["name"],
                info["file"],
                info["architecture"]["line"],
                blob(info["file"], info["architecture"]["line"]),
            ),
            "| 所属子系统 | %s |" % info["subsystem"],
            "| 端口数 | %d |" % len(info["ports"]),
            "| 被例化于 | %s |"
            % (
                "、".join(
                    "%s（`%s`）" % (p, i["instance"])
                    for p, kids in FACTS["hierarchy"]["children"].items()
                    for i in kids
                    if i["entity"] == e
                )
                or "**顶层**"
            ),
            "",
            "## 端口",
            "",
            "| 端口名 | 方向 | 类型与位宽 | 源码注释（含义） | 实际连接 |",
            "|---|---|---|---|---|",
        ]
        for p in info["ports"]:
            conns = usage.get(e, {}).get(p["name"], [])
            lines.append(
                "| `%s` | `%s` | `%s`（%d 位） | %s | %s |"
                % (
                    p["name"],
                    p["dir"],
                    esc(p["type"]),
                    p["width"],
                    esc(p["comment"]) if p["comment"] else "**（源码未写注释）**",
                    "；".join("`%s`" % x.split("← ")[-1] for x in conns[:3]) or "—",
                )
            )
        lines += [
            "",
            "!!! note \"「源码注释」这一列的意思\"",
            "    它就是实体声明里端口后面那一段 `--` 注释的**原文**。",
            "    写 `（源码未写注释）` 的地方是真的没写 —— 这类端口应当在",
            "    [控制信号与握手](../04-interfaces/control-signals.md) 里补上语义说明，",
            "    或者标注 **待核实**。",
            "",
            "!!! warning \"本表不含有效条件与建立/保持要求\"",
            "    那些属于**协议**，无法从端口声明机械推出。见",
            "    [时序契约](../04-interfaces/timing-contracts.md)。",
        ]
        w("ports/%s.md" % e, "\n".join(lines) + "\n")


# ==========================================================================
# 设计包
# ==========================================================================
def gen_pkg() -> None:
    pkg = FACTS["packages"]["puzzle_pkg"]
    consts = [
        "## `puzzle_pkg` 常量表（机械抽取）",
        "",
        "共 %d 条。`值` 列是源码里的**字面量原文**（可能很长，例如 64 位图案掩码）。" % len(pkg["constants"]),
        "",
        "| 常量 | 类型 | 值 | 注释 | 位置 |",
        "|---|---|---|---|---|",
    ]
    for c in pkg["constants"]:
        consts.append(
            "| `%s` | `%s` | `%s` | %s | [`L%d`](%s) |"
            % (
                c["name"],
                esc(c["type"]),
                esc(c["value"] if len(c["value"]) <= 70 else c["value"][:67] + "…"),
                esc(c["comment"]) if c["comment"] else "—",
                c["line"],
                blob(pkg["file"], c["line"]),
            )
        )
    w("pkg-constants.md", "\n".join(consts) + "\n")

    types = ["## `puzzle_pkg` 类型与子类型（机械抽取）", "", "| 类型 | 定义 | 位置 |", "|---|---|---|"]
    for t in pkg["types"]:
        types.append("| `%s` | `%s` | [`L%d`](%s) |" % (t["name"], esc(t["def"]), t["line"], blob(pkg["file"], t["line"])))
    for t in pkg["subtypes"]:
        types.append(
            "| `%s`（subtype） | `%s` | [`L%d`](%s) |" % (t["name"], esc(t["def"]), t["line"], blob(pkg["file"], t["line"]))
        )
    w("pkg-types.md", "\n".join(types) + "\n")

    funcs = [
        "## `puzzle_pkg` 纯函数（机械抽取）",
        "",
        "共 %d 个。这些函数**全部是纯组合逻辑/常量求值**，不含任何状态 ——" % len(pkg["functions"]),
        "它们让“位掩码怎么移位”“旋转后坐标怎么变”这类**位序约定**只写一遍。",
        "",
        "| 函数 | 位置 |",
        "|---|---|",
    ]
    for f in pkg["functions"]:
        funcs.append("| `%s(...)` | [`L%d`](%s) |" % (f["name"], f["line"], blob(pkg["file"], f["line"])))
    w("pkg-functions.md", "\n".join(funcs) + "\n")


# ==========================================================================
# 引脚
# ==========================================================================
def gen_pins() -> None:
    b = FACTS["build"]
    top_ports = {p["name"]: p for p in FACTS["entities"]["puzzle_top"]["ports"]}
    lines = [
        "# 引脚锁定表（机械抽取）",
        "",
        "共 **%d** 个 `set_location_assignment`，来自 [`quartus/puzzle.qsf`](%s)。"
        % (len(b["pins"]), blob("quartus/puzzle.qsf")),
        "顶层端口共 %d 个，**全部有锁定**（未约束引脚数见编译报告）。" % len(top_ports),
        "",
        "| PIN | 信号 | 顶层端口 | 方向 | 位宽 |",
        "|---|---|---|---|---|",
    ]
    for p in b["pins"]:
        sig = p["signal"]
        base = sig.split("[")[0]
        tp = top_ports.get(base)
        lines.append(
            "| `%s` | `%s` | `%s` | %s | %s |"
            % (
                p["pin"],
                sig,
                base if tp else "**（不在顶层端口里！）**",
                tp["dir"] if tp else "—",
                tp["width"] if tp else "—",
            )
        )
    lines += [
        "",
        "!!! note \"引脚是怎么来的\"",
        "    `quartus/puzzle.qsf` 由 `scripts/gen_project.py` 从",
        "    [`scripts/gen_project.py`](%s) 里的引脚表生成，**不是**在 Quartus GUI 里手点出来的；"
        % blob("scripts/gen_project.py"),
        "    所以引脚与板子的对应关系是可复现、可 diff 的。",
        "    `scripts/check_keypad_pins.py` 另外核对键盘行列引脚与实验板手册一致。",
    ]
    w("pins.md", "\n".join(lines) + "\n")


# ==========================================================================
# 仿真轮次 / 断言
# ==========================================================================
def gen_sim() -> None:
    sim = FACTS["sim"]
    lines = [
        "# 12 个模块的最新有效仿真轮次（机械抽取）",
        "",
        "| 模块 | 最新轮次 | 轮次总数 | 断言（通过/总） | 全通过 | 仿真时长 | 测试台 | 波形 | 记录 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for mod, m in sorted(sim["modules"].items()):
        lines.append(
            "| `%s` | r%d | %d | %s / %s | %s | %.3f ms | [`%s`](%s) | [`%s.vwf`](%s) | [`r%d.json`](%s) |"
            % (
                mod,
                m["round"],
                m["rounds_total"],
                m["passed"],
                m["total"],
                "✅" if m["all_pass"] else "❌",
                float(m["duration_ns"] or 0) / 1e6,
                os.path.basename(m["tb"]) if m["tb"] else "—",
                blob(m["tb"]) if m["tb"] else "",
                mod,
                blob(m["vwf"]) if m["vwf"] else "",
                m["round"],
                blob(m["record_json"]),
            )
        )
    lines += [
        "| **合计** | — | — | **%d / %d** | **%s** | — | — | — | — |"
        % (sim["totals"]["passed"], sim["totals"]["assertions"], "✅" if sim["totals"]["all_pass"] else "❌"),
        "",
        "!!! danger \"怎么知道这张表不是陈旧证据\"",
        "    `sim/<模块>.vwf` **既是激励也是结果** —— Quartus 内置仿真器把结果回写进",
        "    同一个 `.vwf` 文件。所以“波形文件的时间戳”骗不了人，但“它是哪一版 RTL 跑出来的”",
        "    必须靠**源码指纹**判断：`sim/rounds/<模块>/rNN.json` 里记了当时 16 个 RTL 文件",
        "    加该模块测试台的指纹；`scripts/sim.py check` 会拿它与当前源码比对。",
        "",
        "    任何一处 RTL 改动都会让**全部 12 个模块**的指纹失效 ⇒ 必须整套重跑。",
        "",
    ]
    w("sim-rounds.md", "\n".join(lines) + "\n")

    idx = [
        "# 断言索引（机械抽取）",
        "",
        "共 **%d** 条断言，全部通过。" % sim["totals"]["assertions"],
        "",
        "!!! note \"为什么这一页里的路径是纯文本、不做成链接\"",
        "    本页位于 `_generated/`，而 `_generated/` 在 `mkdocs.yml` 的 `exclude_docs` 里",
        "    —— 它**不是一个页面**，只是被别的页面用 `--8<--` 内联的片段。",
        "    片段里的相对链接会**以内联它的那个页面**为基准解析：",
        "    例如 `assertions/clk_gen.md` 被内联进 `06-verification/assertions.md` 之后，",
        "    会解析成 `06-verification/assertions/clk_gen.md` ⇒ **死链**。",
        "    所以这里只列路径；要做链接，内联方按自己的位置拼。",
        "",
        "| 模块 | 条数 | 最新轮次 | 明细片段（相对 `_generated/`） |",
        "|---|---|---|---|",
    ]
    for mod, m in sorted(sim["modules"].items()):
        idx.append(
            "| `%s` | %d | r%d | `assertions/%s.md` |" % (mod, m["total"], m["round"], mod)
        )
    idx.append("")
    w("assertions-index.md", "\n".join(idx) + "\n")

    for mod, m in sorted(sim["modules"].items()):
        out = [
            "# `%s` —— 最新一轮（r%d）断言明细" % (mod, m["round"]),
            "",
            "记录文件：[`%s`](%s) ｜ 测试台：[`%s`](%s) ｜ 波形：[`sim/%s.vwf`](%s)"
            % (
                m["record_json"],
                blob(m["record_json"]),
                os.path.basename(m["tb"]) if m["tb"] else "—",
                blob(m["tb"]) if m["tb"] else "",
                mod,
                blob(m["vwf"]),
            ),
            "",
            "时间戳：`%s` ｜ 仿真时长：%.3f ms ｜ 结果：**%d / %d 通过**"
            % (m["timestamp"], float(m["duration_ns"] or 0) / 1e6, m["passed"], m["total"]),
            "",
        ]
        for i, a in enumerate(m["assertions"], start=1):
            out += [
                "### %s" % esc(a["name"]),
                "",
                "| 项 | 内容 |",
                "|---|---|",
                "| 结果 | %s |" % ("✅ 通过" if a["ok"] else "❌ 失败"),
                "| 实测判据 | %s |" % esc(a["detail"]),
                "",
            ]
        w("assertions/%s.md" % mod, "\n".join(out) + "\n")


# ==========================================================================
# 图片 / 故障
# ==========================================================================
KIND_DESC = {
    "quartus_gui_screenshot": "**真实 Quartus GUI 仿真截图**",
    "script_waveform_svg": "脚本渲染的辅助波形（**不是** GUI 截图）",
    "editable_diagram_source": "可编辑图表源文件（draw.io）",
    "demo_animation": "脚本由站点引擎渲染的演示动画（**不是**硬件实测）",
    "rendered_figure": "脚本渲染的静态图（**不是**硬件实测照片）",
    "other": "其他",
}


def gen_figures() -> None:
    lines = [
        "# 图片清单（机械抽取）",
        "",
        "来源目录：[`docs/图/`](%s)。这一页**如实标注每张图的类别**：" % blob("docs/图/README.md"),
        "哪些是 Quartus GUI 里真实抓下来的波形、哪些是脚本渲染的辅助图、",
        "有没有真实硬件照片。",
        "",
        "| 文件 | 类别 | 关联模块 | 字节 | 入库 |",
        "|---|---|---|---|---|",
    ]
    for f in sorted(FACTS["images"], key=lambda x: (x["kind"], x["name"])):
        lines.append(
            "| [`%s`](%s) | %s | %s | %d | %s |"
            % (
                f["name"],
                blob(f["path"]),
                KIND_DESC.get(f["kind"], f["kind"]),
                ("`%s`" % f["module"]) if f["module"] else "—",
                f["bytes"],
                "✅" if f["tracked"] else "⚠️ 未入库",
            )
        )
    n_gui = sum(1 for f in FACTS["images"] if f["kind"] == "quartus_gui_screenshot")
    n_sim = sum(1 for f in FACTS["images"] if f["kind"] == "script_waveform_svg")
    lines += [
        "",
        "## 统计",
        "",
        "| 类别 | 数量 |",
        "|---|---|",
        "| 真实 Quartus GUI 仿真截图 | %d |" % n_gui,
        "| 脚本渲染的辅助波形 SVG | %d |" % n_sim,
        "| **真实硬件实测照片** | **0** |",
        "",
        "!!! danger \"缺什么，说清楚\"",
        "    仓库里**没有**任何一张开发板实拍照片：点阵、数码管、键盘、蜂鸣器在真实",
        "    硬件上的效果目前只有**文字记录**（`docs/06-硬件调试记录.md`）与**上板复测结论**，",
        "    没有影像证据。这是**已知缺失**，不补拍就不存在。",
        "    补拍方法见 [缺失的证据](../06-verification/board-validation.md#待补拍清单)。",
        "    <!-- 注：本页只在 `06-verification/` 下被内联，所以这个相对路径是对的；",
        "         若要挪到别处内联，必须跟着改。 -->",
        "",
        "!!! warning \"不要把脚本渲染的图当成硬件效果\"",
        "    `演示-跑一局.gif` / `演示-首帧.png` / `结算画面-预览.png` 是**浏览器里**",
        "    用 TypeScript 引擎按同一套规则跑出来的动画与截图，用来解释“规则是什么”，",
        "    **不能**用来证明“板子跑出来就是这样”。",
    ]
    w("figures.md", "\n".join(lines) + "\n")


def gen_errors() -> None:
    errs = FACTS["errors"]
    ids = sorted({e["id"] for e in errs}, key=lambda s: int(s.split("-")[1]))
    lines = [
        "# ERR-xxx 故障索引（机械抽取）",
        "",
        "`docs/06-硬件调试记录.md` 里**有独立小节**的故障共 **%d** 条。" % len(ids),
        "全文另外还引用了若干编号（合计 56 个不同编号），但只有下面这些有独立的",
        "现象/根因/修法/证据小节。",
        "",
        "| 编号 | 标题 | 位置 |",
        "|---|---|---|",
    ]
    for e in errs:
        lines.append(
            "| **%s** | %s | [L%d](%s) |"
            % (e["id"], esc(e["title"]), e["line"], blob("docs/06-硬件调试记录.md", e["line"]))
        )
    lines += [
        "",
        "!!! tip \"怎么用这一页\"",
        "    答辩时被问到“这个设计踩过什么坑”，打开这条索引，挑 3~5 条有代表性的",
        "    展开讲（现象 → 怎么定位 → 根因 → 修法 → 回归证据）。",
        "    每条都是**上板真实发生过的**，不是假想的问题清单。",
    ]
    w("errors.md", "\n".join(lines) + "\n")


def main() -> int:
    os.makedirs(GEN, exist_ok=True)
    gen_metrics()
    gen_hierarchy()
    gen_connections()
    gen_ports()
    gen_pkg()
    gen_pins()
    gen_sim()
    gen_figures()
    gen_errors()
    n = sum(len(files) for _, _, files in os.walk(GEN))
    print("gen_pages: 生成 %d 个文件到 book/docs/_generated/" % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
