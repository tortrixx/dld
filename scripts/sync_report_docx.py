# -*- coding: utf-8 -*-
"""sync_report_docx.py —— 把 `.typ` / PNG 的改动"幂等"同步进同名 `.docx`

【为什么要有它】
    `.docx` 是报告的第二份交付物（Word 版），内容必须与 `.typ`（→ PDF）一致。
    终稿期最痛的三类漂移都是它抓出来的：
      ① 旧数字残留（1,048 LE / 68.52 MHz 与真实 1,264 / 54.27 并存）；
      ② 图注/表注没跟（图 16/17 编号、§4.2 表 9 行、§2.3 模块表端口名）；
      ③ 图片字节没换（Canvas 加工图 vs Quartus 真实截图）。
    手工改 Word 必然漏，所以把"`.typ` → `.docx`"做成幂等同步：跑一遍，
    该改的都改；再跑一遍，**0 变更**——这就是"两边已收敛"的机器证明。

【用法】（在仓库根执行）
    python scripts/sync_report_docx.py --check     # 只比对：已收敛打印"0 变更"并 return 0
    python scripts/sync_report_docx.py --apply     # 真正写盘（写前自动快照到 .tmp/report_sync/）
    python scripts/sync_report_docx.py --apply --no-media   # 不动图片字节（图片由 assets 负责时用）

【依赖】
    **需要 lxml**（本机用捆绑 Python，见 `scripts/bootstrap.sh` / README）。
    不需要 python-docx / Pillow：
      · 不靠 python-docx —— 直接操作 OOXML（保留原样式/编号/关系表）；
      · 不靠 Pillow   —— PNG 像素宽高用标准库 `struct` 读 IHDR 即可。
    ⚠️ 不要用系统自带、未装 lxml 的解释器直接跑。

【它同步什么 / 不同步什么】
    同步（幂等，逐项先比对再写）：
      A 媒体字节：按 `<pic:cNvPr name="GUI-xxx.png">` 对上本地 PNG 重灌（--no-media 可跳过）
      B 图片 extent：按 `.typ` 的 `width: N%` × 正文净宽 重算 cx/cy，**不会把图拉变形**
      C 章节标题：章标题全角括号、节标题改名/重编号（如 2.3→2.4）
      D 正文段落：锚点 → `.typ` 连续"内容块"（p/ul/ol，自动跳过中间插着的 figure/table）
      E 表格：**按表头关键字识别**（"资源类别"/"缺陷编号"/"模块"…），不按表序号 —— 
        因为新增 §2.3 表会让后续表号整体后移（这个坑踩过一次）。
        列数不符时：**只在 docx 多列、且 typ 的表头文字是 docx 表头按序子序列时删列**
        （如 §5.2 删掉 "Commit" 列）；其余情形仍拒绝改写
      F 新增章节：若 `.typ` 有、docx 没有的节（当前是 §2.3 模块表）则插入
      G 代码清单 §8.2：按 `top_clean.vhd` 逐行重建（VHDL 是唯一事实源）
    不同步（属排版，Word 侧本来就不同）：
      · `.typ` 的表格列宽/居中规则、页脚页码、自动目录与图号域、代码块边框与高亮
      · §3.2 那次"6 组并排图 → 12 张通栏单图"的一次性结构改造（交付版 docx 已是新结构；
        脚本只做"旧结构检测 + 提示"，不擅自重排表格）

【已知边界】
    1. 段落锚点按 `.typ` 的固定前缀匹配；若 `.typ` 大改章节顺序/措辞到锚点失效，
       脚本会明确打印 `[FAIL] 锚点未命中` 而不是静默跳过 —— 修锚点常量即可。
    2. 表格识别靠表头关键字，新增表时请在 `TBL_JOBS` 里补一行（关键字 + typ 表序号）。
       删列只按**表头文字**对齐：改过表头措辞又同时改了列集合时，请先让两边表头一致。
    3. 只处理 `word/document.xml` 与 `word/media/*`；页眉页脚/样式/编号不动。
    4. 行尾/编码：脚本源码 LF；docx 是二进制不受影响。
"""
import argparse
import copy
import re
import shutil
import struct
import sys
import time
import zipfile
import datetime
from pathlib import Path

