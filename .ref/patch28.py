# -*- coding: utf-8 -*-
"""Remove the obsolete duplicate renderer process (the one that uses acc_cov /
acc_kc / ph), which patch26 left behind next to the new frame renderer."""
import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
lines = p.read_text(encoding="utf-8").splitlines()

# find every "process (i_clk)" block and keep those that do NOT mention acc_cov
blocks = []      # (start_idx, end_idx) inclusive
i = 0
while i < len(lines):
    if re.match(r"\s*process\s*\(", lines[i]):
        depth = 0
        j = i
        started = False
        while j < len(lines):
            depth += len(re.findall(r"\bbegin\b", lines[j]))
            depth -= len(re.findall(r"\bend\s+process\b", lines[j]))
            if re.search(r"\bbegin\b", lines[j]):
                started = True
            if started and depth == 0 and re.search(r"\bend\s+process\b", lines[j]):
                break
            j += 1
        blocks.append((i, j))
        i = j + 1
    else:
        i += 1

drop = []
for (a, b) in blocks:
    body = "\n".join(lines[a:b + 1])
    if "acc_cov" in body:
        drop.append((a, b))
print("processes found:", len(blocks), " -> dropping:", len(drop))

for (a, b) in sorted(drop, reverse=True):
    del lines[a:b + 1]

p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("acc_cov occurrences now:", sum(l.count("acc_cov") for l in lines))
print("ph occurrences now:", sum(1 for l in lines if re.search(r"\bph\b", l)))
