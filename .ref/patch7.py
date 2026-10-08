# -*- coding: utf-8 -*-
"""puzzle_ctrl v5b: replace the rectangle-overlap test with an EXACT per-row
mask comparison.

The bounding-box test over-approximates for non-rectangular pieces (level 1 uses
a cross and an L-tromino), so two pieces that do not actually touch could be
rejected.  Exact comparison builds the piece's row mask and ANDs it with the
other pieces' row masks -- which is what the model in .ref/model_ctrl.py
validates.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# ---- add a row-mask helper function to the architecture header ------------
s = s.replace(
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');\n\nbegin",
    """    signal scanrow : unsigned(2 downto 0) := (others => '0');

    -- Row mask of a piece at a given position: the 8 bits of the piece row that
    -- would appear on panel row 'row'.  Returns 0 when the piece has no cells on
    -- that row.  Used for EXACT overlap tests (a bounding-box test would reject
    -- legal moves of the cross and of the L-tromino, which are not rectangles).
    function row_mask(shp : std_logic_vector(63 downto 0);
                      hgt : integer;
                      ar  : integer;      -- anchor row
                      ac  : integer;      -- anchor col
                      row : integer) return std_logic_vector is
        variable base : std_logic_vector(7 downto 0);
        variable rw   : std_logic_vector(7 downto 0) := (others => '0');
        variable sr   : integer;
        variable idx  : integer;
    begin
        sr := row - ar;
        if (sr < 0) or (sr >= hgt) or (sr > 2) then
            return rw;
        end if;
        if (sr = 0) then
            base := shp(7 downto 0);
        elsif (sr = 1) then
            base := shp(15 downto 8);
        else
            base := shp(23 downto 16);
        end if;
        for c in 0 to 7 loop
            idx := c + ac;
            if (idx <= 7) then
                rw(idx) := base(c);
            end if;
        end loop;
        return rw;
    end function;

