# -*- coding: utf-8 -*-
"""修正实体端口解析器：必须先剥掉 -- 注释。

`entity\s+\w+\s+is\s+port` 会匹配到注释内部（"-- PIN_61, BTN0 reset"），
于是端口子句从错误的位置被截取，只找到一个端口。
一道悄悄少报端口的防线比没有防线更糟，因为它
会在看起来已经检查过的同时放过未约束的引脚。
"""
import pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "scripts" / "gen_project.py"
s = p.read_text(encoding="utf-8")

old_start = s.index("def parse_entity_ports(top: str):")
old_end = s.index("if __name__ ==", old_start)
new = '''def parse_entity_ports(top: str):
    """Return the port names declared by the entity of rtl/<top>.vhd.

    Comments are stripped FIRST.  Without that, the pattern
    "entity <name> is port (" matches inside a comment such as
    "-- PIN_61, BTN0 reset" and the clause is read from the wrong place, which
    makes the guard report fewer ports than the entity really has -- a guard that
    silently under-reports is worse than no guard at all.
    """
    src = ROOT / "rtl" / (top + ".vhd")
    if not src.exists():
        raise SystemExit("top-level source not found: %s" % src)

    raw = src.read_text(encoding="utf-8", errors="replace")
    # strip line comments (no block comments are used in this project's RTL)
    text = "\\n".join(line.split("--")[0] for line in raw.splitlines())

    m = re.search(r"entity\\s+\\w+\\s+is\\s+port\\s*\\(", text, re.I)
    if not m:
        raise SystemExit("could not locate an entity port clause in %s" % src)

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
    for part in clause.split(";"):
        mm = re.match(r"\\s*([A-Za-z_]\\w*)\\s*:", part)
        if mm:
            ports.append(mm.group(1).lower())
    if not ports:
        raise SystemExit("no ports parsed from %s -- the guard cannot be trusted" % src)
    return ports


'''
s = s[:old_start] + new + s[old_end:]
p.write_text(s, encoding="utf-8")
print("parser fixed")
