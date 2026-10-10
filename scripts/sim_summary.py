# -*- coding: utf-8 -*-
"""汇总所有模块的仿真轮次结果（读 sim/rounds/<模块>/rNN.json 的最新一轮）。

⚠️ 2026-10-10：ROOT 原来是**写死的绝对路径**（作者本机的克隆位置），
   换机器/换目录就跑不了 —— 改成按本文件位置推导（`__file__` 的上一级）。
   另：只想看"证据链有没有破"请用 `python scripts/audit_evidence.py`
   （它会**按 git blob 指纹**逐文件判定绿证是否覆盖当前源码，比这里只看"最新一轮"严格得多）。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(__file__).resolve().parent.parent
R = ROOT / "sim" / "rounds"
rows = []
for d in sorted(R.iterdir()):
    if not d.is_dir():
        continue
    js = sorted(d.glob("r*.json"), key=lambda p: int(p.stem[1:]))
    if not js:
        rows.append((d.name, "-", "-", "-", "无记录", ""))
        continue
    last = json.loads(js[-1].read_text(encoding="utf-8"))
    detail = ""
    if not last["all_pass"]:
        detail = "；".join(a["name"][:28] for a in last["assertions"] if not a["ok"])
    # 有没有源码指纹（第 17 工作阶段起才有；老记录没有）
    fp = "有指纹" if last.get("sources") else "⚠️无指纹"
    rows.append((d.name, "r%02d" % last["round"], "%d/%d" % (last["passed"], last["total"]),
                 "%.4g ns" % (last["duration_ns"] or 0),
                 "PASS" if last["all_pass"] else "FAIL " + detail,
                 "%s %s" % (last["timestamp"], fp)))

print("%-18s %-4s %-7s %-14s %-34s %s" % ("模块", "轮", "通过", "激励时长", "结论", "时间/指纹"))
print("-" * 118)
npass = ntot = 0
for r in rows:
    print("%-18s %-4s %-7s %-14s %-34s %s" % r)
    if r[2] != "-":
        a, b = r[2].split("/")
        npass += int(a); ntot += int(b)
print("-" * 118)
print("合计：%d / %d 条断言通过；模块数 %d" % (npass, ntot, len(rows)))
print("提示：更严格的『证据链审查』请跑 `python scripts/audit_evidence.py`")