begin""")

# ---- replace both rectangle tests with exact row-mask tests ---------------
OLD = """                                orow := to_integer(unsigned(npos(7 downto 4)));
                                ocol := to_integer(unsigned(npos(3 downto 0)));

                                if (cr < orow + oh) and (orow < cr + hh)
                                   and (cc < ocol + ow) and (ocol < cc + ww) then
                                    ok := false;
                                end if;"""
NEW = """                                orow := to_integer(unsigned(npos(7 downto 4)));
                                ocol := to_integer(unsigned(npos(3 downto 0)));

                                -- exact: compare the candidate rows with the
                                -- other piece's rows, over the rows they share
                                for rr in 0 to 7 loop
                                    if ((row_mask(oshp, oh, orow, ocol, rr))
                                        and (row_mask(shp_sel, hh, cr, cc, rr))) /= x"00" then
                                        ok := false;
                                    end if;
                                end loop;"""
assert OLD in s
s = s.replace(OLD, NEW)

OLD2 = """                            orow := to_integer(unsigned(npos(7 downto 4)));
                            ocol := to_integer(unsigned(npos(3 downto 0)));

                            if (cr < orow + oh) and (orow < cr + hh)
                               and (cc < ocol + ow) and (ocol < cc + ww) then
                                ok := false;
                            end if;"""
NEW2 = """                            orow := to_integer(unsigned(npos(7 downto 4)));
                            ocol := to_integer(unsigned(npos(3 downto 0)));

                            for rr in 0 to 7 loop
                                if ((row_mask(oshp, oh, orow, ocol, rr))
                                    and (row_mask(shp_new, hh, cr, cc, rr))) /= x"00" then
                                    ok := false;
                                end if;
                            end loop;"""
assert OLD2 in s
s = s.replace(OLD2, NEW2)

# ---- declare the extra variables and latch the shapes --------------------
s = s.replace(
    "        variable oh, ow : integer;    -- other piece's height / width\n"
    "        variable orow, ocol : integer;\n",
    "        variable oh, ow : integer;    -- other piece's height / width\n"
    "        variable orow, ocol : integer;\n"
    "        variable oshp  : std_logic_vector(63 downto 0);\n"
    "        variable shp_sel : std_logic_vector(63 downto 0);\n"
    "        variable shp_new : std_logic_vector(63 downto 0);\n"
    "        variable rr    : integer;\n")

# in the move path, resolve the selected shape before the overlap loop
s = s.replace(
    "                    case to_integer(sel) is\n"
    "                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0));\n"
    "                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1));\n"
    "                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2));\n"
    "                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3));\n"
    "                    end case;\n",
    "                    case to_integer(sel) is\n"
    "                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp_sel := i_sh0;\n"
    "                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp_sel := i_sh1;\n"
    "                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp_sel := i_sh2;\n"
    "                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp_sel := i_sh3;\n"
    "                    end case;\n", 1)

# in the move overlap loop, resolve the other piece's shape too
s = s.replace(
    "                                case k is\n"
    "                                    when 0      => npos := pos(31 downto 24);\n"
    "                                                   oh := to_integer(unsigned(i_h0)); ow := to_integer(unsigned(i_w0));\n"
    "                                    when 1      => npos := pos(23 downto 16);\n"
    "                                                   oh := to_integer(unsigned(i_h1)); ow := to_integer(unsigned(i_w1));\n"
    "                                    when 2      => npos := pos(15 downto 8);\n"
    "                                                   oh := to_integer(unsigned(i_h2)); ow := to_integer(unsigned(i_w2));\n"
    "                                    when others => npos := pos(7 downto 0);\n"
    "                                                   oh := to_integer(unsigned(i_h3)); ow := to_integer(unsigned(i_w3));\n"
    "                                end case;\n",
    "                                case k is\n"
    "                                    when 0      => npos := pos(31 downto 24); oshp := i_sh0;\n"
    "                                                   oh := to_integer(unsigned(i_h0));\n"
    "                                    when 1      => npos := pos(23 downto 16); oshp := i_sh1;\n"
    "                                                   oh := to_integer(unsigned(i_h1));\n"
    "                                    when 2      => npos := pos(15 downto 8); oshp := i_sh2;\n"
    "                                                   oh := to_integer(unsigned(i_h2));\n"
    "                                    when others => npos := pos(7 downto 0); oshp := i_sh3;\n"
    "                                                   oh := to_integer(unsigned(i_h3));\n"
    "                                end case;\n", 1)

# scatter path: resolve the new piece's shape and the other pieces' shapes
s = s.replace(
    "                    case to_integer(sh_k) is\n"
    "                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0));\n"
    "                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1));\n"
    "                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2));\n"
    "                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3));\n"
    "                    end case;\n",
    "                    case to_integer(sh_k) is\n"
    "                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp_new := i_sh0;\n"
    "                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp_new := i_sh1;\n"
    "                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp_new := i_sh2;\n"
    "                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp_new := i_sh3;\n"
    "                    end case;\n", 1)

s = s.replace(
    "                            case k is\n"
    "                                when 0      => npos := pos(31 downto 24);\n"
    "                                               oh := to_integer(unsigned(i_h0)); ow := to_integer(unsigned(i_w0));\n"
    "                                when 1      => npos := pos(23 downto 16);\n"
    "                                               oh := to_integer(unsigned(i_h1)); ow := to_integer(unsigned(i_w1));\n"
    "                                when 2      => npos := pos(15 downto 8);\n"
    "                                               oh := to_integer(unsigned(i_h2)); ow := to_integer(unsigned(i_w2));\n"
    "                                when others => npos := pos(7 downto 0);\n"
    "                                               oh := to_integer(unsigned(i_h3)); ow := to_integer(unsigned(i_w3));\n"
    "                            end case;\n",
    "                            case k is\n"
    "                                when 0      => npos := pos(31 downto 24); oshp := i_sh0;\n"
    "                                               oh := to_integer(unsigned(i_h0));\n"
    "                                when 1      => npos := pos(23 downto 16); oshp := i_sh1;\n"
    "                                               oh := to_integer(unsigned(i_h1));\n"
    "                                when 2      => npos := pos(15 downto 8); oshp := i_sh2;\n"
    "                                               oh := to_integer(unsigned(i_h2));\n"
    "                                when others => npos := pos(7 downto 0); oshp := i_sh3;\n"
    "                                               oh := to_integer(unsigned(i_h3));\n"
    "                            end case;\n", 1)

p.write_text(s, encoding="utf-8")
print("patched; row_mask uses:", s.count("row_mask("))
