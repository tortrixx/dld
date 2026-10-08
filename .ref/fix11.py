# -*- coding: utf-8 -*-
"""Lock the confirmed key mapping.

BENCH EVIDENCE (keypad_diag_top, authoritative pins):
  * raw index 1 is the key that starts the game (it produced the pattern).
  * the scanner now reports distinct indexes per key and returns to 0 on release.
  * pressing the three keys of the right-most physical column drove the reported
    row lines to 110 / 101 / 011, i.e. rows 0..2 respond; row 3 did not move.
  * only rows 0..3 as 4 bits are available, so the index is 4*row + column and
    the confirmed START key is index 1.

Because a full 16-key survey was not completed, the map keeps the confirmed keys
explicit and assigns sensible neighbours, with the whole table in ONE place
(game_fsm.key_of) so it can be corrected from a single measurement.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")

old = '''    --      index  0 = (row0,col0)  -> UP
    --      index  1 = (row0,col1)  -> START      (top row, second key)
    --      index  2 = (row0,col2)  -> DOWN
    --      index  4 = (row1,col0)  -> LEFT
    --      index  5 = (row1,col1)  -> RIGHT
    --      index  6 = (row1,col2)  -> SELECT
    --      index 10 = (row2,col2)  -> CONFIRM'''
new = '''    -- CONFIRMED ON THE BENCH: raw index 1 starts the game.
    -- The remaining assignments are the natural neighbours of that key; the
    -- whole table lives here so a single measurement can correct it.
    --
    --      index  1 = (row0,col1)  -> START     CONFIRMED
    --      index  0 = (row0,col0)  -> LEFT
    --      index  2 = (row0,col2)  -> RIGHT
    --      index  3 = (row0,col3)  -> SELECT
    --      index  4 = (row1,col0)  -> UP
    --      index  5 = (row1,col1)  -> DOWN
    --      index  6 = (row1,col2)  -> CONFIRM'''
assert old in s, "map comment not found"
s = s.replace(old, new)

old_case = '''        case idx is
            when "0000" => return K_UP;
            when "0001" => return K_START;
            when "0010" => return K_DOWN;
            when "0100" => return K_LEFT;
            when "0101" => return K_RIGHT;
            when "0110" => return K_SELECT;
            when "1010" => return K_CONFIRM;
            when others => return K_NONE;
        end case;'''
new_case = '''        case idx is
            when "0001" => return K_START;    -- CONFIRMED on the bench
            when "0000" => return K_LEFT;
            when "0010" => return K_RIGHT;
            when "0011" => return K_SELECT;
            when "0100" => return K_UP;
            when "0101" => return K_DOWN;
            when "0110" => return K_CONFIRM;
            when others => return K_NONE;
        end case;'''
assert old_case in s, "key_of case not found"
s = s.replace(old_case, new_case)

p.write_text(s, encoding="utf-8")
print("key map locked")
