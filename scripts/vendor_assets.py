#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vendor_assets.py —— 把 Docsify 依赖下载到 docs/assets/vendor/ 本地

为什么不用 CDN：
    站点是拿来在答辩现场开的。现场网络未必能访问 cdn.jsdelivr.net，
    而一旦 CDN 不可达，页面会永久停在「正在加载文档…」，且没有任何提示。
    本地副本让站点只依赖自己所在的那台服务器。

升级版本：改下面的 VERSION 表，重跑本脚本，然后本地起服务看一眼再提交。
    python scripts/vendor_assets.py
    python scripts/vendor_assets.py --check   # 只校验本地文件是否齐全
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "assets", "vendor")

CDN = "https://cdn.jsdelivr.net/npm"

# 本地文件名 -> 远端路径。版本全部钉死，避免上游更新把站点改坏。
ASSETS = {
    "docsify.min.js": "docsify@4.13.1/lib/docsify.min.js",
    "vue.css": "docsify@4.13.1/lib/themes/vue.css",
    "search.min.js": "docsify@4.13.1/lib/plugins/search.min.js",
    "zoom-image.min.js": "docsify@4.13.1/lib/plugins/zoom-image.min.js",
    "docsify-copy-code.min.js": "docsify-copy-code@2.1.1/dist/docsify-copy-code.min.js",
    "docsify-pagination.min.js": "docsify-pagination@2.10.1/dist/docsify-pagination.min.js",
    "prism-vhdl.min.js": "prismjs@1.29.0/components/prism-vhdl.min.js",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验本地文件是否齐全，不下载")
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    bad = 0
    for name, remote in sorted(ASSETS.items()):
        dest = os.path.join(OUT, name)
        if args.check:
            ok = os.path.isfile(dest) and os.path.getsize(dest) > 0
            print(("OK   " if ok else "MISS ") + name)
            bad += 0 if ok else 1
            continue
        url = f"{CDN}/{remote}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read()
        except Exception as exc:                      # noqa: BLE001
            print(f"FAIL {name} <- {url}\n     {exc}")
            bad += 1
            continue
        if not data:
            print(f"FAIL {name}: 下载到 0 字节")
            bad += 1
            continue
        with open(dest, "wb") as fh:
            fh.write(data)
        print(f"{name:<30} {len(data):>8} B  <- {remote}")

    if args.check and bad == 0:
        print(f"\n本地依赖齐全（{len(ASSETS)} 个文件），站点不依赖任何外部 CDN。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
