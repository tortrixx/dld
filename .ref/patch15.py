# -*- coding: utf-8 -*-
"""Renderer timing: publish one display row per 5 ticks of the 200 Hz tick, and
hold the output blank during the first frame so no garbage is ever drawn."""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 启动空白计数器 + 已发布行的寄存器
s = s.replace(
    "    signal acc_kc  : std_logic_vector(7 downto 0) := (others => '0');\n",
    "    signal acc_kc  : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal warm    : unsigned(3 downto 0) := (others => '0');  -- startup blank\n")

# 渲染器进程：让相位 0 推进 scanrow，并在预热期间保持空白
s = s.replace(
    """                case to_integer(ph) is
                    when 0 =>
                        scanrow <= scanrow + 1;      -- advance to the next row
                        acc_cov <= (others => '0');
                        acc_kc  <= (others => '0');
""",
    """                case to_integer(ph) is
                    when 0 =>
                        scanrow <= scanrow + 1;      -- advance to the next row
                        acc_cov <= (others => '0');
                        acc_kc  <= (others => '0');
""")

s = s.replace(
    """                    when others =>
                        -- publish the finished row, then restart the frame
                        case to_integer(scanrow) is""",
    """                    when others =>
                        -- publish the finished row; the matrix driver samples it
                        -- on its 40 Hz tick, i.e. once per published row
                        case to_integer(scanrow) is""")

# 用预热计数器对已发布的输出做门控
s = s.replace(
    """                        o_red <= acc_cov or (tgtrow and (not acc_cov));
                        o_grn <= acc_kc;
                end case;

                ph <= ph + 1;""",
    """                        if (warm = 0) then
                            -- first frame: stay dark rather than show a partially
                            -- built row (the accumulator is 8-bit, so a 64-bit
                            -- shift would be needed to blank it properly)
                            o_red <= (others => '0');
                            o_grn <= (others => '0');
                        else
                            o_red <= acc_cov or (tgtrow and (not acc_cov));
                            o_grn <= acc_kc;
                        end if;
                end case;

                ph <= ph + 1;""")

# 在复位分支 / 正常分支中驱动预热计数器
s = s.replace(
    """            if (i_rst = '1') then
                ph      <= (others => '0');
                scanrow <= (others => '0');
                acc_cov <= (others => '0');
                acc_kc  <= (others => '0');
                o_red   <= (others => '0');
                o_grn   <= (others => '0');
            elsif (i_tick = '1') then""",
    """            if (i_rst = '1') then
                ph      <= (others => '0');
                scanrow <= (others => '0');
                acc_cov <= (others => '0');
                acc_kc  <= (others => '0');
                warm    <= (others => '0');
                o_red   <= (others => '0');
                o_grn   <= (others => '0');
            elsif (i_tick = '1') then
                -- warm-up: one full frame (8 rows x 5 ticks) must be produced
                -- before the panel is switched on, so a partially built row can
                -- never be displayed
                if (warm /= 15) then
                    warm <= warm + 1;
                end if;""")

p.write_text(s, encoding="utf-8")
print("renderer timing patched")
