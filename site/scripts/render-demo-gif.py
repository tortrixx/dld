#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
render-demo-gif.py —— 把 `site/.shots/demo-frames.json` 画成演示 GIF

用法（在仓库任意位置都能跑，路径都相对脚本自身解析）：

    <bundled-python> site/scripts/render-demo-gif.py            # 画 GIF
    <bundled-python> site/scripts/render-demo-gif.py --verify    # 再读回验证 + 抽帧存 PNG

画什么：
  · 8×8 双色点阵（圆角小方块；灭 #1d1d22 / 红 #ff3b20 / 绿 #17d96a / 黄 #ffbe0b，底 #0b0b0d）
    —— 颜色语义与 `rtl/puzzle_ctrl.vhd` 的红/绿/黄一致，直接来自帧数据的 cells。
  · 8 位数码管：**真的按 7 段形状画**（段码表从 `site/src/engine/engine.ts` 的 `SEGMENTS` 解析，
    解析失败才退化为内置副本），下标 0 = 最右（DISP0），画的时候从 DISP7 往 DISP0 排。
  · 右上角：关卡 / 阶段 / 倒计时；底部：一帧一句中文说明；右侧：细节说明。
  · 中文用系统字体（msyh.ttc 微软雅黑），找不到就报告并退化为无中文。
  · 抗锯齿：先按 SS 倍分辨率画，再 LANCZOS 缩放。
  · 体积控制：全局 64 色调色板（取若干代表帧做中位切分）+ `optimize=True` 帧间差分。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    # 友好报错而不是甩一堆 traceback：仓库自身的 scripts/*.py 是**纯标准库**，
    # 只有这个 GIF 渲染器需要 Pillow —— 这是站点新增的唯一一个第三方 Python 依赖，
    # 所以必须把"要用哪个解释器、能不能不跑"说清楚。
    sys.stderr.write(
        "\n[render-demo-gif] 需要带 Pillow 的 Python 解释器。\n"
        "  · 仓库自身的 scripts/*.py 是纯标准库；只有这个 GIF 渲染器依赖 Pillow。\n"
        "  · 换一个装了 Pillow 的解释器来跑即可（DSH 捆绑运行时自带 Pillow）。\n"
        "  · 只想构建/部署站点时**不必重跑这一步**：GIF 产物已入库\n"
        "    （docs/图/演示-跑一局.gif），只有改了规则模型或想换演示内容才需重新生成。\n"
    )
    raise SystemExit(2)

try:  # 让中文在 cp936 控制台上也能打印
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
REPO = SITE.parent
FRAMES_JSON = SITE / ".shots" / "demo-frames.json"
OUT_GIF = REPO / "docs" / "图" / "演示-跑一局.gif"
ENGINE_TS = SITE / "src" / "engine" / "engine.ts"

# ---------------------------------------------------------------- 画布与配色

W, H = 640, 420
SS = 2  # 超采样倍数（画完再缩回 W×H，相当于抗锯齿）

BG = (0x0B, 0x0B, 0x0D)
PANEL = (0x14, 0x14, 0x1A)
LEGEND_EDGE = (0x2A, 0x2A, 0x33)
C_OFF = (0x1D, 0x1D, 0x22)
C_RED = (0xFF, 0x3B, 0x20)
C_GREEN = (0x17, 0xD9, 0x6A)
C_YELLOW = (0xFF, 0xBE, 0x0B)
TEXT = (0xE9, 0xE9, 0xF0)
DIM = (0x8B, 0x8B, 0x96)
FAINT = (0x5E, 0x5E, 0x69)
SEG_OFF = (0x10, 0x10, 0x13)
SEG_ON = (0xFF, 0x4B, 0x33)

CELL_COLOR = {
    "off": C_OFF,
    "red": C_RED,
    "green": C_GREEN,
    "yellow": C_YELLOW,
}

