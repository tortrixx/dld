# -*- coding: utf-8 -*-
"""从 Quartus 的 map 报告中打印各模块的逻辑单元分解。

Quartus 写的层次表每个节点一行；模块行就是那些层级较浅的
行。打印完整路径中 '|' 分隔符不超过 2 个的所有行，
从而看到顶层的直接子节点。
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

rpt = ROOT / "quartus" / "output_files" / "puzzle.map.rpt"
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
