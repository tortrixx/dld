# -*- coding: utf-8 -*-
"""Print the per-module logic-cell breakdown from a Quartus map report.

Quartus writes the hierarchy table with one row per node; the module rows are the
shallow ones.  Print every row whose full path has at most 2 '|' separators so we
see the direct children of the top level.
"""
import pathlib, re, sys

rpt = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\quartus\output_files\puzzle.map.rpt")
lines = rpt.read_text(errors="replace").splitlines()

start = None
for i, l in enumerate(lines):
    if "Compilation Hierarchy Node" in l:
        start = i
        break
if start is None:
    sys.exit("hierarchy table not found")

rows = []
for l in lines[start + 2:start + 4000]:
    if not l.startswith(";"):
        if rows:
            break
        continue
    parts = [p.strip() for p in l.split(";")]
    if len(parts) < 4:
        continue
    node = parts[1]
    lc = parts[2]
    full = parts[-3] if len(parts) >= 3 else ""
    m = re.search(r"([\d,]+)", lc)
    if not m:
        continue
    depth = full.count("|")
    if depth <= 2 and re.match(r"^[\s\|]*\S", full):
        rows.append((depth, node, m.group(1), full))

print(f"{'node':<40} {'logic cells':>12}  depth")
rows.sort(key=lambda r: -int(r[2].replace(",", "")))
for d, node, lc, full in rows[:25]:
    print(f"{node:<40} {lc:>12}  {d}")

tot = 0
for d, node, lc, full in rows:
    if d == 1:
        tot += int(lc.replace(",", ""))
print(f"\nsum of top-level children: {tot}")