# 显示器的物理布局：点阵在左，数码管与说明在右
MAT_X, MAT_Y, CELL, GAP = 20, 66, 30, 4
PITCH = CELL + GAP
MAT_SIZE = 8 * CELL + 7 * GAP          # 268
COL_X = MAT_X + MAT_SIZE + 20          # 308
COL_W = W - COL_X - 20                 # 312
SEG_W, SEG_H, SEG_T, SEG_GAP = 34, 58, 7, 4

CAP_Y0, CAP_Y1 = 364, 410

PHASE_CN = {
    "selftest": "S_SELF_TEST 开机自检",
    "idle": "S_IDLE 待机",
    "preview": "S_PREVIEW 预览",
    "playing": "S_PLAYING 对局",
    "win": "S_WIN 胜利",
    "fail": "S_FAIL 失败",
}

# 必须"原样"出现在调色板里的颜色（中位切分可能不给它们格子 ⇒ 手动钉死）
FORCED_PALETTE_COLORS = (
    C_OFF, C_RED, C_GREEN, C_YELLOW,           # 4 种 LED 状态
    BG, PANEL, LEGEND_EDGE,                    # 底色与结构
    SEG_ON, SEG_OFF,                           # 数码管亮/灭段
    TEXT, DIM, FAINT, (0xB9, 0xB9, 0xC4),      # 文字层次
)

# ---------------------------------------------------------------- 字体

FONT_CANDIDATES_CN = [
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path(r"C:\Windows\Fonts\msyhbd.ttc"),
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\simsun.ttc"),
]
FONT_CANDIDATES_MONO = [
    Path(r"C:\Windows\Fonts\consola.ttf"),
    Path(r"C:\Windows\Fonts\consolab.ttf"),
]


def pixel_list(im: Image.Image) -> list:
    """Pillow 12 起 `getdata()` 被标弃用；这里优先用新 API，老版本回退。"""
    getter = getattr(im, "get_flattened_data", None) or im.getdata
    return list(getter())


def pick_font(cands: list[Path]) -> Path | None:
    for p in cands:
        if p.is_file():
            return p
    return None


CN_FONT = pick_font(FONT_CANDIDATES_CN)
MONO_FONT = pick_font(FONT_CANDIDATES_MONO)
_font_cache: dict[tuple[str, int, bool], ImageFont.FreeTypeFont] = {}


def font(size: int, *, mono: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    """按需要渲染的像素尺寸取字体；内部会把 size 乘上超采样倍数。"""
    key = ("mono" if mono else "cn", size, bold)
    if key in _font_cache:
        return _font_cache[key]
    px = int(round(size * SS))
    if mono and MONO_FONT is not None:
        f = ImageFont.truetype(str(MONO_FONT), px)
    elif CN_FONT is not None:
        f = ImageFont.truetype(str(CN_FONT), px)
    else:
        f = ImageFont.load_default(px)
    _font_cache[key] = f
    return f


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], s: str, *, size: int,
         color=TEXT, mono: bool = False, bold: bool = False, anchor: str = "la") -> None:
    draw.text((xy[0] * SS, xy[1] * SS), s, font=font(size, mono=mono, bold=bold),
              fill=color, anchor=anchor)


def text_w(s: str, size: int, *, mono: bool = False, bold: bool = False) -> float:
    return font(size, mono=mono, bold=bold).getlength(s) / SS


# ---------------------------------------------------------------- 7 段数码管

# 段位顺序固定为 a b c d e f g（bit0 = a），与 engine.ts 的 SEGMENTS 一致。
_FALLBACK_SEGMENTS = {
    "0": 0b0111111, "1": 0b0000110, "2": 0b1011011, "3": 0b1001111,
    "4": 0b1100110, "5": 0b1101101, "6": 0b1111101, "7": 0b0000111,
    "8": 0b1111111, "9": 0b1101111,
    "P": 0b1110011, "A": 0b1110111, "S": 0b1101101, "F": 0b1110001,
    "I": 0b0000110, "L": 0b0111000, " ": 0b0000000,
}


