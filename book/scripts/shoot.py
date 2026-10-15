#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book/scripts/shoot.py —— 给站点拍"审图用"的截图（**开发工具，不在 CI 里跑**）

为什么要写它
------------
2026-10-15 这一轮把站点的视觉系统整套换掉了（编辑式排版）。改 CSS 最怕的是
"看着改对了，其实某个页面塌了" —— 而 `mkdocs --strict` 只检查链接和锚点，
**对版式一无所知**。这一轮真实抓到的问题里，有两个就是这样发现的：

  1. **深色主题下"深色报头 + 浅色正文"**：自定义属性只在 `:root` 上求值，
     导致 `--md-*` 映射永远取浅色令牌 —— 只有截图才看得出来。
  2. **同一个页面里两张表宽度不一致**：Material 的 JS 会把表格包进
     `.md-typeset__table`（shrink-to-fit），窄内容的那张就缩成半宽。
     靠"注入 outline 逐层定位"才找到真凶。

所以：**改了 CSS 就拍一遍**。脚本自己起一个临时静态服务、用无头浏览器
按"浅色 / 深色"各拍几页，产物落在 `book/review/`（**不入库**）。

用法
----
    python book/scripts/shoot.py                # 拍默认的几张（首页 + 4 个代表性页面）
    python book/scripts/shoot.py --page 03-modules/puzzle-engine
    python book/scripts/shoot.py --all          # 每个一级章节挑一页

前提：`python book/scripts/book.py build` 已经跑过（要有 `book/site/`），
      本机装了 Chrome 或 Edge（脚本自己找路径，找不到就报错退出）。
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.dirname(HERE)
ROOT = os.path.dirname(BOOK)
SITE = os.path.join(BOOK, "site")
OUT = os.path.join(BOOK, "review")

# Windows 控制台默认是 GBK，直接 print "✓" 会 UnicodeEncodeError（本仓库其它脚本
# 都有这行，原因一样）。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 代表性页面：首页 + 每种"版式压力"各一页
#   · 首页 —— hero / 点阵图 / 事实条 / 章节栅格
#   · 模块页 —— `--8<--` 片段里的长端口表（就是那张"半宽表"的现场）
#   · 架构页 —— 最多张 Mermaid 图
#   · 验证页 —— 大量 figure + 图注 + 代码块
#   · 引脚页 —— 最宽的表格（52 行）
DEFAULT_PAGES = [
    "",
    "03-modules/puzzle-engine",
    "02-architecture/system-overview",
    "06-verification/waveforms",
    "07-implementation/pin-assignment",
]
ALL_SECTIONS = [
    "01-project/overview",
    "02-architecture/system-overview",
    "03-modules/puzzle-engine",
    "04-interfaces/data-encoding",
    "05-gameplay/roundup" if False else "05-gameplay/movement-rotation",
    "06-verification/assertions",
    "07-implementation/timing-report",
    "08-debugging/representative-bugs",
    "09-defense/faq",
]

BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> str:
    env = os.environ.get("BOOK_BROWSER")
    if env and os.path.exists(env):
        return env
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    print("shoot: 找不到 Chrome / Edge。用 BOOK_BROWSER 环境变量指定可执行文件路径。", file=sys.stderr)
    raise SystemExit(2)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """默认的 SimpleHTTPRequestHandler 会把每个请求打到 stderr，
    一次截图 5 页 × 2 主题就是几十行噪音，把真正的输出淹掉。"""

    def log_message(self, fmt, *args):  # noqa: A003
        pass


def serve(directory: str) -> tuple[socketserver.TCPServer, int]:
    handler = functools.partial(_QuietHandler, directory=directory)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def shoot(browser: str, url: str, out: str, width: int, height: int) -> bool:
    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
        "--virtual-time-budget=5000",
        "--window-size=%d,%d" % (width, height),
        "--screenshot=" + out,
        url,
    ]
    r = subprocess.run(cmd, capture_output=True)
    ok = os.path.exists(out) and os.path.getsize(out) > 12_000  # 空白页只有几 KB
    if not ok:
        print("    x %s（%d B）%s" % (os.path.basename(out),
                                     os.path.getsize(out) if os.path.exists(out) else 0,
                                     r.stderr.decode("utf-8", "replace")[:200]))
    return ok


# ⚠️ 为什么不用 `--blink-settings=preferredColorScheme=1/2`：
#    实测它在本机**不可靠**（浅色/深色两条命令产出的图字节数完全一样，
#    也就是根本没切换），而且它依赖"系统主题"这个外部状态。
#    这里改成**改 HTML**：Material 的主题由 `<body data-md-color-scheme=...>` 决定，
#    而它会在加载时按 `(prefers-color-scheme)` 把属性改掉 —— 所以我们在
#    `load` 之后再把它设回目标值。定时器是为了排在 Material 的初始化之后。
FORCE_SCHEME = (
    "<script>addEventListener('load',function(){"
    "setTimeout(function(){document.body.setAttribute('data-md-color-scheme','%s');},120);"
    "});</script>"
)


def stage(site: str, dest: str, pages: list[str], scheme: str) -> None:
    """把 `book/site/` 复制一份，并把要拍的页面注入"强制主题"脚本。"""
    shutil.copytree(site, dest)
    for p in pages:
        html = os.path.join(dest, *(p.split("/") if p else []), "index.html")
        if not os.path.exists(html):
            continue
        text = open(html, "r", encoding="utf-8").read()
        open(html, "w", encoding="utf-8", newline="").write(
            text.replace("</head>", FORCE_SCHEME % scheme + "</head>")
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="给站点拍审图用截图")
    ap.add_argument("--page", action="append", default=[], help="额外/指定页面（相对 docs 的路径，不带 .md）")
    ap.add_argument("--all", action="store_true", help="每个一级章节挑一页")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=1400)
    args = ap.parse_args()

    if not os.path.isdir(SITE):
        print("shoot: 没有 book/site/ —— 先跑 python book/scripts/book.py build", file=sys.stderr)
        return 2
    # 清掉上一轮的产物：截图是"当前状态"的证据，混进旧图就会骗人
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    pages = list(args.page) or (ALL_SECTIONS if args.all else DEFAULT_PAGES)
    browser = find_browser()
    print("shoot: 目标 %s（%d 页 × 2 主题）" % (OUT, len(pages)))
    made = 0
    tmp_root = tempfile.mkdtemp(prefix="book-shoot-")
    try:
        for scheme, tag in (("default", "light"), ("slate", "dark")):
            staged = os.path.join(tmp_root, tag)
            stage(SITE, staged, pages, scheme)
            httpd, port = serve(staged)
            try:
                for p in pages:
                    slug = p.replace("/", "_") or "home"
                    url = "http://127.0.0.1:%d/%s" % (port, (p + "/") if p else "")
                    out = os.path.join(OUT, "%s-%s.png" % (slug, tag))
                    if shoot(browser, url, out, args.width, args.height):
                        print("    ok %s" % os.path.basename(out))
                        made += 1
            finally:
                httpd.shutdown()
                httpd.server_close()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
    print("shoot: 完成 %d 张" % made)
    return 0 if made else 1


if __name__ == "__main__":
    raise SystemExit(main())
