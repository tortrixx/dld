#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_docs.py —— Docsify 站点静态体检（进 CI，防止"改完就坏"）

背景：docs/ 下的站点反复出现过三类**静默**故障——链接指向不存在的图、
侧边栏条目指向被删的页面、以及 Markdown 粗体在中文里根本不渲染。
它们都不会报错，只会在浏览器里悄悄变丑，所以必须由脚本兜住。

检查分三层：

  A. 结构层（对 docs/ 下**所有** Markdown 生效）
     1. 侧边栏完整性：_sidebar.md 里每个链接都能落到真实文件
     2. 图片引用：每个 ![](...) 都真实存在
     3. 站内链接：每个 [](xxx.md) 都真实存在（含锚点目标页）

  B. 渲染层（只对**会被 docsify 渲染的站点页**生效）
     4. 粗体渲染陷阱：**粗体** 紧贴半角标点时 marked 会原样吐出星号
     5. 原始 HTML 块：块级标签开头且中间无空行时，块内 Markdown 全部失效
     6. 数学公式：站点没有启用公式渲染，出现 $$ 会原样显示
     （docs/ 下还有一批 MkDocs 时代的证据文档，它们不参与站点导航、
       也不在发布面上，所以不做渲染层检查。）

  C. 发布面
     7. index.html 引用的本地资源必须存在（含 assets/vendor/ 本地依赖）
     8. 站点页引用的资源必须落在实际发布的文件集合里
        （见 .github/workflows/pages.yml 的 Stage Site Files 步骤）

用法：
    python scripts/check_docs.py            # 体检，有错退出码 1
    python scripts/check_docs.py --quiet    # 只输出结论
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

