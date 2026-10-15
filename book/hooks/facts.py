# -*- coding: utf-8 -*-
"""
book/hooks/facts.py —— MkDocs 钩子：把 `facts/facts.json` 注入 Markdown

为什么用钩子而不是插件
----------------------
Material for MkDocs 原生支持 `hooks:`，**不需要额外依赖**，而且钩子在
`on_page_markdown` 阶段运行 —— 也就是在 Markdown 解析**之前**。
这样占位符在 `--strict` 模式看来就是普通正文，既不会产生警告，
也能让"事实缺失"变成一次**构建失败**（而不是页面上留一个丑陋的空洞）。

占位符（在任意页面里写，钩子会替换成真值）
------------------------------------------
    {{fact:sim.totals.assertions}}      -> 184          （facts.json 的点号路径）
    {{fact:build.fit.le}}               -> 1,264 / 1,270 ( 100 % )
    {{src:rtl/clk_gen.vhd:58}}          -> GitHub 上该文件的第 58 行链接
    {{src:rtl/puzzle_top.vhd}}          -> GitHub 上该文件的链接
    {{tree:sim/rounds}}                 -> GitHub 上该目录的链接
    {{repo}}                            -> https://github.com/tortrixx/dld
    {{docs_site}}                       -> 本站地址（也就是项目唯一的站点）

纪律
----
1. **解析不了的占位符 = 构建失败。** 不允许"写错路径就静默留个空"。
2. 路径必须指向**已入库**的文件，`scripts/check_book.py` 会用 `git ls-files`
   逐个核对（未入库 = 克隆后 404）。
3. 中文字符与空格在 URL 里逐段百分号编码（`docs/图/` 这类路径必然遇到）。
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import quote

_HERE = os.path.dirname(os.path.abspath(__file__))
_BOOK = os.path.dirname(_HERE)
_REPO_ROOT = os.path.dirname(_BOOK)
_DOCS = os.path.join(_BOOK, "docs")
_FACTS_PATH = os.path.join(_REPO_ROOT, "facts", "facts.json")

REPO = "https://github.com/tortrixx/dld"
BRANCH = "main"
# ⚠️ 2026-10-15 第 27 工作阶段：原来是"展示站 + 文档站"两个地址，
#    用户决定去掉展示站（`site/`）只留本站 ⇒ 两个常量现在指向同一个根地址。
#    保留 `DOCS_SITE` 这个名字，是因为页面里用 `{{docs_site}}` 表达
#    "本站的线上地址"；`SHOWCASE` 已删除（不再有第二个站点可指）。
DOCS_SITE = "https://tortrixx.github.io/dld/"

with open(_FACTS_PATH, "r", encoding="utf-8") as _fh:
    FACTS = json.load(_fh)


def _encode_path(path: str) -> str:
    """逐段编码，保留 `/`。中文目录（docs/图）与空格都要能点得开。"""
    return "/".join(quote(seg, safe="") for seg in path.strip("/").split("/"))


def resolve(path: str):
    """点号路径取值；找不到就抛错（不许静默）。"""
    cur = FACTS
    for part in path.strip().split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
                continue
            except (ValueError, IndexError):
                raise KeyError("facts.json 路径 %r 里 %r 不是合法下标" % (path, part))
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError("facts.json 里没有 %r 这个路径" % path)
        cur = cur[part]
    return cur


def _fmt(value) -> str:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "—"
    if isinstance(value, float):
        return ("%.6f" % value).rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        raise TypeError("占位符只接受标量：%r 是 %s" % (value, type(value).__name__))
    return str(value)


_RE_FACT = re.compile(r"\{\{\s*fact:([A-Za-z0-9_.\[\]-]+)\s*\}\}")
_RE_SRC = re.compile(r"\{\{\s*src:([^:}\s]+)(?::(\d+))?\s*\}\}")
_RE_TREE = re.compile(r"\{\{\s*tree:([^}\s]+)\s*\}\}")

# `--8<-- "相对/路径.md"`（可选 `:start:end` 后缀）
_RE_SNIPPET = re.compile(r"(--8<--\s*[\"'])([^\"']+)([\"'])")


def _rewrite_snippets(markdown: str) -> str:
    """把 `--8<-- "docs 内的相对路径"` 改写成**绝对路径**。

    为什么必须做这一步：`pymdownx.snippets` 的 `base_path` 是用
    `os.path.abspath()` 解析的，也就是**相对当前工作目录**。而本项目的构建
    可能从仓库根（`python book/scripts/book.py build`）也可能从别处发起，
    于是 `base_path: ["docs"]` 会指向不存在的 `<cwd>/docs`
    ⇒ `SnippetMissingError: Snippet at path '_generated/hierarchy.md' could not be found`。

    在钩子里把它换成绝对路径就与工作目录无关了（`os.path.join(base, 绝对路径)`
    在 Python 里直接返回那个绝对路径）。这样作者仍然只写简洁的
    `--8<-- "_generated/ports/clk_gen.md"`。

    ⚠️ 解析不到的路径**原样保留**，交给 pymdownx 抛错 ——
    "片段缺失"必须继续是**构建失败**，不许被这里悄悄吞掉。
    """

    def sub(m: re.Match) -> str:
        path = m.group(2)
        if path.startswith(("http://", "https://")) or os.path.isabs(path):
            return m.group(0)
        # `:start` / `:start:end` 形式的行范围后缀：先按整串试，再剥后缀试
        candidates = [path]
        head = path
        while ":" in head:
            head = head.rsplit(":", 1)[0]
            candidates.append(head)
        for cand in candidates:
            full = os.path.normpath(os.path.join(_DOCS, cand))
            if os.path.exists(full):
                rest = path[len(cand) :]
                return m.group(1) + full.replace("\\", "/") + rest + m.group(3)
        return m.group(0)

    return _RE_SNIPPET.sub(sub, markdown)


def _blob(path: str, line: str | None) -> str:
    url = "%s/blob/%s/%s" % (REPO, BRANCH, _encode_path(path))
    return url + ("#L%s" % line if line else "")


def expand(markdown: str, page: str, warnings: list[str]) -> str:
    def fact_sub(m: re.Match) -> str:
        key = m.group(1)
        try:
            return _fmt(resolve(key))
        except (KeyError, TypeError) as exc:
            raise RuntimeError("页面 %s：占位符 {{fact:%s}} 无法解析 —— %s" % (page, key, exc))

    def src_sub(m: re.Match) -> str:
        path, line = m.group(1), m.group(2)
        return _blob(path, line)

    def tree_sub(m: re.Match) -> str:
        return "%s/tree/%s/%s" % (REPO, BRANCH, _encode_path(m.group(1)))

    markdown = _RE_FACT.sub(fact_sub, markdown)
    markdown = _RE_SRC.sub(src_sub, markdown)
    markdown = _RE_TREE.sub(tree_sub, markdown)
    markdown = markdown.replace("{{repo}}", REPO)
    markdown = markdown.replace("{{docs_site}}", DOCS_SITE)

    # 收尾：正文里不允许残留未识别的 `{{...}}`（写错前缀是最常见的笔误）
    leftovers = re.findall(r"\{\{[^}]*\}\}", markdown)
    if leftovers:
        raise RuntimeError("页面 %s：有 %d 个未识别的占位符 %s" % (page, len(leftovers), leftovers[:3]))
    return markdown


def on_page_markdown(markdown: str, page=None, config=None, files=None, **kwargs) -> str:
    warnings: list[str] = []
    where = page.file.src_path if getattr(page, "file", None) else "?"
    markdown = _rewrite_snippets(markdown)
    return expand(markdown, where, warnings)
