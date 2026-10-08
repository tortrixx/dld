# -*- coding: utf-8 -*-
"""Compact the overlap test.

The previous version took four (anchor, shape) pairs and looped over 8 rows,
so every call site replicated 32 row24 evaluations.  Replace it with a single
8-bit row helper `row_mask`, and drive the loop from integer variables that are
computed once per row outside the helper.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# ---- 1. swap the big function for a small row helper ----------------------
start = s.index("    ----------------------------------------------------------------------------\n    -- EXACT overlap test.")
end = s.index("    signal pos    : std_logic_vector(31 downto 0) := (others => '0');")
new_fn = '''    ----------------------------------------------------------------------------
    -- EXACT overlap test helper.
    --
    -- The shapes are NOT all rectangles (level 1 uses a cross and an L-tromino),
    -- so intersecting bounding boxes would reject legal moves.  This returns the
    -- 8 bits a piece contributes to ONE panel row; the caller ANDs the candidate
    -- row against the other pieces' rows.
    --
    -- Deliberately a small single-purpose function: an earlier version took four
    -- (anchor, shape) pairs and looped over eight rows inside, which made every
    -- call site replicate 32 evaluations and cost ~1500 logic cells.
    --
    -- ar/ac are the piece anchor, row the panel row, sr the piece's own row.
    -- All indices are guaranteed in range by the caller's guards, because a
    -- subprogram is elaborated at compile time.
    ----------------------------------------------------------------------------
    function row_mask(shp : std_logic_vector(63 downto 0);
                      sr  : integer;
                      ac  : integer) return std_logic_vector is
        variable base : std_logic_vector(7 downto 0) := (others => '0');
    begin
        if (sr = 0) then
            base := shp(7 downto 0);
        elsif (sr = 1) then
            base := shp(15 downto 8);
        elsif (sr = 2) then
            base := shp(23 downto 16);
        else
            base := (others => '0');
        end if;
        return srl8(base, ac);
    end function;

'''
s = s[:start] + new_fn + s[end:]

p.write_text(s, encoding="utf-8")
print("row_mask helper installed; overlap() references left:", s.count("overlap("))
