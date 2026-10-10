#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_comments.py —— 注释相关的两条守卫（**只用标准库**）。

【它是从哪来的】
    2026-10-10 那次"把全项目英文注释译成中文"的工作里，我用一个临时脚本
    （`.tmp/check_comments_only.py`）证明"95 个文件只改了注释、代码一个字节没动"，
    并**当场抓出过自己的漂移**（只改了 tb 的旋律表、忘了同步 RTL）。
    那条经验值得固化下来，所以把它转正成仓库里的工具。

【两条守卫】
    1. `scan` —— 列出**疑似仍含英文散文**的注释行（给人看的清单，**不是**硬门禁）。
       判据：整行/行尾注释里有 2 个以上英文单词，且**没有任何汉字与中文标点**。
       编码头 / shebang / 纯标识符 / 数据表 / ASCII 图会被排除。
       `.py` 的注释用 `tokenize` 取（**不会把三引号字符串里的内容当成注释**）。

    2. `diff [文件...]` —— 证明"这次改动**只动了注释**"。
       做法：把每个改动文件在 **HEAD 版**与**工作区版**各自按 `srcnorm` 归一化
       （去注释 / 去函数 docstring / 统一行尾）再比较。两边相同 ⇒ 代码部分没动。
       ⚠️ 归一化**忽略行尾差异**（CRLF/LF 不算改动）—— 这是要的：换行尾不改变行为。

【退出码】（⚠️ 三种"0"必须区分开，否则会把"没检查"当成"检查通过"）
    0 —— 全部改动文件都**真的**验证过，且都只改了注释；
    1 —— 有文件**验证失败**（代码被改动），或出现**新增/删除的源码文件**
         （没有基线，无法用本工具证明"只改注释"）；
    2 —— **工具没能执行**（不在 git 仓库、git 不可用、HEAD 无法解析、指定的文件
         一个都不在改动集里）—— 绝不落回"没有差异"当通过。

【用法】
    python scripts/check_comments.py scan
    python scripts/check_comments.py diff
    python scripts/check_comments.py diff rtl/game_fsm.vhd sim/tb_game_fsm.py
