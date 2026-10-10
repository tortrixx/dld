# -*- coding: utf-8 -*-
"""把两处 overlap() 调用点换成内联的 8 位行掩码比较。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

# ---------- 移动路径 -------------------------------------------------------
old_move = """                    -- (2) exact overlap against the live pieces
                    if (ok) then
                        live := "0000";
                        if (to_integer(sel) /= 0) then live(0) := '1'; end if;
                        if (to_integer(sel) /= 1) then live(1) := '1'; end if;
                        if (to_integer(sel) /= 2) then live(2) := '1'; end if;
                        if (lvl2 and (to_integer(sel) /= 3)) then live(3) := '1'; end if;

                        if overlap(cr, cc, sh_new, live,
                                   pos(31 downto 24), i_sh0,
                                   pos(23 downto 16), i_sh1,
                                   pos(15 downto 8),  i_sh2,
                                   pos(7 downto 0),   i_sh3) then
                            ok := false;
                        end if;
                    end if;"""
new_move = """                    -- (2) EXACT overlap test, row by row.  For each panel row
                    --     the candidate occupies, build its 8-bit mask once and
                    --     AND it with each other piece's mask for that row.
                    --     (A bounding-box test would reject legal moves of the
                    --     cross and the L-tromino, which are not rectangles.)
                    if (ok) then
                        for rr in 0 to 7 loop
                            candrow := row_mask(sh_new, rr - cr, cc);
                            if (candrow /= x"00") then
                                if (sel /= "00") then
                                    orow := rr - to_integer(unsigned(pos(31 downto 28)));
                                    if (orow >= 0) and (orow <= 2) then
                                        if (candrow and row_mask(i_sh0, orow,
                                                to_integer(unsigned(pos(27 downto 24))))) /= x"00" then
                                            ok := false;
                                        end if;
                                    end if;
                                end if;
                                if (sel /= "01") then
                                    orow := rr - to_integer(unsigned(pos(23 downto 20)));
                                    if (orow >= 0) and (orow <= 2) then
                                        if (candrow and row_mask(i_sh1, orow,
                                                to_integer(unsigned(pos(19 downto 16))))) /= x"00" then
                                            ok := false;
                                        end if;
                                    end if;
                                end if;
                                if (sel /= "10") then
                                    orow := rr - to_integer(unsigned(pos(15 downto 12)));
                                    if (orow >= 0) and (orow <= 2) then
                                        if (candrow and row_mask(i_sh2, orow,
                                                to_integer(unsigned(pos(11 downto 8))))) /= x"00" then
                                            ok := false;
                                        end if;
                                    end if;
                                end if;
                                if (lvl2 and (sel /= "11")) then
                                    orow := rr - to_integer(unsigned(pos(7 downto 4)));
                                    if (orow >= 0) and (orow <= 2) then
                                        if (candrow and row_mask(i_sh3, orow,
                                                to_integer(unsigned(pos(3 downto 0))))) /= x"00" then
                                            ok := false;
                                        end if;
                                    end if;
                                end if;
                            end if;
                        end loop;
                    end if;"""
assert old_move in s, "move block not found"
s = s.replace(old_move, new_move)

# ---------- 散落路径 ----------------------------------------------------
old_sc = """                    live := "0000";
                    if (to_integer(sh_k) /= 0) then live(0) := '1'; end if;
                    if (to_integer(sh_k) /= 1) then live(1) := '1'; end if;
                    if (to_integer(sh_k) /= 2) then live(2) := '1'; end if;
                    if (lvl2 and (to_integer(sh_k) /= 3)) then live(3) := '1'; end if;

                    ok := not overlap(cr, cc, sh_new, live,
                                      pos(31 downto 24), i_sh0,
                                      pos(23 downto 16), i_sh1,
                                      pos(15 downto 8),  i_sh2,
                                      pos(7 downto 0),   i_sh3);"""
new_sc = """                    ok := true;
                    for rr in 0 to 7 loop
                        candrow := row_mask(sh_new, rr - cr, cc);
                        if (candrow /= x"00") then
                            if (sh_k /= "00") then
                                orow := rr - to_integer(unsigned(pos(31 downto 28)));
                                if (orow >= 0) and (orow <= 2) then
                                    if (candrow and row_mask(i_sh0, orow,
                                            to_integer(unsigned(pos(27 downto 24))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                            end if;
                            if (sh_k /= "01") then
                                orow := rr - to_integer(unsigned(pos(23 downto 20)));
                                if (orow >= 0) and (orow <= 2) then
                                    if (candrow and row_mask(i_sh1, orow,
                                            to_integer(unsigned(pos(19 downto 16))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                            end if;
                            if (sh_k /= "10") then
                                orow := rr - to_integer(unsigned(pos(15 downto 12)));
                                if (orow >= 0) and (orow <= 2) then
                                    if (candrow and row_mask(i_sh2, orow,
                                            to_integer(unsigned(pos(11 downto 8))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                            end if;
                            if (lvl2 and (sh_k /= "11")) then
                                orow := rr - to_integer(unsigned(pos(7 downto 4)));
                                if (orow >= 0) and (orow <= 2) then
                                    if (candrow and row_mask(i_sh3, orow,
                                            to_integer(unsigned(pos(3 downto 0))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                            end if;
                        end if;
                    end loop;"""
assert old_sc in s, "scatter block not found"
s = s.replace(old_sc, new_sc)

# ---------- 变量 -------------------------------------------------------
s = s.replace("        variable live     : std_logic_vector(3 downto 0);\n",
              "        variable candrow  : std_logic_vector(7 downto 0);\n"
              "        variable orow     : integer;\n"
              "        variable rr       : integer;\n"
              "        variable live     : std_logic_vector(3 downto 0);\n")

p.write_text(s, encoding="utf-8")
print("done; overlap( refs:", s.count("overlap("), " row_mask refs:", s.count("row_mask("))