def load_segments() -> tuple[dict[str, int], str]:
    """从 engine.ts 的 `SEGMENTS` 表里解析段码 —— 让"画出来的段形"与页面/RTL 同源。"""
    try:
        src = ENGINE_TS.read_text(encoding="utf-8")
    except OSError as exc:
        return dict(_FALLBACK_SEGMENTS), f"读不到 {ENGINE_TS}（{exc}）⇒ 用内置副本"
    m = re.search(r"export const SEGMENTS[^{]*\{(.*?)\};", src, re.S)
    if not m:
        return dict(_FALLBACK_SEGMENTS), "engine.ts 里没找到 SEGMENTS ⇒ 用内置副本"
    out: dict[str, int] = {}
    for key, bits in re.findall(r"['\"]?([0-9A-Z ])['\"]?\s*:\s*0b([01]{7})", m.group(1)):
        out[key] = int(bits, 2)
    if len(out) < 10:
        return dict(_FALLBACK_SEGMENTS), "engine.ts 的 SEGMENTS 解析结果不完整 ⇒ 用内置副本"
    return out, f"解析自 {ENGINE_TS.name} 的 SEGMENTS（{len(out)} 个字符）"


SEGMENTS, SEG_SOURCE = load_segments()


def hseg(xa: float, xb: float, y: float, t: float) -> list[tuple[float, float]]:
    return [(xa, y), (xa + t / 2, y - t / 2), (xb - t / 2, y - t / 2),
            (xb, y), (xb - t / 2, y + t / 2), (xa + t / 2, y + t / 2)]


def vseg(ya: float, yb: float, x: float, t: float) -> list[tuple[float, float]]:
    return [(x, ya), (x + t / 2, ya + t / 2), (x + t / 2, yb - t / 2),
            (x, yb), (x - t / 2, yb - t / 2), (x - t / 2, ya + t / 2)]


def draw_digit(d: ImageDraw.ImageDraw, x: float, y: float, ch: str, *,
               on=SEG_ON, off=SEG_OFF, w: float = SEG_W, h: float = SEG_H, t: float = SEG_T) -> None:
    """画一位 7 段数码管：先画灭段（暗红），再点亮有效段。"""
    bits = SEGMENTS.get(ch)
    if bits is None:
        bits = 0b0000000
    x0, y0 = x * SS, y * SS
    ww, hh, tt = w * SS, h * SS, t * SS
    mid = y0 + hh / 2
    shapes = {
        0: hseg(x0 + tt / 2, x0 + ww - tt / 2, y0 + tt / 2, tt),          # a
        1: vseg(y0 + tt / 2, mid, x0 + ww - tt / 2, tt),                   # b
        2: vseg(mid, y0 + hh - tt / 2, x0 + ww - tt / 2, tt),              # c
        3: hseg(x0 + tt / 2, x0 + ww - tt / 2, y0 + hh - tt / 2, tt),      # d
        4: vseg(mid, y0 + hh - tt / 2, x0 + tt / 2, tt),                   # e
        5: vseg(y0 + tt / 2, mid, x0 + tt / 2, tt),                        # f
        6: hseg(x0 + tt / 2, x0 + ww - tt / 2, mid, tt),                   # g
    }
    for i in range(7):
        lit = (bits >> i) & 1
        d.polygon(shapes[i], fill=on if lit else off)


# ---------------------------------------------------------------- 点阵

def draw_matrix(d: ImageDraw.ImageDraw, cells: list[list[str]]) -> None:
    for r in range(8):
        for c in range(8):
            x = (MAT_X + c * PITCH) * SS
            y = (MAT_Y + r * PITCH) * SS
            size = CELL * SS
            col = CELL_COLOR.get(cells[r][c], C_OFF)
            d.rounded_rectangle([x, y, x + size, y + size], radius=6 * SS,
                                fill=col, outline=LEGEND_EDGE, width=SS)
            if cells[r][c] != "off":
                # 亮起来的点加一点内高光，远看更像真的 LED（不引入渐变、不动调色板）
                d.rounded_rectangle([x + 5 * SS, y + 5 * SS, x + size - 5 * SS, y + size - 5 * SS],
                                    radius=4 * SS, outline=tuple(min(255, v + 60) for v in col),
                                    width=SS)


