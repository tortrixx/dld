# -*- coding: utf-8 -*-
"""FIX 2 -- make the key-pad index and the game key codes one coherent scheme.

DEFECT (confirmed): keypad_scan built its code as 4*column + row (column-major)
while the K_* constants in puzzle_pkg are laid out row-major-shaped and put
K_START at "0001".  No key in the documented layout could ever produce K_START,
so the game could not react even with a working scanner.

FIX
  * keypad_scan reports the plain KEY INDEX  4*row + column   (row-major, the
    natural "key number" on the 4x4 keypad);
  * game_fsm decodes that index into the game key with ONE explicit table
    (key_of), so the physical layout is described in exactly one place and can be
    corrected from a single measurement.
"""
import pathlib

# ---------------------------------------------------------------- keypad_scan
p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

s = s.replace("""                for r in 0 to 3 loop
                    if (i_row(r) = KP_ACTIVE) then
                        raw_hit  <= '1';
                        raw_code <= std_logic_vector(
                                        to_unsigned(4 * to_integer(phase) + r, 4));
                    end if;
                end loop;""",
              """                -- Report the plain KEY INDEX 4*row + column, NOT a
                -- column-major code.  Row-major is the natural numbering of a
                -- 4x4 keypad (reading order) and it makes the value directly
                -- usable as "which key is this" by the decoder in game_fsm.
                for r in 0 to 3 loop
                    if (i_row(r) = KP_ACTIVE) then
                        raw_hit  <= '1';
                        raw_code <= std_logic_vector(
                                        to_unsigned(4 * r + to_integer(phase), 4));
                    end if;
                end loop;""")

s = s.replace("    -- KEY LAYOUT used by this project (ROW3 is the TOP row):",
              "    -- KEY LAYOUT note: the scan reports the raw key index 4*row + column.\n"
              "    -- Interpreting that index as a game key is game_fsm's job (see key_of).\n"
              "    -- For reference the board's 4x4 keypad reads (top row first):\n"
              "    --    7 8 9 [mode] / 4 5 6 - / 1 2 3 [mode] / - 0 [clear] [ok]\n"
              "    -- Original project layout annotation (ROW3 is the TOP row):")
p.write_text(s, encoding="utf-8")
print("keypad_scan: row-major index")

# ---------------------------------------------------------------- game_fsm
q = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
t = q.read_text(encoding="utf-8")

# add the decode function to the architecture declarative part
anchor = "    signal st      : state_t := S_SELF_TEST;"
assert anchor in t
keyof = '''    ----------------------------------------------------------------------------
    -- KEY MAP -- the ONE place where a physical keypad position becomes a game
    -- key.  The scanner reports the plain key index 4*row + column (row 0 = the
    -- TOP physical row, column 0 = the LEFT-most column).
    --
    -- This project needs seven control keys out of the sixteen available.  They
    -- are chosen to sit on the keypad's own top three rows so they are easy to
    -- find by hand:
    --
    --      index  0 = (row0,col0)  -> UP
    --      index  1 = (row0,col1)  -> START      (top row, second key)
    --      index  2 = (row0,col2)  -> DOWN
    --      index  4 = (row1,col0)  -> LEFT
    --      index  5 = (row1,col1)  -> RIGHT
    --      index  6 = (row1,col2)  -> SELECT
    --      index 10 = (row2,col2)  -> CONFIRM
    --
    -- Everything else returns K_NONE.  If a bench measurement shows a different
    -- physical position for a key, change ONLY this function.
    ----------------------------------------------------------------------------
    function key_of(idx : std_logic_vector(3 downto 0))
        return std_logic_vector is
    begin
        case idx is
            when "0000" => return K_UP;
            when "0001" => return K_START;
            when "0010" => return K_DOWN;
            when "0100" => return K_LEFT;
            when "0101" => return K_RIGHT;
            when "0110" => return K_SELECT;
            when "1010" => return K_CONFIRM;
            when others => return K_NONE;
        end case;
    end function;

'''
t = t.replace(anchor, keyof + anchor)

# add a decoded key signal and use it everywhere i_key was compared
t = t.replace("    signal blink_r : std_logic := '0';",
              "    signal blink_r : std_logic := '0';\n"
              "    signal kdec    : std_logic_vector(3 downto 0) := K_NONE;  -- decoded game key")
t = t.replace("    o_state    <= st;",
              "    -- the scanner's raw key index is decoded into a game key in one place\n"
              "    kdec <= key_of(i_key);\n\n"
              "    o_state    <= st;")
# replace comparisons with the decoded signal
t = t.replace("(i_key = K_START)", "(kdec = K_START)")
t = t.replace("case i_key is", "case kdec is")
q.write_text(t, encoding="utf-8")
print("game_fsm: single explicit key map added")
