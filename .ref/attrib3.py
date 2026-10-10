# -*- coding: utf-8 -*-
"""测量行扫描渲染所占的面积份额，并测试一个静态移位变体。"""
import os, pathlib, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Quartus 安装目录：可用环境变量 QUARTUS_ROOT 覆盖，未设置时用常见安装路径兜底
QUARTUS = pathlib.Path(os.environ.get("QUARTUS_ROOT", r"C:\QuartusII91\QuartusII91\quartus\bin"))
SRC = (ROOT / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")

def measure(name, text, pkg=None):
    d = ROOT / ".tmp" / "scratch" / ("pc_" + name)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "puzzle_ctrl.vhd").write_text(text, encoding="utf-8")
    if pkg:
        (d / "puzzle_pkg.vhd").write_text(pkg, encoding="utf-8")
    else:
        shutil.copy(ROOT / "rtl" / "puzzle_pkg.vhd", d / "puzzle_pkg.vhd")
    shutil.copy(ROOT / ".tmp" / "scratch" / "pc_only" / "scratch_top.vhd", d / "scratch_top.vhd")
    (d / "scratch.qsf").write_text("\n".join([
        'set_global_assignment -name FAMILY "MAX II"',
        'set_global_assignment -name DEVICE EPM1270T144C5',
        'set_global_assignment -name TOP_LEVEL_ENTITY scratch_top',
        'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
        'set_global_assignment -name VHDL_FILE puzzle_pkg.vhd',
        'set_global_assignment -name VHDL_FILE puzzle_ctrl.vhd',
        'set_global_assignment -name VHDL_FILE scratch_top.vhd']) + "\n", encoding="ascii")
    (d / "scratch.qpf").write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<!DOCTYPE project SYSTEM "..\\bin\\project.dtd">\n<project>\n'
        '<header><fileVersion version="1"/></header>\n'
        '<project><name>scratch</name><revision name="scratch"/></project>\n'
        '</project>\n', encoding="ascii")
    r = subprocess.run([str(QUARTUS / "quartus_map.exe"), "scratch"],
                       cwd=d, capture_output=True, text=True, errors="replace")
    rpt = d / "output_files" / "scratch.map.rpt"
    lc = regs = "?"
    if rpt.exists():
        for line in rpt.read_text(errors="replace").splitlines():
            if "Total logic elements" in line:
                pp = [x.strip() for x in line.split(";")]
                if len(pp) > 2 and pp[2].replace(",", "").isdigit() and lc == "?":
                    lc = pp[2]
            if "Total registers" in line and regs == "?":
                pp = [x.strip() for x in line.split(";")]
                if len(pp) > 2 and pp[2].replace(",", "").isdigit():
                    regs = pp[2]
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "Error" in l][:1]
    print(f"{name:<20} LCs={lc:>7}  regs={regs:>5}  {'' if not errs else errs[0][:60]}")

measure("v5_current", SRC)

# 把 render 换成平凡常量，但仍让 o_red/o_grn 由 pos 驱动，
# 以免该状态被优化掉
rstart = SRC.index("    process (scanrow, pos, locked, sel, i_level, i_sh0")
rend = SRC.index("    ----------------------------------------------------------------------------\n    -- Scan row counter")
v = SRC[:rstart] + """    o_red <= pos(7 downto 0) xor pos(15 downto 8);
    o_grn <= pos(23 downto 16) xor pos(31 downto 24);

""" + SRC[rend:]
measure("v5_norender", v)
