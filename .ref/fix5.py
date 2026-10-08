# -*- coding: utf-8 -*-
"""FIX 5 -- matrix content per state.

The state multiplexer only special-cased SELF_TEST / WIN / FAIL; every other
state (including S_IDLE and S_PREVIEW) displayed the ENGINE frame.  But the
scatter only starts in S_PLAYING, so during idle and preview all pieces still sit
at anchor (0,0) and the panel showed a blob in the top-left corner instead of:
    S_IDLE    -> panel dark               (requirement B2 "点阵全灭")
    S_PREVIEW -> the complete pattern     (requirement B4)
The target picture is a package constant, so the preview just slices i_target
directly -- no engine involvement needed.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_top.vhd")
s = p.read_text(encoding="utf-8")

old = """    process (state, gblink, mrow, eng_fr, eng_fg, win_row, fail_row)
        variable lv  : std_logic;
        variable rw  : std_logic_vector(7 downto 0);
        variable gw  : std_logic_vector(7 downto 0);
    begin
        lv := gblink;

        -- slice the row the driver is lighting out of the 64-bit picture.
        -- bit index = 8*row + col with row 0 = TOP, so row 0 is the TOP slice.
        case to_integer(mrow) is
            when 0      => rw := eng_fr(63 downto 56); gw := eng_fg(63 downto 56);
            when 1      => rw := eng_fr(55 downto 48); gw := eng_fg(55 downto 48);
            when 2      => rw := eng_fr(47 downto 40); gw := eng_fg(47 downto 40);
            when 3      => rw := eng_fr(39 downto 32); gw := eng_fg(39 downto 32);
            when 4      => rw := eng_fr(31 downto 24); gw := eng_fg(31 downto 24);
            when 5      => rw := eng_fr(23 downto 16); gw := eng_fg(23 downto 16);
            when 6      => rw := eng_fr(15 downto 8);  gw := eng_fg(15 downto 8);
            when others => rw := eng_fr(7 downto 0);   gw := eng_fg(7 downto 0);
        end case;

        if (state = S_SELF_TEST) then
            -- whole panel yellow, flashing at 2 Hz (requirement B1)
            mat_r <= (others => lv);
            mat_g <= (others => lv);
        elsif (state = S_WIN) then
            mat_r <= win_row and (lv & lv & lv & lv & lv & lv & lv & lv);
            mat_g <= (others => '0');
        elsif (state = S_FAIL) then
            mat_r <= fail_row and (lv & lv & lv & lv & lv & lv & lv & lv);
            mat_g <= (others => '0');
        else
            mat_r <= rw;
            mat_g <= gw;
        end if;
    end process;"""

new = """    process (state, gblink, mrow, eng_fr, eng_fg, win_row, fail_row, prev_row)
        variable lv  : std_logic;
        variable rw  : std_logic_vector(7 downto 0);
        variable gw  : std_logic_vector(7 downto 0);
    begin
        lv := gblink;

        -- slice the row the driver is lighting out of the 64-bit picture.
        -- bit index = 8*row + col with row 0 = TOP, so row 0 is the TOP slice.
        case to_integer(mrow) is
            when 0      => rw := eng_fr(63 downto 56); gw := eng_fg(63 downto 56);
            when 1      => rw := eng_fr(55 downto 48); gw := eng_fg(55 downto 48);
            when 2      => rw := eng_fr(47 downto 40); gw := eng_fg(47 downto 40);
            when 3      => rw := eng_fr(39 downto 32); gw := eng_fg(39 downto 32);
            when 4      => rw := eng_fr(31 downto 24); gw := eng_fg(31 downto 24);
            when 5      => rw := eng_fr(23 downto 16); gw := eng_fg(23 downto 16);
            when 6      => rw := eng_fr(15 downto 8);  gw := eng_fg(15 downto 8);
            when others => rw := eng_fr(7 downto 0);   gw := eng_fg(7 downto 0);
        end case;

        if (state = S_SELF_TEST) then
            -- whole panel yellow, flashing at 2 Hz (requirement B1)
            mat_r <= (others => lv);
            mat_g <= (others => lv);
        elsif (state = S_IDLE) then
            -- B2: the panel is DARK in standby.  The engine frame must NOT be
            -- shown here: the pieces have not been scattered yet (that happens
            -- when play starts) and would all be stacked at anchor (0,0).
            mat_r <= (others => '0');
            mat_g <= (others => '0');
        elsif (state = S_PREVIEW) then
            -- B4: show the COMPLETE pattern.  It is a package constant, so slice
            -- it straight out of the target mask - the engine is not involved.
            mat_r <= prev_row;
            mat_g <= (others => '0');
        elsif (state = S_WIN) then
            mat_r <= win_row and (lv & lv & lv & lv & lv & lv & lv & lv);
            mat_g <= (others => '0');
        elsif (state = S_FAIL) then
            mat_r <= fail_row and (lv & lv & lv & lv & lv & lv & lv & lv);
            mat_g <= (others => '0');
        else
            -- S_PLAYING: the assembled picture from the engine
            mat_r <= rw;
            mat_g <= gw;
        end if;
    end process;"""
assert old in s
s = s.replace(old, new)

# add the preview row source: slice tgt_mask in PACKAGE convention (row 0 = bits 7..0)
s = s.replace("    signal win_row  : std_logic_vector(7 downto 0);",
              "    signal win_row  : std_logic_vector(7 downto 0);\n"
              "    signal prev_row : std_logic_vector(7 downto 0);  -- target picture row\n"
              "    signal fail_row : std_logic_vector(7 downto 0);")

s = s.replace("""    with std_logic_vector(mrow) select
        fail_row <=""",
              """    -- Preview row: the complete pattern, sliced in PACKAGE convention where
    -- row 0 occupies bits 7..0 (NOT the engine's internal MSB-first layout).
    with std_logic_vector(mrow) select
        prev_row <= tgt_mask(7 downto 0)   when "000",
                    tgt_mask(15 downto 8)  when "001",
                    tgt_mask(23 downto 16) when "010",
                    tgt_mask(31 downto 24) when "011",
                    tgt_mask(39 downto 32) when "100",
                    tgt_mask(47 downto 40) when "101",
                    tgt_mask(55 downto 48) when "110",
                    tgt_mask(63 downto 56) when others;

    with std_logic_vector(mrow) select
        fail_row <=""")

p.write_text(s, encoding="utf-8")
print("display routing fixed")
