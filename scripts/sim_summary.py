# -*- coding: utf-8 -*-
"""汇总所有模块的仿真轮次结果（读 sim/rounds/<模块>/rNN.json 的最新一轮）。"""
import json, pathlib

ROOT = pathlib.Path(r"C:\Users\sznnn\Desktop\dld")
R = ROOT / "sim" / "rounds"
rows = []
for d in sorted(R.iterdir()):
    if not d.is_dir():
        continue
    js = sorted(d.glob("r*.json"))
    if not js:
        rows.append((d.name, "-", "-", "-", "无记录"))
        continue
    last = json.loads(js[-1].read_text(encoding="utf-8"))
    detail = ""
    if not last["all_pass"]:
        detail = "；".join(a["name"][:28] for a in last["assertions"] if not a["ok"])
    rows.append((d.name, "r%02d" % last["round"], "%d/%d" % (last["passed"], last["total"]),
                 "%.4g ns" % (last["duration_ns"] or 0),
                 "PASS" if last["all_pass"] else "FAIL " + detail))

print("%-18s %-4s %-7s %-14s %s" % ("模块", "轮", "通过", "激励时长", "结论"))
print("-" * 96)
ntot = npass = 0
for r in rows:
    print("%-18s %-4s %-7s %-14s %s" % r)
    if r[2] != "-":
        a, b = r[2].split("/")
        npass += int(a); ntot += int(b)
print("-" * 96)
print("合计：%d / %d 条断言通过；模块数 %d" % (npass, ntot, len(rows)))
