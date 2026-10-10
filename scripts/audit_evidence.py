#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_evidence.py —— **一条命令跑完"对抗性审查"**

【这个工具从哪来】
    2026-10-10 会话结束时，作者对**自己写的文档**做了一次人工对抗性审查，抓出 ERR-051/ERR-052
    与 7 条注释漂移（见 `docs/06` §17.12/§17.13）。那次审查很值钱，但**全靠人肉**：
    要逐模块比"绿证时间戳 vs RTL mtime"、要把音效码表在四个文件间对账、要回读
    `fit.rpt`/`sta.rpt` 的数字、还要核"文档里写的数字是不是当前值"。
    ⇒ 本工具把那次审查**变成一条可重复执行的命令**，下次改动后跑一遍就知道证据链有没有破。

【它检查什么】（每一项都对应过去真实踩过的坑）
    A 仿真证据时效性（**陈旧绿**，ERR-022）：最新一轮"全过"的绿证，是否覆盖了当前 RTL/tb？
        · 新轮次记录带 `sources`（git blob 哈希）→ **逐文件精确比对**（这是首选判据）
        · 老轮次记录没有 `sources` → 退化为"轮次时间戳 vs 文件 mtime"（会给出 ⚠ 提示）
    B 断言统计：各模块最新一轮的通过数/总数、是否有模块的绿证不是"全过"。
    C 音效码表一致性（ERR-022 的另一半）：`puzzle_pkg.SND_*` ↔ `buzzer_ctrl` 的 `case` 分支
      ↔ `game_fsm` 实际发出的码 ↔ `tb_buzzer_ctrl` 的 MEL 表 ↔ 三首 BGM 的拼线取值。
      **游戏能发出、而 buzzer 没有查表分支的码 = 该场景会意外静音**（这类漂移必须报 FAIL）。
    D 综合读数：`fit.rpt` 的 LE / LAB / 引脚 / Fitter Status + `sta.rpt` 的最差 setup/hold slack，
      并判是否满足 `.sdc` 的 50 MHz 约束、LAB 是否已满（**装不下要先分清卡 LE 还是 LAB**，ERR-046）。
    E 固件一致性：`puzzle.pof` 的生成时间是否**晚于**最新的 RTL 改动（否则板上跑的不是仓库里的逻辑）。
    F 仓库状态：HEAD / 与 `origin/main` 的差距 / 工作树是否干净。
    G 文档数字对齐：文档里提到的 LE / LAB / slack / SEED 是否**包含当前实测值**
      （"注释里的字面量会自己长腿" —— 收尾审查的第 25 条教训）。

【用法】
    python scripts/audit_evidence.py            # 只读；有 FAIL 则退出码 1
    python scripts/audit_evidence.py --strict   # WARN 也算失败
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import sim  # noqa: E402  —— 复用 git blob 哈希与 tb 装载（仓库只读）

ROOT = sim.ROOT
RTL = ROOT / "rtl"
ROUNDS = ROOT / "sim" / "rounds"
QFILES = ROOT / "quartus" / "output_files"

RESULTS = []          # (level, 分组, 标题, 详情)


def add(level, group, title, detail=""):
    RESULTS.append((level, group, title, detail))


