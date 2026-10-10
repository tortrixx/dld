# -*- coding: utf-8 -*-
"""打断上报的关键路径：pos -> o_solved -> game_fsm 音效多路器 -> buzz。

把 solved/all-lock 状态与状态机的音效码寄存起来，可从该路径上
去掉两级组合逻辑。两者都在慢节拍（1 Hz /
2 Hz）上采样，所以一个时钟的流水延迟在行为上不可见。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---- puzzle_ctrl：寄存状态输出 ------------------------------
p = ROOT / "rtl" / "puzzle_ctrl.vhd"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "    signal solved_r  : std_logic;\n    signal alllock_r : std_logic;\n",
    "    signal solved_r  : std_logic;\n    signal alllock_r : std_logic;\n"
    "    signal solved_c  : std_logic;\n    signal alllock_c : std_logic;\n")
s = s.replace("        if (ok and locked_ok) then solved_r <= '1'; else solved_r <= '0'; end if;\n"
              "        if (locked_ok)        then alllock_r <= '1'; else alllock_r <= '0'; end if;\n"
              "    end process;\n",
              "        if (ok and locked_ok) then solved_c <= '1'; else solved_c <= '0'; end if;\n"
              "        if (locked_ok)        then alllock_c <= '1'; else alllock_c <= '0'; end if;\n"
              "    end process;\n\n"
              "    -- Pipeline stage: the status flags feed the state machine, which then\n"
              "    -- drives the sound mux and the buzzer.  Chaining all of that in one\n"
              "    -- clock was the reported critical path (41.6 MHz instead of 50+), so\n"
              "    -- the flags are registered here.\n"
              "    process (i_clk)\n"
              "    begin\n"
              "        if rising_edge(i_clk) then\n"
              "            if (i_rst = '1') then\n"
              "                solved_r  <= '0';\n"
              "                alllock_r <= '0';\n"
              "            else\n"
              "                solved_r  <= solved_c;\n"
              "                alllock_r <= alllock_c;\n"
              "            end if;\n"
              "        end if;\n"
              "    end process;\n")
p.write_text(s, encoding="utf-8")
print("puzzle_ctrl status registered")

# ---- game_fsm：寄存音效码 -------------------------------------
q = ROOT / "rtl" / "game_fsm.vhd"
t = q.read_text(encoding="utf-8")
t = t.replace("    signal sound_r : std_logic_vector(2 downto 0) := \"000\";",
              "    signal sound_r : std_logic_vector(2 downto 0) := \"000\";\n"
              "    signal sound_p : std_logic_vector(2 downto 0) := \"000\";")
t = t.replace("""    process (st, i_press, i_key, i_solved, i_all_lock)
    begin
        case st is""",
              """    process (i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sound_p <= "000";
            else
                -- register the code: it feeds buzzer_ctrl, whose oscillator then
                -- drives the buzz pin, and chaining all of that combinationally
                -- after the state decode was the reported critical path
                sound_p <= sound_r;
            end if;
        end if;
    end process;

    process (st, i_press, i_key, i_solved, i_all_lock)
    begin
        case st is""")
t = t.replace("    o_sound    <= sound_r;", "    o_sound    <= sound_p;")
q.write_text(t, encoding="utf-8")
print("game_fsm sound registered")
