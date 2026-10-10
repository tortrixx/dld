# -*- coding: utf-8 -*-
"""加一道**硬**防线：所选顶层的每一个端口都必须有引脚。

原有的防线只检查 TOP_PORTS 里**列出**的端口，所以从该列表里漏掉一个端口
会悄无声息地产出一个引脚未约束的设计：Quartus 随后
把它们放到任意空闲引脚上，外设就是永远不工作。正是
这个错误让键盘那一段耗掉了一整轮漫长的调试（docs/05 ERR-002）。

这道防线会解析顶层 VHDL 文件的实体声明，并要求
它的每一个端口都出现在引脚表中。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "scripts" / "gen_project.py"
s = p.read_text(encoding="utf-8")

old = '''    # guard: every declared port must have a pin, otherwise Quartus silently
    # drops the unconstrained signal onto an arbitrary free pin
    missing = [p for p in TOP_PORTS[top] if p not in PINS]
    if missing:
        raise SystemExit("no pin defined for port(s): %s" % missing)'''

new = '''    # ---- guard 1: every listed port must have a pin ------------------------
    missing = [p for p in TOP_PORTS[top] if p not in PINS]
    if missing:
        raise SystemExit("no pin defined for port(s): %s" % missing)

    # ---- guard 2: every port of the ENTITY must be listed -------------------
    # Guard 1 cannot see a port that was simply left out of TOP_PORTS, and that
    # omission is exactly what leaves pins unconstrained (the fitter then scatters
    # them over free pins and the peripheral silently never works).
    entity_ports = parse_entity_ports(top)
    unlisted = [q for q in entity_ports if q not in TOP_PORTS[top]]
    if unlisted:
        raise SystemExit(
            "top %s has port(s) %s that are NOT in TOP_PORTS[%s] -- they would "
            "be left unconstrained and placed on arbitrary pins."
            % (top, unlisted, top)
        )'''

assert old in s
s = s.replace(old, new)

# 在 __main__ 块之前加入解析辅助函数
helper = '''
def parse_entity_ports(top: str):
    """Return the port names declared by the entity of rtl/<top>.vhd.

    Deliberately a simple regex over the entity's port clause: it is a build-time
    guard, not a VHDL parser, and it only needs to be conservative (better to
    complain than to let an unconstrained pin through).
    """
    src = ROOT / "rtl" / (top + ".vhd")
    if not src.exists():
        raise SystemExit("top-level source not found: %s" % src)
    text = src.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"entity\\s+\\w+\\s+is\\s+port\\s*\\(", text, re.I)
    if not m:
        return []
    # walk to the matching close paren of the port clause
    depth = 1
    i = m.end()
    while i < len(text) and depth > 0:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    clause = text[m.end():i - 1]
    ports = []
    for line in clause.split(";"):
        mm = re.match(r"\\s*([A-Za-z_]\\w*)\\s*:", line)
        if mm:
            ports.append(mm.group(1).lower())
    return ports

'''
s = s.replace("if __name__ == \"__main__\":", helper + "if __name__ == \"__main__\":")
# 确保已导入 're'
if "\nimport re" not in s:
    s = s.replace("import sys, pathlib", "import re, sys, pathlib")

p.write_text(s, encoding="utf-8")
print("guards installed")
