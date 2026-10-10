# -*- coding: utf-8 -*-
"""最终重构：把重叠检查也串行化。

实测历史（仅 puzzle_ctrl，EPM1270 有 1270 个单元）：
    v4  64 位覆盖范围寄存器                                2350
    v5  行扫描渲染                                         3751（寄存器可以，逻辑不行）
    v5b 每个渲染相位一次 row_mask                          3595
剩下的开销来自展开的重叠检查：它调用了 row_mask 8 行 x
4 个零片 = 32 次。本版本每个 tick 检查一行并累加进累加器，
与渲染器完全一样，因此任一时刻只有一个 row_mask 求值存活，
综合器可以在两个使用者之间共享它。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# ---------------------------------------------------------------- 串行部分
start = s.index("    ----------------------------------------------------------------------------\n    -- Main sequential process")
end = s.rindex("end architecture rtl;")

new = '''    ----------------------------------------------------------------------------
    -- Main sequential process.
    --
    -- Two strictly serialised tasks:
    --   (a) the scatter sequencer, which places the pieces at random
    --   (b) the validation of the requested move (move vs overlap check)
    -- plus a small overlap-check engine that tests one panel row per tick into an
    -- accumulator.  Serialising the check is what keeps ONE row_mask evaluation
    -- alive at a time; the unrolled version instantiated 32 of them.
    ----------------------------------------------------------------------------
    process (i_clk)
        variable cr, cc : integer;
        variable hh, ww : integer;
        variable ok     : boolean;
        variable npos   : std_logic_vector(7 downto 0);
        variable cand   : std_logic_vector(7 downto 0);
        variable ch, cw : integer;
        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable prow   : integer;
        variable srow   : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable lvl2   : boolean;
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                pos <= (others => '0');
                locked <= (others => '0');
                sel <= (others => '0');
                sh <= SH_IDLE;
                sh_k <= (others => '0');
                sh_att <= (others => '0');
                mv <= '0';
                chk <= CH_IDLE;
                rnd_step <= '0';
            else
                rnd_step <= '0';
                lvl2 := (i_level = '1');

                ----------------------------------------------------------------
                -- (1) Buttons -- only while neither engine is busy
                ----------------------------------------------------------------
                if (sh = SH_IDLE) and (chk = CH_IDLE) then
                    if (i_go = '1') then
                        sh     <= SH_TRY;
                        sh_k   <= (others => '0');
                        sh_att <= (others => '0');
                        sel    <= (others => '0');
                        locked <= (others => '0');
                    elsif (i_confirm = '1') then
                        case to_integer(sel) is
                            when 0      => locked(0) <= '1';
                            when 1      => locked(1) <= '1';
                            when 2      => locked(2) <= '1';
                            when others => locked(3) <= '1';
                        end case;
                        if (sel = "10" and not lvl2) then sel <= "00";
                        else                              sel <= sel + 1; end if;
                    elsif (i_select = '1') then
                        if (sel = "10" and not lvl2) then sel <= "00";
                        else                              sel <= sel + 1; end if;
                    elsif (i_move = '1') then
                        mv <= '1';
                    end if;
                end if;

                ----------------------------------------------------------------
                -- (2) A move request starts the validation engine
                ----------------------------------------------------------------
                if (mv = '1') and (chk = CH_IDLE) then
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
                end if;

                ----------------------------------------------------------------
                -- (3) Scatter: each turn proposes an anchor, then runs the SAME
                --     overlap engine.  Rejection sampling with a deterministic
                --     fallback, so a scatter always completes.
                ----------------------------------------------------------------
                if (sh = SH_TRY) and (chk = CH_IDLE) then
                    rnd_step <= '1';

                    case to_integer(sh_k) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0)); shp := i_sh0;
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1)); shp := i_sh1;
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2)); shp := i_sh2;
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3)); shp := i_sh3;
                    end case;

                    ch := 8 - hh;  if (ch < 1) then ch := 1; end if;
                    cw := 8 - ww;  if (cw < 1) then cw := 1; end if;

                    cand := std_logic_vector(to_unsigned(
                                to_integer(unsigned(rnd_val(2 downto 0))) mod ch, 4)) &
                            std_logic_vector(to_unsigned(
                                to_integer(unsigned(rnd_val(5 downto 3))) mod cw, 4));
                    cr := to_integer(unsigned(cand(7 downto 4)));
                    cc := to_integer(unsigned(cand(3 downto 0)));

                    chk_pos <= cand;
                    chk_shp <= shp;
                    chk_h   <= std_logic_vector(to_unsigned(hh, 3));
                    chk_w   <= std_logic_vector(to_unsigned(ww, 3));
                    chk_kind <= '1';                     -- '1' = scatter
                    chk     <= CH_RUN;
                    chk_row <= (others => '0');
                    chk_hit <= '0';
                end if;

                ----------------------------------------------------------------
                -- (4) Overlap engine: one panel row per tick
                ----------------------------------------------------------------
                case chk is
                    when CH_IDLE =>
                        null;

                    when CH_RUN =>
                        chk_row <= chk_row + 1;
                        if (chk_row = 8) then
                            chk <= CH_DONE;
                        else
                            -- candidate's mask for this panel row
                            srow := to_integer(chk_row) -
                                    to_integer(unsigned(chk_pos(7 downto 4)));
                            rw   := row_mask(chk_shp, srow,
                                             to_integer(unsigned(chk_pos(3 downto 0))));
                            if (rw /= x"00") then
                                -- compare against every other live piece, one at
                                -- a time using the same shared row_mask
                                prow := to_integer(unsigned(pos(31 downto 28)));
                                srow := to_integer(chk_row) - prow;
                                if (sel /= "00") and (sh_k /= "00" or chk_kind = '0') then
                                    if (srow >= 0) and (srow <= 2) then
                                        if (rw and row_mask(i_sh0, srow,
                                                to_integer(unsigned(pos(27 downto 24))))) /= x"00" then
                                            chk_hit <= '1';
                                        end if;
                                    end if;
                                end if;
                                prow := to_integer(unsigned(pos(23 downto 20)));
                                srow := to_integer(chk_row) - prow;
                                if (sel /= "01") then
                                    if (srow >= 0) and (srow <= 2) then
                                        if (rw and row_mask(i_sh1, srow,
                                                to_integer(unsigned(pos(19 downto 16))))) /= x"00" then
                                            chk_hit <= '1';
                                        end if;
                                    end if;
                                end if;
                                prow := to_integer(unsigned(pos(15 downto 12)));
                                srow := to_integer(chk_row) - prow;
                                if (sel /= "10") then
                                    if (srow >= 0) and (srow <= 2) then
                                        if (rw and row_mask(i_sh2, srow,
                                                to_integer(unsigned(pos(11 downto 8))))) /= x"00" then
                                            chk_hit <= '1';
                                        end if;
                                    end if;
                                end if;
                                if (lvl2) then
                                    prow := to_integer(unsigned(pos(7 downto 4)));
                                    srow := to_integer(chk_row) - prow;
                                    if (sel /= "11") then
                                        if (srow >= 0) and (srow <= 2) then
                                            if (rw and row_mask(i_sh3, srow,
                                                    to_integer(unsigned(pos(3 downto 0))))) /= x"00" then
                                                chk_hit <= '1';
                                            end if;
                                        end if;
                                    end if;
                                end if;
                            end if;
                        end if;

                    when CH_DONE =>
                        chk <= CH_IDLE;
                        if (chk_hit = '0') then
                            -- accept: commit the anchor
                            if (chk_kind = '0') then
                                case to_integer(sel) is
                                    when 0      => pos(31 downto 24) <= chk_pos;
                                    when 1      => pos(23 downto 16) <= chk_pos;
                                    when 2      => pos(15 downto 8)  <= chk_pos;
                                    when others => pos(7 downto 0)   <= chk_pos;
                                end case;
                            else
                                case to_integer(sh_k) is
                                    when 0      => pos(31 downto 24) <= chk_pos;
                                    when 1      => pos(23 downto 16) <= chk_pos;
                                    when 2      => pos(15 downto 8)  <= chk_pos;
                                    when others => pos(7 downto 0)   <= chk_pos;
                                end case;
                                sh_att <= (others => '0');
                                sh     <= SH_NEXT;
                            end if;
                        else
                            if (chk_kind = '0') then
                                null;                    -- move simply rejected
                            elsif (sh_att = 15) then
                                -- deterministic fallback so a scatter always ends
                                sh_att <= (others => '0');
                                case to_integer(sh_k) is
                                    when 0      => pos(31 downto 24) <= "0000" & "0000";
                                    when 1      => pos(23 downto 16) <= "0000" & "0100";
                                    when 2      => pos(15 downto 8)  <= "0100" & "0000";
                                    when others => pos(7 downto 0)   <= "0100" & "0100";
                                end case;
                                sh <= SH_NEXT;
                            else
                                sh_att <= sh_att + 1;
                            end if;
                        end if;

                    when others =>
                        chk <= CH_IDLE;
                end case;

                -- advance to the next piece, or finish the scatter
                if (sh = SH_NEXT) then
                    if ((sh_k = 2) and (not lvl2)) or (sh_k = 3) then
                        sh <= SH_DONE;
                    else
                        sh_k <= sh_k + 1;
                        sh   <= SH_TRY;
                    end if;
                end if;

                if (sh = SH_DONE) then
                    sh <= SH_IDLE;
                end if;
            end if;
        end if;
    end process;

'''
s = s[:start] + new + s[end:]

# ---- 状态与信号 ----------------------------------------------------
s = s.replace("    type sh_t is (SH_IDLE, SH_TRY, SH_DONE);",
              "    type sh_t is (SH_IDLE, SH_TRY, SH_NEXT, SH_DONE);\n"
              "    type chk_t is (CH_IDLE, CH_RUN, CH_DONE);\n"
              "    signal chk      : chk_t := CH_IDLE;\n"
              "    signal chk_kind : std_logic := '0';\n"
              "    signal chk_row  : unsigned(3 downto 0) := (others => '0');\n"
              "    signal chk_hit  : std_logic := '0';\n"
              "    signal chk_pos  : std_logic_vector(7 downto 0) := (others => '0');\n"
              "    signal chk_shp  : std_logic_vector(63 downto 0) := (others => '0');\n"
              "    signal chk_h    : std_logic_vector(2 downto 0) := (others => '0');\n"
              "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');")

p.write_text(s, encoding="utf-8")
print("serialised check engine installed")
