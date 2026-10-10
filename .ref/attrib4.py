# -*- coding: utf-8 -*-
"""比较检查引擎的几种重叠判定策略。

精确的行掩码判定开销很大，因为它需要 row_mask（8 位可变移位）
再加上逐行 AND。这里测量的是包围盒版本，也就是参考实现所用的做法，
它只需要整数比较。
"""
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
            if "Total logic elements" in line and lc == "?":
                pp = [x.strip() for x in line.split(";")]
                if len(pp) > 2 and pp[2].replace(",", "").isdigit():
                    lc = pp[2]
            if "Total registers" in line and regs == "?":
                pp = [x.strip() for x in line.split(";")]
                if len(pp) > 2 and pp[2].replace(",", "").isdigit():
                    regs = pp[2]
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "Error" in l][:1]
    print(f"{name:<22} LCs={lc:>7} regs={regs:>5} {'' if not errs else errs[0][:55]}")

measure("current_exact", SRC)

# ---- 包围盒变体：把 CH_RUN 的逐行 AND 换成整数比较 --
old = SRC[SRC.index("                    when CH_RUN =>"):SRC.index("                    when CH_DONE =>")]
new = """                    when CH_RUN =>
                        chk_row <= chk_row + 1;
                        if (chk_row = 0) then
                            -- bounding-box overlap, computed in one cycle:
                            --   boxes intersect  <=>  dr < h_sum and dc < w_sum
                            -- The candidate is compared against each live piece.
                            cr := to_integer(unsigned(chk_pos(7 downto 4)));
                            cc := to_integer(unsigned(chk_pos(3 downto 0)));
                            hh := to_integer(unsigned(chk_h));
                            ww := to_integer(unsigned(chk_w));

                            if (sel /= "00") then
                                if (abs(cr - to_integer(unsigned(pos(31 downto 28))))
                                    < hh + to_integer(unsigned(i_h0)))
                                   and (abs(cc - to_integer(unsigned(pos(27 downto 24))))
                                    < ww + to_integer(unsigned(i_w0))) then
                                    chk_hit <= '1';
                                end if;
                            end if;
                            if (sel /= "01") then
                                if (abs(cr - to_integer(unsigned(pos(23 downto 20))))
                                    < hh + to_integer(unsigned(i_h1)))
                                   and (abs(cc - to_integer(unsigned(pos(19 downto 16))))
                                    < ww + to_integer(unsigned(i_w1))) then
                                    chk_hit <= '1';
                                end if;
                            end if;
                            if (sel /= "10") then
                                if (abs(cr - to_integer(unsigned(pos(15 downto 12))))
                                    < hh + to_integer(unsigned(i_h2)))
                                   and (abs(cc - to_integer(unsigned(pos(11 downto 8))))
                                    < ww + to_integer(unsigned(i_w2))) then
                                    chk_hit <= '1';
                                end if;
                            end if;
                            if (lvl2 and (sel /= "11")) then
                                if (abs(cr - to_integer(unsigned(pos(7 downto 4))))
                                    < hh + to_integer(unsigned(i_h3)))
                                   and (abs(cc - to_integer(unsigned(pos(3 downto 0))))
                                    < ww + to_integer(unsigned(i_w3))) then
                                    chk_hit <= '1';
                                end if;
                            end if;
                            chk <= CH_DONE;
                        end if;

"""
measure("bbox", SRC.replace(old, new))
