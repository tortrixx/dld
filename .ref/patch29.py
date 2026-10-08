# -*- coding: utf-8 -*-
"""Insert the frame renderer and fix declarations + output widths."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# ---- 1. output port widths -------------------------------------------------
s = s.replace("        o_rowr    : out std_logic_vector(7 downto 0);   -- red   bits for o_scanrow\n"
              "        o_rowg    : out std_logic_vector(7 downto 0)    -- green bits for o_scanrow\n",
              "        o_rowr    : out std_logic_vector(63 downto 0);  -- red   frame\n"
              "        o_rowg    : out std_logic_vector(63 downto 0)   -- green frame\n")

# ---- 2. declarations -------------------------------------------------------
s = s.replace(
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');\n"
    "    signal ph      : unsigned(2 downto 0) := (others => '0');\n"
    "    signal acc_cov : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal acc_kc  : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal warm    : unsigned(3 downto 0) := (others => '0');  -- startup blank\n",
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');  -- row being scanned\n"
    "    signal frow    : unsigned(2 downto 0) := (others => '0');  -- row being built\n"
    "    signal frame_r : std_logic_vector(63 downto 0) := (others => '0');\n"
    "    signal frame_g : std_logic_vector(63 downto 0) := (others => '0');\n")

# ---- 3. insert the frame renderer before the main sequential process --------
anchor = "    ----------------------------------------------------------------------------\n" \
         "    -- Main sequential process."
assert anchor in s
renderer = '''    ----------------------------------------------------------------------------
    -- FRAME RENDERER -- one ROW per 200 Hz tick, whole frame every 8 ticks.
    --
    -- WHY IT IS ORGANISED THIS WAY
    -- Two earlier arrangements were MEASURED on the board:
    --   * publishing one row per 5 ticks gave a frame rate of 200/(5*8) = 5 Hz,
    --     which visibly FLICKERS;
    --   * spawning all four pieces' row_masks in one tick made the logic far too
    --     large to fit the EPC1270.
    -- So the multiplexing runs over ROWS: each tick still evaluates only one
    -- row_mask per piece slot (so the shared shifter stays cheap), but the frame
    -- is assembled 8 bits at a time into a 64-bit register.  A frame is complete
    -- in 8 ticks and the refresh rate is 200/8 = 25 Hz, above flicker fusion.
    --
    -- The 64-bit frame is simply held; the matrix driver slices the row it is
    -- scanning, so the panel never sees a partially built row and no lockstep
    -- handshake is needed.
    --
    -- Bit convention: bit index = 8*row + col, row 0 = TOP, so logical row 0 is
    -- the TOP slice (63..56).
    ----------------------------------------------------------------------------
    process (i_clk)
        variable r      : integer;
        variable prow   : integer;
        variable srow   : integer;
        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable hh     : integer;
        variable npc    : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable cov    : std_logic_vector(7 downto 0);
        variable kc     : std_logic_vector(7 downto 0);
        variable tgtrow : std_logic_vector(7 downto 0);
        variable redrow : std_logic_vector(7 downto 0);
        variable grnrow : std_logic_vector(7 downto 0);
        variable islck0 : boolean;
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                frow    <= (others => '0');
                scanrow <= (others => '0');
                frame_r <= (others => '0');
                frame_g <= (others => '0');
            elsif (i_tick = '1') then
                r   := to_integer(frow);
                cov := (others => '0');
                kc  := (others => '0');

                if (i_level = '0') then npc := 3; else npc := 4; end if;

                -- ---- piece 0 -------------------------------------------------
                pk := pos(31 downto 24); shp := i_sh0;
                hh := to_integer(unsigned(i_h0));
                srow := r - to_integer(unsigned(pk(7 downto 4)));
                if (srow >= 0) and (srow < hh) then
                    rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                    cov := cov or rw;
                    if (locked(0) = '1') or (sel = "00") then kc := kc or rw; end if;
                end if;

                -- ---- piece 1 -------------------------------------------------
                if (npc > 1) then
                    pk := pos(23 downto 16); shp := i_sh1;
                    hh := to_integer(unsigned(i_h1));
                    srow := r - to_integer(unsigned(pk(7 downto 4)));
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(1) = '1') or (sel = "01") then kc := kc or rw; end if;
                    end if;
                end if;

                -- ---- piece 2 -------------------------------------------------
                if (npc > 2) then
                    pk := pos(15 downto 8); shp := i_sh2;
                    hh := to_integer(unsigned(i_h2));
                    srow := r - to_integer(unsigned(pk(7 downto 4)));
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(2) = '1') or (sel = "10") then kc := kc or rw; end if;
                    end if;
                end if;

                -- ---- piece 3 (level 2 only) ----------------------------------
                if (npc > 3) then
                    pk := pos(7 downto 0); shp := i_sh3;
                    hh := to_integer(unsigned(i_h3));
                    srow := r - to_integer(unsigned(pk(7 downto 4)));
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(3) = '1') or (sel = "11") then kc := kc or rw; end if;
                    end if;
                end if;

                -- ---- target row for the ghost --------------------------------
                case r is
                    when 0      => tgtrow := i_target(7 downto 0);
                    when 1      => tgtrow := i_target(15 downto 8);
                    when 2      => tgtrow := i_target(23 downto 16);
                    when 3      => tgtrow := i_target(31 downto 24);
                    when 4      => tgtrow := i_target(39 downto 32);
                    when 5      => tgtrow := i_target(47 downto 40);
                    when 6      => tgtrow := i_target(55 downto 48);
                    when others => tgtrow := i_target(63 downto 56);
                end case;

                -- colour of this row: green = selected or locked cells, red = any
                -- piece cell plus the part of the target no piece covers
                redrow := cov or (tgtrow and (not cov));
                grnrow := kc;

                -- ---- merge the row into the frame ----------------------------
                case r is
                    when 0      => frame_r(63 downto 56) <= redrow;
                                   frame_g(63 downto 56) <= grnrow;
                    when 1      => frame_r(55 downto 48) <= redrow;
                                   frame_g(55 downto 48) <= grnrow;
                    when 2      => frame_r(47 downto 40) <= redrow;
                                   frame_g(47 downto 40) <= grnrow;
                    when 3      => frame_r(39 downto 32) <= redrow;
                                   frame_g(39 downto 32) <= grnrow;
                    when 4      => frame_r(31 downto 24) <= redrow;
                                   frame_g(31 downto 24) <= grnrow;
                    when 5      => frame_r(23 downto 16) <= redrow;
                                   frame_g(23 downto 16) <= grnrow;
                    when 6      => frame_r(15 downto 8) <= redrow;
                                   frame_g(15 downto 8) <= grnrow;
                    when others => frame_r(7 downto 0) <= redrow;
                                   frame_g(7 downto 0) <= grnrow;
                end case;

                -- the scanned row follows the row being built, one tick behind
                if (frow = 7) then
                    frow <= (others => '0');
                else
                    frow <= frow + 1;
                end if;
                scanrow <= frow;
            end if;
        end if;
    end process;

'''
s = s.replace(anchor, renderer + anchor, 1)
p.write_text(s, encoding="utf-8")
print("frame renderer inserted")
