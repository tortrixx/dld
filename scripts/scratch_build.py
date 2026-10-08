# -*- coding: utf-8 -*-
"""Build a scratch project containing ONLY the modules given, to attribute area.

Usage:  python scripts/scratch_build.py puzzle_ctrl clk_gen ...
Creates .tmp/scratch/<name>/ with a qsf listing just those files plus a wrapper
top level that instantiates the first module named, and reports the logic cells.
"""
import pathlib, shutil, subprocess, sys, re

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
QUARTUS = pathlib.Path(r"C:\QuartusII91\QuartusII91\quartus\bin")
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
    cmd = [str(QUARTUS / "quartus_map.exe"), "scratch"]
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
    # default: measure each module in isolation inside a trivial nothing-top
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
