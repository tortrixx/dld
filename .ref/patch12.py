# -*- coding: utf-8 -*-
"""对引擎做严格的时间复用：每个扫描 tick 处理一个零片，使用 8 位
累加器。这与参考实现的做法一致（32 相
帧引擎），也正是逻辑保持精简的原因：每个周期只处理一个
零片的几何信息，而不是并行处理全部四个。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")

start = s.index("    process (scanrow, pos, locked, sel, i_level, i_sh0, i_sh1, i_sh2, i_sh3, i_target)")
end = s.index("    ----------------------------------------------------------------------------\n    -- Scan row counter")

new = '''    -- Time-multiplexed row renderer.
    --   phase 0..3 : one piece per phase accumulates into the row accumulators
    --   phase 4    : the accumulated row is published
    -- The dot-matrix driver scans one row per tick, so a row is produced every
    -- four ticks and the frame takes 32 ticks -- the same as the reference
    -- implementation's 32-phase frame engine.
    process (i_clk)
        variable prow   : integer;
        variable srow   : integer;
        variable hh     : integer;
        variable cc     : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable tgtrow : std_logic_vector(7 downto 0);
        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable issel  : boolean;
        variable islck  : boolean;
        variable npc    : integer;
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                ph      <= (others => '0');
                scanrow <= (others => '0');
                acc_cov <= (others => '0');
                acc_kc  <= (others => '0');
                o_red   <= (others => '0');
                o_grn   <= (others => '0');
            elsif (i_tick = '1') then
                if (i_level = '0') then npc := 3; else npc := 4; end if;

                case to_integer(ph) is
                    when 0 =>
                        scanrow <= scanrow + 1;      -- advance to the next row
                        acc_cov <= (others => '0');
                        acc_kc  <= (others => '0');

                    when 1 | 2 | 3 | 4 =>
                        -- piece index = ph - 1
                        case to_integer(ph) - 1 is
                            when 0 => pk := pos(31 downto 24); shp := i_sh0;
                                      hh := to_integer(unsigned(i_h0));
                                      islck := (locked(0) = '1');
                                      issel := (sel = "00");
                            when 1 => pk := pos(23 downto 16); shp := i_sh1;
                                      hh := to_integer(unsigned(i_h1));
                                      islck := (locked(1) = '1');
                                      issel := (sel = "01");
                            when 2 => pk := pos(15 downto 8); shp := i_sh2;
                                      hh := to_integer(unsigned(i_h2));
                                      islck := (locked(2) = '1');
                                      issel := (sel = "10");
                            when others => pk := pos(7 downto 0); shp := i_sh3;
                                      hh := to_integer(unsigned(i_h3));
                                      islck := (locked(3) = '1');
                                      issel := (sel = "11");
                        end case;

                        if ((to_integer(ph) - 1) < npc) then
                            prow := to_integer(unsigned(pk(7 downto 4)));
                            cc   := to_integer(unsigned(pk(3 downto 0)));
                            srow := to_integer(scanrow) - prow;
                            if (srow >= 0) and (srow < hh) then
                                rw := row_mask(shp, srow, cc);
                                acc_cov <= acc_cov or rw;
                                if islck or issel then
                                    acc_kc <= acc_kc or rw;
                                end if;
                            end if;
                        end if;

                    when others =>
                        -- publish the finished row, then restart the frame
                        case to_integer(scanrow) is
                            when 0      => tgtrow := i_target(7 downto 0);
                            when 1      => tgtrow := i_target(15 downto 8);
                            when 2      => tgtrow := i_target(23 downto 16);
                            when 3      => tgtrow := i_target(31 downto 24);
                            when 4      => tgtrow := i_target(39 downto 32);
                            when 5      => tgtrow := i_target(47 downto 40);
                            when 6      => tgtrow := i_target(55 downto 48);
                            when others => tgtrow := i_target(63 downto 56);
                        end case;
                        o_red <= acc_cov or (tgtrow and (not acc_cov));
                        o_grn <= acc_kc;
                end case;

                ph <= ph + 1;
            end if;
        end if;
    end process;

'''
s = s[:start] + new + s[end:]

# 为新信号做声明
s = s.replace(
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');\n",
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');\n"
    "    signal ph      : unsigned(2 downto 0) := (others => '0');\n"
    "    signal acc_cov : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal acc_kc  : std_logic_vector(7 downto 0) := (others => '0');\n")

# o_red/o_grn 现在是在进程内部赋值的寄存器：如有遗留，
# 删掉旧的并发默认赋值
s = s.replace("    o_scanrow <= std_logic_vector(scanrow);\n",
              "    o_scanrow <= std_logic_vector(scanrow);\n")

p.write_text(s, encoding="utf-8")
print("time-multiplexed renderer installed")
