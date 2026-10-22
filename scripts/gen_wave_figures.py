# -*- coding: utf-8 -*-
"""gen_wave_figures.py —— 把 docs/图/GUI-*.png（Quartus 现场截图）裁成报告用图

【为什么要裁】
    这 12 张是 Quartus 波形窗口的**整窗截图**，最上面有
    「/sim/<模块>.vwf」标题栏和「Master Time Bar / Pointer / Interval / Start / End」读数行 ——
    那是窗口装饰，不是数据。裁掉它们有两个好处：
      · 报告里不再出现 Windows 窗口边框（观感上像"图"而不是"截图"）；
      · 同样的 100% 版心宽度下，信号名与时间刻度放大约 10%。

【怎么做】
    从 `docs/图/GUI-*.png`（原件，保留不动）读入 → 裁掉顶部窗口装饰 → 写
    `docs/report/GUI-*.png`（报告用）。裁剪高度是**检测**出来的：标题栏是一段
    连续深蓝色带，它结束后的 26px 是读数行。
    两张编译截图（GUI-编译-*.png）早已裁成只剩数据区，本脚本跳过。

【用法】
    python scripts/gen_wave_figures.py           # 裁完写盘
    python scripts/gen_wave_figures.py --check   # 只报告将要裁多少
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

try:
    from PIL import Image
except ImportError:  # Pillow 只在 bundled 解释器里
    sys.stderr.write(
        '需要 Pillow：请用 bundled 解释器运行本脚本\n'
        '  C:\\Users\\<你>\\.dsh\\dsh-runtimes\\dsh-primary-runtime\\dependencies\\python\\python.exe '
        'scripts/gen_wave_figures.py\n')
    raise SystemExit(2)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "图")
DST = os.path.join(ROOT, "docs", "report")
SKIP = ("GUI-编译-",)
READOUT_H = 26          # 标题栏之后的读数行高度


CROP_TOP = 72        # 窗口标题栏 + Master Time Bar/Pointer/Interval 读数行（只留时间刻度与波形）
CROP_LEFT = 86       # 左侧工具栏 + 信号序号列（序号对读图无用，名字那一列保留）


def content_bottom(im):
    """最后一行含深色像素（波形/文字）的 y，再留 8px。"""
    w, h = im.size
    for y in range(h - 1, CROP_TOP, -1):
        xs = list(range(CROP_LEFT, w, 4))
        # 只认"深色"像素：Quartus 的浅灰网格线（约 #c8c8c8）不算内容，
        # 否则每张图都会被判成"到底都有内容"，底部的空白区就裁不掉。
        dark = sum(1 for x in xs
                   if all(c < 120 for c in im.getpixel((x, y))[:3]))
        frac = dark / float(len(xs))
        if 0.02 < frac < 0.60:
            return min(h, y + 8)
    return h


def main():
    ap = argparse.ArgumentParser(description="裁掉 Quartus 截图顶部的窗口装饰")
    ap.add_argument("--check", action="store_true", help="只报告，不写盘")
    args = ap.parse_args()

    names = sorted(f for f in os.listdir(SRC)
                   if f.startswith("GUI-") and f.endswith(".png")
                   and not f.startswith(SKIP))
    if not names:
        print("没找到 GUI-*.png 源图（docs/图/）")
        return 1
    n_ok = 0
    for name in names:
        src = os.path.join(SRC, name)
        dst = os.path.join(DST, name)
        im = Image.open(src).convert("RGB")
        w, h = im.size
        bottom = content_bottom(im)
        box = (CROP_LEFT, CROP_TOP, w, bottom)
        print("  %-26s %4dx%-4d → %4dx%-4d  裁掉 标题栏%d/工具栏%d/底部%d px"
              % (name, w, h, box[2] - box[0], box[3] - box[1],
                 CROP_TOP, CROP_LEFT, h - bottom))
        if args.check:
            continue
        im.crop(box).save(dst, optimize=True)
        n_ok += 1
    print("\n%s：%d 张%s" % ("将处理" if args.check else "已写出", len(names) if args.check else n_ok,
                        "" if args.check else "（%s）" % os.path.relpath(DST, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
