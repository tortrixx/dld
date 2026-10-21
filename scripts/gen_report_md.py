# -*- coding: utf-8 -*-
"""gen_report_md.py —— 由 `.typ` 整篇生成同名 `.md`（报告的两份文字载体保持同源）

【为什么要有它】
    `docs/report/实验报告_题目4_简易拼图游戏.typ`（→ PDF）与同名 `.md` 是**同一份报告的
    两种载体**。终稿期曾出现"PDF 改了、md 还是旧数字"的三方漂移（真实的 1,264 LE /
    54.27 MHz 与旧的 1,048 / 68.52 MHz 并存）—— 手抄同步一定会漏。这里把 `.typ` 当作
    唯一事实源，**整篇重新渲染** md：只要 `.typ` 定稿，一条命令就能让 md 跟上，
    且产物是逐字节可复现的（不再有"这份 md 是谁手改的"的问题）。

【用法】（在仓库根执行）
    python scripts/gen_report_md.py                     # 生成/覆盖交付 md
    python scripts/gen_report_md.py --check             # 只比对不写盘：一致→0，不一致→1
    python scripts/gen_report_md.py --out /tmp/x.md     # 写到别处（调试用）

【依赖】
    **需要 python-docx + lxml（本机用捆绑 Python）** —— 实际只用到 lxml 之外的纯标准库；
    本脚本本身**只用标准库**（re / pathlib / sys），但同目录的 `sync_report_docx.py`
    需要 lxml（PNG 尺寸用标准库 struct 解析，不需要 Pillow），两个脚本通常一起用，故一并提示。
    ⚠️ 不要用系统自带、未装第三方包的解释器直接跑；用 `scripts/bootstrap.sh`
    （或 README 里写明的那套 Python）跑即可。

【已知边界】
    1. 只覆盖 `.typ` 用到的排版子集：标题 `=`/`==`/`===`、段落、`-`/`1.` 列表、
       `#table(...)`（含/不含 `table.header`）、`#figure(image(...), caption:[...])`、
       `#raw(read("x.vhd"))`；其余 directive（`#v()`/`#pagebreak()`/`#outline()`）跳过。
    2. **不做 typst 的图号计算**：`.typ` 里 figure 是自动编号，这里改为在 md 里显式写
       `图 N`（顺序计数），所以 `--check` 比对的是"本脚本的确定性输出"，而非 PDF 的编号机制。
    3. 封面/目录由脚本重建：封面区块是常量（与交付版一致），目录条目由 `.typ` 标题现算。
    4. 图文件名若在 `.typ` 里是 `.svg`/`.pdf`，md 一律改引同名 `.png`（仓库里都有）。
    5. 行尾固定 LF（`.gitattributes` 要求）；输出不带 BOM。
"""
import argparse
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 仓库根 = 本脚本所在目录的上一级（**不写死绝对路径**）
ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT = ROOT / "docs" / "report"
TYP = REPORT / "实验报告_题目4_简易拼图游戏.typ"
MD = REPORT / "实验报告_题目4_简易拼图游戏.md"

# 封面区块（与交付版逐字节一致；行尾两个空格是 markdown 换行）
COVER = [
    "# 《数字电路与逻辑设计实验（下）》课程设计报告",
    "# 题目4：简易拼图游戏设计与实现",
    "",
    "**课程名称**：数字电路与逻辑设计实验（下）  ",
    "**实验学期**：2026～2027学年第一学期  ",
    "**专业班级**：电子工程 / 计算机科学与技术  ",
    "**学生姓名**：课题组成员  ",
    "**学生学号**：202300000000  ",
    "**指导教师**：实验指导教师组  ",
    "**实验成绩**：【评定中】  ",
    "**报告日期**：2026年10月  ",
    "",
    "---",
    "",
]


# --------------------------------------------------------------------------- 行内
def inline(s):
    """typst 行内标记 -> markdown：`$>= 0.000$` 去壳、`*x*`(strong) -> `**x**`。"""
    s = s.replace("$>= 0.000$", ">= 0.000").replace("$\\ge 0.000$", ">= 0.000")
    s = re.sub(r"#h\([^)]*\)", "", s)
    s = re.sub(r"#v\([^)]*\)", "", s)
    s = re.sub(r"\*([^*\n]+)\*", r"**\1**", s)
    return s.strip()


def cell_text(raw):
    """表格单元格 -> (纯文本, 是否整格加粗)。"""
    s = raw.strip()
    bold = bool(re.fullmatch(r"\*[^*]+\*", s))
    if bold:
        s = s[1:-1]
    s = s.replace("$>= 0.000$", ">= 0.000").replace("$\\ge 0.000$", ">= 0.000")
    s = re.sub(r"\s+", " ", s).strip()
    return s, bold


def anchor(title):
    """标题 -> GitHub 风格锚点（用于目录）。"""
    s = title
    for ch in "（）()、：:，,。.·“”\"'":
        s = s.replace(ch, "")
    s = s.lower().replace(" ", "-")
    return "#" + re.sub(r"[^0-9a-z\u4e00-\u9fff\-]", "", s)


