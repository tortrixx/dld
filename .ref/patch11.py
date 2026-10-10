# -*- coding: utf-8 -*-
"""把渲染循环中按变量下标取行的写法换成显式的带保护分支，
与参考实现所用的技巧一致：每个 tick 处理一行，使用 8 位累加器，
不对宽向量做可变切片。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

start = s.index("    process (scanrow, pos, locked, sel, i_level, i_sh0, i_sh1, i_sh2, i_sh3, i_target)")
end = s.index("    ----------------------------------------------------------------------------\n    -- Scan row counter")

new = '''    process (scanrow, pos, locked, sel, i_level, i_sh0, i_sh1, i_sh2, i_sh3, i_target)
        variable r      : integer;
        variable prow   : integer;
        variable srow   : integer;
        variable hh     : integer;
        variable cc     : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable cov    : std_logic_vector(7 downto 0);
        variable kc     : std_logic_vector(7 downto 0);
        variable tgtrow : std_logic_vector(7 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable npc    : integer;
    begin
        r   := to_integer(scanrow);
        cov := (others => '0');
        kc  := (others => '0');

        -- target row for the ghost
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

        if (i_level = '0') then npc := 3; else npc := 4; end if;

        -- ---- piece 0 -------------------------------------------------------
        prow := to_integer(unsigned(pos(31 downto 28)));
        srow := r - prow;
        if (srow >= 0) and (srow < to_integer(unsigned(i_h0))) then
            rw  := row_mask(i_sh0, srow, to_integer(unsigned(pos(27 downto 24))));
            cov := cov or rw;
            if (locked(0) = '1') or (sel = "00") then kc := kc or rw; end if;
        end if;

        -- ---- piece 1 -------------------------------------------------------
        if (npc > 1) then
            prow := to_integer(unsigned(pos(23 downto 20)));
            srow := r - prow;
            if (srow >= 0) and (srow < to_integer(unsigned(i_h1))) then
                rw  := row_mask(i_sh1, srow, to_integer(unsigned(pos(19 downto 16))));
                cov := cov or rw;
                if (locked(1) = '1') or (sel = "01") then kc := kc or rw; end if;
            end if;
        end if;

        -- ---- piece 2 -------------------------------------------------------
        if (npc > 2) then
            prow := to_integer(unsigned(pos(15 downto 12)));
            srow := r - prow;
            if (srow >= 0) and (srow < to_integer(unsigned(i_h2))) then
                rw  := row_mask(i_sh2, srow, to_integer(unsigned(pos(11 downto 8))));
                cov := cov or rw;
                if (locked(2) = '1') or (sel = "10") then kc := kc or rw; end if;
            end if;
        end if;

        -- ---- piece 3 (level 2 only) ----------------------------------------
        if (npc > 3) then
            prow := to_integer(unsigned(pos(7 downto 4)));
            srow := r - prow;
            if (srow >= 0) and (srow < to_integer(unsigned(i_h3))) then
                rw  := row_mask(i_sh3, srow, to_integer(unsigned(pos(3 downto 0))));
                cov := cov or rw;
                if (locked(3) = '1') or (sel = "11") then kc := kc or rw; end if;
            end if;
        end if;

        o_red <= cov or (tgtrow and (not cov));
        o_grn <= kc;
    end process;

'''
s = s[:start] + new + s[end:]
p.write_text(s, encoding="utf-8")
print("render replaced")
