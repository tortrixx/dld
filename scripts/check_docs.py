#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_docs.py —— Docsify 站点静态体检（可进 CI，防止"改完就坏"）

背景：docs/ 下的站点曾反复出现三类**静默**故障——链接指向不存在的图、
侧边栏条目指向被删的页面、以及 Markdown 粗体在中文里根本不渲染。
它们都不会报错，只会在浏览器里悄悄变丑，所以必须由脚本兜住。

本脚本检查 6 项：
  1. 侧边栏完整性  docs/_sidebar.md 里每个链接都能落到真实文件
  2. 图片引用      站点 Markdown 里每张 ![](...) 都真实存在
  3. 站内链接      每个 [](xxx.md) 都真实存在
  4. 粗体渲染陷阱  **粗体** 紧贴半角标点时 marked 会原样吐出星号（详见下方注释）
  5. 孤立图片      docs/assets/images 里没被任何站点页面引用的图（提示，不算失败）
  6. 重复标题     同一页内出现同名标题，docsify 目录会跳错位置

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

# 站点真正对外的页面（docs/ 下其余 md 是事实模型证据，不参与导航）
SITE_PAGES = [
    "README.md",
    "_sidebar.md",
    "subsystems/01_system_top.md",
    "subsystems/02_clock_keypad.md",
    "subsystems/03_game_fsm.md",
    "subsystems/04_puzzle_engine.md",
    "subsystems/05_rom_random.md",
    "subsystems/06_display_audio.md",
]

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+?)(?:#[^)]*)?\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.M)
FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)

# marked 的标点类只认 ASCII；中文全角标点被当成普通字母。
# 于是「**...**」的收尾星号若紧跟在半角标点后、且后面紧跟非 ASCII 标点/非空白，
# 该收尾星号不构成 right-flanking，粗体解析失败 —— 页面上直接显示两个星号。
ASCII_PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
BOLD_RE = re.compile(r"\*\*([^*\n]+?)\*\*")

# marked 把「以块级标签开头、且中间没有空行」的整段当作原始 HTML 直通，
# 段内的 **粗体** 和 `行内代码` 全部原样显示 —— 这类故障肉眼极难发现，
# 因为源文件看起来完全正常。
BLOCK_TAG_RE = re.compile(r"^\s*<(div|section|table|p|ul|ol|details|figure|aside|blockquote)\b", re.I)
BACKTICK_RE = re.compile(r"`")


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_fences(text: str) -> str:
    """把代码块挖空（保留行数），避免把代码里的 ** 当成粗体。"""
    def blank(m: re.Match) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))
    return FENCE_RE.sub(blank, text)


def check_raw_html(text: str):
    """返回 (行号, 片段) 列表：落在原始 HTML 块里、不会被解析的 Markdown 记号。

    marked 的 HTML 块规则（type 6）：从块级标签那一行开始，直到**空行**为止，
    整段原样输出。所以块里写 `**加粗**` 或 `行内代码` 都会连同记号一起显示。
    """
    bad = []
    lines = text.split("\n")
    in_block = False
    for idx, line in enumerate(lines, start=1):
        if BLOCK_TAG_RE.match(line):
            in_block = True
        elif not line.strip():
            in_block = False          # 空行终止 HTML 块
        if not in_block:
            continue
        if "**" in line or BACKTICK_RE.search(line):
            bad.append((idx, line.strip()[:90]))
    return bad


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="只输出结论")
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    referenced: set[str] = set()

    def say(msg: str) -> None:
        if not args.quiet:
            print(msg)

    # ---- 1. 侧边栏完整性 -------------------------------------------------
    sidebar = os.path.join(DOCS, "_sidebar.md")
    if not os.path.exists(sidebar):
        errors.append("缺少 docs/_sidebar.md")
    else:
        for m in LINK_RE.finditer(read(sidebar)):
            target = m.group(1)
            if target.startswith(("http", "#")):
                continue
            if not os.path.exists(os.path.join(DOCS, target)):
                errors.append(f"_sidebar.md 指向不存在的页面：{target}")

    # ---- 2/3. 图片与站内链接 --------------------------------------------
    for page in SITE_PAGES:
        path = os.path.join(DOCS, page)
        if not os.path.exists(path):
            errors.append(f"站点页面缺失：docs/{page}")
            continue
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
                referenced.add(os.path.normpath(os.path.relpath(resolved, DOCS)).replace("\\", "/"))

        for m in LINK_RE.finditer(text):
            href = m.group(1)
            if href.startswith(("http", "#", "mailto:")):
                continue
            line = text.count("\n", 0, m.start()) + 1
            if not os.path.exists(os.path.normpath(os.path.join(base, href))):
                errors.append(f"{page}:{line} 链接不存在 -> {href}")

        # ---- 4. 粗体渲染陷阱 --------------------------------------------
        for line, frag in check_bold(text):
            errors.append(f"{page}:{line} 粗体不会渲染（星号会原样显示）-> {frag}")

        # ---- 4b. 原始 HTML 块里的 Markdown 不会被解析 ---------------------
        for line, frag in check_raw_html(text):
            errors.append(f"{page}:{line} 原始 HTML 块内的 Markdown 记号会原样显示 -> {frag}")

        # ---- 4c. 站点没有启用数学公式渲染，$$ 会原样显示 -------------------
        for n, line in enumerate(text.split("\n"), start=1):
            if "$$" in line:
                errors.append(
                    f"{page}:{n} 站点未启用数学公式渲染，$$ 会原样显示；"
                    f"请改写成行内代码或纯文本 -> {line.strip()[:70]}"
                )

        # ---- 6. 重复标题 -------------------------------------------------
        seen: dict[str, int] = {}
        for m in HEADING_RE.finditer(strip_fences(text)):
            title = m.group(2).strip()
            if title in seen:
                warnings.append(f"{page} 标题重复：「{title}」")
            seen[title] = 1

    # ---- 5. 孤立图片 -----------------------------------------------------
    img_dir = os.path.join(DOCS, "assets", "images")
    if os.path.isdir(img_dir):
        for name in sorted(os.listdir(img_dir)):
            if os.path.isfile(os.path.join(img_dir, name)):
                if f"assets/images/{name}" not in referenced:
                    warnings.append(f"图片未被任何站点页面引用：assets/images/{name}")

    # ---- 汇报 -----------------------------------------------------------
    say("=" * 68)
    say("Docsify 站点体检")
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
        say("\n全部通过，站点链接、图片与 Markdown 渲染均正常。")
    elif not errors:
        say(f"\n无错误（{len(warnings)} 条提示）。")
    else:
        say(f"\n体检失败：{len(errors)} 个错误，{len(warnings)} 条提示。")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
