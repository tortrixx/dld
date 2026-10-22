#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_report.py —— 实验报告「一条命令」构建链（PDF / MD / DOCX 三份载体同源）

【为什么要有它】
    报告有四种载体，唯一事实源是 `docs/report/实验报告_题目4_简易拼图游戏.typ`：
        .typ  --typst-->  .pdf        （交付主件）
        .typ  --本脚本--> .md          （scripts/gen_report_md.py 生成）
        .typ  --本脚本--> .docx        （scripts/sync_report_docx.py 同步）
    以前这条链**没有入口**：Typst 不在 PATH、没人知道要按什么顺序跑哪三个脚本，
    只有 `docs/report/WINDOWS_QUARTUS_HANDOFF.md` 里零散写过，而那份文件没有任何入链。
    于是"改了 .typ 忘了同步 md/docx"这类漂移只能靠事后审计抓。

【用法】（在仓库根执行）
    python scripts/build_report.py                 # 全链：确保 typst → 编译 PDF → 生成 md → 同步 docx
    python scripts/build_report.py --check         # 只校验四件套是否同步（不写盘、不下载）
    python scripts/build_report.py --fetch-only    # 只把 typst 编译器准备好

    # 个人上交版：封面只留 姓名/学号/日期，且**真实信息不进仓库**（从命令行传入）
    python scripts/build_report.py --submission --name 张三 --id 2024000000 \
        --out "C:\\Users\\me\\Desktop\\上交\\张三_实验报告.pdf"

【隐私】
    `--submission` 的姓名/学号只作为 `typst --input` 的参数存在，
    **不写进仓库任何文件**；产物默认写到仓库外，并且本脚本会拒绝写到 `docs/report/` 里。
    中间那一步暂存在 `.tmp/report_build/submission.pdf`（沙箱只允许 typst 写工作区内），
    无论编译成功与否都会在 `finally` 里删除，不会把带身份的 PDF 留在仓库里。

【提交信息也算隐私面】
    文件干净不代表历史干净：真实姓名/学号/本机绝对路径**一旦写进提交信息**，
    就会随 push 一起泄露，而且 `git grep` / `git log -S` 这类按**内容**检索的工具看不见它。
    所以入库前请跑 `python scripts/check_privacy.py`（它会扫跟踪文件 + 提交信息 + 作者身份）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

# ⚠️ Windows 控制台默认 GBK：本脚本要打印 ⚠️/→ 之类的符号，
#    不切 UTF-8 会在**最后一行日志**上抛 UnicodeEncodeError ——
#    文件其实已经写好了，退出码却是 1（自动化会被骗）。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = os.path.join(ROOT, "docs", "report")
TYP_NAME = "实验报告_题目4_简易拼图游戏.typ"
TYP = os.path.join(REPORT, TYP_NAME)
PDF = os.path.join(REPORT, "实验报告_题目4_简易拼图游戏.pdf")

TYPST_VERSION = "0.15.1"
TYPST_DIR = os.path.join(ROOT, ".tmp", "tools", "typst")
TYPST_URL = (
    "https://github.com/typst/typst/releases/download/v{v}"
    "/typst-x86_64-pc-windows-msvc.zip"
)


def log(msg: str) -> None:
    print(msg, flush=True)


# --------------------------------------------------------------------------- typst
def typst_exe() -> str | None:
    for base, _dirs, files in os.walk(TYPST_DIR):
        for f in files:
            if f == "typst.exe":
                return os.path.join(base, f)
    return None


