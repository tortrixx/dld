#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book/scripts/sync_assets.py —— 把 `docs/图/` 里**已入库**的素材同步进文档站

为什么要同步而不是直接引用
--------------------------
MkDocs 只服务 `docs_dir` 里的文件；`docs/图/` 在 `docs_dir` 之外，直接写相对
路径会 404。`site/` 的前端工程早就有同一套做法（`site/scripts/sync-figures.mjs`）：
**真值源只有一份**（`docs/图/`），两边都只是它的副本。

同步目标（全部在 .gitignore 里，不入库）
----------------------------------------
    docs/assets/waveforms/quartus/*.png     真实 Quartus GUI 仿真截图
    docs/assets/waveforms/scripted/*.svg    脚本渲染的辅助波形（**不是** GUI 截图）
    docs/assets/figures/*.gif|png           演示动画与脚本渲染图
    docs/assets/diagrams/*.drawio           可编辑图表源（供下载/二次编辑）

⚠️ `docs/assets/hardware/` **有意为空**：仓库里没有任何真实开发板照片，
   这是已知缺失，见 `docs/06-verification/board-validation.md`。
   同步脚本不会去"造"一张照片。

用法：python book/scripts/sync_assets.py
"""

from __future__ import annotations

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK = os.path.dirname(HERE)
DOCS = os.path.join(BOOK, "docs")
SRC = os.path.join(os.path.dirname(BOOK), "docs", "图")

RULES = [
    ("GUI-*.png", "assets/waveforms/quartus"),
    ("SIM-*.svg", "assets/waveforms/scripted"),
    ("*.drawio", "assets/diagrams"),
    ("演示-*.gif", "assets/figures"),
    ("演示-*.png", "assets/figures"),
    ("结算画面-*.png", "assets/figures"),
]


def main() -> int:
    if not os.path.isdir(SRC):
        print("sync_assets: 找不到 docs/图/", file=sys.stderr)
        return 1
    import fnmatch

    names = sorted(os.listdir(SRC))
    copied = 0
    manual = []
    for pattern, dest in RULES:
        d = os.path.join(DOCS, dest)
        os.makedirs(d, exist_ok=True)
        for n in names:
            if not fnmatch.fnmatch(n, pattern):
                continue
            shutil.copy2(os.path.join(SRC, n), os.path.join(d, n))
            copied += 1
    # 记录一份清单，便于"图片存在性检查"参照（也方便人核对同步了什么）
    lines = ["# 同步到文档站的素材（由 book/scripts/sync_assets.py 生成，勿手改）", ""]
    for dest in sorted({r[1] for r in RULES}):
        d = os.path.join(DOCS, dest)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            lines.append("- `%s/%s`" % (dest, n))
    lines += [
        "",
        "## 有意为空的目录",
        "",
        "- `assets/hardware/` —— 仓库里没有真实开发板照片，属于**已知缺失证据**；",
        "  文档不会用脚本渲染图冒充硬件实拍。补拍清单见",
        "  `docs/06-verification/board-validation.md`。",
        "",
    ]
    os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)
    with open(os.path.join(DOCS, "assets", "SYNCED.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.makedirs(os.path.join(DOCS, "assets", "hardware"), exist_ok=True)
    # 用 `.gitkeep` 之外的显式说明文件，避免"空目录在 git 里消失"造成误解
    hw = os.path.join(DOCS, "assets", "hardware", "README.md")
    if not os.path.exists(hw):
        with open(hw, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(
                "# 真实硬件照片：**缺失**\n\n"
                "这个目录是留给开发板实拍照片的，目前**是空的**，因为仓库里还没有\n"
                "任何一张真实硬件照片。\n\n"
                "不要用 `docs/图/演示-*.gif`、`结算画面-预览.png` 之类由网页引擎渲染的图\n"
                "来填充它 —— 那是**软件模拟**，不是硬件实测。\n\n"
                "需要补拍什么、怎么补，见 "
                "[上板验证与缺失证据](https://tortrixx.github.io/dld/docs/06-verification/board-validation/)。\n"
            )
    print("sync_assets: 同步 %d 个素材 → book/docs/assets/" % copied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
