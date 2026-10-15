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
    """读 sta.rpt -> {setup_slack, hold_slack, fmax_mhz, restricted_fmax_mhz}。

    * `setup_slack` / `hold_slack`：取 `Setup: 'clk'` / `Hold: 'clk'` 表的第一行（= 最差路径）。
    * `fmax_mhz`：取 `Fmax Summary` 表的 `Fmax` 列（第 1 行 = `clk`）。

    ⭐ 2026-10-15 第 27 工作阶段补 `fmax_mhz` 的原因：文档站需要一个**可机读的实测 Fmax**。
    在此之前它只能靠人在文档里抄字面量，或者用 `1/(period − slack)` **反推** ——
    而反推值（54.28）与 TimeQuest 报的 `Fmax Summary`（**54.27**）并不相等
    （STA 自己还会算时钟不确定度/抖动）。两个数字同时出现在文档里就是新的漂移源。
    ⇒ 实测值就该从实测报告里读，并且**入库**（`quartus/output_files/` 是 .gitignore 的）。
    """
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
    # Fmax Summary 表：`; 54.27 MHz ; 54.27 MHz       ; clk        ;      ;`
    idx = t.find("Fmax Summary")
    if idx >= 0:
        for ln in t[idx:].splitlines():
            m = re.match(r"^;\s*([\d.]+)\s*MHz\s*;\s*([\d.]+)\s*MHz\s*;\s*(\S+)\s*;", ln)
            if m:
                out["fmax_mhz"] = float(m.group(1))
                out["restricted_fmax_mhz"] = float(m.group(2))
                out["fmax_clock"] = m.group(3)
                break
    return out


# ---------------------------------------------------------------- 指纹
def rtl_sources():
    """全部 rtl/*.vhd 的 git blob 短哈希（与轮次记录的 `sources` 同一口径）。"""
    return {"rtl/" + f.name: sim._file_blob_hash(f)[:12]
            for f in sorted((ROOT / "rtl").glob("*.vhd"))}


def rtl_logic():
    """同一批 RTL 的**逻辑**指纹（去注释/docstring/行尾）。

    ⭐ 为什么两个都记（2026-10-10 第 20 工作阶段）：
       `sources` 是"原始字节"，所以**只改注释**或**只换 CRLF/LF** 都会让
       "固件落后于 RTL"误报 —— 而这两种改动都不可能改变综合结果
       （本项目实测：只改注释后 `puzzle.pof` 的 sha256 逐字节相同）。
       审计先比 `sources`，不中再比 `sources_logic`，并如实报出"差异只在注释/行尾"。
    """
    return {"rtl/" + f.name: sim.srcnorm.logic_file_hash(f)
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
        "sources_logic": rtl_logic(),
        "pof": pof_identity(),
        "fit": read_fit(),
        "sta": read_sta(),
    }


def main():
    rec = build_record()
    # ⚠️⚠️ 2026-10-11 对抗式审查发现：原来这里读不到产物只**打印一句警告**，
    #    却仍然无条件覆盖 `quartus/build_provenance.json` —— 而那是**入库**的、
    #    唯一记录 `pof.sha256` / LE / LAB / setup·hold slack 的地方
    #    （`quartus/output_files/` 本身是 .gitignore 的）。
    #    也就是说：在**没编译过**的干净 clone 上跑一次本脚本，就会把这份证据**清空**，
    #    而且返回 0（成功）—— 与 `gen_sim_doc.py` 把 docs/03 截断是同一类事故。
    #    ⇒ 缺任一关键产物就**拒绝写盘**并返回 1；确实要写空记录请显式 `--force`。
    _missing = [k for k in ("fit", "pof") if not rec[k]]
    if _missing and "--force" not in sys.argv:
        print("  ✗ 拒绝覆盖 %s：读不到 %s。"
              % (PROVENANCE.relative_to(ROOT), "、".join(_missing)))
        print("    先在仓库根跑一次完整编译（scripts/build.tcl），再记录。")
        print("    确实要写入不完整记录请显式加 `--force`。")
        return 1
    if _missing:
        print("  ⚠️ 读不到 %s（--force 已指定，仍写入）" % "、".join(_missing))
    # LF 落盘（理由见 `scripts/sim.py` 里同一处注释：write_text 在 Windows 上写 CRLF）
    with open(PROVENANCE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, indent=2) + "\n")
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
