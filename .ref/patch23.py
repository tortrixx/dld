# -*- coding: utf-8 -*-
"""Add a dedicated keypad diagnostic to board_test_top (test 9).

The integrated game showed "start does nothing", so the keypad path has to be
isolated before any game logic is suspected.  This test shows, for the key that
is being pressed:
  * the four RAW row line levels on the matrix row 7 (one dot per row line),
    which reveals the idle/pressed polarity directly, and
  * a dot at the key's own position in the 4x4 grid,
  * the decoded key code on DISP1:DISP0.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\board_test_top.vhd")
s = p.read_text(encoding="utf-8")

# extend the test index to cover test 9
s = s.replace("signal test_idx : unsigned(3 downto 0) := (others => '0');",
              "signal test_idx : unsigned(3 downto 0) := (others => '0');")

# ---- pattern generator: add test 9 ------------------------------------------
old = """            -- Test 7 : 7-segment SEGMENT identification."""
new = """            -- Test 9 : KEYPAD identification.
            --   matrix row 7 shows the four RAW row-line levels (colour = level):
            --       red   = that row line reads '0'
            --       green = that row line reads '1'
            --   the remaining rows show the decoded key position.
            when 9 =>
                -- raw row lines on the bottom row, so the idle polarity is visible
                for c in 0 to 3 loop
                    if (kp_row(c) = '0') then
                        v_red(8 * 7 + c) := '1';
                    else
                        v_grn(8 * 7 + c) := '1';
                    end if;
                end loop;

                -- decoded key drawn at its own grid position
                if (key /= K_NONE) then
                    v_red(8 * kp_row_idx + kp_col_idx) := '1';
                    v_grn(8 * kp_row_idx + kp_col_idx) := '1';
                end if;

            -- Test 7 : 7-segment SEGMENT identification."""
assert old in s
s = s.replace(old, new, 1)

# ---- decode the key code into a 4x4 grid position ---------------------------
s = s.replace("    signal seg_raw_en : std_logic;",
              "    -- decoded key position inside the 4x4 keypad grid (test 9)\n"
              "    signal kp_row_idx : integer range 0 to 3 := 0;\n"
              "    signal kp_col_idx : integer range 0 to 3 := 0;\n"
              "    signal seg_raw_en : std_logic;")

s = s.replace("begin\n\n    ----------------------------------------------------------------------------\n    -- Reset generated from BTN0 only.",
              "begin\n\n"
              "    ----------------------------------------------------------------------------\n"
              "    -- Key code -> keypad grid position, for the diagnostic display.\n"
              "    -- The code layout is deliberately spread over the grid so that a wrong\n"
              "    -- row/column order shows up as a visibly wrong POSITION rather than as\n"
              "    -- a merely wrong number.\n"
              "    ----------------------------------------------------------------------------\n"
              "    process (key)\n"
              "    begin\n"
              "        case key is\n"
              "            when K_UP      => kp_row_idx <= 0; kp_col_idx <= 0;\n"
              "            when K_START   => kp_row_idx <= 0; kp_col_idx <= 3;\n"
              "            when K_LEFT    => kp_row_idx <= 1; kp_col_idx <= 0;\n"
              "            when K_DOWN    => kp_row_idx <= 1; kp_col_idx <= 1;\n"
              "            when K_RIGHT   => kp_row_idx <= 1; kp_col_idx <= 2;\n"
              "            when K_SELECT  => kp_row_idx <= 1; kp_col_idx <= 3;\n"
              "            when K_CONFIRM => kp_row_idx <= 2; kp_col_idx <= 3;\n"
              "            when others    => kp_row_idx <= 2; kp_col_idx <= 0;\n"
              "        end case;\n"
              "    end process;\n\n"
              "    ----------------------------------------------------------------------------\n"
              "    -- Reset generated from BTN0 only.")

# ---- seven-segment: show the key code on DISP1:DISP0 during test 9 ----------
old_disp = """    process (test_idx)
        variable v_nib  : std_logic_vector(3 downto 0);
        variable v_disp : std_logic_vector(31 downto 0);
    begin
        v_nib := '0' & std_logic_vector(test_idx(2 downto 0));
        v_disp := (others => '0');
        for d in 0 to 7 loop
            v_disp(4 * d + 3 downto 4 * d) := v_nib;
        end loop;
        disp <= v_disp;
    end process;"""
new_disp = """    process (test_idx, key)
        variable v_nib  : std_logic_vector(3 downto 0);
        variable v_disp : std_logic_vector(31 downto 0);
    begin
        v_nib := '0' & std_logic_vector(test_idx(2 downto 0));
        v_disp := (others => '0');
        for d in 0 to 7 loop
            v_disp(4 * d + 3 downto 4 * d) := v_nib;
        end loop;

        if (test_idx = 9) then
            -- DISP1:DISP0 = decoded key code (0..7), all other digits blanked
            v_disp := (others => '0');
            v_disp(3 downto 0) := key;
        end if;
        disp <= v_disp;
    end process;"""
assert old_disp in s
s = s.replace(old_disp, new_disp)

p.write_text(s, encoding="utf-8")
print("keypad diagnostic added")