# ---------------------------------------------------------------- 排版小工具

def wrap_cjk(s: str, size: int, max_w: float, *, mono: bool = False) -> list[str]:
    """按像素宽度断行；对中文逐字断、对 ASCII 词尽量整词断。"""
    lines: list[str] = []
    cur = ""
    for ch in s:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if text_w(trial, size, mono=mono) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def fit_size(s: str, size: int, max_w: float, *, mono: bool = False, floor: int = 14) -> int:
    while size > floor and text_w(s, size, mono=mono) > max_w:
        size -= 1
    return size


def wrap_ascii_words(s: str, size: int, max_w: float) -> list[str]:
    """中英混排断行：优先在空白/标点后断，宽度不够时退化为逐字断。"""
    out: list[str] = []
    cur = ""
    for ch in s:
        trial = cur + ch
        if text_w(trial, size) <= max_w or not cur:
            cur = trial
            continue
        # 找一个可断点（空格、顿号、逗号、右括号之后）
        cut = max(cur.rfind(" "), cur.rfind("、"), cur.rfind("，"), cur.rfind("）"), cur.rfind(")"))
        if cut > len(cur) * 0.4:
            out.append(cur[: cut + 1])
            cur = cur[cut + 1:] + ch
        else:
            out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- 单帧绘制

def render_frame(fr: dict) -> Image.Image:
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)

    # ---- 顶栏：左标题 / 右关卡·阶段·倒计时 ----
    text(d, (MAT_X, 14), "8×8 双色点阵拼图 · 演示一局（浏览器端规则模型重放）",
         size=14, color=FAINT)

    phase = fr["phase"]
    digits = fr["digits"]
    blank = fr["blank"]

    # 关卡号只从 DISP0 读（B3）。自检态 DISP0 = '8'（八位全显），那是自检画面、不是"第 8 关"。
    level: int | None = None
    if phase != "selftest" and not blank[0]:
        try:
            level = int(digits[0])
        except ValueError:
            level = None
    right = f"第 {level} 关 · {PHASE_CN.get(phase, phase)}" if level else PHASE_CN.get(phase, phase)
    text(d, (W - MAT_X, 10), right, size=17, color=TEXT, bold=True, anchor="ra")

    # 帧数据里没有单列倒计时字段：倒计时直接**从数码管读回来**（对局 = DISP4/DISP3，预览 = DISP7）
    left_s = ""
    if phase == "playing" and not blank[4] and not blank[3]:
        left_s = f"限时倒计时 {digits[4]}{digits[3]} s"
    elif phase == "preview" and not blank[7]:
        left_s = f"预览倒数 {digits[7]} s"
    elif phase == "selftest":
        left_s = "自检窗口 8 拍 = 2.0 s"
    if left_s:
        text(d, (W - MAT_X, 34), left_s, size=15, color=C_YELLOW, bold=True, anchor="ra")

    # ---- 点阵 ----
    draw_matrix(d, fr["cells"])
    text(d, (MAT_X, MAT_Y + MAT_SIZE + 8), "点阵配色：灭 / 红（未选中）/ 绿（选中）/ 黄（已锁定）",
         size=12, color=FAINT)

    # ---- 右列：数码管 ----
    sx = COL_X
    for disp in range(7, -1, -1):  # DISP7 在最左
        ch = " " if blank[disp] else digits[disp]
        draw_digit(d, sx, MAT_Y, ch)
        text(d, (sx + SEG_W / 2, MAT_Y + SEG_H + 4), f"{disp}", size=10,
             color=FAINT, mono=True, anchor="ma")
        sx += SEG_W + SEG_GAP
    text(d, (COL_X, MAT_Y + SEG_H + 20), "DISP0 = 关卡号；DISP2 全程熄灭（口径 C）", size=12, color=FAINT)

    line_y = MAT_Y + SEG_H + 44
    d.line([(COL_X * SS, line_y * SS), ((COL_X + COL_W) * SS, line_y * SS)],
           fill=LEGEND_EDGE, width=SS)

    # ---- 右列：细节说明 ----
    text(d, (COL_X, line_y + 8), "这一帧发生了什么", size=13, color=DIM)
    dy = line_y + 28
    for ln in wrap_ascii_words(fr["detail"], 14, COL_W)[:8]:
        text(d, (COL_X, dy), ln, size=14, color=(0xB9, 0xB9, 0xC4))
        dy += 20

    # ---- 底部说明条 ----
    d.rounded_rectangle([16 * SS, CAP_Y0 * SS, (W - 16) * SS, CAP_Y1 * SS],
                        radius=8 * SS, fill=PANEL, outline=LEGEND_EDGE, width=SS)
    cap = fr["caption"]
    size = fit_size(cap, 18, W - 60, floor=13)
    text(d, (30, (CAP_Y0 + CAP_Y1) / 2), cap, size=size, color=TEXT, bold=True, anchor="lm")
    return img