# Windows 控制台默认可能是 GBK/cp936，直接 print 中文会 UnicodeEncodeError 崩掉。
# CI 是 UTF-8 不会有事，但本地跑不应该因为终端编码而失败。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---- 发布面：与 .github/workflows/pages.yml 的 Stage Site Files 保持一致 ----
PUBLISHED_FILES = {"index.html", "README.md", "_sidebar.md", ".nojekyll"}
PUBLISHED_DIRS = ("assets/", "subsystems/")

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+?)(?:#[^)]*)?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)
# index.html 里的本地 src= / href=（跳过 http(s)、//、data:、#）
HTML_REF_RE = re.compile(r'(?:src|href)\s*=\s*"([^"]+)"')

# marked 的标点类只认 ASCII；中文全角标点被当成普通字母。
# 于是「**...**」的收尾星号若紧跟在半角标点后、且后面紧跟非 ASCII 标点/非空白，
# 该收尾星号不构成 right-flanking，粗体解析失败 —— 页面上直接显示两个星号。
ASCII_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
BOLD_RE = re.compile(r"\*\*(?!\s)([^\n]+?)\*\*")

# marked 把「以块级标签开头、且中间没有空行」的整段当作原始 HTML 直通，
# 段内的 **粗体** 和 `行内代码` 全部原样显示 —— 这类故障肉眼极难发现，
# 因为源文件看起来完全正常。
BLOCK_TAG_RE = re.compile(
    r"^\s*<(div|section|article|aside|nav|header|footer|main|figure|figcaption|"
    r"table|thead|tbody|tr|td|th|p|ul|ol|li|dl|dt|dd|blockquote|pre|form|fieldset|"
    r"details|summary|h[1-6]|hr|iframe|address|script|style|template)\b",
    re.I,
)
BACKTICK_RE = re.compile(r"`")


def read(path: str) -> str:
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def strip_fences(text: str) -> str:
    """把代码块挖空（保留行数），避免把代码里的 ** 当成粗体。"""
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    return FENCE_RE.sub(blank, text)


def site_pages() -> list[str]:
    """站点页 = 侧边栏里列出的页面 + 首页。不再硬编码，新增页面自动纳入检查。"""
    pages = ["README.md"]
    sidebar = os.path.join(DOCS, "_sidebar.md")
    if os.path.isfile(sidebar):
        for m in LINK_RE.finditer(read(sidebar)):
            target = m.group(1)
            if target.startswith(("http", "#", "mailto:")):
                continue
            target = target.replace("/", os.sep)
            if target.lower().endswith(".md") and target not in pages:
                pages.append(target)
    return pages


def all_docs_markdown() -> list[str]:
    out = []
    for base, _dirs, files in os.walk(DOCS):
        for name in files:
            if name.lower().endswith(".md"):
                out.append(os.path.relpath(os.path.join(base, name), DOCS))
    return sorted(out)


def is_published(rel_to_docs: str) -> bool:
    rel = rel_to_docs.replace("\\", "/")
    if rel in PUBLISHED_FILES:
        return True
    return any(rel.startswith(p) for p in PUBLISHED_DIRS)


def check_bold(text: str):
    """返回 (行号, 片段) 列表：会渲染失败的粗体。"""
    bad = []
    plain = strip_fences(text)
    for m in BOLD_RE.finditer(plain):
        # m.end() 落在收尾 "**" 之后，所以收尾星号前一个字符是 m.end()-3
        close_at = m.end() - 3
        before = plain[close_at] if close_at >= 0 else ""
        after = plain[m.end()] if m.end() < len(plain) else ""
        if before in ASCII_PUNCT and after and after not in ASCII_PUNCT and not after.isspace():
            line = plain.count("\n", 0, m.start()) + 1
            bad.append((line, m.group(0)))
    return bad


def check_raw_html(text: str):
    """返回 (行号, 片段) 列表：落在原始 HTML 块里、不会被解析的 Markdown 记号。"""
    bad = []
    in_block = False
    for idx, line in enumerate(text.split("\n"), start=1):
        if BLOCK_TAG_RE.match(line):
            in_block = True
        elif not line.strip():
            in_block = False          # 空行终止 HTML 块
        if not in_block:
            continue
        if "**" in line or BACKTICK_RE.search(line):
            bad.append((idx, line.strip()[:90]))
    return bad


def check_index_html(errors: list[str]) -> None:
    """index.html 引用的本地资源必须存在（以前完全没查，删了 custom.js 也照样通过）。"""
    path = os.path.join(DOCS, "index.html")
    if not os.path.isfile(path):
        errors.append("缺少 docs/index.html")
        return
    for m in HTML_REF_RE.finditer(read(path)):
        ref = m.group(1)
        if ref.startswith(("http", "//", "data:", "#", "mailto:")):
            continue
        ref = ref.split("?")[0].split("#")[0]
        if not os.path.exists(os.path.join(DOCS, ref.replace("/", os.sep))):
            errors.append(f"index.html 引用的本地资源不存在：{ref}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    referenced: set[str] = set()
    pages = site_pages()

    def say(msg: str) -> None:
        if not args.quiet:
            print(msg)

    # ---- 1. 侧边栏完整性 -------------------------------------------------
    sidebar = os.path.join(DOCS, "_sidebar.md")
    if not os.path.isfile(sidebar):
        errors.append("缺少 docs/_sidebar.md")
    else:
        for m in LINK_RE.finditer(read(sidebar)):
            target = m.group(1)
            if target.startswith(("http", "#", "mailto:")):
                continue
            if not os.path.exists(os.path.join(DOCS, target.replace("/", os.sep))):
                errors.append(f"_sidebar.md 指向不存在的页面：{target}")

    # ---- 2/3. 图片与站内链接（对 docs/ 下所有 Markdown）------------------
    for page in all_docs_markdown():
        path = os.path.join(DOCS, page)
        text = read(path)
        base = os.path.dirname(path)

        for m in IMG_RE.finditer(text):
            src = m.group(1)
            if src.startswith(("http", "data:")):
                continue
            line = text.count("\n", 0, m.start()) + 1
            resolved = os.path.normpath(os.path.join(base, src))
            if not os.path.exists(resolved):
                errors.append(f"{page}:{line} 图片不存在 -> {src}")
            else:
                rel = os.path.relpath(resolved, DOCS).replace("\\", "/")
                referenced.add(rel)
                if page in pages and not is_published(rel):
                    errors.append(f"{page}:{line} 引用了不会被发布的文件 -> {src}")

        for m in LINK_RE.finditer(text):
            href = m.group(1)
            if href.startswith(("http", "#", "mailto:")):
                continue
            line = text.count("\n", 0, m.start()) + 1
            resolved = os.path.normpath(os.path.join(base, href))
            if not os.path.exists(resolved):
                errors.append(f"{page}:{line} 链接不存在 -> {href}")
            elif page in pages and os.path.isfile(resolved):
                rel = os.path.relpath(resolved, DOCS).replace("\\", "/")
                if not is_published(rel):
                    errors.append(f"{page}:{line} 链接到不会被发布的文件 -> {href}")

    # ---- 4/5/6. 渲染层：只查会被 docsify 渲染的站点页 --------------------
    for page in pages:
        path = os.path.join(DOCS, page)
        if not os.path.isfile(path):
            errors.append(f"站点页面缺失：docs/{page}")
            continue
        text = read(path)

        for line, frag in check_bold(text):
            errors.append(f"{page}:{line} 粗体不会渲染（星号会原样显示）-> {frag}")

        for line, frag in check_raw_html(text):
            errors.append(f"{page}:{line} 原始 HTML 块内的 Markdown 记号会原样显示 -> {frag}")

        for n, line in enumerate(text.split("\n"), start=1):
            if "$$" in line:
                errors.append(
                    f"{page}:{n} 站点未启用数学公式渲染，$$ 会原样显示；"
                    f"请改写成行内代码或纯文本 -> {line.strip()[:70]}"
                )

        seen: dict[str, int] = {}
        for m in HEADING_RE.finditer(strip_fences(text)):
            title = m.group(2).strip()
            if title in seen:
                warnings.append(f"{page} 标题重复：「{title}」")
            seen[title] = 1

    # ---- 7. index.html 的本地资源 ---------------------------------------
    check_index_html(errors)

    # ---- 8. 孤立图片 -----------------------------------------------------
    img_dir = os.path.join(DOCS, "assets", "images")
    if os.path.isdir(img_dir):
        for name in sorted(os.listdir(img_dir)):
            if os.path.isfile(os.path.join(img_dir, name)):
                if f"assets/images/{name}" not in referenced:
                    warnings.append(f"图片未被任何 docs/ 页面引用：assets/images/{name}")

    # ---- 汇报 -----------------------------------------------------------
    say("=" * 68)
    say("Docsify 站点体检")
    say(f"站点页 {len(pages)} 个：{', '.join(pages)}")
    say("=" * 68)
    if errors:
        say(f"\n[错误] {len(errors)} 项：")
        for e in errors:
            say("  x " + e)
    if warnings:
        say(f"\n[提示] {len(warnings)} 项：")
        for w in warnings:
            say("  - " + w)
    if not errors and not warnings:
        say("\n全部通过：链接、图片、渲染与发布面均正常。")
    elif not errors:
        say(f"\n无错误（{len(warnings)} 条提示）。")
    else:
        say(f"\n体检失败：{len(errors)} 个错误，{len(warnings)} 条提示。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
