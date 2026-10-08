# -*- coding: utf-8 -*-
"""Patch puzzle_ctrl:
  * resolve the selected-piece footprint/shape into REGISTERS once per cycle
    (a 64-bit 4:1 mux evaluated once, instead of several),
  * register the render outputs (red/green) so the colour mix is computed once
    per clock instead of being a deep combinational cone on the output ports.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# --- 1. register the render outputs ----------------------------------------
s = s.replace(
    "    signal mv     : std_logic := '0';\n"
    "    signal solved_r  : std_logic;\n"
    "    signal alllock_r : std_logic;\n",
    "    signal mv     : std_logic := '0';\n"
    "    signal solved_r  : std_logic;\n"
    "    signal alllock_r : std_logic;\n"
    "    signal red_r     : std_logic_vector(63 downto 0) := (others => '0');\n"
    "    signal grn_r     : std_logic_vector(63 downto 0) := (others => '0');\n"
    "    signal kcol_r    : std_logic_vector(63 downto 0) := (others => '0');\n")

# --- 2. render: compute kcol combinationally but register the outputs -------
old_render = s[s.index("    -- RENDER: selected -> green"):s.index("    ----------------------------------------------------------------------------\n    -- Scatter candidate lookup.")]
new_render = """    -- RENDER.
    -- Three colours from two bit-planes: selected -> GREEN, locked -> YELLOW
    -- (red AND green), everything else inside the picture -> RED ghost.
    -- The mixed result is REGISTERED: computing it combinationally straight onto
    -- the output pins made the synthesiser build a deep cone on 128 output bits
    -- and cost far more logic than the register does.
    ----------------------------------------------------------------------------
    process (m0, m1, m2, m3, locked, sel, i_level)
        variable kc : std_logic_vector(63 downto 0);
    begin
        kc := (others => '0');
        if (locked(0) = '1') or (sel = "00") then kc := kc or m0; end if;
        if (locked(1) = '1') or (sel = "01") then kc := kc or m1; end if;
        if (locked(2) = '1') or (sel = "10") then kc := kc or m2; end if;
        if (i_level = '1') then
            if (locked(3) = '1') or (sel = "11") then kc := kc or m3; end if;
        end if;
        kcol_r <= kc;
    end process;

    process (i_clk)
        variable cov : std_logic_vector(63 downto 0);
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                red_r <= (others => '0');
                grn_r <= (others => '0');
            else
                cov := m0 or m1 or m2;
                if (i_level = '1') then
                    cov := cov or m3;
                end if;
                red_r <= cov or (i_target and (not cov));
                grn_r <= kcol_r;
            end if;
        end if;
    end process;

    o_px_red <= red_r;
    o_px_grn <= grn_r;

"""
s = s.replace(old_render, new_render)

p.write_text(s, encoding="utf-8")
print("patched")
print("o_px_red assignments:", s.count("o_px_red <="))
