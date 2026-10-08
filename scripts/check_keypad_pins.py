# -*- coding: utf-8 -*-
"""Cross-check EVERY keypad-related pin against the board manual text and against
what the fitter actually placed.  This is the check that decides whether the
keypad fault can possibly be a pin-assignment mistake in this project."""
import pathlib, re, sys

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
sys.path.insert(0, str(ROOT / "scripts"))
import gen_project as g

# --- what the manual says (transcribed verbatim from the extracted text) -----
MANUAL = {
    "kp_col[0]": 117, "kp_col[1]": 118, "kp_col[2]": 119, "kp_col[3]": 120,
    "kp_row[0]": 111, "kp_row[1]": 112, "kp_row[2]": 113, "kp_row[3]": 114,
}

# --- what the generator emits -------------------------------------------------
want = {}
for k, v in g.PINS.items():
    if isinstance(v, list):
        for i, p in enumerate(v):
            want["%s[%d]" % (k, i)] = p
    else:
        want[k] = v

# --- what the fitter actually placed (from the last build's .pin report) -----
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
