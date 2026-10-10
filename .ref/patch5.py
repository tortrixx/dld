# -*- coding: utf-8 -*-
"""修补 puzzle_ctrl：
  * 每个周期把被选中零片的覆盖形状/外形解析进**寄存器**一次
    （一个 64 位 4 选 1 多路器只求值一次，而不是求值多次），
  * 把渲染输出（红/绿）寄存起来，使颜色混合每个时钟只算一次，
    而不是在输出端口上形成很深的组合逻辑锥。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# --- 1. 寄存渲染输出 ----------------------------------------
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

# --- 2. 渲染：kcol 用组合逻辑算，但输出要寄存 -------
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
