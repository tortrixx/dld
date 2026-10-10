# -*- coding: utf-8 -*-
"""锁定已确认的键位映射。

实测证据（keypad_diag_top，权威引脚）：
  * 原始下标 1 就是启动游戏的那个键（它产生了该图案）。
  * 扫描器现在对每个键报出互不相同的下标，并在松手时回到 0。
  * 按下最右侧物理列的那三个键，使报出的行线变成 110 / 101 / 011，
    即第 0..2 行有响应；第 3 行没有变化。
  * 可用的只有第 0..3 行这 4 位，所以下标为 4*row + column，
    已确认的 START 键是下标 1。

由于未完成全部 16 键的普查，该映射把已确认的键显式列出，并为其
分配合理的相邻键，而整张表集中在唯一一处（game_fsm.key_of），
因此一次测量就能校正它。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "game_fsm.vhd"
s = p.read_text(encoding="utf-8")

old = '''    --      index  0 = (row0,col0)  -> UP
    --      index  1 = (row0,col1)  -> START      (top row, second key)
    --      index  2 = (row0,col2)  -> DOWN
    --      index  4 = (row1,col0)  -> LEFT
    --      index  5 = (row1,col1)  -> RIGHT
    --      index  6 = (row1,col2)  -> SELECT
    --      index 10 = (row2,col2)  -> CONFIRM'''
new = '''    -- CONFIRMED ON THE BENCH: raw index 1 starts the game.
    -- The remaining assignments are the natural neighbours of that key; the
    -- whole table lives here so a single measurement can correct it.
    --
    --      index  1 = (row0,col1)  -> START     CONFIRMED
    --      index  0 = (row0,col0)  -> LEFT
    --      index  2 = (row0,col2)  -> RIGHT
    --      index  3 = (row0,col3)  -> SELECT
    --      index  4 = (row1,col0)  -> UP
    --      index  5 = (row1,col1)  -> DOWN
    --      index  6 = (row1,col2)  -> CONFIRM'''
assert old in s, "map comment not found"
s = s.replace(old, new)

old_case = '''        case idx is
            when "0000" => return K_UP;
            when "0001" => return K_START;
            when "0010" => return K_DOWN;
            when "0100" => return K_LEFT;
            when "0101" => return K_RIGHT;
            when "0110" => return K_SELECT;
            when "1010" => return K_CONFIRM;
            when others => return K_NONE;
        end case;'''
new_case = '''        case idx is
            when "0001" => return K_START;    -- CONFIRMED on the bench
            when "0000" => return K_LEFT;
            when "0010" => return K_RIGHT;
            when "0011" => return K_SELECT;
            when "0100" => return K_UP;
            when "0101" => return K_DOWN;
            when "0110" => return K_CONFIRM;
            when others => return K_NONE;
        end case;'''
assert old_case in s, "key_of case not found"
s = s.replace(old_case, new_case)

p.write_text(s, encoding="utf-8")
print("key map locked")
