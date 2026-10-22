#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_privacy.py —— 隐私体检：**四个面**一起查

    ① 被跟踪文件的**文件名与内容**（当前工作树）
    ② 全部可达提交的**提交信息正文**（`git log --all`）
    ③ 提交的**作者 / 提交者姓名与邮箱**
    ④ ⭐ 全部可达历史的 **blob 内容** —— "现在删了、但历史里还在"的东西

【为什么必须四个面都查（2026-10-22 同一天踩到两次）】
    第一次：HEAD 的**提交信息正文**里写着个人上交版的完整落点路径（含真实姓名与学号），
            而且已经 push 到公开仓库。当时工作树、全部 blob、`git grep`、`git log -S`
            全都是 0 命中 —— 因为 `git grep` 扫的是**内容**、`git log -S` 扫的是**增删差异**，
            两者都看不见 commit message，而 commit message 是随 push 一起公开的。
    第二次（补上面第 ④ 面时才暴露）：本机账户名出现在**历史 blob** 里 ——
            `.ref/` 的一次性脚本、旧版 `scripts/*.py`、旧版 `HANDOFF.md`、
            已删除的 `docs/modules/*.md`（那些页里写着 `file:///c:/Users/<账户>/...`）。
            它们后来被改掉/删掉了，于是**当前工作树干净、`git grep` 0 命中**，
            但 `git cat-file` 一读历史就还在。
    ⇒ **"工作树干净" 与 "仓库干净" 是两件事**；只查前三个面会打出误导性的 PASS。

    ⚠️ 第 ④ 面会区分两种情况（这个区分很重要，否则门禁永远红着就没人看了）：
       · `历史内容（当前树仍在）` —— 同一个路径**现在**也命中 ⇒ **FAIL**，那是活的问题；
       · `历史内容`             —— 只留在被改掉/被删掉的旧 blob 里 ⇒ 归入"历史残留"，
         汇总成一行（命中数 + 去重路径数 + 抽样）并在 `KNOWN_HISTORICAL` 里登记理由。
         想真清掉得重写全史，代价见 `KNOWN_HISTORICAL` 的注释与 HANDOVER.md §7。

【用法】（在仓库根执行）
    python scripts/check_privacy.py                 # 四个面全查；有问题 exit 1
    python scripts/check_privacy.py --quiet         # 只打印汇总与命中
    python scripts/check_privacy.py --no-history    # 跳过第 ④ 面（快，但会漏"删掉的历史内容"）
    python scripts/check_privacy.py --extra FILE    # 追加自己的正则（一行一条）

    想查"某个只有你知道的词"（例如真实姓名），**不要**把它写进仓库里的任何文件
    —— 默认的追加规则文件放在仓库外：`~/.dld-privacy-patterns`（一行一条正则）。

【判据（全是**形状**匹配，脚本里不含任何真实身份）】
    FAIL  本机绝对路径：`X:\\Users\\<非占位符>\\...`（含 `C:\\\\Users\\\\...` 这种转义写法）、
          `/Users/<非占位符>/`、`/home/<非占位符>/`
    FAIL  10 位学号形状的数字串：可选 1~8 个字母前缀 + `20` + 8 位数字
          （占位符 `202300000000` 是 12 位，不会误报；16 进制串里不会命中，因为前面还有 16 进制字符）
    FAIL  追加规则命中
    WARN  12 位以上纯数字串（只在**提交信息**里跑：文件里这类数字是正常数据，例如 64 位掩码、DOI）

【已知边界（都写在这里，不藏着）】
    · **二进制容器**（PNG / PDF / DOCX / .docx 里的 XML）按压缩字节存，原始字节里看不到明文，
      因此只查文件名、不查内容（脚本会打印跳过了几个）。要查它们得另行解包。
    · **CI** 里 `actions/checkout` 默认只取 1 个提交 ⇒ 只能查到那一个提交的信息与 blob。
      **本地跑一次才是全量**；脚本会打印实际扫到的提交/blob 数，别被 CI 的绿灯骗了。
    · `--extra` 里的正则若写得过宽，会产生误报；脚本只做语法检查，不做语义检查。
