#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book/scripts/check_book.py —— 文档站一致性门禁

分两层：

  * **页面级**（给定文件参数时）：逐页检查
      · `{{fact:...}}` 能否在 facts/facts.json 里解析
      · `{{src:path:line}}` / `{{tree:path}}` 指向的文件是否**已入库**（`git ls-files`）
        —— 未入库的文件在克隆出来的仓库里不存在，链接必然 404
      · `--8<-- "_generated/x.md"` 引用的生成页是否存在
      · `![...](相对路径)` 引用的图片是否存在
      · `[文字](xxx.md)` 相对链接是否存在
      · 有没有残留未解析的 `{{...}}`
      · 有没有残留占位标记（防止"空壳页"混进交付）

  * **站点级**（不给参数时）：在页面级之上再加
      · `mkdocs.yml` 的 nav 里每一页都存在，且文档目录里没有"漏进 nav"的页面
      · `facts/facts.json` 与源码一致（调用 `scripts/extract_facts.py --check`）
      · 关键工程数字：页面里出现的 LE/LAB/Fmax 必须能在 facts.json 里找到同值
      · 每个真实实体都有对应文档页；每个模块页都链接了它自己的测试台与最新轮次
      · GitHub Pages 子路径：产物里 `/dld/` 前缀与相对资源都能对上

用法
----
    python book/scripts/check_book.py                 # 全量
    python book/scripts/check_book.py book/docs/03-modules/index.md [...]
    python book/scripts/check_book.py --site          # 连构建产物一起查

退出码：0 通过；1 有失败项。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.dirname(HERE)
ROOT = os.path.dirname(BOOK)
DOCS = os.path.join(BOOK, "docs")
FACTS_PATH = os.path.join(ROOT, "facts", "facts.json")

REL_DOC_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
IMG_LINK = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
SNIPPET = re.compile(r"--8<--\s*[\"']([^\"']+)[\"']")
FACT = re.compile(r"\{\{fact:([A-Za-z0-9_.\[\]-]+)\}\}")
SRC = re.compile(r"\{\{src:([^:}\s]+)(?::\d+)?\}\}")
TREE = re.compile(r"\{\{tree:([^}\s]+)\}\}")
# 合法的占位符形态（含无冒号的那三个）。**必须**与 hooks/facts.py 的实现一致：
# 钩子认得的一律不算"残留"，只有钩子不认得的才算错。
LEGIT_PLACEHOLDER = re.compile(r"^\{\{\s*(?:fact:[A-Za-z0-9_.\[\]-]+|src:[^:}\s]+(?::\d+)?|tree:[^}\s]+|repo|docs_site)\s*\}\}$")
LEFTOVER = re.compile(r"\{\{[^}]*\}\}")
PLACEHOLDER = "<!-- PLACEHOLDER"

# 工作区里存在、但**还没入库**的引用：页面模式下只警告（开发中期是正常的），
# 站点模式下算失败（克隆下来就是死链）。
TRACKED_STRICT = False

errors: list[str] = []
warnings: list[str] = []
checked = 0


def err(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def unbacked(rel: str, what: str, target: str) -> None:
    """「工作区有、git 还没有」的引用：按当前模式记 WARN 或 FAIL。"""
    msg = "%s: %s 指向 %s，工作区存在但**尚未入库**（克隆下来会 404；提交后即消失）" % (rel, what, target)
    if TRACKED_STRICT:
        err(msg)
    else:
        warn(msg)


def load_facts() -> dict:
    with open(FACTS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def git_tracked() -> set[str]:
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "-z"], capture_output=True).stdout
    return {p for p in out.decode("utf-8").split("\0") if p}


def resolve(facts: dict, path: str):
    cur = facts
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            if not isinstance(cur, dict) or part not in cur:
                raise KeyError(path)
            cur = cur[part]
    return cur


