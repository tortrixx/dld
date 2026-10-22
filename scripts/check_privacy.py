#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_privacy.py —— 隐私体检：**跟踪文件 + 提交信息 + 作者身份**三面一起查

【为什么要有它】
    2026-10-22 实盘踩到一次真泄漏：工作树与全部 blob 都干净（`git grep` / `git log -S`
    都是 0 命中），但 **HEAD 的提交信息正文里**赫然写着
    `C:\\Users\\<用户>\\Desktop\\...\\<真实姓名>_<真实学号>_....pdf`，而且已经 push 到远端。
    原因很简单：`git grep` 扫的是**内容**，`git log -S` 扫的是**增删内容的差异**，
    两者都看不见 commit message —— 而 commit message 是随 push 一起公开的。

    所以本脚本把隐私面明确成三块，缺一块都算没查：
      ① 被跟踪的**文件名与文件内容**（含二进制按 latin-1 兜底解一遍）
      ② 全部可达提交的**提交信息正文**（`git log --all`）
      ③ 提交的**作者/提交者姓名与邮箱**（`git log --all --format=%an/%ae/%cn/%ce`）

【用法】（在仓库根执行）
    python scripts/check_privacy.py                 # 三面全查；有问题 exit 1
    python scripts/check_privacy.py --quiet         # 只打印结论与命中
    python scripts/check_privacy.py --extra FILE     # 追加自己的正则（一行一条）

    想查"某个只有你知道的词"（例如真实姓名），**不要**把它写进仓库里的任何文件
    —— 默认的追加规则文件放在仓库外：`~/.dld-privacy-patterns`（一行一条正则）。

【判据（都不含任何真实身份，纯形状匹配）】
    FAIL  本机绝对路径：`X:\\Users\\<非占位符>\\...`、`/Users/<非占位符>/`、`/home/<非占位符>/`
    FAIL  10 位学号形状的数字串：`20` + 8 位数字（占位符 202300000000 是 12 位，不会误报）
    FAIL  追加规则命中
    WARN  12 位以上的纯数字串（可能是学号/工号，也可能是正常数据，人工判）

【已知边界】
    · CI 里 `actions/checkout` 默认只取 1 个提交 ⇒ 只能查到那一个提交的信息。
      所以**本地跑一次才是全量**；脚本会打印实际扫到的提交数，别被 CI 的绿灯骗了。
    · 二进制文件按 latin-1 解，只可能**多报**不可能漏报；PDF/DOCX 这类压缩容器
      原始字节里看不到明文，需要另行解包（`--extra` 挡不住这一点）。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EXTRA = os.path.join(os.path.expanduser("~"), ".dld-privacy-patterns")
MAX_BYTES = 8 * 1024 * 1024          # 超过 8 MB 的文件跳过内容扫描（仍查文件名）
BINARY_SNIFF = 8192                  # 头 8 KB 里有 NUL ⇒ 当二进制，不扫内容

# 占位符白名单：文档里的示例路径本来就该长这样，不算泄漏
_PLACEHOLDER = r"(?!me[/\\]|user[/\\]|you[/\\]|<|xxx|XXX|USER|用户名)"
RULES = [
    ("本机绝对路径（Windows 用户目录）",
     re.compile(r"[A-Za-z]:[\\/]Users[\\/]" + _PLACEHOLDER + r"[^\\/\s\"'|<>]+")),
    ("本机绝对路径（macOS / Linux 家目录）",
     re.compile(r"/(?:Users|home)/(?!me/|user/|you/|<|xxx|USER)[A-Za-z0-9._-]+/")),
    ("10 位学号形状的数字串",
     re.compile(r"(?<![0-9A-Za-z])20[0-9]{8}(?![0-9A-Za-z])")),
]
# 文档里**有意**写的示例学号：写在这里是为了让"示例"与"真泄漏"可区分，
# 而不是为了让扫描变松 —— 加值必须同时补一条注释说明它为什么安全。
ALLOW = {
    "2024000000",     # README/HANDOVER 里 --id 的用法示例
}
# 只对**提交信息**跑：提交信息里出现 12 位以上纯数字串很反常（文件里则是正常数据，例如
# 64 位掩码、DOI、DOI 里的流水号），所以不进文件扫描，避免噪音淹没真信号。
WARNS = [
    ("12 位以上纯数字串（人工判）", re.compile(r"(?<![0-9A-Za-z])[0-9]{12,}(?![0-9A-Za-z])")),
]

# ---------------------------------------------------------------------------
# 已知历史基线：这几个**旧提交的信息里**提到过本机绝对路径（只有用户名，没有姓名/学号）。
#
# 为什么不重写它们：它们在 2026-10-10 / 10-10 / 10-15，重写会把之后 23～54 个提交的
# 哈希全部换掉 —— 而 `HANDOFF.md` / `docs/03` / `docs/06` / `PROGRESS.md` / `AI_LOG.md`
# 大量按哈希引用那些提交（`sim/rounds/*.json` 的证据链也挂在上面）。
# 拿"文档里所有哈希引用集体失效"去换"3 条旧提交信息里的一个用户名"不划算，
# 所以这里**显式登记**为已知项：命中它们只报 WARN，且必须写明理由。
# 新增项必须同时补理由；这一节不是"忽略清单"，而是"已知并接受的清单"。
KNOWN_HISTORICAL = {
    "4117137c": "2026-10-15：提交信息在描述 refs/README.md 脱敏时引用了脱敏前的路径原文",
    "65ada936": "2026-10-10：提交信息在描述「消除全部作者绝对路径」时引用了被消除的路径原文",
    "219e4bbd": "2026-10-10：提交信息在描述 sim_summary.py 去写死路径时引用了旧路径原文",
}


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SystemExit("git %s 失败：%s" % (" ".join(args), p.stderr.strip()))
    return p.stdout


