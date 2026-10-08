# -*- coding: utf-8 -*-
"""Register the keypad diagnostics WITH the keypad ports, and make the generator
reject a top whose declared port list omits a port the entity actually has.

Root cause of the "keypad never responds" saga:
  keypad_raw_top and keypad_diag_top were added to TOP_PORTS with the clock,
  switch, matrix and display ports but WITHOUT kp_row / kp_col.  The generator
  only constrains ports that are listed, so the keypad pins were left
  unconstrained; Quartus then placed them on arbitrary free pins.  The design
  compiled and ran and simply drove/read the wrong pins.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\scripts\gen_project.py")
s = p.read_text(encoding="utf-8")

s = s.replace('''    "keypad_diag_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                        "seg", "cat"],''',
              '''    "keypad_diag_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                        "dot_row", "dot_colr", "dot_colg", "seg", "cat"],''')
s = s.replace('''    "keypad_raw_top": ["clk", "sw7", "btn", "dot_row", "dot_colr", "dot_colg",
                       "seg", "cat"],''',
              '''    # NOTE: kp_row / kp_col MUST be listed.  Omitting them is not caught by the
    # "port has no pin" guard below (that guard only sees the ports you DID list),
    # so the keypad pins silently end up unconstrained and the fitter scatters
    # them over arbitrary free pins -- which looks exactly like broken hardware.
    "keypad_raw_top": ["clk", "sw7", "btn", "kp_row", "kp_col",
                       "dot_row", "dot_colr", "dot_colg", "seg", "cat"],''')

p.write_text(s, encoding="utf-8")
print("keypad tops now list kp_row/kp_col")
