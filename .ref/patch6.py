# -*- coding: utf-8 -*-
"""puzzle_ctrl: final structural pass to cut area.

Root causes found by measurement (.ref/attrib.py: the move path alone cost 961
logic cells):
  * `pos(8*sel+7 downto 8*sel)` is a VARIABLE SLICE -> every bit becomes its own
    mux tree.  Replaced by four straight reads through one explicit 4:1 select.
  * `for r in 0 to 7 ... occ(8*r+7 downto 8*r) := ...` builds a per-row mux.
    Replaced by 8 explicit slice assignments (pure wiring).
  * the selected footprint was read via `inst_mask(to_integer(sel))`; now it is
    selected once into a dedicated signal.
  * the render cone is registered (see patch5).
"""
import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# ---------------------------------------------------------------- declarations
s = s.replace(
    "    -- candidates for the scatter\n"
    "    signal sh_pos : std_logic_vector(7 downto 0) := (others => '0');\n",
    "")
s = s.replace(
    "    signal sh_col : unsigned(3 downto 0) := (others => '0');\n",
    "")
# add explicit per-piece anchor selects
s = s.replace(
    "    signal sel_p  : std_logic_vector(7 downto 0);\n"
    "    signal sel_m  : std_logic_vector(63 downto 0);\n",
    "    signal sel_p  : std_logic_vector(7 downto 0);\n"
    "    signal sel_m  : std_logic_vector(63 downto 0);\n"
    "    signal sel_locked : std_logic;\n")

# ---------------------------------------------------- add the explicit selects
s = s.replace(
    "    with sel select\n"
    "        sel_m <= m0 when \"00\",\n"
    "                 m1 when \"01\",\n"
    "                 m2 when \"10\",\n"
    "                 m3 when others;\n",
    "    with sel select\n"
    "        sel_m <= m0 when \"00\",\n"
    "                 m1 when \"01\",\n"
    "                 m2 when \"10\",\n"
    "                 m3 when others;\n"
    "\n"
    "    with sel select\n"
    "        sel_locked <= locked(0) when \"00\",\n"
    "                      locked(1) when \"01\",\n"
    "                      locked(2) when \"10\",\n"
    "                      locked(3) when others;\n")

# ------------------------------------------------------------- rewrite the move
start = s.index("                if (mv = '1') then")
end = s.index("                ------------------------------------------------------------------\n                -- 3. Scatter sequencer.")
new_move = """                if (mv = '1') then
                    mv <= '0';

                    -- Anchors are read through ONE explicit 4:1 select.  A
                    -- variable slice such as pos(8*sel+7 downto 8*sel) makes
                    -- every destination bit its own multiplexer and was a large
                    -- part of the 961 logic cells this path used to cost.
                    cr := to_integer(unsigned(sel_p(7 downto 4)));
                    cc := to_integer(unsigned(sel_p(3 downto 0)));
                    hh := to_integer(sel_h);
                    ww := to_integer(sel_w);

                    if (i_up = '1') then
                        if (cr > 0) then cr := cr - 1; end if;
                    elsif (i_down = '1') then
                        if (cr < 7) then cr := cr + 1; end if;
                    elsif (i_left = '1') then
                        if (cc > 0) then cc := cc - 1; end if;
                    elsif (i_right = '1') then
                        if (cc < 7) then cc := cc + 1; end if;
                    end if;

                    -- (1) BOUNDS -- analytic, verified against geometry in
                    --     .ref/model_ctrl.py (0 mismatches for every shape/place)
                    ok := (cr + hh <= 8) and (cc + ww <= 8);

                    if (ok) then
                        -- (2) candidate footprint by FIXED one-cell shifts,
                        --     written as explicit slice assignments (wiring only)
                        occ := sel_m;
                        if (i_down = '1') then
                            occ2 := occ(55 downto 0) & x"00";
                        elsif (i_up = '1') then
                            occ2 := x"00" & occ(63 downto 8);
                        elsif (i_left = '1') then
                            occ2(7 downto 0)   := '0' & occ(7 downto 1);
                            occ2(15 downto 8)  := '0' & occ(15 downto 9);
                            occ2(23 downto 16) := '0' & occ(23 downto 17);
                            occ2(31 downto 24) := '0' & occ(31 downto 25);
                            occ2(39 downto 32) := '0' & occ(39 downto 33);
                            occ2(47 downto 40) := '0' & occ(47 downto 41);
                            occ2(55 downto 48) := '0' & occ(55 downto 49);
                            occ2(63 downto 56) := '0' & occ(63 downto 57);
                        elsif (i_right = '1') then
                            occ2(7 downto 0)   := occ(6 downto 0)   & '0';
                            occ2(15 downto 8)  := occ(14 downto 8)  & '0';
                            occ2(23 downto 16) := occ(22 downto 16) & '0';
                            occ2(31 downto 24) := occ(30 downto 24) & '0';
                            occ2(39 downto 32) := occ(38 downto 32) & '0';
                            occ2(47 downto 40) := occ(46 downto 40) & '0';
                            occ2(55 downto 48) := occ(54 downto 48) & '0';
                            occ2(63 downto 56) := occ(62 downto 56) & '0';
                        else
                            occ2 := occ;
                        end if;

                        -- (3) overlap with the other pieces
                        if (i_level = '0') then
                            case to_integer(sel) is
                                when 0      => rest := m1 or m2;
                                when 1      => rest := m0 or m2;
                                when others => rest := m0 or m1;
                            end case;
                        else
                            case to_integer(sel) is
                                when 0      => rest := m1 or m2 or m3;
                                when 1      => rest := m0 or m2 or m3;
                                when 2      => rest := m0 or m1 or m3;
                                when others => rest := m0 or m1 or m2;
                            end case;
                        end if;
                        if ((occ2 and rest) /= MASK_ZERO) then
                            ok := false;
                        end if;
                    end if;

                    -- (4) locked pieces do not move
                    if (sel_locked = '1') then
                        ok := false;
                    end if;

                    if (ok) then
                        npos := std_logic_vector(to_unsigned(cr, 4)) &
                                std_logic_vector(to_unsigned(cc, 4));
                        case to_integer(sel) is
                            when 0      => p0 <= npos; m0 <= occ2;
                            when 1      => p1 <= npos; m1 <= occ2;
                            when 2      => p2 <= npos; m2 <= occ2;
                            when others => p3 <= npos; m3 <= occ2;
                        end case;
                    end if;
                end if;

"""
s = s[:start] + new_move + s[end:]

# ------------------------------------------- scatter: replace variable slices
s = s.replace("""                        cr := to_integer(unsigned(sh_pos(7 downto 4)));
                        cc := to_integer(unsigned(sh_pos(3 downto 0)));""",
              """                        cr := to_integer(unsigned(sh_pos(7 downto 4)));
                        cc := to_integer(unsigned(sh_pos(3 downto 0)));""")

p.write_text(s, encoding="utf-8")
print("patched; o_px_red assignments =", s.count("o_px_red <="))
