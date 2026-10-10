#!/bin/sh
# ============================================================================
#  bootstrap.sh —— 一键生成 Quartus 工程（Linux / macOS 同学用）
#
#  用法：
#     sh scripts/bootstrap.sh                 # 顶层实体 = puzzle_top
#     sh scripts/bootstrap.sh board_test_top  # 换一个顶层实体
#
#  它**只做一件事**：把同学从"记得先跑生成脚本"里解放出来 ——
#  先定位仓库根，再调用 scripts/gen_project.py 写出
#  quartus/puzzle.qpf + quartus/puzzle.qsf。于是一份全新 clone 出来的仓库
#  就能直接编译，无需任何手工建工程的步骤。
#
#  说明：
#    · 只用系统 Python 3 的**标准库**，不安装任何东西，也不改别的文件。
#    · 本脚本**不**写死任何 Quartus 安装路径。
#    · ⚠️ 本脚本靠 $0 定位仓库根，**只支持"直接执行"**（sh scripts/bootstrap.sh）；
#      不要用 `source` / `.` 或软链接调用 —— 那样 $0 会变成调用者的名字或软链接
#      路径，算出来的仓库根是错的，随后会去错误的目录里找 scripts/gen_project.py。
#    · 本文件刻意不使用 emoji：有些终端 locale 不支持，会打出乱码。
#    · 只用 POSIX sh 语法（没有 bash 专有写法），dash / ash 也能跑。
# ============================================================================

set -u

# 仓库根 = 本脚本所在目录（scripts/）的上一级。
# 用 $0 定位而不是当前目录，这样**从任意目录**调用都能工作。
# 前缀 CDPATH= 是必要的：否则用户环境里的 CDPATH 会污染 cd 的输出。
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(dirname -- "$SCRIPT_DIR")
cd -- "$ROOT" || { echo "错误：无法进入仓库根目录：$ROOT" >&2; exit 1; }

# 顶层实体名：给了参数就用参数当顶层实体名；否则用游戏本体 puzzle_top
# （gen_project.py 自己的默认值是 board_test_top，那是板级自检，不是游戏）。
if [ "$#" -ge 1 ] && [ -n "$1" ]; then
    TOP=$1
else
    TOP=puzzle_top
fi

echo "=============================================================="
echo " bootstrap : 仓库根 = $ROOT"
echo " 顶层实体  : $TOP"
echo " 将要执行  : python scripts/gen_project.py $TOP"
echo "=============================================================="

# ---- 检查 1：找 python3 或 python --------------------------------------
# 优先 python3：有些系统上 python 仍然是 Python 2，而 gen_project.py
# 用了 pathlib 与函数注解，在 Python 2 下直接语法错误。
PY=
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    # 退回 python 之前先确认它真的是 Python 3，免得报出难懂的语法错误。
    if [ "$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null)" = "3" ]; then
        PY=python
    else
        echo "" >&2
        echo "错误：找到的 python 不是 Python 3。" >&2
        echo "      请安装 Python 3（例如 apt install python3 / brew install python3），" >&2
        echo "      然后确认 python3 --version 能显示 Python 3.x。" >&2
        exit 1
    fi
fi

if [ -z "$PY" ]; then
    echo "" >&2
    echo "错误：找不到 python3 或 python。" >&2
    echo "      请先安装 Python 3 并加入 PATH，然后重新跑本脚本。" >&2
    echo "      验证方法：执行 python3 --version，应显示 Python 3.x。" >&2
    exit 1
fi
echo " 已找到 Python : $(command -v "$PY")"

# ---- 调用生成脚本（在仓库根下执行，相对路径才成立）-------------------
"$PY" scripts/gen_project.py "$TOP"
CODE=$?

# ---- 检查 2：把 gen_project 的退出码**原样透传** -----------------------
if [ "$CODE" -ne 0 ]; then
    echo "" >&2
    echo "错误：gen_project.py 失败（退出码 $CODE），Quartus 工程没有生成。" >&2
    echo "      常见原因：顶层实体名拼错（可选值见 scripts/gen_project.py 的 TOP_PORTS）。" >&2
    exit "$CODE"
fi

# ---- 成功：直接打印下一步，省掉"接下来干嘛"的疑问 ---------------------
echo ""
echo "下一步："
echo "  1) 打开工程 : quartus/puzzle.qpf（Quartus II 9.1 -> File -> Open Project）"
echo "  2) 编译     : quartus_sh -t scripts/build.tcl"
echo "                （quartus_sh 在 Quartus 安装目录的 bin/ 下；"
echo "                  本脚本不写死安装路径，请用完整路径或把它加进 PATH）"
echo "  3) 烧录     : quartus_pgm -c \"USB-Blaster [USB-0]\" -m jtag -o \"p;quartus/output_files/puzzle.pof\""
echo "                （先在 Quartus 里编译出 .pof；也可以到 quartus/output_files 下执行）"
