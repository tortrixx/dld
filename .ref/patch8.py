# -*- coding: utf-8 -*-
"""Replace the local per-call row_mask function with the package helper row24 and
restructure the overlap tests so the candidate row is computed once per row."""

import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# ---- 1. drop the local row_mask function ---------------------------------
start = s.index("    -- Row mask of a piece at a given position")
end = s.index("begin\n\n    o_lock")
s = s[:start] + s[end:]
s = s.replace("    signal scanrow : unsigned(2 downto 0) := (others => '0');\n\n",
              "    signal scanrow : unsigned(2 downto 0) := (others => '0');\n\n")

# ---- 2. move path: exact overlap, candidate row computed once -------------
mstart = s.index("                    -- (2) rectangle overlap against the other pieces")
mend = s.index("                    -- (3) locked pieces do not move")
new_move = """                    -- (2) EXACT overlap test, row by row.  A bounding-box test
                    --     would over-approximate for the cross and the L-tromino,
                    --     rejecting legal moves.  For each panel row that the
                    --     candidate occupies, build its 8-bit mask once and AND it
                    --     with each other piece's mask for that row.
                    if (ok) then
                        for rr in 0 to 7 loop
                            candrow := row24(shp_sel24, rr - cr, cc);
                            if (candrow /= x"00") then
                                -- piece 0
                                if ((k /= 0) and (k_mv /= 0)) then null; end if;
                            end if;
                        end loop;
                    end if;

                    -- unrolled exact test (the loop above only builds the mask)
                    if (ok) then
                        for rr in 0 to 7 loop
                            candrow := row24(shp_sel24, rr - cr, cc);
                            if (candrow /= x"00") then
                                if (k_incl(0)) then
                                    if (candrow and row24(i_sh0(23 downto 0),
                                          rr - to_integer(unsigned(pos(31 downto 24))),
                                          to_integer(unsigned(pos(27 downto 24))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                                if (k_incl(1)) then
                                    if (candrow and row24(i_sh1(23 downto 0),
                                          rr - to_integer(unsigned(pos(23 downto 20))),
                                          to_integer(unsigned(pos(19 downto 16))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                                if (k_incl(2)) then
                                    if (candrow and row24(i_sh2(23 downto 0),
                                          rr - to_integer(unsigned(pos(15 downto 12))),
                                          to_integer(unsigned(pos(11 downto 8))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                                if (i_level = '1') and (sel /= "11") then
                                    if (candrow and row24(i_sh3(23 downto 0),
                                          rr - to_integer(unsigned(pos(7 downto 4))),
                                          to_integer(unsigned(pos(3 downto 0))))) /= x"00" then
                                        ok := false;
                                    end if;
                                end if;
                            end if;
                        end loop;
                    end if;

"""
s = s[:mstart] + new_move + s[mend:]

p.write_text(s, encoding="utf-8")
print("move path rewritten")
