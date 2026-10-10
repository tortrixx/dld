#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qenv.py —— Quartus II 9.1 工具链探测（**只用标准库**）。

【为什么单独抽一个模块】
    以前"Quartus 装在哪"这件事被写死在 `sim.py` 里
    （`C:\\QuartusII91\\QuartusII91\\quartus\\bin`）。别人把 Quartus 装在别处，
    或者干脆克隆到另一台机器，脚本就直接找不到工具。
    现在把"怎么找 Quartus"集中到这一处，`sim.py` / `scratch_build.py` /
    `check_env.py` 都调它，**不再有任何一处写死安装路径**（只把常见位置当兜底）。

【查找顺序】（先找到先用）
    1. 环境变量 `QUARTUS_ROOT` —— **两种填法都接受**：
         · 指向**安装根目录**（例如 `C:\\QuartusII91\\QuartusII91`），会自动接上 `\\quartus\\bin`；
         · 直接指向 **`quartus\\bin` 目录**。
       这是为了让文档里"填你自己的安装目录"这句话对两种习惯都成立。
    2. 环境变量 `QUARTUS_BIN` —— 历史名字，语义就是 bin 目录，保留兼容。
    3. `PATH` 里的 `quartus_sh` / `quartus_sh.exe`。
    4. 常见安装位置（Windows 上的几种 Quartus 安装布局）。
    全找不到就抛 `QuartusNotFound`，**报错文案里写清三种解决办法**，
    而不是丢一句"找不到文件"。

【为什么"找不到"不写成模块级异常】
    `sim.py` 会被 `audit_evidence.py` / `record_build.py` **导入**，而那两个脚本
    完全不需要 Quartus（只读报告）。所以这里所有函数都是**惰性**的：
    导入本模块永远不会因为"没装 Quartus"而失败，只有真的要用工具时才报错。
"""
import os
import pathlib
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Quartus 的命令行工具（不带扩展名）。跨平台：Windows 上是 .exe，类 Unix 上没有后缀。
TOOLS = ("quartus_sh", "quartus_map", "quartus_fit", "quartus_asm",
         "quartus_tan", "quartus_sta", "quartus_sim", "quartus_pgm", "jtagconfig")

# 兜底的"常见安装位置"：只列**安装布局**，不列某一台机器的用户名路径。
# 每一项是"可能包含 quartus/bin 的父目录"的 glob 模式。
_COMMON_GLOBS = (
    r"C:\QuartusII91\*",          # 课程常用：C:\QuartusII91\QuartusII91\
    r"C:\altera\*",               # Altera 老安装器
    r"C:\altera_lite\*",
    r"C:\intelFPGA\*",
    r"C:\intelFPGA_lite\*",
)


class QuartusNotFound(RuntimeError):
    """找不到 Quartus 命令行工具时抛出（文案里带解决办法）。"""


def _has_tool(d, name):
    """目录 d 里有没有名为 name 的可执行文件（带不带 .exe 都认）。"""
    try:
        if not d or not d.is_dir():
            return False
    except OSError:
        return False
    return (d / (name + ".exe")).is_file() or (d / name).is_file()


def _as_bin_dir(cand):
    """把一个候选目录规范化成**真正的 bin 目录**（支持"安装根目录"与"bin 目录"两种填法）。

    返回 None 表示这个候选里没有 quartus_sh。
    """
    if not cand:
        return None
    cand = pathlib.Path(cand)
    if _has_tool(cand, "quartus_sh"):                  # 直接就是 bin
        return cand
    nested = cand / "quartus" / "bin"                  # 是安装根目录
    if _has_tool(nested, "quartus_sh"):
        return nested
    return None


def candidate_dirs():
    """按查找顺序产出候选 bin 目录（给 `check_env.py` 打印诊断用）。"""
    out = []

    def add(x):
        if x:
            p = pathlib.Path(x)
            if p not in out:
                out.append(p)

    add(os.environ.get("QUARTUS_ROOT"))
    add(os.environ.get("QUARTUS_BIN"))
    # PATH 里的 quartus_sh 所在目录
    for name in ("quartus_sh", "quartus_sh.exe"):
        w = shutil.which(name)
        if w:
            add(pathlib.Path(w).parent)
    # 常见安装位置
    for pat in _COMMON_GLOBS:
        try:
            for base in pathlib.Path(pat.split("*")[0]).glob(pat.split("\\")[-1] or "*"):
                add(base)
        except (OSError, ValueError):
            pass
    return out


_BIN_CACHE = None


def quartus_bin():
    """返回 Quartus 的 bin 目录（`pathlib.Path`）；找不到返回 **None**（不抛异常）。"""
    global _BIN_CACHE
    if _BIN_CACHE is None:
        for cand in candidate_dirs():
            d = _as_bin_dir(cand)
            if d:
                _BIN_CACHE = d
                break
        else:
            _BIN_CACHE = False          # 用 False 表示"找过了，没有"
    return _BIN_CACHE or None


def _howto():
    return ("怎么解决（任选一种）：\n"
            "  · 设置环境变量 QUARTUS_ROOT 指向 Quartus 安装目录\n"
            "      PowerShell :  $env:QUARTUS_ROOT = \"C:\\QuartusII91\\QuartusII91\"\n"
            "      （也可以直接指向其中的 quartus\\bin 子目录，两种填法都认）\n"
            "  · 把 Quartus 的 bin 目录加进 PATH\n"
            "  · 确认装的是 **Quartus II 9.1**（本项目锁定 9.1 + MAX II，不要用新版）\n"
            "自检命令： python scripts/check_env.py")


def tool(name):
    """返回工具的可执行文件路径；找不到抛 `QuartusNotFound`（文案带解决办法）。"""
    d = quartus_bin()
    if d is None:
        raise QuartusNotFound(
            "✗ 找不到 Quartus 命令行工具 %s —— 本机似乎没有可用的 Quartus II 9.1。\n%s"
            % (name, _howto()))
    for cand in (d / (name + ".exe"), d / name):
        if cand.is_file():
            return cand
    raise QuartusNotFound("✗ 在 %s 里找不到 %s。\n%s" % (d, name, _howto()))


def has(name):
    """工具存在与否（不抛异常）。"""
    try:
        return tool(name) is not None
    except QuartusNotFound:
        return False


def describe():
    """一行人类可读的状态（给 `check_env.py`）。"""
    d = quartus_bin()
    if d is None:
        return "未找到（Quartus II 9.1 未安装或未加入 PATH）"
    missing = [t for t in TOOLS if not has(t)]
    s = str(d)
    if missing:
        s += "（缺少：%s）" % "、".join(missing)
    return s


if __name__ == "__main__":
    # 直接跑本文件 = 打印探测结果（等价于 check_env 的一小节，方便排错）
    print("qenv: Quartus bin = %s" % describe())
    for c in candidate_dirs():
        print("  候选：%s%s" % (c, "  ← 命中" if _as_bin_dir(c) else ""))