def _ts(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:                                        # noqa: BLE001
        return None


def _mtime(p):
    return datetime.datetime.fromtimestamp(pathlib.Path(p).stat().st_mtime)


def _blob_at(commit, rel):
    """`git rev-parse <commit>:<rel>` —— 那个提交里该文件的 blob 哈希。"""
    return sim._git("rev-parse", "%s:%s" % (commit, rel))


def _last_commit_of(rel):
    """最后一次改动该文件的提交（用内容判陈旧绿，避免被 mtime 骗）。"""
    return sim._git("log", "-1", "--format=%H", "--", rel)


def _worktree_blob(rel):
    """工作树上该文件的 blob 哈希（走 git 的 clean 过滤器，与仓库 blob 同口径）。"""
    return sim._git("hash-object", "--", rel)


# ============================================================================
# A + B：仿真证据时效性与断言统计
# ============================================================================
def audit_rounds():
    if not ROUNDS.exists():
        add("FAIL", "A", "找不到 sim/rounds —— 没有任何仿真证据")
        return
    tot_pass = tot_all = 0
    n_mod = 0
    for d in sorted(p for p in ROUNDS.iterdir() if p.is_dir()):
        module = d.name
        js = sorted(d.glob("r*.json"), key=lambda p: int(re.findall(r"\d+", p.stem)[0]))
        if not js:
            add("WARN", "A", "%s 没有任何轮次记录" % module)
            continue
        n_mod += 1
        rel_round = "sim/rounds/%s/%s.json" % (module, js[-1].stem)
        last = json.loads(js[-1].read_text(encoding="utf-8"))
        tot_pass += last["passed"]
        tot_all += last["total"]

        # ---- 最新一轮是否全过
        if not last["all_pass"]:
            add("FAIL", "B", "%s 最新一轮 %s **不是全过**（%d/%d）"
                % (module, js[-1].stem, last["passed"], last["total"]))
            continue

        # ---- 陈旧绿判定：首选"轮次记录里的源码指纹"（精确）
        src = last.get("sources")
        if src:
            cur = sim.source_fingerprint(module)
            changed = sorted(k for k in set(src) | set(cur) if src.get(k) != cur.get(k))
            if changed:
                add("FAIL", "A", "%s 的绿证 %s **已过期**：以下文件在那一轮之后被改过"
                    % (module, js[-1].stem),
                    "、".join("%s（%s → %s）" % (k, src.get(k, "无"), cur.get(k, "无"))
                              for k in changed))
            else:
                add("OK", "A", "%s 绿证 %s 覆盖当前 RTL/tb（%d 个文件指纹一致）"
                    % (module, js[-1].stem, len(src)))
            continue

        # ---- 老记录（无哈希）：**仍然按内容判** —— 找出"最后一次改动该轮次记录的提交"，
        #      再看当时被测的 RTL/tb 与现在的 blob 是否相同。
        #      ⚠️ 不用 mtime：本会话实测过 mtime 会骗人 —— 把 CRLF 重新 checkout 成 LF
        #      时**内容一字未变、blob 完全相同**，但 mtime 全变了，于是"陈旧绿"会误报。
        commit = _last_commit_of(rel_round)
        if not commit:
            add("WARN", "A", "%s 的绿证 %s 未提交，且老记录没有源码指纹 —— 无法判定时效"
                % (module, js[-1].stem))
            continue
        dirty = sim._git("status", "--porcelain", "--", rel_round)
        targets = ["rtl/%s.vhd" % module, "sim/tb_%s.py" % module]
        changed = []
        for rel in targets:
            old = _blob_at(commit, rel)
            new = _worktree_blob(rel)
            if old and new and old != new:
                changed.append(rel.split("/")[-1])
        if changed:
            add("FAIL", "A", "%s 的绿证 %s **已过期**：%s 在 %s 之后被改过"
                % (module, js[-1].stem, "、".join(changed), commit[:8]),
                "重跑该模块（新记录会带上源码指纹，之后就能精确比对）")
        else:
            add("OK", "A", "%s 绿证 %s（老记录：按 git 内容判定未过期，%s）"
                % (module, js[-1].stem, commit[:8]),
                "⚠️ 该记录没有源码指纹，只能按'最后一次改动该记录的提交'判；"
                "重跑一次即可升级为精确判据" + ("；轮次记录本身有未提交改动" if dirty else ""))
    add("INFO", "B", "断言合计：**%d / %d**（%d 个模块/场景）" % (tot_pass, tot_all, n_mod))


# ============================================================================
# C：音效码表一致性（四个文件 + 拼线取值）
# ============================================================================
RE_PKG_SND = re.compile(
    r"constant\s+(SND_\w+)\s*:\s*std_logic_vector\(3 downto 0\)\s*:=\s*\"([01]{4})\"")
RE_BUZZ_ARM = re.compile(r"when\s+\"([01]{4})\"\s*=>\s*tone_sel\s*<=\s*(MEL_\w+)")
RE_FSM_EMIT = re.compile(r"(?:evc\s*:=|sound_p\s*<=)\s*(SND_\w+)")
RE_FSM_BGM = re.compile(r'sound_p\s*<=\s*"10"\s*&\s*lvl3\s*&\s*level')


def audit_sound():
    pkg = (RTL / "puzzle_pkg.vhd").read_text(encoding="utf-8", errors="replace")
    buz = (RTL / "buzzer_ctrl.vhd").read_text(encoding="utf-8", errors="replace")
    fsm = (RTL / "game_fsm.vhd").read_text(encoding="utf-8", errors="replace")

    snd = {name: code for name, code in RE_PKG_SND.findall(pkg)}
    if len(snd) != 16:
        add("FAIL", "C", "puzzle_pkg 的 SND_* 常量不是 16 个（实测 %d）" % len(snd))
    else:
        add("OK", "C", "puzzle_pkg 定义了 16 个 SND_* 码")
    name2code = snd
    code2name = {c: n for n, c in snd.items()}
    if len(code2name) != len(snd):
        add("FAIL", "C", "SND_* 里有**重复的码值**：%s" % snd)

    arms = dict(RE_BUZZ_ARM.findall(buz))                    # code -> MEL_*
    if not arms:
        add("FAIL", "C", "在 buzzer_ctrl 里找不到 `case i_sel` 的查表分支")
    else:
        add("OK", "C", "buzzer_ctrl 有 %d 个码的查表分支：%s"
            % (len(arms), "、".join(sorted(arms))))

    # ---- 能发出的码 ⊆ 有分支的码
    emits = set(RE_FSM_EMIT.findall(fsm))
    emitted_codes = {name2code[n] for n in emits if n in name2code}
    if RE_FSM_BGM.search(fsm):
        emitted_codes |= {name2code["SND_BGM1"], name2code["SND_BGM2"], name2code["SND_BGM3"]}
    else:
        add("WARN", "C", "game_fsm 里没找到 `sound_p <= \"10\" & lvl3 & level` 的拼线赋值")
    silent = sorted(emitted_codes - set(arms))
    if silent:
        add("FAIL", "C", "game_fsm 能发出、但 buzzer_ctrl **没有查表分支**的码：%s"
            % "、".join("%s(%s)" % (c, code2name.get(c, "?")) for c in silent),
            "这些场景会意外静音（落入 when others）")
    else:
        add("OK", "C", "game_fsm 可发出的 %d 个码全部有查表分支（不会意外静音）"
            % len(emitted_codes))
    orphan = sorted(set(arms) - set(snd.values()))
    if orphan:
        add("FAIL", "C", "buzzer_ctrl 有分支、但 puzzle_pkg 里没有对应常量的码：%s" % orphan)

    # ---- 三首 BGM 的拼线取值必须与 SND_BGM* 一致
    #   ⚠️ 2026-10-10 第 18 工作阶段（收尾审查整改）：原来写成 `for ... else:`，
    #      而**循环体内没有 `break`** ⇒ `else`（OK 分支）**总会执行**，
    #      于是"刚报了 FAIL 又报一条假 OK"。审查里用内存篡改 SND_BGM3 复现过。
    #      ⇒ 改成先收集不一致项、循环后统一报一次。
    _bgm_bad = []
    for lvl3, level, want in ((0, 0, "SND_BGM1"), (0, 1, "SND_BGM2"), (1, 1, "SND_BGM3")):
        code = "10" + str(lvl3) + str(level)
        if name2code.get(want) != code:
            _bgm_bad.append("lvl3=%d,level=%d → %s 与 %s=%s 不一致"
                            % (lvl3, level, code, want, name2code.get(want)))
    if _bgm_bad:
        add("FAIL", "C", "BGM 拼线 `\"10\" & lvl3 & level` 与 SND_BGM* 不一致", "；".join(_bgm_bad))
    else:
        add("OK", "C", "三首 BGM 的拼线取值 1000/1001/1011 == SND_BGM1/2/3")

    # ---- tb_buzzer_ctrl 的 MEL 表
    tb = (ROOT / "sim" / "tb_buzzer_ctrl.py").read_text(encoding="utf-8", errors="replace")
    keys = sorted(int(k) for k in re.findall(r"^\s*(\d+)\s*:\s*\[", tb, re.M))
    if len(keys) != 16 or keys != list(range(16)):
        add("FAIL", "C", "tb_buzzer_ctrl 的 MEL 表键不是 0..15（实测 %s）" % keys)
    else:
        add("OK", "C", "tb_buzzer_ctrl 的 MEL 表覆盖 0..15 全部 16 个码")
    m = re.search(r"EMITTED\s*=\s*\[([^\]]*)\]", tb)
    if not m:
        # ⚠️ 审查发现：正则匹配不到时这里**无声消失**（不加任何消息）⇒ 改成显式 WARN。
        add("WARN", "C", "在 tb_buzzer_ctrl 里没匹配到 `EMITTED = [...]` —— 无法对账查表臂集合",
            "tb 改了变量名或格式的话，这条检查会静默失效")
    else:
        emitted = sorted(int(x) for x in re.split(r"[,\s]+", m.group(1)) if x.strip())
        arms_codes = sorted(int(c, 2) for c in arms)
        # ⚠️ 审查发现：原来只比**个数**，不比集合内容 ⇒ 个数相同但码不同会被漏掉。
        if emitted != arms_codes:
            add("FAIL", "C", "tb_buzzer_ctrl 的 EMITTED 与 buzzer_ctrl 的查表臂**集合**不一致",
                "tb=%s / RTL 臂=%s" % (emitted, arms_codes))
        else:
            add("OK", "C", "tb_buzzer_ctrl 的 EMITTED 与 buzzer_ctrl 的查表臂集合一致（%d 个）"
                % len(arms_codes))

    # ---- 预留码必须真的静音（没有 case 分支）
    #   ⚠️ 第 18 工作阶段起，"无查表臂"的码从 3 个变成 5 个：
    #      1101/1110/1111（一直预留）+ **1010（旋转）/1100（确认）**
    #      —— 用户要求"确认、旋转不要打扰背景音乐"，`game_fsm` 不再生成这两个码，
    #      查表臂也一并删掉（净省逻辑）。
    reserved = ["1010", "1100", "1101", "1110", "1111"]
    bad = [c for c in reserved if c in arms]
    if bad:
        add("FAIL", "C", "下列码本应无查表臂（静音），实测却有分支：%s" % bad)
    else:
        add("OK", "C", "无查表臂的 5 个码 1010/1100/1101/1110/1111 均落入 when others → 整句静音"
                       "（含第 18 工作阶段删掉的【旋转】【确认】）")

    # ---- 文档口径：发出的码只有 12 个（历史上曾误写"九个瞬时短语"）
    add("INFO", "C", "game_fsm 实际可发出的码 = %d 个：%s"
        % (len(emitted_codes), "、".join(sorted(emitted_codes))))


# ============================================================================
# D：综合读数
# ============================================================================
RE_FIT_ROW = r"^;\s*%s\s*;\s*([^;]+?)\s*;"


def _fit_field(text, label):
    m = re.search(RE_FIT_ROW % re.escape(label), text, re.M)
    return m.group(1).strip() if m else None


def audit_reports():
    fit = QFILES / "puzzle.fit.rpt"
    sta = QFILES / "puzzle.sta.rpt"
    if not fit.exists():
        add("WARN", "D", "本机没有 %s —— 没有本机编译读数" % fit.relative_to(ROOT),
            "quartus/output_files/ 是 .gitignore 的构建产物（新 clone 本来就没有）；"
            "在本机跑一次 `quartus_sh -t scripts/build.tcl` 即可")
        return None
    text = fit.read_text(encoding="utf-8", errors="replace")

    status = _fit_field(text, "Fitter Status")
    le = _fit_field(text, "Total logic elements")
    lab = _fit_field(text, "Total LABs")
    pins = _fit_field(text, "Total pins")
    # ⚠️ 2026-10-10 第 18 工作阶段（收尾审查整改）：解析不到时必须**明确报"报告格式可能变了"**，
    #    否则会打出 `OK Fitter Status = None` + `WARN LAB 已满（0/0）` + 无条件的"面积余量"OK
    #    —— 三个都是假结论（审查里用"删掉 fit.rpt 三行"复现过）。
    missing = [k for k, v in (("Fitter Status", status), ("Total logic elements", le),
                              ("Total LABs", lab), ("Total pins", pins)) if not v]
    if missing:
        add("WARN", "D", "fit.rpt 里解析不到：%s —— 报告格式可能变了" % "、".join(missing),
            "解析不到时**不再**给出面积/装箱结论（否则会报出 0/0 这种假读数）")
        return None
    if not status.lower().startswith("successful"):
        add("FAIL", "D", "Fitter Status = %s" % status)
    else:
        add("OK", "D", "Fitter Status = %s" % status)
    add("INFO", "D", "资源：LE %s；LAB %s；引脚 %s" % (le, lab, pins))

    def _num(s):
        m = re.match(r"([\d,]+)\s*/\s*([\d,]+)", s or "")
        return (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) if m else (0, 0)

    le_u, le_m = _num(le)
    lab_u, lab_m = _num(lab)
    if lab_m == 0 or le_m == 0:
        add("WARN", "D", "面积字段解析不出 '占用/总量' 形式：LE=%r LAB=%r" % (le, lab))
        return None
    if lab_u >= lab_m:
        add("WARN", "D", "LAB 已满（%d/%d）—— 再加逻辑必须先腾面积；"
                        "**判'装不下'要读 LAB，不是只读 LE**（ERR-046）" % (lab_u, lab_m))
    if le_u >= le_m:
        add("WARN", "D", "LE 已满（%d/%d）" % (le_u, le_m))
    add("OK", "D", "面积余量：LE 剩 %d、LAB 剩 %d" % (le_m - le_u, lab_m - lab_u))

    # ---- 时序
    if not sta.exists():
        add("FAIL", "D", "找不到 %s —— 时序未验证" % sta.relative_to(ROOT))
        return
    stext = sta.read_text(encoding="utf-8", errors="replace")
    slacks = {}
    for kind in ("Setup", "Hold"):
        idx = [m.start() for m in re.finditer(r"^;\s*%s: 'clk'" % kind, stext, re.M)]
        if not idx:
            continue
        tail = stext[idx[-1]:].splitlines()
        for ln in tail[1:]:
            m = re.match(r"^;\s*(-?[\d.]+)\s*;", ln)
            if m:
                slacks[kind] = float(m.group(1))
                break
    if "Setup" not in slacks:
        add("WARN", "D", "没能从 sta.rpt 解析出 setup slack（报告格式可能变了）")
    else:
        s = slacks["Setup"]
        if s < 0:
            add("FAIL", "D", "**时序违例**：setup slack = %+.3f ns（不满足 50 MHz）" % s)
        else:
            add("OK", "D", "时序满足 50 MHz：setup slack = %+.3f ns（≈%.1f MHz）"
                % (s, 1000.0 / (20.0 - s)))
        if "Hold" in slacks:
            h = slacks["Hold"]
            add("OK" if h >= 0 else "FAIL", "D",
                "hold slack = %+.3f ns" % h)
    return {"le": le, "lab": lab, "pins": pins, "slack": slacks.get("Setup")}


# ============================================================================
# E：固件与 RTL 一致性（**按内容**，不按 mtime —— mtime 会骗人）
# ============================================================================
def audit_firmware():
    prov_path = ROOT / "quartus" / "build_provenance.json"
    pof = QFILES / "puzzle.pof"

    if not prov_path.exists():
        add("WARN", "E", "没有 quartus/build_provenance.json —— 无法按内容核对固件与 RTL",
            "编译后跑一次 `python scripts/record_build.py`（它会记录 RTL 指纹 + pof 的 "
            "sha256 + fit/sta 读数）")
        if pof.exists():
            add("INFO", "E", "puzzle.pof 时间戳 %s（仅供参考；**mtime 不是内容判据**）" % _mtime(pof))
        return

    rec = json.loads(prov_path.read_text(encoding="utf-8"))
    cur = sim.source_fingerprint("puzzle_top")
    cur_rtl = {k: v for k, v in cur.items() if k.startswith("rtl/")}
    old_rtl = rec.get("sources", {})
    changed = sorted(k for k in set(old_rtl) | set(cur_rtl) if old_rtl.get(k) != cur_rtl.get(k))
    if changed:
        add("FAIL", "E", "**固件落后于 RTL**：以下文件在 %s 那次编译记录之后被改过"
            % rec.get("timestamp"),
            "、".join("%s（%s → %s）" % (k, old_rtl.get(k, "无"), cur_rtl.get(k, "无"))
                      for k in changed)
            + " —— 板上跑的不是仓库里的逻辑，需要重新编译 + 烧录 + 重记 provenance")
    else:
        add("OK", "E", "固件覆盖当前 RTL：%d 个 rtl/*.vhd 指纹与 %s 的编译记录一致"
            % (len(cur_rtl), rec.get("timestamp")))

    pof_rec = rec.get("pof")
    if pof_rec and pof.exists():
        now = hashlib.sha256(pof.read_bytes()).hexdigest()
        if now != pof_rec.get("sha256"):
            add("WARN", "E", "puzzle.pof 的 sha256 与编译记录不符（可能被重新生成过）",
                "记录 %s… / 现在 %s…" % (pof_rec.get("sha256", "")[:16], now[:16]))
        else:
            add("OK", "E", "puzzle.pof 身份一致：sha256 %s…（%s，%d 字节）"
                % (now[:16], pof_rec.get("mtime"), pof_rec.get("bytes")))
    elif not pof.exists():
        add("WARN", "E", "找不到 puzzle.pof（本机没有固件产物）")

    fit = rec.get("fit") or {}
    sta = rec.get("sta") or {}
    if fit:
        add("INFO", "E", "编译记录读数：LE %s；LAB %s；引脚 %s；setup %s ns；hold %s ns"
            % (fit.get("le"), fit.get("lab"), fit.get("pins"),
               sta.get("setup_slack"), sta.get("hold_slack")))


# ============================================================================
# F：仓库状态
# ============================================================================
def audit_git():
    head = sim._git("rev-parse", "HEAD")
    origin = sim._git("rev-parse", "refs/remotes/origin/main")
    dirty = sim._git("status", "--porcelain") or ""
    if head and origin and head != origin:
        add("WARN", "F", "本地 HEAD 与 origin/main 不一致（有未推提交）", "HEAD=%s origin=%s" % (head[:12], origin[:12]))
    elif head:
        add("OK", "F", "origin/main == HEAD（%s）" % head[:12])
    else:
        add("WARN", "F", "不是 git 工作树，跳过仓库状态检查")
    if dirty:
        add("INFO", "F", "工作树有 %d 处未提交改动" % len(dirty.splitlines()))
    else:
        add("OK", "F", "工作树干净")


# ============================================================================
# G：文档数字对齐
# ============================================================================
DOCS = ["README.md", "HANDOFF.md", "PROGRESS.md",
        "docs/00-规范理解与需求.md", "docs/02-模块详细设计.md",
        "docs/03-仿真验证方案.md", "docs/05-资源利用与编译报告.md",
        "docs/06-硬件调试记录.md"]


def audit_doc_numbers(fit_info):
    if not fit_info:
        return
    le_u = re.match(r"([\d,]+)", fit_info["le"] or "")
    cur_le = le_u.group(1).replace(",", "") if le_u else None
    found_le, found_seed, found_slack = set(), set(), set()
    for rel in DOCS:
        p = ROOT / rel
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        found_le |= set(re.findall(r"(\d{3,4})\s*/\s*1[,]?270\s*LE", t))
        found_seed |= set(re.findall(r"SEED\s*(\d+)", t))
        # ⚠️ 2026-10-10 第 18 工作阶段（收尾审查整改）：这条正则原来只认
        #    `slack` 后面紧跟 `**`/空格/`+`，于是
        #      · 认不出 `slack = +0.861 ns`（docs/05 就是这个写法）；
        #      · 认不出**负值**（时序违例时最该认出来）；
        #    而且把 setup 与 hold 的数值混进同一个集合（"当前 setup slack 在文档里"会被
        #    hold 的数字蒙混过关）。现在按 setup/hold 分开收，并允许 `= : ≈ ** ` 等修饰。
        for kind in ("setup", "hold"):
            found_slack |= set(re.findall(
                r"%s\s*slack\s*[=:≈]?\s*\**\s*`?\s*([+-]?[\d.]+)\s*`?\s*\**\s*ns" % kind, t, re.I))
    if cur_le and cur_le not in found_le:
        add("WARN", "G", "文档里**没有出现**当前的 LE 值 %s（出现过的是 %s）"
            % (cur_le, "、".join(sorted(found_le))))
    elif cur_le:
        add("OK", "G", "当前 LE=%s 在文档里出现过（文档提到的 LE 值：%s）"
            % (cur_le, "、".join(sorted(found_le))))
    gen = (ROOT / "scripts" / "gen_project.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"-name SEED (\d+)", gen)
    if m:
        seed = m.group(1)
        if seed not in found_seed:
            add("WARN", "G", "gen_project.py 里的 SEED %s 没在文档里出现过（文档：%s）"
                % (seed, "、".join(sorted(found_seed))))
        else:
            add("OK", "G", "SEED %s 与文档一致（文档提到的种子：%s）"
                % (seed, "、".join(sorted(found_seed))))
    if fit_info.get("slack") is not None:
        s = "%.3f" % fit_info["slack"]
        # ⚠️ 文档里常带符号写（`+0.861`），收集到的集合里也是带符号的 ⇒ 比较前统一去符号。
        found_norm = {x.lstrip("+") for x in found_slack}
        if s not in found_norm:
            add("WARN", "G", "文档里没有出现当前的 setup slack %s（出现过：%s）"
                % (s, "、".join(sorted(found_slack))))
        else:
            # ⚠️ 审查发现：这条原来**没有 OK 分支** ⇒ 输出里分不清"查过且过了"与"根本没跑"。
            add("OK", "G", "当前 setup slack %s 在文档里出现过" % s)

    # ---- ⭐ 关卡限时常量（第 18 工作阶段补：**这条缺口让"第三关 40→60 s"的文档漂移漏网**）
    #   审查发现：G 段只对账 LE/SEED/slack，于是 HANDOFF/docs/00/docs/02 里残留的
    #   `T_LEVEL3 = 40` 一直没人发现。⇒ 现在把 4 个限时常量也纳入对账。
    #   ⚠️ 只认**紧邻**的两种写法（`T_LEVEL3 = 40 s` 与 `40 s（自拟 T_LEVEL3）`）——
    #      早先版本用"±80 字符窗口"，把同一张表里别的常量值也误报成漂移。
    pkg = (ROOT / "rtl" / "puzzle_pkg.vhd").read_text(encoding="utf-8", errors="replace")
    times = {}
    for n in ("T_PREVIEW", "T_LEVEL1", "T_LEVEL2", "T_LEVEL3"):
        mm = re.search(r"constant\s+%s\s*:\s*integer\s*:=\s*(\d+)" % n, pkg)
        times[n] = mm.group(1) if mm else None
    bad_doc = []
    for n, v in times.items():
        if v is None:
            continue
        pat_fwd = re.compile(r"%s\s*(?:=|:=|为|是)\s*\**\s*`?\s*(\d{1,3})\s*(?:s\b|秒)" % re.escape(n))
        pat_rev = re.compile(r"(\d{1,3})\s*(?:s\b|秒)\s*[（(][^)）]{0,14}%s" % re.escape(n))
        for rel in DOCS:
            p = ROOT / rel
            if not p.exists():
                continue
            t = p.read_text(encoding="utf-8", errors="replace")
            for pat in (pat_fwd, pat_rev):
                for mm in pat.finditer(t):
                    if mm.group(1) != v:
                        bad_doc.append("%s：`%s` 写成 %s s（当前 %s）" % (rel, n, mm.group(1), v))
    if bad_doc:
        add("WARN", "G", "文档里的**关卡限时常量**与 RTL 不一致（当前 %s）"
            % "、".join("%s=%s" % (k, v) for k, v in times.items()),
            "；".join(sorted(set(bad_doc))[:8]))
    else:
        add("OK", "G", "关卡限时常量与文档一致（%s）"
            % "、".join("%s=%s" % (k, v) for k, v in times.items()))


# ============================================================================
def main():
    ap = argparse.ArgumentParser(description="证据链对抗性审查（只读）")
    ap.add_argument("--strict", action="store_true", help="WARN 也算失败")
    args = ap.parse_args()

    print("=" * 78)
    print(" 证据链对抗性审查 —— %s" % ROOT)
    print("=" * 78)
    audit_rounds()
    audit_sound()
    fit_info = audit_reports()
    audit_firmware()
    audit_git()
    audit_doc_numbers(fit_info)

    groups = {}
    for lvl, grp, title, detail in RESULTS:
        groups.setdefault(grp, []).append((lvl, title, detail))
    names = {"A": "仿真证据时效性（陈旧绿 / ERR-022）", "B": "断言统计",
             "C": "音效码表一致性（四方对账）",
             "D": "综合读数（面积 / 装箱 / 引脚 / 时序）",
             "E": "固件与 RTL 一致性", "F": "仓库状态", "G": "文档数字对齐"}
    icon = {"OK": "✓", "INFO": "·", "WARN": "⚠", "FAIL": "✗"}
    for grp in sorted(groups):
        print("\n== %s. %s ==" % (grp, names.get(grp, grp)))
        for lvl, title, detail in groups[grp]:
            print("  %s %s" % (icon[lvl], title))
            if detail:
                print("      %s" % detail)

    n_fail = sum(1 for r in RESULTS if r[0] == "FAIL")
    n_warn = sum(1 for r in RESULTS if r[0] == "WARN")
    print("\n" + "=" * 78)
    print(" 合计：%d FAIL / %d WARN / %d OK" % (
        n_fail, n_warn, sum(1 for r in RESULTS if r[0] == "OK")))
    print("=" * 78)
    if n_fail or (args.strict and n_warn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
