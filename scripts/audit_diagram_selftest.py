#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""audit_diagram_selftest.py -- self-test for scripts/audit_diagram.py.

Writes three tiny synthetic layout sidecars into .tmp/audit_selftest/ and runs
the auditor as a subprocess, asserting:

  1. clean.json          -> exit 0, no ERROR findings, 0 crossings
                            (and the SCORE line equals the documented formula)
  2. box_hit.json        -> exit 1 with E-BOX-HIT naming the box that the wire
                            runs through
  3. label_overlap.json  -> exit 1 with E-LABEL-LABEL naming both wires

Extra assertions (cheap regression guards, all on the same fixtures):
  4. --help exits 0 and prints the check codes
  5. --json emits a parseable report whose last line is the SCORE line and whose
     "score" field matches the printed SCORE
  6. --quiet prints only ERROR findings + the SCORE line
  7. --fidelity does not crash when scripts/arch_data.py is absent and says so
  8. a wire that runs into its own endpoint box beyond the 6 px attachment zone
     is still reported (E-BOX-HIT), i.e. endpoint boxes are not skipped

Usage:
    python scripts/audit_diagram_selftest.py [--python <interpreter>]

Exit code 0 when every assertion passes, 1 otherwise.  Pure standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Importing the auditor (test [8]) must not leave .pyc files in scripts/__pycache__;
# the only paths this self-test is allowed to write are .tmp/audit_selftest/*.
sys.dont_write_bytecode = True

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "scripts", "audit_diagram.py")
FIXDIR = os.path.join(ROOT, ".tmp", "audit_selftest")

# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
# 1. clean: four boxes, one zone, two parallel wires, labels clear of everything.
CLEAN = {
    "id": "selftest_clean",
    "canvas": {"w": 800, "h": 600},
    "boxes": [
        {"id": "A", "kind": "entity", "x": 100, "y": 100, "w": 160, "h": 80,
         "title": "A", "sub": "rtl/a.vhd"},
        {"id": "B", "kind": "entity", "x": 500, "y": 100, "w": 160, "h": 80,
         "title": "B", "sub": "rtl/b.vhd"},
        {"id": "C", "kind": "entity", "x": 100, "y": 400, "w": 160, "h": 80,
         "title": "C", "sub": "rtl/c.vhd"},
        {"id": "D", "kind": "ext", "x": 500, "y": 400, "w": 160, "h": 80,
         "title": "D", "sub": "PIN_1"},
    ],
    "zones": [{"id": "Z", "x": 80, "y": 80, "w": 600, "h": 120, "title": "top"}],
    "wires": [
        {"id": "w1", "from": "A", "to": "B", "from_side": "right",
         "to_side": "left", "pts": [[260, 140], [500, 140]],
         "nets": ["go", "sel"],
         "label": {"text": "go/sel", "x": 380, "y": 125, "anchor": "middle",
                   "size": 13.5},
         "width_px": 1.9},
        {"id": "w2", "from": "C", "to": "D", "from_side": "right",
         "to_side": "left", "pts": [[260, 440], [500, 440]],
         "nets": ["move"],
         "label": {"text": "move", "x": 380, "y": 425, "anchor": "middle",
                   "size": 13.5},
         "width_px": 1.9},
    ],
}

# 2. box_hit: the wire between A and B runs straight through the glue box M.
BOX_HIT = {
    "id": "selftest_box_hit",
    "canvas": {"w": 800, "h": 600},
    "boxes": [
        {"id": "A", "kind": "entity", "x": 100, "y": 100, "w": 120, "h": 80,
         "title": "A"},
        {"id": "M", "kind": "glue", "x": 340, "y": 100, "w": 120, "h": 80,
         "title": "M"},
        {"id": "B", "kind": "entity", "x": 600, "y": 100, "w": 120, "h": 80,
         "title": "B"},
    ],
    "zones": [],
    "wires": [
        {"id": "w_bad", "from": "A", "to": "B", "from_side": "right",
         "to_side": "left", "pts": [[220, 140], [600, 140]],
         "nets": ["n1"], "width_px": 1.9},
    ],
}

