# -*- coding: utf-8 -*-
"""go_done must be driven from ONE process only.  It was assigned both in the
state-register process (lines 133/142) and in the command process.  The command
process already re-arms it whenever the state is not S_PLAYING, so the state
process doesn't need to touch it at all."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")

# drop the two assignments in the state-register process (they end with "go_done <= '0';\n")
s = s.replace("                selfc <= (others => '0');\n                go_done <= '0';\n",
              "                selfc <= (others => '0');\n")
s = s.replace("                selfc <= (others => '0');\n                go_done <= '0';\n",
              "                selfc <= (others => '0');\n")

p.write_text(s, encoding="utf-8")
print("go_done assignments now:", [i + 1 for i, l in enumerate(s.splitlines()) if "go_done <=" in l])