"""
from __future__ import annotations

import argparse
import os
import re
import string
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EXTRA = os.path.join(os.path.expanduser("~"), ".dld-privacy-patterns")
MAX_BYTES = 8 * 1024 * 1024          # 单个文件/blob 超过它就不读内容（仍查文件名/路径）
BINARY_SNIFF = 8192                  # 头 8 KB 里有 NUL ⇒ 当二进制
HISTORY_BUDGET = 96 * 1024 * 1024    # 第 ④ 面的总字节预算，防内存失控

# 占位符白名单：文档里的示例路径本来就该长这样，不算泄漏。
# ⚠️ 必须要求"占位符之后就是分隔符或结尾"，否则 `xxxavier` / `USERNAME1` 会被整体放行。
_PH = r"(?!(?:me|user|you|xxx|username|用户名|<)(?:[\\/]|$))"
RULES = [
    ("本机绝对路径（Windows 用户目录）",
     re.compile(r"[A-Za-z]:[\\/]{1,2}users[\\/]{1,2}" + _PH + r"[^\\/\s\"'|<>]+", re.I)),
    ("本机绝对路径（macOS / Linux 家目录）",
     re.compile(r"/(?:Users|home)/" + _PH + r"[A-Za-z0-9._-]+(?=[/\s\"'`)\],;:]|$)", re.I)),
    ("10 位学号形状的数字串",
     re.compile(r"(?<![0-9A-Za-z])[A-Za-z]{0,8}20[0-9]{8}(?![0-9A-Za-z])")),
]
# 文档里**有意**写的示例学号：写在这里是为了让"示例"与"真泄漏"可区分，
# 而不是为了让扫描变松 —— 加值必须同时补一条注释说明它为什么安全。
ALLOW = {
    "2024000000",     # README/HANDOVER 里 --id 的用法示例
}
# 只对**提交信息**跑：提交信息里出现 12 位以上纯数字串很反常（文件里则是正常数据，
# 例如 64 位掩码、DOI 里的流水号），所以不进文件扫描，避免噪音淹没真信号。
WARNS = [
    ("12 位以上纯数字串（人工判）", re.compile(r"(?<![0-9A-Za-z])[0-9]{12,}(?![0-9A-Za-z])")),
]

# ---------------------------------------------------------------------------
# 已知历史基线：登记"已知且**决定接受**"的命中，避免门禁永远红着而被整体忽略。
#
# ⚠️ 这里的 `blob:` 只覆盖**历史残留**那一类，判定规则很窄（见 face_history）：
#    只有"这个 blob 的内容**已经不在当前工作树里**"（被改掉或被删掉）才归入残留；
#    如果同一个路径的**当前版本**也命中，标签会变成"历史内容（当前树仍在）"⇒ 照样 FAIL。
#    所以这条不是"忽略所有历史 blob"，而是"忽略已经被修好、只留在历史里的旧内容"。
#
# 为什么不直接重写历史把它们清掉：
#   · `msg:` 的三条在 2026-10-10 / 10-10 / 10-15；`blob:` 那一大批是 2026-10-10
#     提交 65ada93（"消除全部作者绝对路径"）**之前**的 `.ref/` 一次性脚本、旧版
#     `scripts/*.py`、旧版 `HANDOFF.md` 与已删除的 `docs/modules/*.md`。
#   · 重写全史会让**所有**提交哈希变掉 —— 而 `HANDOFF.md` / `docs/03` / `docs/06` /
#     `PROGRESS.md` / `AI_LOG.md` 是按哈希引用提交的，`sim/rounds/*.json` 与
#     `quartus/build_provenance.json` 里还存着 `git_head`（提交 SHA），
#     `audit_evidence.py` 正是靠这些做证据链核对。
#   ⇒ 拿"整条证据链的引用集体失效"去换"历史里的一个本机账户名"不划算。
#     要真清掉，得先决定"重写全史 + 同步改写文档哈希与 git_head"，那是一次独立的、
#     需要用户点头的工程（做法与代价见 HANDOVER.md §7）。
# 新增条目必须**同时写清理由**；这一节是"已知并接受的清单"，不是"忽略清单"。
KNOWN_HISTORICAL = {
    "msg:4117137c": "2026-10-15：提交信息在描述 refs/README.md 脱敏时引用了脱敏前的路径原文",
    "msg:65ada936": "2026-10-10：提交信息在描述「消除全部作者绝对路径」时引用了被消除的路径原文",
    "msg:219e4bbd": "2026-10-10：提交信息在描述 sim_summary.py 去写死路径时引用了旧路径原文",
    "blob:": "历史残留：当前工作树已经改好、但旧 blob 里还在的本机账户名路径"
             "（`.ref/` 一次性脚本、旧版 `scripts/*.py`、旧版 `HANDOFF.md`、"
             "已删除的 `docs/modules/*.md`）。清掉要重写全史，代价见上面的注释。",
}
RESIDUE_SAMPLES = 5          # 历史残留最多展开几条明细（全量太吵，汇总更重要）


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit("git %s 失败：%s" % (" ".join(args), p.stderr.strip()))
    return p.stdout


def decode(raw: bytes) -> str:
    """文本解码：UTF-8 为主；出现替换字符时再按 latin-1 兜一遍（只可能多报，不会漏报）。"""
    text = raw.decode("utf-8", "replace")
    if "\ufffd" in text:
        text += "\n" + raw.decode("latin-1", "replace")
    return text


def scan(label: str, text: str, where: str, rules, hits: list, quiet: bool) -> None:
    for name, rx in rules:
        for m in rx.finditer(text):
            tok = m.group(0)
            # 学号规则允许字母前缀，白名单按"尾部的 10 位数字"比对
            if tok in ALLOW or tok.lstrip(string.ascii_letters) in ALLOW:
                continue
            frag = text[max(0, m.start() - 24):m.end() + 24].replace("\n", " ")
            hits.append((label, name, where, frag))
            if not quiet:
                print("  ✗ [%s] %s\n      %s\n      …%s…" % (label, name, where, frag))


def baseline_key(label: str, where: str) -> str:
    """把一条命中映射到基线键（只有提交信息与历史残留可能命中基线）。"""
    if label == "提交信息":
        return "msg:" + where
    if label == "历史内容":          # 只可能是"当前树已修好"的残留，见 face_history
        return "blob:"
    return ""


def classify(hits: list) -> tuple[list, list]:
    fails, known = [], []
    for h in hits:
        key = baseline_key(h[0], h[2])
        (known if key and key in KNOWN_HISTORICAL else fails).append(h)
    return fails, known


# --------------------------------------------------------------------------- 四个面
def face_files(rules, fails, warns, quiet) -> tuple[int, int, int, set]:
    files = [f for f in git("ls-files", "-z").split("\0") if f]
    print("== ① 跟踪文件：%d 个 ==" % len(files))
    skipped = binaries = 0
    for rel in files:
        scan("文件路径", rel, rel, rules, fails, quiet)
        abs_p = os.path.join(ROOT, rel)
        try:
            if os.path.getsize(abs_p) > MAX_BYTES:
                skipped += 1
                continue
            raw = open(abs_p, "rb").read()
        except OSError:
            continue
        if b"\0" in raw[:BINARY_SNIFF]:
            binaries += 1
            continue
        scan("文件内容", decode(raw), rel, rules, fails, quiet)
    print("   跳过：%d 个 > %d MB、%d 个二进制容器（PNG/PDF/DOCX，见脚本头部）"
          % (skipped, MAX_BYTES // 1024 // 1024, binaries))
    # 当前工作树里就已经泄漏的路径 —— 第 ④ 面靠它区分"活的问题"与"历史残留"
    live = {h[2] for h in fails if h[0] in ("文件内容", "文件路径")}
    return len(files), skipped, binaries, live


def face_messages(rules, warns, fails, quiet) -> tuple[int, bool]:
    shallow = git("rev-parse", "--is-shallow-repository").strip() == "true"
    raw = git("log", "--all", "--format=%H%x1f%B%x1e")
    commits = [c for c in raw.split("\x1e") if c.strip()]
    print("== ② 提交信息：扫到 %d 个提交%s =="
          % (len(commits), "（⚠️ 浅克隆：看不到更早的历史）" if shallow else ""))
    for c in commits:
        sha, _, msg = c.partition("\x1f")
        scan("提交信息", msg, sha.strip()[:8], rules, fails, quiet)
        scan("提交信息", msg, sha.strip()[:8], WARNS, warns, quiet)
    return len(commits), shallow


def face_identity(rules, fails, quiet) -> int:
    ids = set()
    for line in git("log", "--all", "--format=%an%x1f%ae%x1f%cn%x1f%ce").splitlines():
        for part in line.split("\x1f"):
            if part.strip():
                ids.add(part.strip())
    print("== ③ 作者/提交者身份：%d 个不同取值 ==" % len(ids))
    for v in sorted(ids):
        scan("作者身份", v, v, rules, fails, quiet)
    return len(ids)


def face_history(rules, fails, quiet, live: set) -> int:
    """④ 可达历史的 blob 内容 —— 找"现在改好了、历史里还在"的东西。

    ⚠️ 关键区分：同一个路径的**当前版本**也命中时，标签是
    `历史内容（当前树仍在）` ⇒ 照样算 FAIL（那是活的问题，不是残留）；
    只有"当前树已经改好/已删除"的旧 blob 才归入 `历史内容` 残留档。
    """
    want: dict[str, str] = {}
    for ln in git("rev-list", "--objects", "--all").splitlines():
        sha, _, path = ln.partition(" ")
        if len(sha) == 40:
            want.setdefault(sha, path)
    print("== ④ 历史 blob：可达对象 %d 个 ==" % len(want))
    if not want:
        return 0
    shas = list(want)
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, capture_output=True,
                       input=("\n".join(shas) + "\n").encode("ascii"))
    if p.returncode != 0:
        raise SystemExit("git cat-file --batch 失败：%s" % p.stderr.decode("utf-8", "replace"))
    data, i, n_blob, n_big, budget = p.stdout, 0, 0, 0, HISTORY_BUDGET
    while i < len(data):
        j = data.index(b"\n", i)
        head = data[i:j].decode("utf-8", "replace").split()
        i = j + 1
        if len(head) == 2:                       # `<sha> missing`
            continue
        if len(head) != 3:
            break
        sha, typ, size = head[0], head[1], int(head[2])
        body, i = data[i:i + size], i + size + 1
        if typ != "blob" or size > MAX_BYTES or budget <= 0:
            n_big += 1
            continue
        budget -= size
        n_blob += 1
        path = want.get(sha, "?")
        label = "历史内容（当前树仍在）" if path in live else "历史内容"
        # 残留可能有几百条：明细不逐条刷屏，留给下面的汇总（活的问题照常逐条打印）
        scan(label, decode(body), "%s %s" % (sha[:8], path), rules, fails,
             quiet or label == "历史内容")
    print("   扫描 %d 个 blob（跳过 %d 个过大/超预算）" % (n_blob, n_big))
    return n_blob


def main() -> int:
    ap = argparse.ArgumentParser(description="隐私体检：跟踪文件 + 提交信息 + 作者身份 + 历史 blob")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总与命中摘要")
    ap.add_argument("--no-history", action="store_true", help="跳过第 ④ 面（历史 blob）")
    ap.add_argument("--extra", metavar="FILE", default=DEFAULT_EXTRA,
                    help="追加规则文件（一行一条正则；默认 ~/.dld-privacy-patterns）")
    args = ap.parse_args()

    rules = list(RULES)
    if os.path.isfile(args.extra):
        extra = []
        with open(args.extra, encoding="utf-8") as fh:
            for k, line in enumerate(fh, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    extra.append(("追加规则（%s:%d）" % (os.path.basename(args.extra), k),
                                  re.compile(line)))
                except re.error as exc:
                    raise SystemExit("[错误] %s 第 %d 行不是合法正则：%s" % (args.extra, k, exc))
        rules += extra
        print("已加载追加规则 %d 条（来自仓库外的 %s）" % (len(extra), args.extra))
    elif args.extra != DEFAULT_EXTRA:
        print("[警告] 指定的追加规则文件不存在：%s" % args.extra)

    fails: list = []
    warns: list = []

    n_files, _skip, _bin, live = face_files(rules, fails, warns, args.quiet)
    n_commits, shallow = face_messages(rules, warns, fails, args.quiet)
    n_ids = face_identity(rules, fails, args.quiet)
    n_blobs = 0 if args.no_history else face_history(rules, fails, args.quiet, live)

    print("-" * 74)
    fails, known = classify(fails)

    # 历史残留：可能成百上千条，逐条展开只会淹没真信号 ⇒ 汇总 + 抽样 + 去重路径
    residue = [h for h in known if h[0] == "历史内容"]
    others = [h for h in known if h[0] != "历史内容"]
    for _label, name, where, _frag in others:
        print("  ⚠ [已知历史] %s @ %s：%s" % (name, where, KNOWN_HISTORICAL[baseline_key(_label, where)]))
    if residue:
        paths = sorted({h[2].split(" ", 1)[1] for h in residue if " " in h[2]})
        print("  ⚠ [已知历史残留] 历史 blob 命中 **%d 处 / %d 个路径**（当前工作树已修好，只是旧 blob 里还在）："
              % (len(residue), len(paths)))
        print("      %s" % KNOWN_HISTORICAL["blob:"])
        for path in paths[:12]:
            print("      · %s" % path)
        if len(paths) > 12:
            print("      · …另有 %d 个路径" % (len(paths) - 12))
        for _label, name, where, _frag in residue[:RESIDUE_SAMPLES]:
            print("      抽样：%s @ %s" % (name, where))
        print("      ⚠ 要真清掉得重写全史并 force-push（会作废文档引用的全部提交哈希与")
        print("        `sim/rounds/*.json` / `quartus/build_provenance.json` 里的 `git_head`）——")
        print("        那是需要单独决策的工程，做法与代价见 HANDOVER.md §7。")

    for _label, name, where, frag in warns[:10]:
        print("  ⚠ [%s] %s @ %s：…%s…" % (name, where, frag))
    if len(warns) > 10:
        print("  ⚠ …另有 %d 条 WARN 未展开" % (len(warns) - 10))

    if fails:
        print("FAIL：%d 处疑似隐私泄漏（跟踪文件 / 提交信息 / 作者身份 / 历史 blob）" % len(fails))
        print("      ⚠ 文件里的泄漏改文件就行；**提交信息或历史 blob 里的改文件没用**，")
        print("        必须重写历史并 force-push（做法见 HANDOVER.md §7），")
        print("        或者像 KNOWN_HISTORICAL 那样显式登记为'已知并接受'并写清理由。")
        if any(h[0] == "提交信息" for h in fails):
            print("      💡 提交信息里**不要写路径原文**（哪怕是举例）：用 `<用户>` 这类占位符，")
            print("         或者干脆只描述形状（'Windows 用户目录下的绝对路径'）。")
        return 1

    print("PASS：跟踪文件 %d + 提交信息 %d + 作者身份 %d + 历史 blob %d，均无命中%s。"
          % (n_files, n_commits, n_ids, n_blobs,
             "（%d 条命中已登记为已知历史）" % len(known) if known else ""))
    if shallow:
        print("      ⚠️ 本次是浅克隆，只覆盖 %d 个提交 —— 全量结论请在完整克隆上跑。" % n_commits)
    if args.no_history:
        print("      ⚠️ 本次跳过了第 ④ 面（--no-history）—— 已删除的历史内容没有被检查。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
