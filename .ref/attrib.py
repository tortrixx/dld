# -*- coding: utf-8 -*-
"""通过逐个去掉某项功能来构造变体，从而归属 puzzle_ctrl 的面积开销。

分别测量以下变体的 Total logic elements：
    full        原样
    no_render   o_px_red 由常量驱动（去掉 render 进程）
    no_scatter  散落状态机被强制为 SH_IDLE（去掉散落逻辑）
    no_move     禁用移动路径
这样就能看出究竟是哪个结构在消耗面积，而不是靠猜。
"""
import os, pathlib, re, shutil, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
# Quartus 安装目录：可用环境变量 QUARTUS_ROOT 覆盖，未设置时用常见安装路径兜底
QUARTUS = pathlib.Path(os.environ.get("QUARTUS_ROOT", r"C:\QuartusII91\QuartusII91\quartus\bin"))
SRC = (ROOT / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")

def variant(name, text):
    d = ROOT / ".tmp" / "scratch" / ("pc_" + name)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "puzzle_ctrl.vhd").write_text(text, encoding="utf-8")

    top = (ROOT / ".tmp" / "scratch" / "pc_only" / "scratch_top.vhd").read_text(encoding="ascii")
    (d / "scratch_top.vhd").write_text(top, encoding="ascii")
    shutil.copy(ROOT / "rtl" / "puzzle_pkg.vhd", d / "puzzle_pkg.vhd")

    qsf = ['set_global_assignment -name FAMILY "MAX II"',
           'set_global_assignment -name DEVICE EPM1270T144C5',
           'set_global_assignment -name TOP_LEVEL_ENTITY scratch_top',
           'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
           'set_global_assignment -name VHDL_FILE puzzle_pkg.vhd',
           'set_global_assignment -name VHDL_FILE puzzle_ctrl.vhd',
           'set_global_assignment -name VHDL_FILE scratch_top.vhd']
    (d / "scratch.qsf").write_text("\n".join(qsf) + "\n", encoding="ascii")
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
                p = [x.strip() for x in line.split(";")]
                if len(p) > 2 and p[2].replace(",", "").isdigit():
                    lc = p[2]
            if "Total registers" in line:
                p = [x.strip() for x in line.split(";")]
                if len(p) > 2 and p[2].replace(",", "").isdigit() and regs == "?":
                    regs = p[2]
    err = [l for l in (r.stdout + r.stderr).splitlines() if "Error" in l][:2]
    print(f"{name:<12} LCs={lc:>8}  regs={regs:>5}  {'OK' if not err else err[0][:70]}")
    return lc

# ---- full -----------------------------------------------------------------
variant("full", SRC)

# ---- 去掉 render：o_px_red / o_px_grn 接常量 -----------------
v = re.sub(r"    process \(m0, m1, m2, m3, locked, sel, i_target, i_level\).*?end process;",
           "    o_px_red <= (others => '0');\n    o_px_grn <= (others => '0');",
           SRC, flags=re.S)
v = v.replace("        o_px_red <= covered or (i_target and (not covered));\n"
              "        o_px_grn <= kcol;\n", "")
assert v != SRC
variant("no_render", v)

# ---- 去掉散落：状态机直接跳到 SH_DONE ------------------------
v2 = SRC.replace("if (i_go = '1') then\n                        sh     <= SH_GET;",
                 "if (i_go = '1') then\n                        sh     <= SH_DONE;")
assert v2 != SRC
variant("no_scatter", v2)

# ---- 去掉移动路径 -----------------------------------------------------
v3 = SRC.replace("if (mv = '1') then\n                    mv <= '0';",
                 "if (false) then\n                    mv <= '0';")
assert v3 != SRC
variant("no_move", v3)
