# -*- coding: utf-8 -*-
"""建一个只含指定模块的临时工程，用来把面积归因到模块。

用法： python scripts/scratch_build.py puzzle_ctrl clk_gen ...
在 .tmp/scratch/<name>/ 下生成 qsf，其中只列这些文件，外加一个
只例化第一个模块的包装顶层，并报告逻辑单元数。
"""
import pathlib, shutil, subprocess, sys, re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 仓库根 = 本脚本所在目录的上一级（**不写死绝对路径**，见 gen_project.py 的同款说明）
ROOT = pathlib.Path(__file__).resolve().parent.parent
# ⚠️ Quartus 安装位置交给 scripts/qenv.py 探测（环境变量 → PATH → 常见安装位置）
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import qenv  # noqa: E402
OUT = ROOT / ".tmp" / "scratch"

def build(files, top, name):
    d = OUT / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    qsf = [f'set_global_assignment -name FAMILY "MAX II"',
           f'set_global_assignment -name DEVICE EPM1270T144C5',
           f'set_global_assignment -name TOP_LEVEL_ENTITY {top}',
           'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files']
    for f in files:
        qsf.append(f'set_global_assignment -name VHDL_FILE {ROOT / "rtl" / f}')
    (d / "scratch.qsf").write_text("\n".join(qsf) + "\n", encoding="ascii")
    (d / "scratch.qpf").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<!DOCTYPE project SYSTEM "..\\bin\\project.dtd">\n<project>\n'
        '<header><fileVersion version="1"/></header>\n'
        '<project><name>scratch</name><revision name="scratch"/></project>\n'
        '</project>\n', encoding="ascii")
    cmd = [str(qenv.tool("quartus_map")), "scratch"]
    r = subprocess.run(cmd, cwd=d, capture_output=True, text=True, errors="replace")
    rpt = d / "scratch.map.rpt"
    lc = "?"
    if rpt.exists():
        for line in rpt.read_text(errors="replace").splitlines():
            if "Total logic elements" in line:
                parts = [p.strip() for p in line.split(";")]
                if len(parts) > 2 and parts[2].replace(",", "").isdigit():
                    lc = parts[2]
                    break
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "Error" in l][:3]
    print(f"{name:<22} top={top:<18} LCs={lc}")
    for e in errs:
        print("    ", e.strip())
    return lc, r.returncode

if __name__ == "__main__":
    args = sys.argv[1:]
    # 默认：在只有一个空顶层的工程里，逐个模块单独测面积
    if not args:
        for m, f in [("clk_gen", "clk_gen.vhd"),
                     ("keypad_scan", "keypad_scan.vhd"),
                     ("seg_scan", "seg_scan.vhd"),
                     ("dot_matrix_scan", "dot_matrix_scan.vhd"),
                     ("game_fsm", "game_fsm.vhd"),
                     ("disp_format", "disp_format.vhd"),
                     ("buzzer_ctrl", "buzzer_ctrl.vhd"),
                     ("rng_lfsr", "rng_lfsr.vhd")]:
            build(["puzzle_pkg.vhd", f], m, m)
