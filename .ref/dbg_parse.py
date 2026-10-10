# -*- coding: utf-8 -*-
"""检查 parse_entity_ports 实际看到的内容。"""
import pathlib, re, sys

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
text = (ROOT / "rtl" / "puzzle_top.vhd").read_text(encoding="utf-8")

m = re.search(r"entity\s+\w+\s+is\s+port\s*\(", text, re.I)
print("match at", m.start() if m else None)
i = m.end()
depth = 1
while i < len(text) and depth > 0:
    if text[i] == "(":
        depth += 1
    elif text[i] == ")":
        depth -= 1
    i += 1
clause = text[m.end():i - 1]
print("clause length", len(clause))
print("---- first 400 chars ----")
print(clause[:400])
print("---- port names found ----")
names = []
for part in clause.split(";"):
    mm = re.match(r"\s*([A-Za-z_]\w*)\s*:", part)
    if mm:
        names.append(mm.group(1))
print(names)