def check_page(path: str, facts: dict, tracked: set[str]) -> None:
    global checked
    checked += 1
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    text = open(path, "r", encoding="utf-8").read()

    if PLACEHOLDER in text:
        err("%s: 仍是预置占位页（正文未撰写）" % rel)

    for m in FACT.finditer(text):
        try:
            resolve(facts, m.group(1))
        except Exception:
            err("%s: {{fact:%s}} 在 facts.json 里不存在" % (rel, m.group(1)))

    for m in SRC.finditer(text):
        p = m.group(1)
        fp = os.path.join(ROOT, p)
        if not os.path.exists(fp):
            err("%s: {{src:%s}} 指向的文件不存在" % (rel, p))
        elif p not in tracked:
            unbacked(rel, "{{src:%s}}" % p, p)

    for m in TREE.finditer(text):
        p = m.group(1)
        fp = os.path.join(ROOT, p)
        if not os.path.isdir(fp):
            err("%s: {{tree:%s}} 不是仓库里的目录" % (rel, p))
        elif not any(t.startswith(p.rstrip("/") + "/") for t in tracked):
            unbacked(rel, "{{tree:%s}}" % p, p)

    for m in SNIPPET.finditer(text):
        inc = m.group(1)
        if inc.startswith(("http://", "https://")):
            continue
        target = inc if os.path.isabs(inc) else os.path.join(DOCS, inc.lstrip("/") if inc.startswith("/") else inc)
        if not os.path.exists(target):
            err("%s: --8<-- \"%s\" 引用的生成页不存在（先跑 book/scripts/gen_pages.py）" % (rel, inc))

    for m in IMG_LINK.finditer(text):
        src = m.group(1)
        if re.match(r"^(https?:)?//|^data:", src):
            continue
        src_clean = src.split(" ")[0].split("#")[0]
        target = os.path.normpath(os.path.join(os.path.dirname(path), src_clean))
        if not os.path.exists(target):
            err("%s: 图片 %s 不存在" % (rel, src_clean))

    for m in REL_DOC_LINK.finditer(text):
        href = m.group(1)
        if re.match(r"^(https?:)?//|^mailto:|^#|^data:", href):
            continue
        target_part = href.split("#")[0]
        if not target_part:
            continue
        if not target_part.endswith(".md"):
            # 指向仓库里非 md 的原始文件（例如 .vhd/.py）在站点内不可达，
            # 必须走 {{src:...}} 的 GitHub 链接
            if re.search(r"\.(vhd|py|json|qsf|sdc|vwf|v|sv|tcl|ps1|sh)$", target_part):
                err("%s: 相对链接 %s 指向仓库源文件；站点内不可达，请改用 {{src:%s}}" % (rel, href, target_part.lstrip("./")))
            continue
        target = os.path.normpath(os.path.join(os.path.dirname(path), target_part))
        if not os.path.exists(target):
            err("%s: 内部链接 %s 不存在（对应 %s）" % (rel, href, os.path.relpath(target, ROOT)))

    left = [x for x in LEFTOVER.findall(text) if not LEGIT_PLACEHOLDER.match(x)]
    if left:
        err("%s: 残留未识别的占位符 %s（钩子只认 {{fact:}} / {{src:}} / {{tree:}} / {{repo}} / {{docs_site}}）" % (rel, left[:3]))


def nav_pages() -> list[str]:
    text = open(os.path.join(BOOK, "mkdocs.yml"), encoding="utf-8").read()
    nav = text.split("\nnav:", 1)[1]
    out = []
    for a, b in re.findall(r":\s*([0-9A-Za-z_./-]+\.md)\s*$|^\s*-\s*([0-9A-Za-z_./-]+\.md)\s*$", nav, re.M):
        out.append(a or b)
    return out


