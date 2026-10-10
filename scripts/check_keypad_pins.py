# -*- coding: utf-8 -*-
"""把每一个与键盘相关的引脚，同时与开发板手册文本和
布局布线器实际放置的位置对账。这条检查用来判定：
键盘故障有没有可能是本项目的引脚分配错误。"""
import pathlib, re, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 仓库根 = 本脚本所在目录的上一级（**不写死绝对路径**）
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gen_project as g

# --- 手册怎么说（从提取出的文本逐字照抄） -----
MANUAL = {
    "kp_col[0]": 117, "kp_col[1]": 118, "kp_col[2]": 119, "kp_col[3]": 120,
    "kp_row[0]": 111, "kp_row[1]": 112, "kp_row[2]": 113, "kp_row[3]": 114,
}

# --- 生成器发出什么 -------------------------------------------------
want = {}
for k, v in g.PINS.items():
    if isinstance(v, list):
        for i, p in enumerate(v):
            want["%s[%d]" % (k, i)] = p
    else:
        want[k] = v

# --- 布局布线器实际放在哪（取自最近一次编译的 .pin 报告） -----
pinrpt = ROOT / "quartus" / "output_files" / "puzzle.pin"
got = {}
if pinrpt.exists():
    for line in pinrpt.read_text(errors="replace").splitlines():
        m = re.match(r"\s*(\S+)\s*:\s*(\d+)\s*:", line)
        if m:
            got[m.group(1)] = int(m.group(2))

print("signal        manual  generator  fitter")
bad = 0
for sig, mpin in MANUAL.items():
    gpin = want.get(sig)
    fpin = got.get(sig)
    ok = (gpin == mpin) and (fpin == mpin)
    if not ok:
        bad += 1
    print("%-12s  %6s  %9s  %6s   %s" % (sig, mpin, gpin, fpin, "OK" if ok else "<<< MISMATCH"))

print()
if bad == 0:
    print("RESULT: every keypad pin matches the manual AND the fitter placement.")
    print()
    print("        Run this after EVERY build.  If it ever reports mismatches, the")
    print("        pins are unconstrained and Quartus has scattered them over free")
    print("        pins -- the design will still compile and run, and the keypad will")
    print("        look exactly like broken hardware.  That is ERR-002.")
else:
    print("RESULT: %d mismatch(es)." % bad)
    print()
    print("        A mismatch means the port is missing from TOP_PORTS in")
    print("        scripts/gen_project.py, so no pin constraint was emitted for it.")
    print("        Add the port, regenerate, and rebuild.  See docs/06 ERR-002.")