# --------------------------------------------------------------------------- 解析
def parse_typ(lines):
    """把 `.typ` 正文（`= 一、` 之后）解析成块列表。"""
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
                header.append([cell_text(c) for c in re.findall(r"\[([^\[\]]*)\]", s)])
            elif s.startswith("[") and s.endswith("],"):
                rows.append([cell_text(c) for c in s[1:-2].split("], [")])
            j += 1
        raise SystemExit("`#table(` 未闭合 —— 检查 .typ 是否被手工改坏")

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
        if s.startswith("#align(center)["):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("#table("):
                j += 1
            header, rows, j = parse_table(j)
            blocks.append(("table", header, rows))
            while j < len(lines) and lines[j].strip() in ("]", ""):
                j += 1
            i = j
            continue
        if s.startswith("#table("):
            header, rows, j = parse_table(i)
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
            mc = re.search(r"caption:\s*\[(.*?)\]\s*\)?\s*$", chunk, re.S)
            cap = re.sub(r"\s+", " ", mc.group(1)).strip() if mc else ""
            if cap.endswith("]"):
                cap = cap[:-1].strip()
            blocks.append(("img", mf.group(1), cap))
            i = j
            continue
        if s.startswith("#raw(read("):
            mf = re.search(r'read\("([^"]+)"\)', s)
            ml = re.search(r'lang:\s*"([^"]+)"', s)
            body = (REPORT / mf.group(1)).read_text(encoding="utf-8")
            blocks.append(("code", ml.group(1) if ml else "", body))
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
        if para:
            blocks.append(("p", "".join(para)))
        else:
            i += 1
    return blocks


# --------------------------------------------------------------------------- 渲染
def render(blocks):
    out = list(COVER)
    out.append("## 目录")
    for b in blocks:
        if b[0] == "h" and b[1] == 1:
            out.append("- [%s](%s)" % (b[2], anchor(b[2])))
        elif b[0] == "h" and b[1] == 2:
            out.append("  - [%s](%s)" % (b[2], anchor(b[2])))
    out += ["", "---", ""]

    fig_no = 0
    for b in blocks:
        kind = b[0]
        if kind == "h":
            out += ["#" * b[1] + " " + b[2], ""]
        elif kind == "p":
            out += [inline(b[1]), ""]
        elif kind == "ul":
            out += ["- " + inline(x) for x in b[1]] + [""]
        elif kind == "ol":
            out += [inline(x) for x in b[1]] + [""]
        elif kind == "img":
            fig_no += 1
            fname = re.sub(r"\.(svg|pdf)$", ".png", b[1], flags=re.I)
            out += ["![图 %d %s](%s)" % (fig_no, b[2], fname), ""]
        elif kind == "code":
            out += ["```" + b[1], b[2].rstrip("\n"), "```", ""]
        elif kind == "table":
            header, rows = b[1], b[2]
            if not header and rows:                  # 没有 table.header 的表：首行当表头
                header, rows = [rows[0]], rows[1:]
            ncols = len(header[0]) if header else len(rows[0])
            if header:
                out.append("| " + " | ".join("**%s**" % t if bd else t for t, bd in header[0]) + " |")
            out.append("|" + "|".join([":---"] * ncols) + "|")
            for r in rows:
                cells = []
                for t, bd in r:
                    t = inline(t) if "*" in t else t
                    cells.append("**%s**" % t if bd else t)
                out.append("| " + " | ".join(cells) + " |")
            out.append("")

    text = "\n".join(out).rstrip("\n") + "\n"
    return re.sub(r"\n{3,}", "\n\n", text)


# --------------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="由 .typ 整篇生成同名 .md")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="只比对不写盘：一致→0，不一致→1")
    g.add_argument("--apply", action="store_true",
                   help="显式写盘（与不带参数相同，保留此开关只为与 sync_report_docx.py 用法对称）")
    ap.add_argument("--out", metavar="PATH", help="输出到指定路径（默认覆盖交付 md）")
    args = ap.parse_args()

    blocks = parse_typ(TYP.read_text(encoding="utf-8").splitlines())
    text = render(blocks)
    data = text.encode("utf-8")

    if args.check:
        cur = MD.read_bytes() if MD.is_file() else b""
        if cur == data:
            print("PASS  md 与 .typ 生成结果逐字节一致（%d B）" % len(data))
            return 0
        a = text.split("\n")
        b = cur.decode("utf-8", "replace").split("\n")
        diff = [(k, x, y) for k, (x, y) in enumerate(zip(a, b)) if x != y]
        print("FAIL  md 与 .typ 不一致：%d B vs %d B，首个差异行 %s"
              % (len(data), len(cur), (diff[0][0] + 1) if diff else "（长度不同）"))
        for k, x, y in diff[:5]:
            print("   L%d\n     .typ->md: %s\n     md 现状 : %s" % (k + 1, x[:100], y[:100]))
        return 1

    target = pathlib.Path(args.out) if args.out else MD
    target.write_text(text, encoding="utf-8", newline="\n")
    print("写出 %s（%d B）" % (target, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
