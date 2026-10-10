# -*- coding: utf-8 -*-
"""删掉过时的重复渲染进程（即使用 acc_cov /
acc_kc / ph 的那个），它是 patch26 留在新帧渲染器旁边的残留。"""
import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
lines = p.read_text(encoding="utf-8").splitlines()

# 找出每一个 "process (i_clk)" 块，保留其中**不**提及 acc_cov 的
blocks = []      # (起始下标, 结束下标)，闭区间
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
