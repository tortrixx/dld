# -*- coding: utf-8 -*-
"""给引擎加流水，以满足 50 MHz 的要求。

实测：设计能装下（1028/1270 LE），但 TimeQuest 只报出 38.98 MHz
（关键路径 25.65 ns，起点 sh_k）。长路径都在散落数据通路上：
    cand = (rnd_val mod (8-h)) & (rnd_val mod (8-w))
这一串是从 sh_k 组合算出来的，后面还跟着范围检查和写入。散落
序列器本来就要跑很多个周期，所以把这份工作拆到两个时钟、并把中间值
寄存起来不花任何代价。

修订：SH_TRY 现在只**锁存** cand/hh/ww（不做有效性检查）；有效性检查
推迟一个时钟、挪到新增的 SH_CHK 状态，那里操作数是寄存器的
输出，而不是 sh_k 的函数。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 1. 新增状态
s = s.replace("    type sh_t is (SH_IDLE, SH_TRY, SH_NEXT, SH_DONE);",
              "    type sh_t is (SH_IDLE, SH_TRY, SH_CHK, SH_NEXT, SH_DONE);")

# 2. 寄存后的散落操作数
s = s.replace(
    "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');",
    "    signal chk_w    : std_logic_vector(2 downto 0) := (others => '0');\n"
    "    -- registered scatter operands (pipelining -- see the header note)\n"
    "    signal sc_hh    : std_logic_vector(2 downto 0) := (others => '0');\n"
    "    signal sc_ww    : std_logic_vector(2 downto 0) := (others => '0');\n"
    "    signal sc_cand  : std_logic_vector(7 downto 0) := (others => '0');\n"
    "    signal sc_ok    : std_logic := '0';")

# 3. SH_TRY：只锁存
old_try = s[s.index("                if (sh = SH_TRY) and (chk = CH_IDLE) then"):
            s.index("                ----------------------------------------------------------------\n                -- (4) Overlap engine: one panel row per tick")]
new_try = """                if (sh = SH_TRY) and (chk = CH_IDLE) then
                    rnd_step <= '1';

                    case to_integer(sh_k) is
                        when 0      => hh := to_integer(unsigned(i_h0)); ww := to_integer(unsigned(i_w0));
                        when 1      => hh := to_integer(unsigned(i_h1)); ww := to_integer(unsigned(i_w1));
                        when 2      => hh := to_integer(unsigned(i_h2)); ww := to_integer(unsigned(i_w2));
                        when others => hh := to_integer(unsigned(i_h3)); ww := to_integer(unsigned(i_w3));
                    end case;

                    ch := 8 - hh;  if (ch < 1) then ch := 1; end if;
                    cw := 8 - ww;  if (cw < 1) then cw := 1; end if;

                    -- Pipeline stage 1: latch the operands and the two modulo
                    -- results.  The modulo is the expensive part of the critical
                    -- path, so it is evaluated here and consumed one cycle later
                    -- in SH_CHK rather than being chained into the validity test.
                    sc_hh   <= std_logic_vector(to_unsigned(hh, 3));
                    sc_ww   <= std_logic_vector(to_unsigned(ww, 3));
                    sc_cand <= std_logic_vector(to_unsigned(
                                   to_integer(unsigned(rnd_val(2 downto 0))) mod ch, 4)) &
                               std_logic_vector(to_unsigned(
                                   to_integer(unsigned(rnd_val(5 downto 3))) mod cw, 4));
                    sh <= SH_CHK;
                end if;

                ----------------------------------------------------------------
                -- Pipeline stage 2: start the overlap check on the registered
                -- operand set.
                ----------------------------------------------------------------
                if (sh = SH_CHK) and (chk = CH_IDLE) then
                    case to_integer(sh_k) is
                        when 0      => shp := i_sh0;
                        when 1      => shp := i_sh1;
                        when 2      => shp := i_sh2;
                        when others => shp := i_sh3;
                    end case;

                    chk_pos <= sc_cand;
                    chk_shp <= shp;
                    chk_h   <= sc_hh;
                    chk_w   <= sc_ww;
                    chk_kind <= '1';                     -- '1' = scatter
                    chk     <= CH_RUN;
                    chk_row <= (others => '0');
                    chk_hit <= '0';
                end if;

"""
s = s.replace(old_try, new_try)

p.write_text(s, encoding="utf-8")
print("scatter pipelined; SH_CHK present:", "SH_CHK" in s)
