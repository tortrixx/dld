# -*- coding: utf-8 -*-
"""修复 1（干净版）—— keypad_scan 的本轮捕获。

已确认的缺陷
  D1  时序器停留在 ST_IDLE 期间（约 250 000 个时钟），而 round_code 在
      每个时钟都被清零，消抖级却只在 200 Hz tick 上采样它。捕获到的值
      只存活一个时钟，所以采样器读到的永远是 K_NONE，o_key 恒为 0——
      这恰恰就是实测现象
      「按任何键都没有反应」。
  D2  只有第 3 相（第 3 列）会被捕获，所以第 0..2 列的按键
      完全看不到。

修复
  * 取本轮任意已稳定相位的首次命中；
  * 保持到下一轮开始，这样消抖级（在 tick 上采样，约 5 ms 之后）
    才能真正看到它，而「连续 N 轮稳定」也终于
    有了意义。
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\keypad_scan.vhd")
s = p.read_text(encoding="utf-8")

# --- 定位整个行采样进程体 -----------------------------
start = s.index("            if (i_rst = '1') then\n                raw_hit    <= '0';")
end = s.index("    end process;", start)
body = '''            if (i_rst = '1') then
                raw_hit    <= '0';
                raw_code   <= K_NONE;
                round_code <= K_NONE;
                round_seen <= '0';
            else
                -- Combinational view of the currently settled phase.
                -- NOTE: a for loop with last-assignment-wins means the HIGHEST
                -- matching row index is reported when more than one row reads
                -- active (which should not happen for a sane keypad, but is
                -- deterministic if it does).
                raw_hit  <= '0';
                raw_code <= K_NONE;
                for r in 0 to 3 loop
                    if (i_row(r) = KP_ACTIVE) then
                        raw_hit  <= '1';
                        raw_code <= std_logic_vector(
                                        to_unsigned(4 * to_integer(phase) + r, 4));
                    end if;
                end loop;

                -- (1) publish the finished round: the tick is precisely the edge
                --     at which the sequencer leaves ST_IDLE and starts the next
                --     round, so at this moment round_code still holds what the
                --     round that just ended captured.
                if (i_tick = '1') and (state = ST_IDLE) then
                    round_code <= round_hold;     -- hand the result to debounce
                    round_seen <= '0';            -- re-arm for the new round
                end if;

                -- (2) capture the FIRST hit of any settled scan phase.
                --     Previously only (state = ST_SCAN and phase = 3) was taken,
                --     which hid columns 0..2 entirely.
                if (state = ST_SCAN) and (raw_hit = '1') and (round_seen = '0') then
                    round_hold <= raw_code;
                    round_seen <= '1';
                end if;
            end if;
'''
s = s[:start] + body + s[end:]

# --- 新信号 -------------------------------------------------------------
s = s.replace("    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- key seen in this round",
              "    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- result of the LAST round\n"
              "    signal round_hold : std_logic_vector(3 downto 0) := K_NONE;  -- captured this round\n"
              "    signal round_seen : std_logic := '0';   -- a hit was already taken this round")

p.write_text(s, encoding="utf-8")
print("keypad_scan capture fixed")
