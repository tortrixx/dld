# -*- coding: utf-8 -*-
"""Pipeline the move proposal.

Reported path (42.2 MHz): sel -> pos mux -> LessThan(bounds) -> cr -> chk_pos ->
  Add10 -> process_2 -> chk.CH_IDLE
i.e. anchor select, direction clamp, bounds test and state launch all in one
clock.  Splitting it: the move handler now latches the ORIGINAL anchor and the
active direction into a flag, and the clamp + bounds test happens one cycle later
on register outputs.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# extra registers
s = s.replace("    signal chk_orow : unsigned(3 downto 0) := (others => '0');  -- pipelined row index",
              "    signal chk_orow : unsigned(3 downto 0) := (others => '0');  -- pipelined row index\n"
              "    -- pending move proposal (pipelined so the clamp + bounds test is not\n"
              "    -- chained after the anchor select in the same clock)\n"
              "    signal mv_pend  : std_logic := '0';\n"
              "    signal mv_anchor: std_logic_vector(7 downto 0) := (others => '0');\n"
              "    signal mv_dir   : std_logic_vector(3 downto 0) := (others => '0');")

# reset the new registers
s = s.replace("                mv <= '0';\n                chk <= CH_IDLE;",
              "                mv <= '0';\n                mv_pend <= '0';\n                chk <= CH_IDLE;")

# ---- stage 1: latch the proposal ------------------------------------------
old = """                if (mv = '1') and (chk = CH_IDLE) then
                    mv  <= '0';
                    -- proposed new anchor, clamped so no integer goes negative
                    cr := to_integer(unsigned(sel_p(7 downto 4)));
                    cc := to_integer(unsigned(sel_p(3 downto 0)));
                    case to_integer(sel) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp := i_sh0;
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp := i_sh1;
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp := i_sh2;
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp := i_sh3;
                    end case;

                    if (i_up = '1') then
                        if (cr > 0) then cr := cr - 1; end if;
                    elsif (i_down = '1') then
                        if (cr < 7) then cr := cr + 1; end if;
                    elsif (i_left = '1') then
                        if (cc > 0) then cc := cc - 1; end if;
                    elsif (i_right = '1') then
                        if (cc < 7) then cc := cc + 1; end if;
                    end if;

                    chk_pos <= std_logic_vector(to_unsigned(cr, 4)) &
                               std_logic_vector(to_unsigned(cc, 4));
                    chk_shp <= shp;
                    chk_h   <= std_logic_vector(to_unsigned(hh, 3));
                    chk_w   <= std_logic_vector(to_unsigned(ww, 3));
                    -- bounds are analytic (verified against geometry in
                    -- .ref/model_ctrl.py, 0 mismatches for every shape/position)
                    if (cr + hh <= 8) and (cc + ww <= 8)
                       and (locked(to_integer(sel)) = '0') then
                        chk_kind <= '0';                 -- '0' = move
                        chk      <= CH_RUN;
                        chk_row  <= (others => '0');
                        chk_hit  <= '0';
                    end if;
                end if;"""
new = """                -- stage 1: latch the proposal (anchor + which direction)
                if (mv = '1') and (chk = CH_IDLE) then
                    mv       <= '0';
                    mv_pend  <= '1';
                    mv_anchor<= sel_p;
                    mv_dir   <= i_up & i_down & i_left & i_right;
                end if;

                -- stage 2: clamp, test the bounds and launch the overlap engine.
                -- All operands are register outputs, so this is a short path.
                if (mv_pend = '1') and (chk = CH_IDLE) then
                    mv_pend <= '0';

                    cr := to_integer(unsigned(mv_anchor(7 downto 4)));
                    cc := to_integer(unsigned(mv_anchor(3 downto 0)));
                    case to_integer(sel) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp := i_sh0;
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp := i_sh1;
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp := i_sh2;
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp := i_sh3;
                    end case;

                    if (mv_dir(3) = '1') then
                        if (cr > 0) then cr := cr - 1; end if;
                    elsif (mv_dir(2) = '1') then
                        if (cr < 7) then cr := cr + 1; end if;
                    elsif (mv_dir(1) = '1') then
                        if (cc > 0) then cc := cc - 1; end if;
                    elsif (mv_dir(0) = '1') then
                        if (cc < 7) then cc := cc + 1; end if;
                    end if;

                    -- bounds: analytic, verified against geometry in
                    -- .ref/model_ctrl.py (0 mismatches for every shape/position)
                    if (cr + hh <= 8) and (cc + ww <= 8)
                       and (locked(to_integer(sel)) = '0') then
                        chk_pos  <= std_logic_vector(to_unsigned(cr, 4)) &
                                    std_logic_vector(to_unsigned(cc, 4));
                        chk_shp  <= shp;
                        chk_h    <= std_logic_vector(to_unsigned(hh, 3));
                        chk_w    <= std_logic_vector(to_unsigned(ww, 3));
                        chk_kind <= '0';                 -- '0' = move
                        chk      <= CH_RUN;
                        chk_row  <= (others => '0');
                        chk_hit  <= '0';
                    end if;
                end if;"""
assert old in s, "move block not found"
s = s.replace(old, new)
p.write_text(s, encoding="utf-8")
print("move proposal pipelined")