# ---------------------------------------------------------------- 调色板

def build_palette(images: list[Image.Image], colors: int, out_w: int, out_h: int) -> Image.Image:
    """做一张**全局**调色板（逐帧自适应调色板会写进每一帧、把体积撑大）。

    做法：把**所有帧**缩到一半拼成一张长图 → 中位切分 → 然后把关键色（4 种 LED、底色、
    文字层次）**强行写回调色板的末尾几格**。

    ⚠️ 最后这一步不是装饰，是必须的：绿（选中）与黄（已锁定）只在少数几帧出现、像素占比极小，
    中位切分完全可能不分配单独的格子 —— 实测过，绿色会被平均成灰绿 (119, 212, 164)，
    于是"选中的零片"在 GIF 里变成脏兮兮的橄榄色。钉死之后 `dither=NONE` 的最近色映射
    就一定能命中原色（`main()` 里有往返自检打印这件事）。
    """
    tw, th = max(1, out_w // 2), max(1, out_h // 2)
    sheet = Image.new("RGB", (tw, th * len(images)))
    for i, im in enumerate(images):
        # NEAREST：缩略图里点阵格心仍是纯色，不会因插值把纯色冲淡
        sheet.paste(im.resize((tw, th), Image.Resampling.NEAREST), (0, i * th))

    pal = sheet.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    buf = bytearray(pal.getpalette() or [])
    if buf:
        for i, col in enumerate(FORCED_PALETTE_COLORS):
            if i >= colors:
                break
            idx = colors - 1 - i
            if idx * 3 + 3 <= len(buf):
                buf[idx * 3: idx * 3 + 3] = bytes(col)
        pal.putpalette(bytes(buf))
    return pal


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="把 demo-frames.json 画成演示 GIF")
    ap.add_argument("--verify", action="store_true", help="写完后读回 GIF 验证，并抽 3 帧存成 PNG")
    ap.add_argument("--colors", type=int, default=64, help="调色板颜色数（默认 64）")
    ap.add_argument("--scale", type=int, default=1, help="输出分辨率倍率（1 = 640×420；体积超标时降到…）")
    args = ap.parse_args()

    if not FRAMES_JSON.is_file():
        print(f"✗ 找不到帧数据：{FRAMES_JSON}\n  先跑：node_modules/.bin/vite-node scripts/gen-demo-frames.ts")
        return 2
    frames = json.loads(FRAMES_JSON.read_text(encoding="utf-8"))
    print(f"读入 {FRAMES_JSON}：{len(frames)} 帧，总时长 {sum(f['delayMs'] for f in frames)} ms")
    print(f"7 段段码：{SEG_SOURCE}")
    print(f"中文字体：{CN_FONT if CN_FONT else '✗ 没找到中文字体 —— 中文会画成方块/缺字'}"
          f"；等宽字体：{MONO_FONT if MONO_FONT else '✗ 没找到（用中文字体代替）'}")

    out_w, out_h = W * args.scale, H * args.scale
    if args.scale != 1:
        print(f"⚠ 输出分辨率缩放到 {out_w}×{out_h}")

    # 超采样绘制 → LANCZOS 缩回最终尺寸（这一步就是抗锯齿）
    rgb_frames = []
    for fr in frames:
        im = render_frame(fr).resize((W, H), Image.LANCZOS)
        if args.scale != 1:
            im = im.resize((out_w, out_h), Image.LANCZOS)
        rgb_frames.append(im)

    palette = build_palette(rgb_frames, args.colors, out_w, out_h)
    p_frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in rgb_frames]

    # 调色板自检：4 种 LED 色必须能"原样"存活 —— 否则量化会把绿/黄映射成灰调
    probe = Image.new("RGB", (4, 1))
    probe.putdata([C_OFF, C_RED, C_GREEN, C_YELLOW])
    got = list(pixel_list(probe.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")))
    worst = max(abs(a - b) for g, w in zip(got, [C_OFF, C_RED, C_GREEN, C_YELLOW]) for a, b in zip(g, w))
    print(f"调色板自检：4 色往返 = {got}；最大通道误差 = {worst} "
          f"⇒ {'✓ 原样（≤8，视觉无差）' if worst <= 8 else '✗ 被映射掉了（GIF 里的绿/黄会失真）'}")

    OUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    durations = [int(f["delayMs"]) for f in frames]
    p_frames[0].save(
        OUT_GIF,
        save_all=True,
        append_images=p_frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        # ⚠️ 不要设 disposal=2（"每帧恢复背景"）：那会让 Pillow 每帧都写全画幅、
        #    帧间差分彻底失效。实测同一批帧：disposal=2 → 1,608,890 B；
        #    disposal=1 → 296,561 B（5.4 倍）。这是首屏唯一的大资源，必须吃下这个红利。
        disposal=1,
        comment="tortrixx/dld 8x8 双色点阵拼图 · 演示一局（帧数据由 site/scripts/gen-demo-frames.ts 用规则模型 reducer 生成）",
    )
    size = OUT_GIF.stat().st_size
    print(f"✓ 写出 {OUT_GIF}")
    print(f"  字节数 = {size} ({size / 1024:.1f} KiB) / 帧数 = {len(p_frames)} / 尺寸 = {out_w}×{out_h} / "
          f"总时长 = {sum(durations)} ms")
    if size > 2_500_000:
        print("⚠ 超过 2.5 MB：可用 --scale 或抽帧压缩（见脚本注释）")

    if args.verify:
        with Image.open(OUT_GIF) as im:
            n = getattr(im, "n_frames", 1)
            print(f"回读：格式 {im.format} / 模式 {im.mode} / 尺寸 {im.size} / n_frames = {n} / "
                  f"info.loop = {im.info.get('loop')}")
            if n != len(frames):
                print(f"  ⚠ GIF 物理帧数 {n} ≠ JSON 帧数 {len(frames)}（Pillow 把完全相同的相邻帧合并了；"
                      "总时长不变）")
            durs = []
            for i in range(n):
                im.seek(i)
                im.convert("RGB").load()
                durs.append(im.info.get("duration", 0))
            print(f"  逐帧解码 OK（{n} 帧）；duration 合计 = {sum(durs)} ms；"
                  f"首帧 {durs[0]} ms、末帧 {durs[-1]} ms")
            for i in sorted({0, n // 2, n - 1}):
                im.seek(i)
                out = SITE / ".shots" / f"demo-check-{i:02d}.png"
                im.convert("RGB").save(out)
                print(f"  抽帧 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