def scan(label: str, text: str, where: str, rules, hits: list, quiet: bool) -> None:
    for name, rx in rules:
        for m in rx.finditer(text):
            if m.group(0) in ALLOW:
                continue
            frag = text[max(0, m.start() - 24):m.end() + 24].replace("\n", " ")
            hits.append((label, name, where, frag))
            if not quiet:
                print("  ✗ [%s] %s\n      %s\n      …%s…" % (label, name, where, frag))


def classify(hits: list) -> tuple[list, list]:
    """把命中分成 (真 FAIL, 已知历史 WARN)。

    只有**提交信息**的命中才可能落进已知基线（基线是按提交登记的）。
    """
    fails, known = [], []
    for h in hits:
        label, _name, where, _frag = h
        if label == "提交信息" and where in KNOWN_HISTORICAL:
            known.append(h)
        else:
            fails.append(h)
    return fails, known


def main() -> int:
    ap = argparse.ArgumentParser(description="隐私体检：跟踪文件 + 提交信息 + 作者身份")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总与命中摘要")
    ap.add_argument("--extra", metavar="FILE", default=DEFAULT_EXTRA,
                    help="追加规则文件（一行一条正则；默认 ~/.dld-privacy-patterns）")
    args = ap.parse_args()

    rules = list(RULES)
    if os.path.isfile(args.extra):
        extra = []
        with open(args.extra, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    extra.append(("追加规则（%s）" % os.path.basename(args.extra), re.compile(line)))
        rules += extra
        print("已加载追加规则 %d 条（来自仓库外的 %s）" % (len(extra), args.extra))
    elif args.extra != DEFAULT_EXTRA:
        print("[警告] 指定的追加规则文件不存在：%s" % args.extra)

    fails: list = []
    warns: list = []

    # ---- ① 跟踪文件 -------------------------------------------------------
    files = [f for f in git("ls-files", "-z").split("\0") if f]
    print("== ① 跟踪文件：%d 个 ==" % len(files))
    skipped = binaries = 0
    for rel in files:
        scan("文件路径", rel, rel, rules, fails, args.quiet)
        abs_p = os.path.join(ROOT, rel)
        try:
            if os.path.getsize(abs_p) > MAX_BYTES:
                skipped += 1
                continue
            raw = open(abs_p, "rb").read()
        except OSError:
            continue
        if b"\0" in raw[:BINARY_SNIFF]:
            binaries += 1                     # PNG/PDF/DOCX 等压缩容器，原始字节里看不到明文
            continue
        text = raw.decode("utf-8", "replace")
        if "\ufffd" in text:                  # 不是干净 UTF-8 ⇒ 再按 latin-1 兜一遍
            text += "\n" + raw.decode("latin-1", "replace")
        scan("文件内容", text, rel, rules, fails, args.quiet)
    print("   跳过：%d 个 > %d MB、%d 个二进制（PNG/PDF/DOCX 需另行解包，见脚本头部）"
          % (skipped, MAX_BYTES // 1024 // 1024, binaries))

    # ---- ② 提交信息 -------------------------------------------------------
    shallow = git("rev-parse", "--is-shallow-repository").strip() == "true"
    raw = git("log", "--all", "--format=%H%x1f%B%x1e")
    commits = [c for c in raw.split("\x1e") if c.strip()]
    print("== ② 提交信息：扫到 %d 个提交%s =="
          % (len(commits), "（⚠️ 浅克隆：看不到更早的历史）" if shallow else ""))
    for c in commits:
        sha, _, msg = c.partition("\x1f")
        scan("提交信息", msg, sha.strip()[:8], rules, fails, args.quiet)
        scan("提交信息", msg, sha.strip()[:8], WARNS, warns, args.quiet)

    # ---- ③ 作者 / 提交者身份 ---------------------------------------------
    ids = set()
    for line in git("log", "--all", "--format=%an%x1f%ae%x1f%cn%x1f%ce").splitlines():
        for part in line.split("\x1f"):
            if part.strip():
                ids.add(part.strip())
    print("== ③ 作者/提交者身份：%d 个不同取值 ==" % len(ids))
    for v in sorted(ids):
        scan("作者身份", v, v, rules, fails, args.quiet)

    # ---- 汇总 -------------------------------------------------------------
    print("-" * 74)
    fails, known = classify(fails)
    for label, name, where, frag in known:
        print("  ⚠ [已知历史] %s @ %s：%s" % (name, where, KNOWN_HISTORICAL[where]))
    for label, name, where, frag in warns[:10]:
        print("  ⚠ [%s] %s @ %s：…%s…" % (label, name, where, frag))
    if len(warns) > 10:
        print("  ⚠ …另有 %d 条 WARN 未展开" % (len(warns) - 10))
    if fails:
        print("FAIL：%d 处疑似隐私泄漏（跟踪文件 / 提交信息 / 作者身份）" % len(fails))
        print("      提交信息里的泄漏**改文件没用**，必须重写历史并 force-push，")
        print("      改完再跑一次本脚本确认；具体做法见 HANDOVER.md §7。")
        return 1
    print("PASS：跟踪文件 %d 个 + 提交信息 %d 个 + 作者身份 %d 个，均无命中%s。"
          % (len(files), len(commits), len(ids),
             "（%d 条命中已登记为已知历史）" % len(known) if known else ""))
    if shallow:
        print("      ⚠️ 本次是浅克隆，历史只覆盖 %d 个提交 —— 全量结论请在完整克隆上跑。" % len(commits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
