# -*- coding: utf-8 -*-
"""Break the reported critical path: pos -> o_solved -> game_fsm sound mux -> buzz.

Registering the solved/all-lock status and the FSM's sound code removes two
combinational stages from that path.  Both are sampled on slow ticks (1 Hz /
2 Hz), so a one-clock pipeline delay is invisible in behaviour.
"""
import pathlib

# ---- puzzle_ctrl: register the status outputs ------------------------------
p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
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

# ---- game_fsm: register the sound code -------------------------------------
q = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\game_fsm.vhd")
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
