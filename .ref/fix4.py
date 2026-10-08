# -*- coding: utf-8 -*-
"""FIX 4 -- engine colour: the selected piece could never be GREEN.

CONFIRMED DEFECT: the renderer computed
    redrow := cov or (tgtrow and (not cov))
where 'cov' is EVERY piece cell, while the green channel was built only from
cells already inside 'cov'.  Green was therefore always a subset of red, so a
pure green dot could not exist: the selected piece rendered RED+GREEN = YELLOW,
exactly like a locked piece.  Requirement B6 ("the selected piece turns green")
was not met, and B6/B8 were visually indistinguishable.

FIX: build a separate 'sel' row for the selected piece and exclude it from red.
    green = selected OR locked
    red   = (all piece cells AND NOT selected) OR target-ghost
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# --- accumulate a dedicated selected-mask row -------------------------------
for k, (issel) in enumerate(['(sel = "00")', '(sel = "01")',
                             '(sel = "10")', '(sel = "11")']):
    old = "                    if (locked(%d) = '1') or %s then kc := kc or rw; end if;" % (k, issel)
    new = ("                    if (locked(%d) = '1') then kc := kc or rw; end if;\n"
           "                    if %s then selrow := selrow or rw; end if;" % (k, issel))
    assert old in s, "slot %d not found" % k
    s = s.replace(old, new)

# declare the variable
s = s.replace("        variable redrow : std_logic_vector(7 downto 0);",
              "        variable redrow : std_logic_vector(7 downto 0);\n"
              "        variable selrow : std_logic_vector(7 downto 0);")

# initialise it next to cov/kc
s = s.replace("                cov := (others => '0');\n                kc  := (others => '0');",
              "                cov    := (others => '0');\n"
              "                kc     := (others => '0');\n"
              "                selrow := (others => '0');")

# --- colour mixing ----------------------------------------------------------
s = s.replace("""                -- colour of this row: green = selected or locked cells, red = any
                -- piece cell plus the part of the target no piece covers
                redrow := cov or (tgtrow and (not cov));
                grnrow := kc;""",
              """                -- Colour of this row.
                --   green = selected piece OR locked piece
                --   red   = every OTHER piece cell, plus the part of the target
                --           that no piece covers (the ghost)
                -- Excluding exactly the selected cells from red is what makes the
                -- selected piece pure GREEN; without it green was a subset of red
                -- and the piece showed up as yellow, the same as a locked one.
                redrow := (cov and (not selrow)) or (tgtrow and (not cov));
                grnrow := kc or selrow;""")

p.write_text(s, encoding="utf-8")
print("engine colour fixed")
