# -*- coding: utf-8 -*-
"""Patch: game_fsm port naming (inputs named i_*) + puzzle_ctrl busy output."""
import pathlib

# ---- game_fsm.vhd ---------------------------------------------------------
p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
s = p.read_text(encoding="utf-8")
s = s.replace("        o_solved   : in  std_logic;                      -- from puzzle_ctrl\n"
              "        o_all_lock : in  std_logic;                      -- from puzzle_ctrl\n"
              "        o_shuf_busy: in  std_logic;                      -- from puzzle_ctrl\n",
              "        i_solved   : in  std_logic;                      -- from puzzle_ctrl\n"
              "        i_all_lock : in  std_logic;                      -- from puzzle_ctrl\n"
              "        i_shuf_busy: in  std_logic;                      -- from puzzle_ctrl\n")
# body references
s = s.replace("o_solved = '1'", "i_solved = '1'")
s = s.replace("o_all_lock = '1'", "i_all_lock = '1'")
s = s.replace("o_shuf_busy = '0'", "i_shuf_busy = '0'")
s = s.replace("o_shuf_busy = '1'", "i_shuf_busy = '1'")
s = s.replace("o_solved, o_all_lock)", "i_solved, i_all_lock)")
p.write_text(s, encoding="utf-8")
print("game_fsm patched")

# ---- puzzle_ctrl.vhd : add the busy output -------------------------------
q = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
t = q.read_text(encoding="utf-8")
t = t.replace("        o_solved  : out std_logic;                      -- all locked AND all on target\n"
              "        o_all_lock: out std_logic;                      -- every piece locked\n",
              "        o_solved  : out std_logic;                      -- all locked AND all on target\n"
              "        o_all_lock: out std_logic;                      -- every piece locked\n"
              "        o_busy    : out std_logic;                      -- scatter in progress\n")
t = t.replace("    o_solved   <= solved_r;\n    o_all_lock <= alllock_r;\n",
              "    o_solved   <= solved_r;\n    o_all_lock <= alllock_r;\n"
              "    -- busy while the scatter sequencer is doing anything other than idling\n"
              "    o_busy     <= '1' when (sh /= SH_IDLE) else '0';\n")
q.write_text(t, encoding="utf-8")
print("puzzle_ctrl patched")
