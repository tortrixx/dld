#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_env.py —— 复现环境自检（**只用标准库**，退出码 0/1）。

【为什么要有它】
    "clone 下来编译不了"最常见的原因不是代码坏了，而是**环境没对上**：
    Quartus 装在别处、Python 版本太老、或者忘了先跑 `gen_project.py` 生成 `.qpf`。
    这一条命令把这三件事一次说清，**并且给出可直接照抄的修复命令**，
    免得同学对着一句 "No such file or directory" 猜半天。

【用法】
    python scripts/check_env.py            # 人看
    python scripts/check_env.py --quiet    # 只输出一行结论（给 CI / agent 用）

退出码：0 = 可以编译；1 = 有阻塞项（会逐条列出）。
"""
import pathlib
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import qenv  # noqa: E402  （同目录，纯标准库）

MIN_PY = (3, 8)

# 复现所需的最小文件集（缺任何一个都编译不了）
REQUIRED = [
    "rtl/puzzle_top.vhd",
    "rtl/puzzle_pkg.vhd",
    "quartus/puzzle.sdc",
    "scripts/gen_project.py",
]
# 由生成脚本产出、**故意不入库**（避免 Quartus 时间戳污染 git）
GENERATED = ["quartus/puzzle.qpf", "quartus/puzzle.qsf"]

ok = []
warn = []
bad = []


def check(cond, good, bad_msg, bucket):
    (ok if cond else bucket).append(good if cond else bad_msg)


# ---- 1. Python 版本 ---------------------------------------------------------
check(sys.version_info >= MIN_PY + (0,),
      "Python %d.%d.%d（要求 ≥ %d.%d）" % (sys.version_info[0], sys.version_info[1],
                                           sys.version_info[2], MIN_PY[0], MIN_PY[1]),
      "Python %d.%d.%d 太老（要求 ≥ %d.%d）—— 本项目脚本用了 f-string 等 3.6+ 语法，"
      "建议装 3.8 以上" % (sys.version_info[0], sys.version_info[1], sys.version_info[2],
                          MIN_PY[0], MIN_PY[1]),
      bad)

# ---- 2. 必需文件 -----------------------------------------------------------
for rel in REQUIRED:
    check((ROOT / rel).is_file(), "存在 %s" % rel,
          "**缺少 %s** —— 这不是一个完整的克隆（是不是只拷了一部分文件？）" % rel, bad)

# ---- 3. 生成物（缺了不算错，只是"还没跑第一步"）----------------------------
missing_gen = [g for g in GENERATED if not (ROOT / g).is_file()]
if missing_gen:
    warn.append("还没生成 %s —— 这是**正常的**（`.qpf` 故意不入库）；"
                "先跑一次： python scripts/gen_project.py puzzle_top" % "、".join(missing_gen))
else:
    ok.append("已生成 %s" % "、".join(GENERATED))

# ---- 4. Quartus ------------------------------------------------------------
qbin = qenv.quartus_bin()
if qbin is None:
    bad.append("**找不到 Quartus II 9.1 的命令行工具**。\n" +
               "\n".join("      " + l for l in qenv._howto().splitlines()))
else:
    missing_tools = [t for t in qenv.TOOLS if not qenv.has(t)]
    if missing_tools:
        warn.append("Quartus bin = %s，但缺少工具：%s（仿真/编译可能用不了）"
                    % (qbin, "、".join(missing_tools)))
    else:
        ok.append("Quartus bin = %s（%d 个命令行工具齐全）" % (qbin, len(qenv.TOOLS)))

# ---- 5. 第三方依赖（本项目应当一个都不需要）--------------------------------
third = [m for m in ("numpy", "pandas", "PIL", "docx", "pptx", "openpyxl", "lxml", "xlsxwriter")
         if (ROOT / (m + ".py")).exists()]
if third:
    warn.append("仓库里出现了疑似第三方模块：%s" % "、".join(third))
else:
    ok.append("无第三方 Python 依赖（只用标准库；不需要 venv / requirements.txt）")

# ---- 6. 输出 ---------------------------------------------------------------
quiet = "--quiet" in sys.argv
if not quiet:
    print("=" * 70)
    print("复现环境自检 —— %s" % ROOT)
    print("=" * 70)
    for s in ok:
        print("  ✓ %s" % s)
    for s in warn:
        print("  ⚠ %s" % s)
    for s in bad:
        print("  ✗ %s" % s)
    print("-" * 70)
    if bad:
        print("结论：**有 %d 项阻塞**，先按上面的提示修掉再编译。" % len(bad))
    elif warn:
        print("结论：可以编译（有 %d 条提醒）。下一步： python scripts/gen_project.py puzzle_top" % len(warn))
    else:
        print("结论：环境就绪。下一步： python scripts/gen_project.py puzzle_top")
else:
    print("check_env: %s" % ("FAIL(%d)" % len(bad) if bad else "OK"))

sys.exit(1 if bad else 0)