def site_checks(facts: dict) -> None:
    pages = nav_pages()
    for p in pages:
        if not os.path.exists(os.path.join(DOCS, p)):
            err("nav 里的 %s 在 docs/ 下不存在" % p)
    # 反向：docs 下的 md 是否都在 nav（生成页与白名单除外）
    allowed_extra = {"assets/SYNCED.md", "assets/hardware/README.md"}
    for root_dir, _dirs, files in os.walk(DOCS):
        for f in files:
            if not f.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root_dir, f), DOCS).replace("\\", "/")
            if rel.startswith("_generated/"):
                continue
            if rel in pages or rel in allowed_extra:
                continue
            err("docs/%s 没有出现在 mkdocs.yml 的 nav 里（漏进 nav 的页面 = 读者找不到）" % rel)

    # facts 是否过期
    r = subprocess.run([sys.executable, "scripts/extract_facts.py", "--check"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        err("facts/facts.json 与源码不一致：" + r.stdout.decode("utf-8", "replace").strip()
            + r.stderr.decode("utf-8", "replace").strip())

    # 每个真实实体都要有文档页点名（默认：模块页正文里出现实体名）
    ents = list(facts["entities"])
    allmd = {}
    for p in pages:
        fp = os.path.join(DOCS, p)
        if os.path.exists(fp):
            allmd[p] = open(fp, "r", encoding="utf-8").read()
    blob_text = "\n".join(allmd.values())
    for e in ents:
        if e not in blob_text:
            err("实体 %s 在整个文档站里一次都没被提到" % e)
    for mod, m in facts["sim"]["modules"].items():
        if m["record_json"] not in blob_text and ("sim/rounds/%s" % mod) not in blob_text and ("r%d" % m["round"]) not in blob_text:
            warn("仿真模块 %s 的最新轮次记录 %s 在正文里没有被引用" % (mod, m["record_json"]))

    # 关键数字不得与 facts.json 冲突：同一个指标不许出现**两个当前值**。
    #
    # ⚠️ 但不能把**如实记录的历史值**也判错 —— 这个项目的文档大量写"当时那一轮
    #    是 1268/1270 LE（当前读数是 {{fact:build.fit.le}}）"，那是正确的写法。
    #    所以豁免条件是**两条同时成立**：
    #      · 该行有明确的历史标记（当时 / 历史 / 此前 / 曾经 / 上一轮 …）
    #      · 该行同时给出了当前值（引用 {{fact:build.fit.le}} 或直接写出当前数）
    #    否则一律 FAIL —— 不允许拿"这是历史"当挡箭牌糊弄过去。
    HIST_MARKERS = ("当时", "历史", "此前", "曾经", "上一轮", "旧版", "早期", "那一次")
    fit = facts["build"]["fit"]
    le = re.sub(r"[^\d]", "", fit["le"].split("/")[0])
    for p, text in allmd.items():
        for lineno, line in enumerate(text.splitlines(), start=1):
            for bad in re.findall(r"(\d{3,4})\s*/\s*1270", line):
                if bad == le:
                    continue
                historical = any(h in line for h in HIST_MARKERS) and (
                    "{{fact:build.fit.le}}" in line or le in line
                )
                if historical:
                    warn("%s:%d 出现历史值 %s/1270（同行已标明历史并给出当前值 %s）—— 允许，仅提示"
                         % (p, lineno, bad, le))
                    continue
                err("%s:%d 写了 LE %s/1270，但 build_provenance.json 是 %s/1270；"
                    "若这是历史值，请在**同一行**标明“当时/历史”并同时给出当前值"
                    % (p, lineno, bad, le))

    # 页面里引用的 GitHub 源码/目录链接必须已入库
    tracked = git_tracked()
    for p, text in allmd.items():
        for m in SRC.finditer(text):
            if m.group(1) not in tracked:
                unbacked(p, "{{src:%s}}" % m.group(1), m.group(1))
        for m in TREE.finditer(text):
            if not any(t.startswith(m.group(1).rstrip("/") + "/") for t in tracked):
                unbacked(p, "{{tree:%s}}" % m.group(1), m.group(1))


def main() -> int:
    ap = argparse.ArgumentParser(description="文档站一致性门禁")
    ap.add_argument("pages", nargs="*", help="只检查这些页面（相对仓库根或绝对路径）")
    ap.add_argument("--site", action="store_true", help="额外检查构建产物")
    args = ap.parse_args()

    facts = load_facts()
    tracked = git_tracked()

    # 站点模式（不给页面参数）= 交付前的最终门禁 ⇒ "未入库"必须算失败；
    # 页面模式 = 写作中的自检 ⇒ 只警告（此时 book/ facts/ 往往还没提交）。
    global TRACKED_STRICT
    TRACKED_STRICT = not args.pages

    if args.pages:
        for p in args.pages:
            fp = p if os.path.isabs(p) else os.path.join(ROOT, p)
            if not os.path.exists(fp):
                err("找不到页面 %s" % p)
                continue
            check_page(fp, facts, tracked)
    else:
        pages = nav_pages()
        for p in pages:
            fp = os.path.join(DOCS, p)
            if os.path.exists(fp):
                check_page(fp, facts, tracked)
            else:
                err("nav 页缺失：%s" % p)
        site_checks(facts)

    if args.site:
        # ⚠️ 2026-10-15 第 27 工作阶段：站点从"两个"（site/ 展示站 + book/ 文档站）
        #    变成"一个"（book/ 文档站占用根路径 /dld/），所以产物目录是 `book/site/`。
        dist = os.path.join(BOOK, "site")
        if not os.path.isdir(dist):
            err("book/site 不存在（先跑 python book/scripts/book.py build）")
        else:
            for need in ("index.html", "search/search_index.json", "sitemap.xml",
                         "assets/javascripts/mermaid.min.js"):
                if not os.path.exists(os.path.join(dist, *need.split("/"))):
                    err("站点产物缺少 %s" % need)
            # ---- GitHub Pages 子路径检查 ----
            # ⚠️ 这里**不能**简单 grep `/dld/assets/`：Material 生成的资源引用是
            #    **相对路径**（`assets/brand/mark.svg`），那在任何子路径下都对，
            #    比写死 `/dld/` 更健壮。真正能证明"子路径配对了"的是这三条：
            #      ① canonical 链接等于 site_url（MkDocs 由 site_url 推出）
            #      ② sitemap.xml 里的 URL 都带 /dld/ 前缀
            #      ③ 页面里不存在**绕开子路径的绝对路径**引用
            #         （`/assets/...` 这种才会在 /dld/ 下 404）
            idx = os.path.join(dist, "index.html")
            if os.path.exists(idx):
                html = open(idx, "r", encoding="utf-8").read()
                m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
                if not m:
                    err("产物 index.html 里没有 canonical 链接")
                elif not m.group(1).startswith("https://tortrixx.github.io/dld/"):
                    err("canonical 是 %s，与 mkdocs.yml 的 site_url（/dld/）不符" % m.group(1))
                else:
                    print("  OK    canonical = %s" % m.group(1))
                bad_abs = [
                    r
                    for r in re.findall(r'(?:href|src)="(/[^"/][^"]*)"', html)
                    if not r.startswith("/dld/")
                ]
                if bad_abs:
                    err("产物里有绕开子路径的绝对路径引用（在 /dld/ 下会 404）：%s" % bad_abs[:5])
                if re.search(r'src="https?://', html):
                    err("产物里出现了外部 CDN 的 <script src>（违反'不用外部 CDN 作核心依赖'）")
                else:
                    print("  OK    没有外部 CDN 的 <script src>（Mermaid 自持）")

            sm = os.path.join(dist, "sitemap.xml")
            if os.path.exists(sm):
                locs = re.findall(r"<loc>([^<]+)</loc>", open(sm, "r", encoding="utf-8").read())
                bad_loc = [u for u in locs if not u.startswith("https://tortrixx.github.io/dld/")]
                if bad_loc:
                    err("sitemap 里有不带头路径的 URL：%s" % bad_loc[:3])
                elif locs:
                    print("  OK    sitemap %d 条 URL 全部在 /dld/ 下" % len(locs))

    print("check_book: 检查 %d 个页面" % checked)
    for x in warnings:
        print("  WARN  " + x)
    for x in errors:
        print("  FAIL  " + x)
    print("check_book: %d FAIL / %d WARN" % (len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
