#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""srcnorm.py —— 源码**归一化**：把"改了也不会改变行为"的东西抹掉（只用标准库）。

【为什么需要它】
    本项目的证据链靠"源码指纹"来判"这条绿证/固件是不是覆盖当前源码"
    （`sim.source_fingerprint` / `record_build.rtl_sources`）。原来的指纹是
    **工作树上的原始字节**的 git blob 哈希 —— 于是两类**根本不影响行为**的改动
    会把它全部打翻，制造大片假"过期"：

      1. **注释**：VHDL 的 `--`、Python 的 `#`。注释不可能影响综合
         （本项目已实测：只改注释后 `puzzle.pof` 的 sha256 逐字节相同）。
      2. **行尾**：同一个文件 CRLF 与 LF 的字节哈希不同，但 VHDL/Python/Tcl
         三种语言都**不区分**行尾。本项目为此已经踩过一次（ERR-054 的同族问题：
         重新 checkout 后内容一字未变、blob 完全相同，指纹却全变了）。

    ⇒ 这里提供"**逻辑指纹**"：先把注释与行尾抹掉，再算哈希。
      它回答的是"**产生这条证据的逻辑还在不在**"，而不是"文件字节有没有动过"。
      严格指纹（原始字节）仍然保留 —— 两个一起记，审计时先比严格的，
      不中再比逻辑的，并把"差异只在注释/行尾"如实报出来（不静默放过）。

【口径（按后缀分派）】
    · `.vhd`  —— 去掉 `--` 到行尾（**尊重 `"..."` 字符串字面量**，VHDL 里字符串内的
                 `""` 表示一个引号）；再统一行尾、去行尾空白、丢空行。
    · `.py`   —— 用 `ast.dump(ast.parse(...))`（不含 lineno/col_offset）并剔除
                 **函数/类/方法的 docstring** ⇒ 注释、这些 docstring、空行、
                 缩进风格、行尾**全部**被忽略，只剩"代码本身"。
                 ⚠️ **模块级 docstring 要保留**：本仓库的 `scripts/sim.py` 真的会
                 `print(__doc__)` 当 CLI 用法文本，改它**是**用户可见的行为改动。
                 **解析不了就退化成"只去 `#` 注释"**，绝不抛异常
                 （审计工具不能因为一个语法错误就整体挂掉）。
    · `.tcl` / `.sdc` / `.qsf` —— 去掉**命令起始位置**的 `#` 注释
                 （⚠️ Tcl 里 `#` **只有**在命令起始处才是注释：`set x {a#b}` 与
                 `set y a#b` 里的 `#` 都是**数据**。这一条是 2026-10-10 第 20 工作阶段
                 的对抗审查抓出来的：早先"见到引号外的 `#` 就截断"会把
                 `{a#b}` → `{a#c}` 这种**真改动**抹成同一串，给出假的"只改了注释"）。
    · 其它后缀 —— **只统一行尾**（不 rstrip、不丢空行：`.vwf`/`.hex` 这类数据文件里
                 空行与行尾空白可能有意义）。

⚠️ **编码**：绝不使用 `errors="replace"` —— 它会把**不同的非法字节塌成同一个
   U+FFFD**，于是两个只在字符串常量上不同的 GBK/latin-1 源文件会得到**相同**的逻辑
   指纹（对抗审查已端到端复现出"真逻辑改动被判成逻辑未变"）。现在的做法是：
   `.py` 按 PEP 263 读声明的编码解码；解不开就退回 **latin-1**（字节↔字符双射，
   永不塌陷，且往返可逆）。⚠️ 不用 `surrogateescape` —— 代理字符会让 `ast.parse`
   抛 `UnicodeEncodeError`、也会让 `logic_blob_hash` 的 `.encode("utf-8")` 抛异常。

⚠️ **它不替代严格指纹**：严格指纹记的是"当时到底跑了哪一版字节"。
   逻辑指纹只用来判"逻辑有没有变"。
"""
import ast
import hashlib
import io
import pathlib
import re
import tokenize

# 哪些后缀按"哈希注释"处理；其余一律只做行尾归一
VHDL = (".vhd",)
PY = (".py",)
HASH_COMMENT = (".tcl", ".sdc", ".qsf")

# PEP 263 的编码声明（只看前两行）
_CODING_RE = re.compile(br"^[ \t\f]*#.*?coding[:=][ \t]*([-\w.]+)")


def declared_encoding(data):
    """按 PEP 263 取源码声明的编码；没有声明就按 utf-8。"""
    for ln in data[:2048].replace(b"\r\n", b"\n").split(b"\n")[:2]:
        m = _CODING_RE.match(ln.lstrip(b"\xef\xbb\xbf"))
        if m:
            try:
                return m.group(1).decode("ascii")
            except Exception:                                  # noqa: BLE001
                return "utf-8"
    return "utf-8"


def _norm_eol(text):
    """统一行尾 + 去掉每行行尾空白 + 丢掉纯空行（**只用于三种源码后缀**）。"""
    out = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        ln = ln.rstrip()
        if ln:
            out.append(ln)
    return "\n".join(out)


def _norm_eol_only(text):
    """**只**统一行尾（未知后缀用：不动行尾空白、不丢空行）。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_vhdl(text):
    """去掉 VHDL 的 `--` 注释（尊重 `"..."` 字面量；`""` 是字符串内的引号）。"""
    out = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        res, i, in_str = [], 0, False
        while i < len(ln):
            ch = ln[i]
            if in_str:
                res.append(ch)
                if ch == '"':
                    if i + 1 < len(ln) and ln[i + 1] == '"':   # 转义的引号
                        res.append('"')
                        i += 2
                        continue
                    in_str = False
                i += 1
                continue
            if ch == '"':
                in_str = True
                res.append(ch)
                i += 1
                continue
            if ch == "-" and i + 1 < len(ln) and ln[i + 1] == "-":
                break                                          # 注释开始，丢掉行尾
            res.append(ch)
            i += 1
        out.append("".join(res))
    return _norm_eol("\n".join(out))


