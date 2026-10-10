# -*- coding: utf-8 -*-
"""修正渲染器的相位计数器。

ph 是一个 3 位计数器（0..7），而 case 只用到 0..4。相位 5、6、7 落进
'others' 分支，而该分支会**再次发布**这一行 —— 于是同一行每周期
被发布三次，行周期从 5 个 tick 变成 8 个 tick，
由此得到的帧率是 200/(8*8) = 约 3 Hz。这就是肉眼可见的闪烁。

修法：让 ph 只数 0..4。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

s = s.replace("                ph <= ph + 1;",
              "                -- modulo-5 phase counter: 0..3 = one piece each, 4 = publish\n"
              "                if (ph = 4) then\n"
              "                    ph <= (others => '0');\n"
              "                else\n"
              "                    ph <= ph + 1;\n"
              "                end if;")

p.write_text(s, encoding="utf-8")
print("phase counter fixed; occurrences:", s.count("if (ph = 4) then"))
