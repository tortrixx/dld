# -*- coding: utf-8 -*-
"""Narrow down: disable pieces of the SCATTER path and measure each."""
import pathlib, shutil, subprocess

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
QUARTUS = pathlib.Path(r"C:\QuartusII91\QuartusII91\quartus\bin")
SRC = (ROOT / "rtl" / "puzzle_ctrl.vhd").read_text(encoding="utf-8")

def measure(name, text):
    d = ROOT / ".tmp" / "scratch" / ("pc_" + name)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    (d / "puzzle_ctrl.vhd").write_text(text, encoding="utf-8")
    shutil.copy(ROOT / ".tmp" / "scratch" / "pc_only" / "scratch_top.vhd", d / "scratch_top.vhd")
    shutil.copy(ROOT / "rtl" / "puzzle_pkg.vhd", d / "puzzle_pkg.vhd")
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
                if len(pp) > 2 and pp[2].replace(",", "").isdigit():
                    lc = pp[2]
            if "Total registers" in line and regs == "?":
                pp = [x.strip() for x in line.split(";")]
                if len(pp) > 2 and pp[2].replace(",", "").isdigit():
                    regs = pp[2]
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "Error" in l][:1]
    print(f"{name:<22} LCs={lc:>8}  regs={regs:>5}  {'' if not errs else errs[0][:60]}")
    return lc

measure("full", SRC)

# A. scatter never leaves SH_IDLE
v = SRC.replace("if (i_go = '1') then\n                        sh     <= SH_GET;",
                "if (i_go = '1') then\n                        sh     <= SH_IDLE;")
assert v != SRC
measure("A_scatter_off", v)

# B. remove the column-shift case in SH_PLACE (use sh_acc unchanged)
start = v.index("                        -- column shift: move each row right by cc (fixed loop)")
end = v.index("                        ok := (cr + hh <= 8) and (cc + ww <= 8);\n                        if (ok) then\n                            if (i_level = '0') then\n                                case to_integer(sh_k) is\n                                    when 0      => rest := m1 or m2;")
valsrc = """
                        occ := sh_acc;
"""
measure("B_nocolshift", SRC[:start] + valsrc + SRC[end:])

# C. remove the serial row shifter (SH_SHIFT does nothing)
v3 = SRC.replace("""                        if (to_integer(sh_row) < lim) then
                            sh_row <= sh_row + 1;
                            if (to_integer(sh_row) = 0) then
                                sh_acc <= x"00" & nexth(63 downto 8);
                            else
                                sh_acc <= x"00" & sh_acc(63 downto 8);
                            end if;
                        else
                            sh <= SH_PLACE;
                        end if;""",
                 "                        sh <= SH_PLACE;")
assert v3 != SRC
measure("C_norowshift", v3)

# D. no overlap check in SH_PLACE
v4 = SRC.replace("if ((occ and rest) /= MASK_ZERO) then\n                                ok := false;\n                            end if;\n                        end if;\n\n                        if (ok) then\n                            case to_integer(sh_k) is",
                 "null;\n                        end if;\n\n                        if (ok) then\n                            case to_integer(sh_k) is")
measure("D_nooverlap", v4)