def strip_hash_comment(text):
    """去掉 Tcl / sdc / qsf 的 `#` 注释 —— **只认命令起始位置的 `#`**。

    ⚠️ Tcl 的规则（已用 Quartus 自带 `tclsh85` 实测确认）：
        · `set x {a#b}`   → 变量 x 的值就是 `a#b`（花括号内是字面数据）
        · `set y a#b`     → `a#b` 是普通单词（词中间的 `#` 不是注释）
        · `set z 1 ; # c` → 这个 `#` 才是注释
        · 行首（可带缩进）的 `#` 也是注释
      所以判据是"**本行/本命令起始处**（前面只有空白，或紧跟 `;`）且不在引号里"。
      早先"见到引号外的 `#` 就截断"是错的：它会把 `{a#b}` → `{a#c}` 这种真改动
      抹成同一串，从而给出假的"只改了注释"。
    """
    out = []
    for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        res, i, q, cmd_start = [], 0, None, True
        while i < len(ln):
            ch = ln[i]
            if q:
                res.append(ch)
                if ch == q:
                    q = None
                elif ch == "\\" and q == '"' and i + 1 < len(ln):
                    res.append(ln[i + 1])
                    i += 2
                    continue
                i += 1
                continue
            if ch in "\"'":
                q = ch
                res.append(ch)
                i += 1
                cmd_start = False
                continue
            if ch == "#" and cmd_start:
                break                                          # 命令起始处的注释
            if ch == ";":
                cmd_start = True
                res.append(ch)
                i += 1
                continue
            if not ch.isspace():
                cmd_start = False
            res.append(ch)
            i += 1
        out.append("".join(res))
    return _norm_eol("\n".join(out))


def _drop_docstrings(tree):
    """剔除**函数/类/方法**的 docstring；**模块级 docstring 保留**。

    ⚠️ 为什么保留模块级：本仓库 `scripts/sim.py` 会 `print(__doc__)` 当 CLI 用法文本
       （无参或未知子命令时），改模块 docstring 是**用户可见**的行为改动。
       保留它是"偏严"的方向：只会让指纹更敏感，不会放过真改动。
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                node.body = body[1:]
    return tree


def strip_python(text):
    """Python 的"代码骨架"：注释、函数/类 docstring、格式、行尾全部忽略。

    解析不了时退化成"只去 `#` 注释"（用 `tokenize`）；连 tokenize 都失败就只做行尾归一。
    """
    try:
        return ast.dump(_drop_docstrings(ast.parse(text)))
    except SyntaxError:
        pass
    except Exception:                                          # noqa: BLE001
        pass
    keep = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.COMMENT:
                keep.append((tok.type, tok.string))
        return repr(keep)
    except Exception:                                          # noqa: BLE001
        return _norm_eol_only(text)


def normalize(text, suffix):
    """按后缀选口径做归一化。"""
    s = suffix.lower()
    if s in VHDL:
        return strip_vhdl(text)
    if s in PY:
        return strip_python(text)
    if s in HASH_COMMENT:
        return strip_hash_comment(text)
    return _norm_eol_only(text)


def normalize_bytes(data, suffix):
    """把字节解码成文本再归一化。

    ⚠️ **绝不用 `errors="replace"`**：它把不同的非法字节塌成同一个 U+FFFD，
       会让"只在字符串常量上不同"的非 UTF-8 源文件得到相同指纹（假 OK）。
       这里的顺序是：`.py` 按声明的编码 → 失败退回 latin-1（双射、永不塌陷）。
    """
    enc = declared_encoding(data) if suffix.lower() in PY else "utf-8"
    try:
        text = data.decode(enc)
    except (UnicodeDecodeError, LookupError):
        text = data.decode("latin-1")
    return normalize(text, suffix)


def logic_blob_hash(data, suffix):
    """"逻辑指纹"：归一化之后的 git blob 风格 sha1（与严格指纹同一套写法）。"""
    body = normalize_bytes(data, suffix).encode("utf-8")
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(body))
    h.update(body)
    return h.hexdigest()


def logic_file_hash(path, short=12):
    p = pathlib.Path(path)
    return logic_blob_hash(p.read_bytes(), p.suffix)[:short]


def differs_only_in_comments(old_bytes, new_bytes, suffix):
    """两份字节是不是"只差注释/行尾"（给 check_comments.py 与审计共用）。"""
    return normalize_bytes(old_bytes, suffix) == normalize_bytes(new_bytes, suffix)


# 已知的**文本**后缀：归一化有意义（至少能统一行尾）。
# ⚠️ 不在这个集合里的按**原始字节**严格比较 —— 宁可严，不可放过二进制文件的改动。
TEXT_SUFFIXES = VHDL + PY + HASH_COMMENT + (
    ".vwf", ".md", ".txt", ".json", ".hex", ".mif", ".csv", ".ps1", ".sh",
    ".gitignore", ".gitattributes", ".qpf", ".v", ".sv", ".svh",
)


def is_text_suffix(suffix):
    return suffix.lower() in TEXT_SUFFIXES