try:
    from lxml import etree  # noqa: E402  （第三方：lxml）
except ModuleNotFoundError:  # pragma: no cover - 环境提示
    sys.stderr.write(
        "[FATAL] 缺少 lxml：本脚本按 OOXML 节点级精确改写，必须用 lxml 才能保证\n"
        "        未改动的 part 逐字节不变，因此不接受“读取-重写”式的标准库替代。\n"
        "        请改用仓库文档里指明的捆绑解释器（含 lxml），或先 pip install lxml。\n"
    )
    raise SystemExit(3)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "report"
TYP = REPORT / "实验报告_题目4_简易拼图游戏.typ"
DOCX = REPORT / "实验报告_题目4_简易拼图游戏.docx"
VHD = REPORT / "top_clean.vhd"
SNAP = ROOT / ".tmp" / "report_sync"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": W, "wp": WP, "a": A, "pic": PIC, "r": R}
EMU_PER_TWIP = 635

# 表格识别表：(typ 表序号, 表头关键字, 人类可读名)
TBL_JOBS = [
    (0, ("FPGA", "引脚"), "§1.3 引脚表"),
    (1, ("模块", "职责"), "§2.3 模块表"),
    (2, ("测试平台",), "§3.1 断言表"),
    (3, ("资源类别",), "§4.2 资源表"),
    (4, ("缺陷编号",), "§5.2 缺陷表"),
    (5, ("Prompt",), "§7.2 提示词表"),
    (6, ("缺陷类别",), "§7.3 纠错表"),
]

# `.typ` 里已经删掉、但 docx 里还留着的**尾部章节**：从该标题（含）一路删到文末。
# 只支持"文末章节"——中间章节得靠"下一个标题"定位，容易删错，所以不做。
# 背景：§九 参考文献 于 2026-10-22 按用户要求从报告里去掉（老师不查文献表）。
DROP_TAIL = [
    "九、参考文献",
]

# 正文段落锚点：(docx 段落前缀, typ 块前缀, 连续"内容块"个数)
PARA_JOBS = [
    ("核心逻辑器件", "核心逻辑器件", 1),
    ("课题涵盖 11 项基础功能要求", "课题涵盖 11 项基础功能要求", 2),
    ("以上 11 类信号共锁定", "以上 11 类信号共锁定", 1),
    ("硬件设计关键裁决", "硬件设计关键裁决", 2),
    ("针对 Altera MAX II", "针对 Altera MAX II", 2),
    ("整机划分为", "整机划分为", 3),
    ("游戏主控状态机（FSM）", "游戏主控状态机（FSM）", 3),
    ("拼图核心引擎采用数据流解耦", "拼图核心引擎采用数据流解耦", 3),
    ("工程建立了", "工程建立了", 1),
    ("各模块最新轮次", "各模块最新轮次", 1),
    ("下列波形均为", "下列波形均为", 1),
    ("系统在硬件平台上完成全部功能指标", "系统在硬件平台上完成全部功能指标", 1),
    ("下列数据全部取自", "下列数据全部取自", 1),
    ("下表数据的读数来源", "下表数据的读数来源", 1),
    ("127 LAB 物理装箱瓶颈深度剖析", "127 LAB 物理装箱瓶颈深度剖析", 1),
    ("本项目在开发与调试过程中建立了", "本项目在开发与调试过程中建立了", 13),
    ("本课题在 Altera MAX II EPM1270T144C5 CPLD", "本课题在 Altera MAX II EPM1270T144C5 CPLD", 1),
    ("1. 硬件并发思维", "1. 硬件并发思维", 1),
    ("若将本设计迁移", "若将本设计迁移", 1),
    ("本课题在架构设计", "本课题在架构设计", 2),
    ("AI 在处理模式化推演", "AI 在处理模式化推演", 3),
    ("puzzle_top.vhd 是唯一绑定引脚", "puzzle_top.vhd 是唯一绑定引脚", 1),
]
for _name in ("时钟分频分析", "键盘消抖分析", "状态机迁移分析", "拼图引擎运算分析",
              "目标图库分析", "零片几何分析", "随机数源分析", "显示格式化分析",
              "数码管扫描分析", "点阵驱动分析", "音频合成分析", "整机端到端全流程分析"):
    PARA_JOBS.append((_name, _name, 1))