def ensure_typst() -> str | None:
    exe = typst_exe()
    if exe:
        return exe
    os.makedirs(TYPST_DIR, exist_ok=True)
    url = TYPST_URL.format(v=TYPST_VERSION)
    zip_path = os.path.join(TYPST_DIR, "typst.zip")
    log(f"下载 Typst {TYPST_VERSION} …\n  {url}")
    try:
        with urllib.request.urlopen(url, timeout=300) as resp, open(zip_path, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(TYPST_DIR)
        os.remove(zip_path)
    except Exception as exc:                          # noqa: BLE001
        log(f"[错误] 下载/解压 Typst 失败：{exc}")
        log("       报告 PDF 需要它；md/docx 两条链不需要，可用 --check 单独校验。")
        return None
    return typst_exe()


def compile_typst(exe: str, out_pdf: str, inputs: dict[str, str] | None = None) -> int:
    cmd = [exe, "compile"]
    for k, v in (inputs or {}).items():
        cmd += ["--input", f"{k}={v}"]
    cmd += [TYP_NAME, out_pdf]
    log("  $ typst " + " ".join(cmd[1:]))
    p = subprocess.run(cmd, cwd=REPORT)
    return p.returncode


# --------------------------------------------------------------------------- 子步骤
def run_script(rel: str, *args: str) -> int:
    cmd = [sys.executable, os.path.join(ROOT, "scripts", rel), *args]
    log("  $ python scripts/" + rel + " " + " ".join(args))
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验四件套是否同步")
    ap.add_argument("--fetch-only", action="store_true", help="只准备 typst 编译器")
    ap.add_argument("--submission", action="store_true", help="生成个人上交版 PDF（封面只留姓名/学号/日期）")
    ap.add_argument("--name", help="--submission 用：学生姓名")
    ap.add_argument("--id", help="--submission 用：学生学号")
    ap.add_argument("--date", default="2026年10月", help="--submission 用：报告日期")
    ap.add_argument("--out", help="--submission 用：输出 PDF 路径（**必须在仓库外**）")
    args = ap.parse_args()

    if not os.path.isfile(TYP):
        log(f"[错误] 找不到事实源：{TYP}")
        return 1

    # ---- 个人上交版 -------------------------------------------------------
    if args.submission:
        if not args.name or not args.id or not args.out:
            log("[错误] --submission 需要同时给 --name / --id / --out")
            return 2
        out_abs = os.path.abspath(args.out)
        # ⚠️ 必须 normcase 后再比：Windows 路径大小写不敏感，大小写变体
        #    （把盘符/目录名换一种写法）用裸 startswith 是**绕得过去**的
        #    —— 同一个目录会被当成"仓库外"。
        root_abs = os.path.normcase(os.path.abspath(ROOT))
        out_norm = os.path.normcase(out_abs)
        if out_norm == root_abs or out_norm.startswith(root_abs + os.sep):
            log("[错误] 上交版含真实姓名/学号，**不能写进仓库目录**（含 docs/report/）。")
            log(f"       请换一个仓库外的路径，例如：{os.path.join(os.path.expanduser('~'), 'Desktop')}\\上交\\报告.pdf")
            return 2
        exe = ensure_typst()
        if not exe:
            return 1
        # typst 在沙箱里只能写工作区内，所以先编到 .tmp/ 再搬出去。
        # ⚠️ 暂存件**含真实姓名/学号**，所以无论成败都在 finally 里删掉 ——
        #    否则编译成功但搬移失败时，仓库里会留下一份带身份的 PDF。
        #    （进程被硬杀（SIGKILL）时 finally 不会执行，仍可能残留一份；
        #      所以 .tmp/ 本身也在 .gitignore 里，且 scripts/check_privacy.py 会扫历史 blob。）
        stage_dir = os.path.join(ROOT, ".tmp", "report_build")
        os.makedirs(stage_dir, exist_ok=True)
        staged = os.path.join(stage_dir, "submission.pdf")
        try:
            rc = compile_typst(exe, staged, {
                "submission": "true", "name": args.name, "id": args.id, "date": args.date,
            })
            if rc != 0 or not os.path.isfile(staged):
                log("[错误] 上交版编译失败")
                return 1
            os.makedirs(os.path.dirname(out_abs) or ".", exist_ok=True)
            shutil.move(staged, out_abs)
        finally:
            if os.path.isfile(staged):
                os.remove(staged)
        log(f"\n上交版已写出（仓库外）：{out_abs}")
        log(f"  封面字段：学生姓名 / 学生学号 / 报告日期（{args.date}）")
        log("  ⚠️ 请勿把这份文件复制进仓库；docs/report/ 下只保留占位符版本。")
        return 0

    # ---- 只准备编译器 -----------------------------------------------------
    if args.fetch_only:
        exe = ensure_typst()
        log(f"typst: {exe}" if exe else "typst: 不可用")
        return 0 if exe else 1

    # ---- 只校验 -----------------------------------------------------------
    if args.check:
        rc = 0
        log("== 1/3 md 与 .typ 是否一致 ==")
        rc |= run_script("gen_report_md.py", "--check")
        log("== 2/3 docx 是否与 .typ 收敛 ==")
        rc |= run_script("sync_report_docx.py", "--check")
        log("== 3/3 PDF 是否存在且比 .typ 新 ==")
        if not os.path.isfile(PDF):
            log("  x 缺 PDF")
            rc |= 1
        elif os.path.getmtime(PDF) < os.path.getmtime(TYP):
            log("  x PDF 比 .typ 旧 —— .typ 改过但没重新编译")
            rc |= 1
        else:
            log("  OK PDF 存在且不早于 .typ")
        log("\n" + ("全部同步。" if rc == 0 else "有不同步项（见上）。"))
        return 1 if rc else 0

    # ---- 全链 -------------------------------------------------------------
    log("== 1/3 编译 PDF ==")
    exe = ensure_typst()
    if exe:
        if compile_typst(exe, PDF) != 0:
            log("[错误] PDF 编译失败")
            return 1
        log(f"  OK {os.path.relpath(PDF, ROOT)}")
    else:
        log("  跳过（typst 不可用）")

    log("== 2/3 生成 .md ==")
    if run_script("gen_report_md.py") != 0:
        return 1

    log("== 3/3 同步 .docx ==")
    if run_script("sync_report_docx.py", "--apply") != 0:
        return 1

    log("\n完成。四件套已同源；如需个人上交版：")
    log("  python scripts/build_report.py --submission --name <姓名> --id <学号> --out <仓库外路径>.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