# 3. label_overlap: two wire labels sit on top of each other.
LABEL_OVERLAP = {
    "id": "selftest_label_overlap",
    "canvas": {"w": 800, "h": 600},
    "boxes": [
        {"id": "A", "kind": "entity", "x": 100, "y": 100, "w": 120, "h": 80,
         "title": "A"},
        {"id": "B", "kind": "entity", "x": 600, "y": 100, "w": 120, "h": 80,
         "title": "B"},
        {"id": "C", "kind": "entity", "x": 100, "y": 400, "w": 120, "h": 80,
         "title": "C"},
        {"id": "D", "kind": "entity", "x": 600, "y": 400, "w": 120, "h": 80,
         "title": "D"},
    ],
    "zones": [],
    "wires": [
        {"id": "w1", "from": "A", "to": "B", "pts": [[220, 140], [600, 140]],
         "nets": ["n1"],
         "label": {"text": "alpha", "x": 400, "y": 140, "anchor": "middle",
                   "size": 13.5}},
        {"id": "w2", "from": "C", "to": "D", "pts": [[220, 440], [600, 440]],
         "nets": ["n2"],
         "label": {"text": "beta", "x": 405, "y": 145, "anchor": "middle",
                   "size": 13.5}},
    ],
}

# 4. endpoint_intrusion: the wire starts on A's right edge and immediately runs
#    back through A's interior, so the endpoint box must still be reported.
ENDPOINT_INTRUSION = {
    "id": "selftest_endpoint_intrusion",
    "canvas": {"w": 800, "h": 600},
    "boxes": [
        {"id": "A", "kind": "entity", "x": 100, "y": 100, "w": 200, "h": 80,
         "title": "A"},
        {"id": "B", "kind": "entity", "x": 600, "y": 100, "w": 120, "h": 80,
         "title": "B"},
    ],
    "zones": [],
    "wires": [
        {"id": "w_loop", "from": "A", "to": "B", "pts": [[300, 140], [150, 140],
                                                          [150, 300], [660, 300],
                                                          [660, 140], [600, 140]],
         "nets": ["n1"]},
    ],
}

