#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book/scripts/book.py —— 文档站的**唯一入口**（生成 / 构建 / 校验 / 起服务）

为什么要有这一个入口
--------------------
文档站里有三类内容，顺序错了就会得到"陈旧但能构建"的假成功：
    1. `facts/facts.json`   ← 从 rtl/ sim/ quartus/ 抽取（scripts/extract_facts.py）
    2. `docs/_generated/`   ← 从 facts.json 生成的表格页（book/scripts/gen_pages.py）
    3. `docs/assets/`       ← 从 docs/图/ 同步的素材（book/scripts/sync_assets.py）
    4. 然后才是 `mkdocs build --strict`
把这四步包在一个命令里，就不会出现"忘了重新生成事实页"这种事。

子命令
------
    serve    生成 + 起本地预览服务（默认 http://127.0.0.1:8000/）
    build    生成 + `mkdocs build --strict`（CI 用）
    check    只做一致性校验（facts 是否过期、book 与源码是否一致），不构建
    gen      只做前三步生成（不构建）

用法
----
    python book/scripts/book.py serve
    python book/scripts/book.py build
    # 产物默认落在 book/site/（site_dir 由 mkdocs.yml 定义，相对该配置文件所在目录）；
    # 想放别处就传一个**相对 book/ 的路径**：
    python book/scripts/book.py build --site-dir ../somewhere-else
    python book/scripts/book.py check
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.dirname(HERE)
ROOT = os.path.dirname(BOOK)
PY = sys.executable
MK = os.path.join(BOOK, ".venv", "Scripts", "python.exe" if os.name == "nt" else "bin/python")

if not os.path.exists(MK):
    MK = PY  # 允许用任意已有解释器（CI 里通常直接 pip install -r）


def run(cmd: list[str], cwd: str | None = None, env: dict | None = None) -> None:
    print("+ " + " ".join(cmd))
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(cmd, cwd=cwd or ROOT, env=e)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def gen(check: bool = False) -> None:
    if check:
        run([PY, "scripts/extract_facts.py", "--check"])
    else:
        run([PY, "scripts/extract_facts.py"])
    run([PY, "book/scripts/gen_pages.py"])
    run([PY, "book/scripts/sync_assets.py"])


def mkdocs(*args: str, site_dir: str | None = None) -> None:
    env = {
        # Material 9.7.7 会在构建时往 stderr 打一段"MkDocs 2.0 迁移警告"横幅。
        # 它是 print 不是 log.warning（不影响 --strict），但会把 CI 日志搅乱，
        # 所以显式关掉。素材自带的开关名是上游定义的：NO_MKDOCS_2_WARNING。
        "NO_MKDOCS_2_WARNING": "true",
    }
    if site_dir:
        env["BOOK_SITE_DIR"] = site_dir
    run([MK, "-m", "mkdocs", *args, "-f", os.path.join(BOOK, "mkdocs.yml")], env=env)


def main() -> int:
    ap = argparse.ArgumentParser(description="文档站统一入口")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="生成并起本地服务")
    p_serve.add_argument("--dev-addr", default="127.0.0.1:8000")
    p_serve.add_argument("--site-dir", default=None)

    p_build = sub.add_parser("build", help="生成并 --strict 构建")
    p_build.add_argument("--site-dir", default=None)
    p_build.add_argument("--no-strict", action="store_true")

    sub.add_parser("gen", help="只做生成")
    sub.add_parser("check", help="只做一致性校验（不构建）")

    args = ap.parse_args()

    if args.cmd == "check":
        gen(check=True)
        run([PY, os.path.join("book", "scripts", "check_book.py")])
        return 0
    if args.cmd == "gen":
        gen()
        return 0
    if args.cmd == "serve":
        gen()
        # 每次改页面都重新生成，避免"改了源码但事实页没动"
        mkdocs("serve", "-a", args.dev_addr, site_dir=args.site_dir)
        return 0
    if args.cmd == "build":
        gen()
        mkdocs("build", *(["--strict"] if not args.no_strict else []), site_dir=args.site_dir)
        # 构建完立刻**自证产物**：canonical 是否等于 site_url、sitemap 是否都在
        # /dld/ 下、有没有绕开子路径的绝对路径引用、有没有外部 CDN 的 <script src>。
        # 只有在用默认产物目录（book/site）时才有意义 —— 传了 --site-dir 的话
        # check_book 找不到它，所以跳过（那一档由工作流自己断言）。
        if not args.site_dir:
            run([PY, os.path.join("book", "scripts", "check_book.py"), "--site"])
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