CHANGES = []          # [(说明, 数量)]
FAILS = []            # 锚点/表格失配（会导致"以为 0 变更、其实没同步"）


def fail(msg):
    """记录并打印失配；**计入失败**，不允许静默当作“0 变更”。"""
    FAILS.append(msg)
    print("  [FAIL] %s" % msg)


def count(tag, n):
    if n:
        CHANGES.append((tag, n))


# --------------------------------------------------------------------------- typ 解析
def typ_blocks(lines):
    blocks = []
    i = next(k for k, l in enumerate(lines) if l.strip().startswith("= 一、"))

    def parse_table(j):
        header, rows = [], []
        j += 1
        while j < len(lines):
            s = lines[j].strip()
            if s == ")":
                return header, rows, j + 1
            if s.startswith("table.header("):
                header.append(re.findall(r"\[([^\[\]]*)\]", s))
            elif s.startswith("[") and s.endswith("],"):
                rows.append(s[1:-2].split("], ["))
            j += 1
        raise SystemExit("`#table(` 未闭合 —— 检查 .typ 是否被改坏")

    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        m = re.match(r"^(=+)\s+(.*)$", s)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if s.startswith(("#align(center)[", "#table(")):
            j = i if s.startswith("#table(") else i + 1
            while j < len(lines) and not lines[j].strip().startswith("#table("):
                j += 1
            header, rows, j = parse_table(j)
            while j < len(lines) and lines[j].strip() in ("]", ""):
                j += 1
            blocks.append(("table", header, rows))
            i = j
            continue
        if s.startswith("#figure("):
            if "caption:" in s and s.count("(") == s.count(")"):
                chunk, j = s, i + 1
            else:
                j, buf = i, []
                while j < len(lines):
                    buf.append(lines[j])
                    j += 1
                    if lines[j - 1].strip() == ")":
                        break
                chunk = "\n".join(buf)
            mf = re.search(r'image\("([^"]+)"', chunk)
            mw = re.search(r"width:\s*(\d+)%", chunk)
            mc = re.search(r"caption:\s*\[(.*?)\]\s*\)?\s*$", chunk, re.S)
            cap = re.sub(r"\s+", " ", mc.group(1)).strip() if mc else ""
            blocks.append(("figure", mf.group(1), cap, int(mw.group(1)) if mw else 100))
            i = j
            continue
        if s.startswith("#raw("):
            blocks.append(("code",))
            i += 1
            continue
        if s.startswith(("#v(", "#pagebreak", "#outline")):
            i += 1
            continue
        if s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            blocks.append(("ul", items))
            continue
        if re.match(r"^\d+\.\s", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i].strip()):
                items.append(lines[i].strip())
                i += 1
            blocks.append(("ol", items))
            continue
        para = []
        while i < len(lines):
            s2 = lines[i].strip()
            if (not s2) or re.match(r"^(=+)\s", s2) or s2.startswith(
                    ("#align(", "#table(", "#figure(", "#raw(", "#v(", "- ")) \
               or re.match(r"^\d+\.\s", s2):
                break
            para.append(s2)
            i += 1
        blocks.append(("p", "".join(para)))
    return blocks


# --------------------------------------------------------------------------- 文本
def plain(s):
    s = s.replace("$>= 0.000$", ">= 0.000").replace("$\\ge 0.000$", ">= 0.000")
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = re.sub(r"#h\([^)]*\)|#v\([^)]*\)", "", s)
    return re.sub(r"[ \t]+", " ", s.replace("*", "").replace("`", "")).strip()


def btext(b):
    if b[0] == "p":
        return plain(b[1])
    if b[0] in ("ul", "ol"):
        return " ".join(plain(x) for x in b[1])
    return ""


def joinb(blocks):
    out = []
    for b in blocks:
        if b[0] == "p":
            out.append(plain(b[1]))
        elif b[0] == "ul":
            out.append("• " + "；".join(plain(x).rstrip("；;。") for x in b[1]) + "。")
        elif b[0] == "ol":
            out.append(" ".join(plain(x) for x in b[1]))
    return "".join(x for x in out if x)


