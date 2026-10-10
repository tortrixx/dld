# -*- coding: utf-8 -*-
"""修复 1 —— keypad_scan：本轮结果在被采样之前就被销毁了。

缺陷（两处均经阅读代码确认）：
  D1  扫描时序器停留在 ST_IDLE 期间（约 250 000 个时钟）时，round_code 在每
      个时钟都被清零，而消抖级只在 200 Hz tick 上采样它。于是第 3 相的捕获
      只存活恰好一个时钟，采样器读到的永远是 K_NONE  ->  o_key 恒为 0，
      这正是实测现象：
      「按任何键都没有反应」。
  D2  只有第 3 相会被捕获，所以第 0..2 列的按键永远看不到。

修复：在本轮的任意已稳定相位捕获（首次命中者胜出），并把结果保持到
下一轮开始。把结果保持整整一个扫描周期，也让消抖级的「连续 N 轮稳定」
比较真正有意义，而在此之前，
这种比较根本不可能有意义。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "keypad_scan.vhd"
s = p.read_text(encoding="utf-8")

old = """                if (state = ST_IDLE) then
                    round_code <= K_NONE;          -- new round is starting
                elsif ((state = ST_SCAN) and (phase = 3)) then
                    round_code <= raw_code;        -- last phase of the round
                end if;"""

new = """                -- Capture policy:
                --   * take the FIRST hit of ANY settled phase (not just phase 3),
                --     so keys in every column are visible;
                --   * HOLD the result until the next round is kicked off, because
                --     the debounce stage samples it on the 200 Hz tick -- roughly
                --     250 000 clocks after the round finished.  Clearing it on
                --     every ST_IDLE clock (the previous behaviour) meant the
                --     sampler read K_NONE forever and no key was ever accepted.
                if ((state = ST_IDLE) and (i_tick = '1')) then
                    round_code <= raw_code;        -- publish the finished round
                elsif ((state = ST_SCAN) or (state = ST_SETTLE)) then
                    if (raw_hit = '1') and (round_code /= raw_code) then
                        -- do not overwrite an accepted hit within the same round
                        null;
                    end if;
                end if;
                -- first hit of the round wins; earlier phases take priority
                if (state = ST_SCAN) and (raw_hit = '1') then
                    if (round_code = K_NONE) or (round_seen = '0') then
                        round_code <= raw_code;
                        round_seen <= '1';
                    end if;
                elsif ((state = ST_IDLE) and (i_tick = '1')) then
                    round_seen <= '0';             -- re-arm for the next round
                end if;"""

assert old in s, "capture block not found"
s = s.replace(old, new)

# 新增的置位标志
s = s.replace("    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- key seen in this round",
              "    signal round_code : std_logic_vector(3 downto 0) := K_NONE;  -- key seen in this round\n"
              "    signal round_seen : std_logic := '0';   -- a hit was already taken this round")

# 复位这个新标志
s = s.replace("                raw_hit    <= '0';\n                raw_code   <= K_NONE;\n                round_code <= K_NONE;",
              "                raw_hit    <= '0';\n                raw_code   <= K_NONE;\n"
              "                round_code <= K_NONE;\n                round_seen <= '0';")

p.write_text(s, encoding="utf-8")
print("keypad_scan patched")
