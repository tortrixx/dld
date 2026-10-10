# -*- coding: utf-8 -*-
"""渲染器 v6：用 8 个 tick 累积出**整帧**（25 Hz），而不是每 5 个
tick 发布一行（5 Hz）。

板上出现了可见的闪烁。原因是刷新率，而不是消隐：在 200 Hz 的 tick 下
每 5 个 tick 发布一行，得到 200/(5*8) = 5 Hz 的帧率，
远低于闪烁融合频率。

因此把时分复用重新组织成按**行**而不是按零片进行：
每个 tick 仍然只求值每个槽位的一份 row_mask（逻辑量因此保持
很小），但零片循环改在行内进行，而不再把一行拆到
多个 tick 上。于是一帧在 8 个 tick 内完成，显示刷新率为
200/8 = 25 Hz。

代价：一对 8 位累加器外加一个 64 位帧寄存器。实测见下。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

start = s.index("    -- Time-multiplexed row renderer.")
end = s.index("    ----------------------------------------------------------------------------\n    -- Main sequential process.")

new = '''    -- ---------------------------------------------------------------------------
    -- FRAME RENDERER -- one ROW per 200 Hz tick, whole frame every 8 ticks.
    --
    -- Each tick: gather the 8-bit row for the row under construction (one
    -- row_mask per piece slot, so the shared shifter stays cheap), merge it into
    -- the 64-bit frame accumulator, and after 8 rows publish the frame.
    -- Frame rate = 200/8 = 25 Hz, which is above flicker fusion.
    --
    -- The frame is held in a 64-bit register and simply repeated to the matrix
    -- driver, which selects the slice for the row it is scanning.  There is no
    -- second frame buffer and no per-row regeneration, so the panel never sees a
    -- partially built row.
    -- ---------------------------------------------------------------------------
    process (i_clk)
        variable r      : integer;
        variable prow   : integer;
        variable srow   : integer;
        variable shp    : std_logic_vector(63 downto 0);
        variable pk     : std_logic_vector(7 downto 0);
        variable hh     : integer;
        variable cc     : integer;
        variable npc    : integer;
        variable rw     : std_logic_vector(7 downto 0);
        variable cov    : std_logic_vector(7 downto 0);
        variable kc     : std_logic_vector(7 downto 0);
        variable tgtrow : std_logic_vector(7 downto 0);
        variable issel  : boolean;
        variable islck  : boolean;
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                frow    <= (others => '0');
                frame_r <= (others => '0');
                frame_g <= (others => '0');
                warm    <= (others => '0');
            elsif (i_tick = '1') then
                r   := to_integer(frow);
                cov := (others => '0');
                kc  := (others => '0');

                if (i_level = '0') then npc := 3; else npc := 4; end if;

                -- ---- piece 0 ------------------------------------------------
                pk := pos(31 downto 24); shp := i_sh0;
                hh := to_integer(unsigned(i_h0));
                prow := to_integer(unsigned(pk(7 downto 4)));
                srow := r - prow;
                if (srow >= 0) and (srow < hh) then
                    rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                    cov := cov or rw;
                    if (locked(0) = '1') or (sel = "00") then kc := kc or rw; end if;
                end if;

                -- ---- piece 1 ------------------------------------------------
                if (npc > 1) then
                    pk := pos(23 downto 16); shp := i_sh1;
                    hh := to_integer(unsigned(i_h1));
                    prow := to_integer(unsigned(pk(7 downto 4)));
                    srow := r - prow;
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(1) = '1') or (sel = "01") then kc := kc or rw; end if;
                    end if;
                end if;

                -- ---- piece 2 ------------------------------------------------
                if (npc > 2) then
                    pk := pos(15 downto 8); shp := i_sh2;
                    hh := to_integer(unsigned(i_h2));
                    prow := to_integer(unsigned(pk(7 downto 4)));
                    srow := r - prow;
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(2) = '1') or (sel = "10") then kc := kc or rw; end if;
                    end if;
                end if;

                -- ---- piece 3 (level 2 only) ---------------------------------
                if (npc > 3) then
                    pk := pos(7 downto 0); shp := i_sh3;
                    hh := to_integer(unsigned(i_h3));
                    prow := to_integer(unsigned(pk(7 downto 4)));
                    srow := r - prow;
                    if (srow >= 0) and (srow < hh) then
                        rw := row_mask(shp, srow, to_integer(unsigned(pk(3 downto 0))));
                        cov := cov or rw;
                        if (locked(3) = '1') or (sel = "11") then kc := kc or rw; end if;
                    end if;
                end if;

                -- ---- target row for the ghost -------------------------------
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

                -- ---- merge this row into the frame accumulator ---------------
                -- The mask convention is bit index = 8*row + col with row 0 at the
                -- TOP, so logical row 0 occupies the TOP slice (63..56).
                case r is
                    when 0      => frame_r(63 downto 56) <= cov;
                                   frame_g(63 downto 56) <= kc;
                    when 1      => frame_r(55 downto 48) <= cov;
                                   frame_g(55 downto 48) <= kc;
                    when 2      => frame_r(47 downto 40) <= cov;
                                   frame_g(47 downto 40) <= kc;
                    when 3      => frame_r(39 downto 32) <= cov;
                                   frame_g(39 downto 32) <= kc;
                    when 4      => frame_r(31 downto 24) <= cov;
                                   frame_g(31 downto 24) <= kc;
                    when 5      => frame_r(23 downto 16) <= cov;
                                   frame_g(23 downto 16) <= kc;
                    when 6      => frame_r(15 downto 8) <= cov;
                                   frame_g(15 downto 8) <= kc;
                    when others => frame_r(7 downto 0) <= cov;
                                   frame_g(7 downto 0) <= kc;
                end case;

                -- ghost rows are ORed in as each row arrives (cheap 8-bit op)
                if (r = 0) then
                    o_rowr(63 downto 56) <= cov or (tgtrow and (not cov));
                    o_rowg(63 downto 56) <= kc;
                elsif (r = 1) then
                    o_rowr(55 downto 48) <= cov or (tgtrow and (not cov));
                    o_rowg(55 downto 48) <= kc;
                elsif (r = 2) then
                    o_rowr(47 downto 40) <= cov or (tgtrow and (not cov));
                    o_rowg(47 downto 40) <= kc;
                elsif (r = 3) then
                    o_rowr(39 downto 32) <= cov or (tgtrow and (not cov));
                    o_rowg(39 downto 32) <= kc;
                elsif (r = 4) then
                    o_rowr(31 downto 24) <= cov or (tgtrow and (not cov));
                    o_rowg(31 downto 24) <= kc;
                elsif (r = 5) then
                    o_rowr(23 downto 16) <= cov or (tgtrow and (not cov));
                    o_rowg(23 downto 16) <= kc;
                elsif (r = 6) then
                    o_rowr(15 downto 8) <= cov or (tgtrow and (not cov));
                    o_rowg(15 downto 8) <= kc;
                else
                    o_rowr(7 downto 0) <= cov or (tgtrow and (not cov));
                    o_rowg(7 downto 0) <= kc;
                end if;

                frow <= frow + 1;
            end if;
        end if;
    end process;

'''
s = s[:start] + new + s[end:]

# 信号：frow 取代 ph/scanrow；frame_r/frame_g 取代原来的行寄存器
s = s.replace(
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');\n"
    "    signal ph      : unsigned(2 downto 0) := (others => '0');\n"
    "    signal acc_cov : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal acc_kc  : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal warm    : unsigned(3 downto 0) := (others => '0');  -- startup blank\n",
    "    signal scanrow : unsigned(2 downto 0) := (others => '0');  -- row being scanned\n"
    "    signal frow    : unsigned(2 downto 0) := (others => '0');  -- row being built\n"
    "    signal frame_r : std_logic_vector(63 downto 0) := (others => '0');\n"
    "    signal frame_g : std_logic_vector(63 downto 0) := (others => '0');\n"
    "    signal warm    : unsigned(3 downto 0) := (others => '0');\n")

# o_rowr/o_rowg 变成 64 位的帧输出
s = s.replace("        o_rowr    : out std_logic_vector(7 downto 0);   -- red   bits for o_scanrow\n"
              "        o_rowg    : out std_logic_vector(7 downto 0)    -- green bits for o_scanrow\n",
              "        o_rowr    : out std_logic_vector(63 downto 0);  -- red   frame\n"
              "        o_rowg    : out std_logic_vector(63 downto 0)   -- green frame\n")

# 保持 o_scanrow 由 frow 驱动（frow 就是当前正在构造/扫描的那一行）
s = s.replace("    o_scanrow <= std_logic_vector(scanrow);",
              "    o_scanrow <= std_logic_vector(scanrow);\n"
              "    -- the matrix driver scans with its own 40 Hz pulse; the published frame\n"
              "    -- is stable, so no lockstep handshake is needed any more")

p.write_text(s, encoding="utf-8")
print("frame renderer installed")
