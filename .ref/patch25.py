# -*- coding: utf-8 -*-
"""Fix the renderer's phase counter.

ph was a 3-bit counter (0..7) while the case only used 0..4.  Phases 5,6,7 fell
into the 'others' branch, which PUBLISHES the row again -- so the same row was
published three times per cycle, the row period became 8 ticks instead of 5, and
the resulting frame rate was 200/(8*8) = ~3 Hz.  That is the visible flicker.

Fix: make ph count 0..4 only.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
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
