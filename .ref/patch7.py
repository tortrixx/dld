# -*- coding: utf-8 -*-
"""puzzle_ctrl v5b：把矩形重叠判定换成**逐行掩码**的精确
比较。

包围盒判定对非矩形零片（第一关用到一个十字形和一个 L 形三格）会过度
近似，于是两块实际上并不接触的零片也可能被判为重叠。精确比较的做法是
构造该零片的行掩码，再把它与其它零片的行掩码相与 —— 这正是
.ref/model_ctrl.py 里的模型
所校验的做法。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

# ---- 在结构体头部加入一个行掩码辅助函数 ------------
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

# ---- 把两处矩形判定都换成精确的行掩码判定 ---------------
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

# ---- 声明额外变量并锁存各零片的形状 --------------------
s = s.replace(
    "        variable oh, ow : integer;    -- other piece's height / width\n"
    "        variable orow, ocol : integer;\n",
    "        variable oh, ow : integer;    -- other piece's height / width\n"
    "        variable orow, ocol : integer;\n"
    "        variable oshp  : std_logic_vector(63 downto 0);\n"
    "        variable shp_sel : std_logic_vector(63 downto 0);\n"
    "        variable shp_new : std_logic_vector(63 downto 0);\n"
    "        variable rr    : integer;\n")

# 在移动路径中，于重叠循环之前先解析出被选中的形状
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

# 在移动的重叠循环中，也要解析出另一块零片的形状
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

# 散落路径：解析新零片的形状以及其它零片的形状
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