FIXTURES = [
    ("clean.json", CLEAN),
    ("box_hit.json", BOX_HIT),
    ("label_overlap.json", LABEL_OVERLAP),
    ("endpoint_intrusion.json", ENDPOINT_INTRUSION),
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
class Checker(object):
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def check(self, cond, label, detail=""):
        if cond:
            self.passed += 1
            print("  PASS  {}".format(label))
        else:
            self.failed += 1
            self.failures.append(label)
            print("  FAIL  {}{}".format(label, ("  <- " + detail) if detail else ""))
        return bool(cond)


def write_fixtures():
    os.makedirs(FIXDIR, exist_ok=True)
    written = []
    for name, doc in FIXTURES:
        path = os.path.join(FIXDIR, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        written.append(path)
    return written


def run_audit(py, fixture, extra=()):
    cmd = [py, AUDIT, fixture] + list(extra)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def split_score(stdout):
    """Return (body_lines, score_or_None); SCORE must be the last non-empty line."""
    lines = [ln for ln in stdout.splitlines()]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines or not lines[-1].startswith("SCORE "):
        return lines, None
    try:
        score = float(lines[-1].split()[1])
    except (IndexError, ValueError):
        return lines, None
    return lines[:-1], score


def parse_json_report(stdout):
    body, _score = split_score(stdout)
    return json.loads("\n".join(body))


def codes(report):
    return [f["code"] for f in report["findings"]]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="audit_diagram_selftest.py",
        description="Self-test for scripts/audit_diagram.py (writes fixtures into "
                    ".tmp/audit_selftest/ and asserts the documented behaviour).")
    ap.add_argument("--python", default=sys.executable,
                    help="interpreter used to run the auditor "
                         "(default: the current interpreter)")
    args = ap.parse_args(argv)

    py = args.python
    c = Checker()
    print("audit_diagram self-test")
    print("  auditor      : {}".format(AUDIT))
    print("  interpreter  : {} ({})".format(py, sys.version.split()[0]))
    print("  fixtures dir : {}".format(FIXDIR))
    print("")

    paths = write_fixtures()
    print("fixtures written:")
    for p in paths:
        print("  {} ({} bytes)".format(p, os.path.getsize(p)))
    print("")

    clean = os.path.join(FIXDIR, "clean.json")
    box_hit = os.path.join(FIXDIR, "box_hit.json")
    label_overlap = os.path.join(FIXDIR, "label_overlap.json")
    endpoint_intrusion = os.path.join(FIXDIR, "endpoint_intrusion.json")

    # ---- 1. clean ---------------------------------------------------------
    print("[1] clean.json -> exit 0, no errors, 0 crossings")
    rc, out, err = run_audit(py, clean, ["--json"])
    c.check(rc == 0, "clean: exit code is 0", "got {}".format(rc))
    rep = None
    try:
        rep = parse_json_report(out)
        c.check(True, "clean: --json output parses")
    except Exception as exc:  # noqa: BLE001
        c.check(False, "clean: --json output parses", "{}: {}".format(type(exc).__name__, exc))
    if rep is not None:
        c.check(rep["counts"]["errors"] == 0, "clean: 0 ERROR findings",
                "codes={}".format(sorted(set(codes(rep)))))
        c.check(rep["crossings"]["total"] == 0, "clean: 0 crossings",
                "got {}".format(rep["crossings"]["total"]))
        c.check(rep["collinear"]["pairs"] == 0, "clean: 0 collinear wire pairs",
                "got {}".format(rep["collinear"]["pairs"]))
        c.check("E-BOX-HIT" not in codes(rep) and "E-ATTACH" not in codes(rep),
                "clean: no E-BOX-HIT / E-ATTACH",
                "codes={}".format(sorted(set(codes(rep)))))
        expected = round(200.0 * rep["whitespace"]["empty_fraction"]
                         + rep["stats"]["longest_wire"]["length"] / 100.0, 2)
        c.check(abs(rep["score"] - expected) < 1e-6,
                "clean: score matches the documented formula",
                "score={} expected={}".format(rep["score"], expected))
        body, score = split_score(out)
        c.check(score is not None and abs(score - rep["score"]) < 1e-9,
                "clean: last stdout line is 'SCORE <score>'",
                "score_line={!r}".format(score))
        print("        score = {}   (errors={}, crossings={}, collinear={}, "
              "empty_fraction={}, longest_wire={})".format(
                  rep["score"], rep["counts"]["errors"], rep["crossings"]["total"],
                  rep["collinear"]["pairs"], rep["whitespace"]["empty_fraction"],
                  rep["stats"]["longest_wire"]["length"]))
    print("")

    # ---- 2. box hit -------------------------------------------------------
    print("[2] box_hit.json -> exit 1 with E-BOX-HIT")
    rc, out, err = run_audit(py, box_hit, ["--json"])
    c.check(rc == 1, "box_hit: exit code is 1", "got {}".format(rc))
    rep = None
    try:
        rep = parse_json_report(out)
    except Exception as exc:  # noqa: BLE001
        c.check(False, "box_hit: --json output parses", "{}".format(exc))
    if rep is not None:
        c.check("E-BOX-HIT" in codes(rep), "box_hit: E-BOX-HIT reported",
                "codes={}".format(sorted(set(codes(rep)))))
        hits = [f for f in rep["findings"] if f["code"] == "E-BOX-HIT"]
        boxes = sorted({f.get("data", {}).get("box") for f in hits})
        c.check(boxes == ["M"], "box_hit: E-BOX-HIT names box M",
                "got {}".format(boxes))
        print("        {}".format(hits[0]["message"] if hits else "(none)"))
        print("        score = {}".format(rep["score"]))
    print("")

    # ---- 3. label overlap -------------------------------------------------
    print("[3] label_overlap.json -> exit 1 with E-LABEL-LABEL")
    rc, out, err = run_audit(py, label_overlap, ["--json"])
    c.check(rc == 1, "label_overlap: exit code is 1", "got {}".format(rc))
    rep = None
    try:
        rep = parse_json_report(out)
    except Exception as exc:  # noqa: BLE001
        c.check(False, "label_overlap: --json output parses", "{}".format(exc))
    if rep is not None:
        c.check("E-LABEL-LABEL" in codes(rep),
                "label_overlap: E-LABEL-LABEL reported",
                "codes={}".format(sorted(set(codes(rep)))))
        ll = [f for f in rep["findings"] if f["code"] == "E-LABEL-LABEL"]
        pairs = sorted({tuple(sorted(f.get("data", {}).get("wires", [])))
                        for f in ll})
        c.check(pairs == [("w1", "w2")], "label_overlap: pair is w1 x w2",
                "got {}".format(pairs))
        print("        {}".format(ll[0]["message"] if ll else "(none)"))
        print("        score = {}".format(rep["score"]))
    print("")

    # ---- 4. endpoint intrusion (regression guard) -------------------------
    print("[4] endpoint_intrusion.json -> E-BOX-HIT on the wire's own endpoint box")
    rc, out, err = run_audit(py, endpoint_intrusion, ["--json"])
    c.check(rc == 1, "endpoint_intrusion: exit code is 1", "got {}".format(rc))
    rep = None
    try:
        rep = parse_json_report(out)
    except Exception as exc:  # noqa: BLE001
        c.check(False, "endpoint_intrusion: --json output parses", "{}".format(exc))
    if rep is not None:
        hits = [f for f in rep["findings"] if f["code"] == "E-BOX-HIT"]
        boxes = sorted({f.get("data", {}).get("box") for f in hits})
        c.check("A" in boxes,
                "endpoint_intrusion: E-BOX-HIT names endpoint box A",
                "boxes={} codes={}".format(boxes, sorted(set(codes(rep)))))
        print("        {}".format(hits[0]["message"] if hits else "(none)"))
    print("")

    # ---- 5. --help --------------------------------------------------------
    print("[5] --help")
    proc = subprocess.run([py, AUDIT, "--help"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, encoding="utf-8",
                          errors="replace")
    c.check(proc.returncode == 0, "--help exits 0", "got {}".format(proc.returncode))
    c.check("E-BOX-HIT" in (proc.stdout or "") and "SCORE" in (proc.stdout or ""),
            "--help documents the check codes and the SCORE line")
    print("")

    # ---- 6. --quiet -------------------------------------------------------
    print("[6] --quiet -> only ERROR findings + SCORE")
    rc, out, err = run_audit(py, box_hit, ["--quiet"])
    body, score = split_score(out)
    c.check(score is not None, "--quiet: SCORE line present")
    c.check("E-BOX-HIT" in out, "--quiet: error finding still printed")
    c.check("W-CROSS" not in out and "I-STATS" not in out and "summary" not in out,
            "--quiet: warnings/info/summary suppressed")
    rc2, out2, _ = run_audit(py, clean, ["--quiet"])
    c.check(rc2 == 0 and len([ln for ln in out2.splitlines() if ln.strip()]) == 1,
            "--quiet clean: stdout is exactly the SCORE line",
            "stdout={!r}".format(out2))
    print("")

    # ---- 7. --fidelity (repo arch_data.py may be absent or may not match) --
    print("[7] --fidelity on the clean fixture (repo arch_data.py state unknown)")
    rc, out, err = run_audit(py, clean, ["--json", "--fidelity"])
    rep = None
    try:
        rep = parse_json_report(out)
    except Exception as exc:  # noqa: BLE001
        c.check(False, "fidelity: --json output parses", "{}".format(exc))
    if rep is not None:
        fi = rep.get("fidelity", {})
        c.check(rc in (0, 1), "fidelity: no crash (exit 0 or 1)",
                "got {}".format(rc))
        if fi.get("available"):
            c.check(bool(fi.get("link_source")),
                    "fidelity: repo arch_data.py loaded, link source recorded",
                    "fidelity={!r}".format(fi))
            print("        repo arch_data.py used; link source = {}; "
                  "errors = {} (the synthetic fixture need not match the real "
                  "design)".format(fi.get("link_source"), rep["counts"]["errors"]))
        else:
            c.check("fidelity skipped" in (fi.get("message") or "")
                    and "fidelity skipped" in err,
                    "fidelity: skipped with a clear message in report + stderr",
                    "message={!r} stderr={!r}".format(fi.get("message"), err[:200]))
            print("        {}".format(fi.get("message")))
    print("")

    # ---- 8. fidelity logic, deterministically, with synthetic modules -----
    print("[8] --fidelity logic against synthetic arch_data.py modules")
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib
    ad = importlib.import_module("audit_diagram")
    good_mod = (
        'LINKS = [("A", "B", "go"), ("A", "B", "sel"), ("C", "D", "move")]\n'
        'ENTITIES = {"A": {"file": "rtl/a.vhd"}, "B": {"file": "rtl/b.vhd"}, '
        '"C": {"file": "rtl/c.vhd"}}\n'
        'EXTERNAL = {"D": {"title": "D", "sub": "PIN_1"}}\n'
        'GLOBALS = {"A": [], "B": [], "C": [], "D": []}\n'
    )
    bad_mod = (
        'LINKS = [("A", "B", "go")]\n'
        'ENTITIES = {"A": {"file": "rtl/a.vhd"}, "B": {"file": "rtl/b.vhd"}, '
        '"C": {"file": "rtl/c.vhd"}, "X": {"file": "rtl/x.vhd"}}\n'
        'EXTERNAL = {}\n'
        'GLOBALS = {"A": ["clk"], "B": [], "C": [], "D": []}\n'
    )
    wt_mod = (
        'def wire_triples():\n'
        '    return [("A", "B", "go"), ("A", "B", "sel"), ("C", "D", "move")]\n'
        'ENTITIES = {"A": {}, "B": {}, "C": {}}\n'
        'EXTERNAL = {"D": {}}\n'
        'GLOBALS = {"A": [], "B": [], "C": [], "D": []}\n'
    )
    wg_mod = (
        'WIRE_GROUPS = [("A", "B", ["go", "sel"]), ("C", "D", ["move"])]\n'
        'ENTITIES = {"A": {}, "B": {}, "C": {}}\n'
        'EXTERNAL = {"D": {}}\n'
        'GLOBALS = {"A": [], "B": [], "C": [], "D": []}\n'
    )
    mods = {"fidelity_good": (good_mod, "LINKS"),
            "fidelity_fallback_wt": (wt_mod, "wire_triples()"),
            "fidelity_fallback_wg": (wg_mod, "WIRE_GROUPS"),
            "fidelity_bad": (bad_mod, "LINKS")}
    for name, (src, _want) in mods.items():
        d = os.path.join(FIXDIR, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "arch_data.py"), "w", encoding="utf-8") as fh:
            fh.write(src)

    for name in ("fidelity_good", "fidelity_fallback_wt", "fidelity_fallback_wg"):
        want = mods[name][1]
        r = ad.build_report(clean, fidelity=True, script_dir=os.path.join(FIXDIR, name))
        got_codes = sorted({f["code"] for f in r["findings"]})
        c.check(r["fidelity"]["available"] is True
                and r["fidelity"].get("link_source") == want,
                "{}: link source is {}".format(name, want),
                "fidelity={!r}".format(r["fidelity"]))
        c.check(r["counts"]["errors"] == 0,
                "{}: matching layout has 0 errors".format(name),
                "codes={}".format(got_codes))
    r = ad.build_report(clean, fidelity=True,
                        script_dir=os.path.join(FIXDIR, "fidelity_bad"))
    cats = sorted({f.get("data", {}).get("category")
                   for f in r["findings"] if f["code"] == "E-FIDELITY"})
    c.check(cats == ["ENTITIES", "EXTERNAL", "LINKS"],
            "fidelity_bad: E-FIDELITY for LINKS + ENTITIES + EXTERNAL",
            "categories={}".format(cats))
    gmiss = [f for f in r["findings"] if f["code"] == "E-GLOBAL-MISSING"]
    c.check(len(gmiss) == 1
            and gmiss[0].get("data", {}).get("box") == "A"
            and gmiss[0].get("data", {}).get("missing") == ["clk"],
            "fidelity_bad: E-GLOBAL-MISSING for box A (missing clk)",
            "got={}".format([(f.get("data", {}).get("box"),
                              f.get("data", {}).get("missing")) for f in gmiss]))
    c.check(r["counts"]["errors"] == 4,
            "fidelity_bad: 4 ERROR findings (3 x E-FIDELITY + 1 x E-GLOBAL-MISSING)",
            "got {}".format(r["counts"]["errors"]))
    for f in r["findings"]:
        if f["code"] in ("E-FIDELITY", "E-GLOBAL-MISSING"):
            print("        {}".format(f["message"]))
    print("")

    # ---- summary ----------------------------------------------------------
    print("=" * 72)
    print("passed {} / failed {}".format(c.passed, c.failed))
    if c.failures:
        print("failed assertions:")
        for name in c.failures:
            print("  - {}".format(name))
    print("RESULT: {}".format("PASS" if c.failed == 0 else "FAIL"))
    return 1 if c.failed else 0


if __name__ == "__main__":
    sys.exit(main())