def collect(T, k, n_content):
    """从 k 起收集 n 个"内容块"（p/ul/ol）；中途跳过 figure/table/code。"""
    got, i = [], k
    while i < len(T) and len(got) < n_content:
        if T[i][0] in ("p", "ul", "ol"):
            got.append(T[i])
        elif T[i][0] == "h":
            break
        i += 1
    return got


# --------------------------------------------------------------------------- docx 工具
def ptext(p):
    return "".join(t.text or "" for t in p.findall(".//w:t", NS))


def clean(t):
    return t.lstrip("• \u00b7").strip()


def set_para_text(p, text):
    ts = p.findall(".//w:t", NS)
    if not ts:
        r = etree.SubElement(p, "{%s}r" % W)
        t = etree.SubElement(r, "{%s}t" % W)
        ts = [t]
    ts[0].text = text
    for t in ts[1:]:
        t.text = ""


def png_size(data):
    """标准库读 PNG 的 IHDR（避免引入 Pillow）。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    return struct.unpack(">II", data[16:24])


def drop_cols(tbl, keep):
    """保留 keep 指定的列（升序索引），删掉其余列，并把余下列宽均分回原总宽。

    用途：`.typ` 里删掉一整列（如 §5.2 的 "Commit" 列）时，docx 必须跟着删。
    本脚本原本"列数不符就拒绝改写"，于是这条链会卡死；而"删列"是合法的结构变更 ——
    只要**按表头文字**能把 typ 的列一一对上，就删掉 docx 多出来的列。
    列宽按原总宽均分（余数给前几列），保证与文档里其它表的列宽风格一致。

    ⚠️ 这里是**破坏性**操作，所以 `keep` 必须先过一遍自检（空/越界一律抛错；
       重复索引会被去重、乱序会被升序化）。
       曾经 `keep=[]`（表头解析出 0 格）会把整张表的列删光，而外层 FAILS 还是空的。
    """
    keep = sorted(set(keep))
    rows = tbl.findall("w:tr", NS)
    n_before = len(rows[0].findall("w:tc", NS)) if rows else 0
    if not keep:
        raise ValueError("keep 为空 —— 会删光整张表")
    if n_before == 0:
        raise ValueError("这张表一行都没有")
    if keep[-1] >= n_before:
        raise ValueError("keep 越界：%r（表里只有 %d 列）" % (keep, n_before))

    grid = tbl.find("w:tblGrid", NS)
    cols = grid.findall("w:gridCol", NS) if grid is not None else []
    total = sum(int(c.get("{%s}w" % W) or 0) for c in cols)
    if grid is not None:
        for ci in range(len(cols) - 1, -1, -1):
            if ci not in keep:
                grid.remove(cols[ci])
    n_keep = len(keep)
    base, rem = divmod(total, n_keep)
    widths = [base + (1 if i < rem else 0) for i in range(n_keep)]
    if grid is not None:
        for i, c in enumerate(grid.findall("w:gridCol", NS)):
            c.set("{%s}w" % W, str(widths[i]))
    for tr in rows:
        tcs = tr.findall("w:tc", NS)
        for ci in range(len(tcs) - 1, -1, -1):
            if ci not in keep:
                tr.remove(tcs[ci])
        for i, tc in enumerate(tr.findall("w:tc", NS)):
            tcw = tc.find("w:tcPr/w:tcW", NS)
            if tcw is not None:
                tcw.set("{%s}w" % W, str(widths[i]))
    return n_before - n_keep


# --------------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="把 .typ / PNG 的改动幂等同步进 .docx")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="只比对，不写盘（默认）")
    g.add_argument("--apply", action="store_true", help="写盘（写前快照到 .tmp/report_sync/）")
    ap.add_argument("--no-media", action="store_true", help="不替换 word/media/* 字节")
    ap.add_argument("--docx", metavar="PATH", help="调试用：同步到指定的 docx 副本（默认交付 docx）")
    args = ap.parse_args()
    do_write = args.apply
    global DOCX
    if args.docx:
        DOCX = Path(args.docx).resolve()

    T = typ_blocks(TYP.read_text(encoding="utf-8").splitlines())
    Tfig = [b for b in T if b[0] == "figure"]
    Ttbl = [b for b in T if b[0] == "table"]

    with zipfile.ZipFile(DOCX) as zf:
        infos = zf.infolist()
        data = {i.filename: zf.read(i.filename) for i in infos}
    root = etree.fromstring(data["word/document.xml"])
    body = root.find("w:body", NS)
    rels = etree.fromstring(data["word/_rels/document.xml.rels"])
    rid2f = {r.get("Id"): r.get("Target") for r in rels}
    local_png = {p.name: p for p in REPORT.glob("*.png")}

    print("=" * 74)
    print("sync_report_docx.py —— .typ(唯一事实源) → .docx 幂等同步")
    print("=" * 74)

    # ---- A 媒体 -----------------------------------------------------------
    n_media = 0
    if not args.no_media:
        for dr in root.findall(".//w:drawing", NS):
            pic = dr.find(".//pic:cNvPr", NS)
            name = pic.get("name") if pic is not None else None
            if name not in local_png:
                continue
            blip = dr.find(".//a:blip", NS)
            if blip is None:
                continue
            target = "word/" + rid2f[blip.get("{%s}embed" % R)]
            want = local_png[name].read_bytes()
            if data.get(target) != want:
                data[target] = want
                n_media += 1
                print("  [A] media %s <- %s (%d B)" % (target, name, len(want)))
    print("  [A] 媒体字节：%d 张%s" % (n_media, "（--no-media 跳过）" if args.no_media else ""))
    count("媒体字节", n_media)

    # ---- B extent ---------------------------------------------------------
    sect = root.find(".//w:sectPr", NS)
    pg, mar = sect.find("w:pgSz", NS), sect.find("w:pgMar", NS)
    text_w = (int(pg.get("{%s}w" % W)) - int(mar.get("{%s}left" % W))
              - int(mar.get("{%s}right" % W))) * EMU_PER_TWIP
    pct = {f[1]: f[3] for f in Tfig}
    n_ext = 0
    for dr in root.findall(".//w:drawing", NS):
        pic = dr.find(".//pic:cNvPr", NS)
        name = pic.get("name") if pic is not None else None
        if name not in pct:
            continue
        blip = dr.find(".//a:blip", NS)
        media = "word/" + rid2f[blip.get("{%s}embed" % R)]
        try:
            pw, ph = png_size(data[media])
        except Exception:                                    # noqa: BLE001
            continue
        cx = int(text_w * pct[name] / 100)
        cy = int(cx * ph / pw)
        ext = dr.find(".//wp:extent", NS)
        aext = dr.find(".//a:xfrm/a:ext", NS)
        if ext is not None and (int(ext.get("cx")) != cx or int(ext.get("cy")) != cy):
            ext.set("cx", str(cx))
            ext.set("cy", str(cy))
            if aext is not None:
                aext.set("cx", str(cx))
                aext.set("cy", str(cy))
            n_ext += 1
            print("  [B] extent %s %d%% -> %.2f x %.2f in"
                  % (name, pct[name], cx / 914400, cy / 914400))
    print("  [B] 图片 extent：%d 张" % n_ext)
    count("图片 extent", n_ext)

    # ---- C 标题 -----------------------------------------------------------
    paras = root.findall(".//w:p", NS)
    n_h = 0
    for b in T:
        if b[0] != "h":
            continue
        lvl, title = b[1], b[2]
        if lvl == 1:
            cand = [p for p in paras if ptext(p).startswith(title.split("、")[0] + "、")
                    and len(ptext(p)) < len(title) + 12]
        else:
            core = re.sub(r"^\d+(\.\d+)*\s+", "", title)
            cand = [p for p in paras
                    if re.match(r"^\d+(\.\d+)*\s+", ptext(p))
                    and re.sub(r"^\d+(\.\d+)*\s+", "", ptext(p)) == core]
        if len(cand) == 1:
            if ptext(cand[0]) != title:
                set_para_text(cand[0], title)
                n_h += 1
                print("  [C] 标题 -> %s" % title)
        elif len(cand) == 0 and lvl == 2:
            print("  [C] 新节（由 F 阶段插入或人工确认）：%s" % title)
        elif len(cand) > 1:
            fail("标题锚点重名：%s（命中 %d 段）" % (title, len(cand)))
    print("  [C] 标题：%d 处" % n_h)
    count("标题", n_h)

    # ---- D 段落 -----------------------------------------------------------
    paras = root.findall(".//w:p", NS)
    n_p = 0
    for dpre, tpre, cnt in PARA_JOBS:
        dcand = [p for p in paras if clean(ptext(p)).startswith(dpre)]
        tsel = [k for k, b in enumerate(T) if b[0] in ("p", "ul", "ol") and btext(b).startswith(tpre)]
        if len(dcand) != 1 or len(tsel) != 1:
            fail("段落锚点 %r：docx %d 段 / typ %d 块" % (dpre, len(dcand), len(tsel)))
            continue
        tgt = joinb(collect(T, tsel[0], cnt))
        p = dcand[0]
        if ptext(p) != tgt:
            old = ptext(p)
            set_para_text(p, tgt)
            n_p += 1
            print("  [D] %s… %d -> %d 字" % (dpre[:16], len(old), len(tgt)))
    print("  [D] 正文段落：%d 处" % n_p)
    count("正文段落", n_p)

    # ---- E 表格 -----------------------------------------------------------
    def tables():
        return root.findall(".//w:tbl", NS)

    def find_tbl(*kw):
        for ti, t in enumerate(tables()):
            trs = t.findall("w:tr", NS)
            if not trs:
                continue
            head = "".join(x.text or "" for x in trs[0].findall(".//w:t", NS))
            if all(k in head for k in kw):
                return ti, t
        return None, None

    n_cell = 0
    n_col = 0
    for tidx, kw, name in TBL_JOBS:
        header, rows = Ttbl[tidx][1], Ttbl[tidx][2]
        allrows = (list(header) + list(rows)) if header else list(rows)
        ncols = len(allrows[0])
        # `.typ` 自己的表先得是矩形：否则"列数"这个概念就不成立，后面删列会删错
        widths = sorted({len(r) for r in allrows})
        if widths != [ncols]:
            fail("%s：.typ 表格自身列数不齐 %s —— 拒绝改写" % (name, widths))
            continue
        ti, tbl = find_tbl(*kw)
        if tbl is None:
            fail("%s：未找到表（关键字 %s）" % (name, kw))
            continue
        real = len(tbl.findall("w:tr", NS)[0].findall("w:tc", NS))
        if real != ncols:
            keep = None
            if real > ncols and header and header[0]:
                dtxt = ["".join(x.text or "" for x in tc.findall(".//w:t", NS)).strip()
                        for tc in tbl.findall("w:tr", NS)[0].findall("w:tc", NS)]
                keep, cur = [], -1
                for cell in header[0]:
                    # 本脚本的 parse_table 保留原始字符串；gen_report_md.py 那边是 (文本, 粗体) 元组
                    want = plain(cell[0] if isinstance(cell, tuple) else cell)
                    nxt = next((k for k in range(cur + 1, len(dtxt)) if dtxt[k] == want), None)
                    if nxt is None:
                        keep = None
                        break
                    keep.append(nxt)
                    cur = nxt
                # 必须**恰好**把 typ 的每一列都配上，且非空 —— 半截/空的 keep 会删错列
                if keep is None or len(keep) != ncols:
                    keep = None
            if keep is None:
                fail("%s：列数 docx=%d vs typ=%d，拒绝改写" % (name, real, ncols))
                continue
            try:
                n_col += drop_cols(tbl, keep)
            except ValueError as exc:                      # drop_cols 的自检
                fail("%s：拒绝删列 —— %s" % (name, exc))
                continue
            print("  [E] %s：docx 多 %d 列 -> 按表头对齐保留列 %s" % (name, real - ncols, keep))
        trs = tbl.findall("w:tr", NS)
        while len(trs) < len(allrows):
            trs[-1].addnext(copy.deepcopy(trs[-1]))
            trs = tbl.findall("w:tr", NS)
        while len(trs) > len(allrows):
            tbl.remove(trs[-1])
            trs = tbl.findall("w:tr", NS)
        for ri, row in enumerate(allrows):
            tcs = trs[ri].findall("w:tc", NS)
            for ci in range(min(ncols, len(tcs))):
                pp = tcs[ci].find("w:p", NS)
                if pp is None:
                    continue
                tgt = plain(row[ci])
                if ptext(pp) != tgt:
                    set_para_text(pp, tgt)
                    n_cell += 1
        print("  [E] %s（tbl#%d）%d×%d" % (name, ti, len(allrows), ncols))
    print("  [E] 表格单元格：%d 格；删列：%d" % (n_cell, n_col))
    count("表格单元格", n_cell)
    count("删除表格列", n_col)

    # ---- F 缺节插入（当前只有 §2.3 模块表）--------------------------------
    n_ins = 0
    has23 = any(ptext(p).strip() == "2.3 分块设计与模块接口一览" for p in root.findall(".//w:p", NS))
    if not has23:
        header, rows = Ttbl[1][1], Ttbl[1][2]
        allrows = (list(header) + list(rows)) if header else list(rows)
        anchor = next(p for p in root.findall(".//w:p", NS) if ptext(p).strip().startswith("2.4 主状态机"))
        tmpl_h = next(p for p in root.findall(".//w:p", NS) if ptext(p).strip().startswith("2.2 系统总体框图"))
        tmpl_p = next(p for p in root.findall(".//w:p", NS) if clean(ptext(p)).startswith("整机划分为"))
        nh = copy.deepcopy(tmpl_h)
        set_para_text(nh, "2.3 分块设计与模块接口一览")
        anchor.addprevious(nh)
        intro = plain(next(b[1] for b in T if b[0] == "p" and b[1].startswith("整机由 11 个子模块组成")))
        np_ = copy.deepcopy(tmpl_p)
        for dr in np_.findall(".//w:drawing", NS):
            dr.getparent().remove(dr)
        set_para_text(np_, intro)
        anchor.addprevious(np_)
        nt = copy.deepcopy(tables()[1])
        trs = nt.findall("w:tr", NS)
        while len(trs) < len(allrows):
            trs[-1].addnext(copy.deepcopy(trs[-1]))
            trs = nt.findall("w:tr", NS)
        while len(trs) > len(allrows):
            nt.remove(trs[-1])
            trs = nt.findall("w:tr", NS)
        for ri, row in enumerate(allrows):
            tcs = trs[ri].findall("w:tc", NS)
            for ci in range(min(len(row), len(tcs))):
                set_para_text(tcs[ci].find("w:p", NS), plain(row[ci]))
        anchor.addprevious(nt)
        n_ins = 3
        print("  [F] 插入 §2.3：标题 + 引言 + %d×%d 模块表" % (len(allrows), len(allrows[0])))
    print("  [F] 缺失章节：%s" % ("已插入" if n_ins else "无"))
    count("缺失章节", n_ins)

    # ---- H 删除 `.typ` 里已去掉的**尾部章节** -----------------------------
    # 只支持"文末章节"：从该标题（含）一路删到文末（`w:sectPr` 除外）。
    # 中间章节得靠"下一个标题"定位，容易删错，所以不在这里做。
    # 背景：§九 参考文献 于 2026-10-22 按用户要求从报告里去掉（老师不查文献表）。
    n_drop = 0
    body_el = root.find("w:body", NS)
    for title in DROP_TAIL:
        kids = list(body_el)
        hit = [c for c in kids if c.tag == "{%s}p" % W and ptext(c).strip() == title]
        if not hit:
            continue
        tail = kids[kids.index(hit[0]):]
        doomed = [c for c in tail if c.tag != "{%s}sectPr" % W]
        for c in doomed:
            body_el.remove(c)
        n_drop += len(doomed)
        print("  [H] 删除尾部章节「%s」：%d 个块" % (title, len(doomed)))
    print("  [H] 已删章节块：%d" % n_drop)
    count("删除章节", n_drop)

    # ---- G §8.2 代码清单 --------------------------------------------------
    vhd = VHD.read_text(encoding="utf-8").rstrip("\n").split("\n")
    paras = list(root.findall(".//w:p", NS))
    n_code = 0
    i82 = next((k for k, p in enumerate(paras) if ptext(p).strip() == "8.2 规范注释的顶层 VHDL 代码清单"), None)
    # 代码清单的右边界 = `.typ` 里 §8.2 之后的**下一个一级标题**（没有就是文末）。
    # ⚠️ 这里原来硬编码 "九、参考文献" 当边界；那个章节被删掉之后，
    #    硬编码会让整段 G **静默跳过**（代码清单不再校验）——所以改成从 `.typ` 现算。
    i_end = len(paras)
    t82 = next((k for k, b in enumerate(T) if b[0] == "h" and b[2].startswith("8.2 ")), None)
    if t82 is not None:
        nxt = next((b[2] for b in T[t82 + 1:] if b[0] == "h" and b[1] == 1), None)
        if nxt:
            j = next((k for k, p in enumerate(paras) if ptext(p).strip() == nxt), None)
            if j is not None and (i82 is None or j > i82):
                i_end = j
    if i82 is not None and i82 < i_end:
        code = paras[i82 + 1:i_end]
        if [ptext(p) for p in code] != vhd:
            n_code = len(code)
            tmpl = copy.deepcopy(code[0]) if code else None
            if tmpl is not None:
                for p in code:
                    p.getparent().remove(p)
                prev = paras[i82]
                for line in vhd:
                    np2 = copy.deepcopy(tmpl)
                    set_para_text(np2, line)
                    prev.addnext(np2)
                    prev = np2
            print("  [G] §8.2 代码清单重建：%d 段 -> %d 段" % (n_code, len(vhd)))
    print("  [G] 代码清单：%s" % ("已重建" if n_code else "与 top_clean.vhd 一致"))
    count("代码清单", 1 if n_code else 0)

    # ---- 旧结构检测（只提示，不擅改）--------------------------------------
    # 旧版 §3.2 是「一张表里并排 2 张波形图 + 分析列」；交付版已改成 12 张单图。
    # §4.2 的 1×2 图题表是**有意保留**的排版（两张编译截图并排），不在此列。
    legacy = [t for t in tables()
              if len(t.findall("w:tr", NS)) == 1
              and len(t.findall(".//w:drawing", NS)) == 2
              and "仿真波形" in "".join(x.text or "" for x in t.findall(".//w:t", NS))]
    if legacy:
        print("  [i] 检测到 %d 张「§3.2 并排 2 图」旧结构表 —— 交付版应为 12 张单图；"
              "本脚本不擅自重排表格（属一次性结构改造，见 git 历史）。" % len(legacy))

    # ---- 汇总 -------------------------------------------------------------
    total = sum(n for _, n in CHANGES)
    print("-" * 74)
    if FAILS:
        print("有 %d 处锚点/表格失配 —— 无法保证幂等，**已中止（不写盘）**。" % len(FAILS))
        print("请按上面的 [FAIL] 行修 .typ 措辞，或改本脚本顶部的 PARA_JOBS / TBL_JOBS 常量。")
        return 1
    if not total:
        print("0 变更 —— docx 已与 .typ / PNG 收敛（幂等）")
        return 0
    print("待变更 %d 项：%s" % (total, "、".join("%s %d" % (k, n) for k, n in CHANGES)))
    if not do_write:
        print("（--check 模式：未写盘。确认无误后加 --apply 执行）")
        return 1

    # ---- 写盘（先快照）----------------------------------------------------
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    snapdir = SNAP / stamp
    snapdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DOCX, snapdir / DOCX.name)
    print("已快照 -> %s" % (snapdir / DOCX.name).relative_to(ROOT))

    data["word/document.xml"] = etree.tostring(
        root, xml_declaration=True, encoding="UTF-8", standalone=True)
    tmp = DOCX.with_suffix(".docx.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for i in infos:
            zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
            zi.compress_type = i.compress_type
            zi.external_attr = i.external_attr
            zi.create_system = i.create_system
            zo.writestr(zi, data[i.filename])
    for _ in range(15):                     # Windows / AV 偶发占用 -> 重试
        try:
            tmp.replace(DOCX)
            break
        except PermissionError:
            time.sleep(0.3)
    else:
        print("[FAIL] 写入失败：docx 被占用（先关掉 Word 再试）")
        return 1
    print("已写入 %s（%d B）" % (DOCX.name, DOCX.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