"""
import pathlib
import re
import subprocess
import sys
import tokenize

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import srcnorm  # noqa: E402

# 构建产物 / 隔离工程 / 轮次记录不参与
SKIP_PREFIX = (".tmp/", "quartus/db/", "quartus/output_files/", "quartus/incremental_db/",
               "sim/rounds/")

# 汉字 **与中文标点**（U+3000–303F 中日韩符号、U+FF00–FFEF 全角形式）——
# ⚠️ 早先只认 U+3400–9FFF，于是 `DISP7=5，DISP0=level（B2、B3）` 这种
#     "只有中文标点、没有汉字"的数据行被误报成英文散文。
CJK = re.compile(r"[\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")
# "两个以上英文单词"才算散文；单个标识符/命令/单位不算
PROSE = re.compile(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}")


def _git(*a, binary=False):
    """跑 git。返回 (ok, 输出)；**ok=False 表示 git 本身失败**（绝不与"无输出"混淆）。"""
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false"] + list(a), cwd=str(ROOT),
                           capture_output=True)
    except Exception as e:                                     # noqa: BLE001
        return False, "无法执行 git：%s" % e
    if r.returncode != 0:
        return False, r.stderr.decode("utf-8", "replace").strip() or ("git rc=%d" % r.returncode)
    return True, (r.stdout if binary else r.stdout.decode("utf-8", "replace"))


# ---------------------------------------------------------------- scan
def _comment_lines_py(path):
    """用 tokenize 取 .py 的真注释（不会把三引号字符串里的内容当成注释）。"""
    out = []
    try:
        with open(path, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.COMMENT:
                    out.append((tok.start[0], tok.string))
    except Exception:                                          # noqa: BLE001
        for i, ln in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if ln.strip().startswith("#"):
                out.append((i, ln.strip()))
    return out


def _comment_lines_vhdl(text):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        in_str = False
        for k in range(len(ln) - 1):
            if ln[k] == '"':
                in_str = not in_str
            if not in_str and ln[k] == "-" and ln[k + 1] == "-":
                out.append((i, ln[k:]))
                break
    return out


def _comment_lines_hash(text):
    out = []
    for i, ln in enumerate(text.splitlines(), 1):
        st = ln.strip()
        if st.startswith("#"):
            out.append((i, st))
    return out


def cmd_scan():
    ok, files = _git("ls-files")
    if not ok:
        print("✗ 无法列出仓库文件：%s" % files)
        return 2
    hits = []
    for rel in files.splitlines():
        if not rel.strip() or rel.startswith(SKIP_PREFIX):
            continue
        p = ROOT / rel
        suffix = p.suffix.lower()
        if not p.exists():
            continue
        if suffix == ".py":
            cl = _comment_lines_py(p)
        elif suffix == ".vhd":
            cl = _comment_lines_vhdl(p.read_text(encoding="utf-8", errors="replace"))
        elif suffix in (".tcl", ".sdc", ".qsf"):
            cl = _comment_lines_hash(p.read_text(encoding="utf-8", errors="replace"))
        else:
            continue
        for i, body in cl:
            t = body.lstrip("#-").strip()
            if not t or t.startswith("-*-") or t.startswith("!"):
                continue
            if PROSE.search(t) and not CJK.search(t):
                hits.append((rel, i, t[:100]))
    print("=" * 76)
    print("疑似仍含**英文散文**的注释行：%d 处（%d 个文件）" % (len(hits), len({h[0] for h in hits})))
    print("=" * 76)
    for rel, i, t in hits:
        print("  %-40s %5d  %s" % (rel, i, t))
    if not hits:
        print("  （无）")
    print("-" * 76)
    print("说明：**不是硬门禁**（恒返回 0）。编码头、shebang、纯标识符、数据表、ASCII 图都已排除；")
    print("      剩下的如果确实该译，就译掉；如果是有意保留的英文，忽略即可。")
    return 0


# ---------------------------------------------------------------- diff
def cmd_diff(only=None):
    ok, out = _git("diff", "--name-status", "HEAD")
    if not ok:
        print("✗ 无法取得与 HEAD 的差异：%s" % out)
        print("  （不在 git 仓库里、或 HEAD 还不存在 —— 本工具无法判断，**不会**当作通过）")
        return 2

    entries = []          # (status, rel)
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 2:
            entries.append((parts[0].strip(), parts[-1]))
    entries = [e for e in entries if not e[1].startswith(SKIP_PREFIX)]

    # ⚠️ `git diff HEAD` **看不到未跟踪的新文件** —— 只靠它，一个刚写出来、
    #    还没 `git add` 的源码文件会被完全忽略，而结论却仍写「只改了注释 ✓」。
    #    这里把未跟踪文件也收进来（标成 A，走"没有基线"那条失败分支）。
    ok_u, untracked = _git("ls-files", "--others", "--exclude-standard")
    if ok_u:
        for rel in untracked.splitlines():
            if rel.strip() and not rel.startswith(SKIP_PREFIX):
                entries.append(("A?", rel))

    if only:
        want = {pathlib.PurePosixPath(x.replace("\\", "/")).as_posix().lstrip("./").lower()
                for x in only}
        sel = [e for e in entries
               if pathlib.PurePosixPath(e[1]).as_posix().lower() in want]
        if not sel:
            print("✗ 你指定的文件一个都不在改动集里：%s" % "、".join(sorted(want)))
            print("  （当前改动集：%s）" % ("、".join(e[1] for e in entries) or "空"))
            return 2
        entries = sel

    if not entries:
        print("工作区与 HEAD 没有差异（没有可检查的改动）")
        return 0

    verified, failed, unchecked = [], [], []
    for status, rel in entries:
        suffix = pathlib.Path(rel).suffix.lower()
        if status.startswith("D"):
            failed.append((rel, "**删除了源码文件** —— 这不是「只改注释」，且没有可比较的基线"))
            continue
        if status.startswith("A"):
            failed.append((rel, "**新增了源码文件** —— 没有基线，本工具无法证明「只改注释」"))
            continue
        if not srcnorm.is_text_suffix(suffix):
            unchecked.append((rel, "非文本（按字节比较）"))
            ok2, old = _git("show", "HEAD:" + rel, binary=True)
            new_p = ROOT / rel
            if not ok2 or not new_p.exists():
                unchecked.append((rel, "取不到基线或工作区文件"))
                continue
            (verified if old == new_p.read_bytes() else failed).append(
                rel if old == new_p.read_bytes() else (rel, "**字节不同**（非文本文件）"))
            continue
        ok2, old = _git("show", "HEAD:" + rel, binary=True)
        new_p = ROOT / rel
        if not ok2 or not new_p.exists():
            unchecked.append((rel, "取不到基线或工作区文件"))
            continue
        try:
            same = srcnorm.differs_only_in_comments(old, new_p.read_bytes(), suffix)
        except Exception as e:                                 # noqa: BLE001
            failed.append((rel, "归一化失败：%s" % e))
            continue
        if same:
            verified.append(rel)
        else:
            failed.append((rel, "**代码部分被改动了**（抽掉注释后仍有差异）"))

    print("=" * 76)
    print("「只改了注释」证明：%d 个改动文件" % len(entries))
    print("=" * 76)
    for rel in verified:
        print("  ✓ %-42s 代码部分一致（只差注释/行尾）" % rel)
    for rel, why in failed:
        print("  ✗ %-42s %s" % (rel, why))
    for rel, why in unchecked:
        print("  ? %-42s %s —— **未验证**" % (rel, why))
    print("-" * 76)
    if failed:
        print("结论：**不能算「只改注释」**（%d 个通过 / %d 个失败 / %d 个未验证）"
              % (len(verified), len(failed), len(unchecked)))
    elif unchecked:
        print("结论：已验证的 %d 个文件都只改了注释，但**还有 %d 个文件没验证**（见上面的 ? 行）"
              % (len(verified), len(unchecked)))
    else:
        print("结论：**只改了注释** ✓（%d 个全部通过）" % len(verified))
    return 1 if (failed or unchecked) else 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if cmd == "diff":
        sys.exit(cmd_diff(sys.argv[2:] or None))
    sys.exit(cmd_scan())
