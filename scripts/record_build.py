#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""record_build.py —— 记录"这份固件是用哪一版 RTL 编出来的"（**编译后**跑一次）

【补的是哪个洞】
    `quartus/output_files/` 是 `.gitignore` 的构建产物，所以仓库里**没有任何东西**
    能把"板上烧的那份 `.pof`"和"仓库里的 RTL"机检地连起来。过去的做法是**人肉**比对
    mtime + 在文档里抄一遍读数（`docs/05`、`README.md` §2）——
    而"抄一遍的数字会自己长腿"正是收尾审查的第 25 条教训。

    更糟的是 **mtime 不可靠**：本次会话就踩到一次 —— 把 7 个物理 CRLF 的 `rtl/*.vhd`
    重新 checkout 成 LF 之后，**内容一字未变、blob 哈希完全相同**，但 mtime 全变成了
    "现在"，于是"固件落后于 RTL"的检查**误报**了。⇒ 判据必须是**内容哈希**。

【产出】`quartus/build_provenance.json`（**入库**，与 `sim/rounds/*.json` 同一性质）：
    {
      "timestamp":    编译记录写入时间,
      "git_head":     当时的 HEAD（可复现标识，不用抄字面量）,
      "git_dirty":    当时工作树是否脏,
      "sources":      {rtl/*.vhd -> git blob 哈希（12 位）},
      "pof":          {mtime, sha256, bytes}  ← **固件身份**（.pof 本身不入库，哈希入库）,
      "fit":          {status, le, lab, pins},
      "sta":          {setup_slack, hold_slack}
    }

【用法】
    # 编译成功后（见 README §4 的命令序列）
    python scripts/record_build.py
    python scripts/audit_evidence.py       # E 段据此判定"固件是否覆盖当前 RTL"
"""
import hashlib
import json
import pathlib
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import sim  # noqa: E402

ROOT = sim.ROOT
QUARTUS = ROOT / "quartus"
OUT = QUARTUS / "output_files"
PROVENANCE = QUARTUS / "build_provenance.json"


# ---------------------------------------------------------------- 报告解析
def _fit_field(text, label):
    m = re.search(r"^;\s*%s\s*;\s*([^;]+?)\s*;" % re.escape(label), text, re.M)
    return m.group(1).strip() if m else None


def read_fit(qdir=OUT):
    """读 fit.rpt -> {status, le, lab, pins}（读不到就给 None，不抛异常）。"""
    p = pathlib.Path(qdir) / "puzzle.fit.rpt"
    if not p.exists():
        return {}
    t = p.read_text(encoding="utf-8", errors="replace")
    return {"status": _fit_field(t, "Fitter Status"),
            "le": _fit_field(t, "Total logic elements"),
            "lab": _fit_field(t, "Total LABs"),
            "pins": _fit_field(t, "Total pins")}


def read_sta(qdir=OUT):
    """读 sta.rpt -> {setup_slack, hold_slack}（取 `Setup: 'clk'` 表的第一行 = 最差）。"""
    p = pathlib.Path(qdir) / "puzzle.sta.rpt"
    if not p.exists():
        return {}
    t = p.read_text(encoding="utf-8", errors="replace")
    out = {}
    for kind, key in (("Setup", "setup_slack"), ("Hold", "hold_slack")):
        idx = [m.start() for m in re.finditer(r"^;\s*%s: 'clk'" % kind, t, re.M)]
        if not idx:
            continue
        for ln in t[idx[-1]:].splitlines()[1:]:
            m = re.match(r"^;\s*(-?[\d.]+)\s*;", ln)
            if m:
                out[key] = float(m.group(1))
                break
    return out


# ---------------------------------------------------------------- 指纹
def rtl_sources():
    """全部 rtl/*.vhd 的 git blob 短哈希（与轮次记录的 `sources` 同一口径）。"""
    return {"rtl/" + f.name: sim._file_blob_hash(f)[:12]
            for f in sorted((ROOT / "rtl").glob("*.vhd"))}


def pof_identity():
    p = OUT / "puzzle.pof"
    if not p.exists():
        return None
    raw = p.read_bytes()
    return {"mtime": time.strftime("%Y-%m-%d %H:%M:%S",
                                  time.localtime(p.stat().st_mtime)),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw)}


def build_record():
    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_head": sim._git("rev-parse", "HEAD"),
        "git_dirty": bool(sim._git("status", "--porcelain")),
        "sources": rtl_sources(),
        "pof": pof_identity(),
        "fit": read_fit(),
        "sta": read_sta(),
    }


def main():
    rec = build_record()
    if not rec["fit"]:
        print("  ⚠️ 读不到 quartus/output_files/puzzle.fit.rpt —— 先编译再记录")
    if not rec["pof"]:
        print("  ⚠️ 读不到 quartus/output_files/puzzle.pof —— 还没有生成固件")
    PROVENANCE.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    print("  ✓ 已写 %s" % PROVENANCE.relative_to(ROOT))
    print("     git HEAD %s（%s）" % ((rec["git_head"] or "-")[:12],
                                    "工作树脏" if rec["git_dirty"] else "工作树干净"))
    if rec["pof"]:
        print("     固件 %s，%d 字节，sha256 %s…"
              % (rec["pof"]["mtime"], rec["pof"]["bytes"], rec["pof"]["sha256"][:16]))
    if rec["fit"]:
        print("     面积 LE %s / LAB %s / 引脚 %s（%s）"
              % (rec["fit"].get("le"), rec["fit"].get("lab"),
                 rec["fit"].get("pins"), rec["fit"].get("status")))
    if rec["sta"]:
        print("     时序 setup %s ns / hold %s ns"
              % (rec["sta"].get("setup_slack"), rec["sta"].get("hold_slack")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
