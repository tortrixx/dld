# -*- coding: utf-8 -*-
"""Finalise the frame renderer: unify to ONE pair of 64-bit frame registers and
have the engine output them directly."""
import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 1. drop the redundant o_rowr/o_rowg shadow writes (the frame registers ARE the outputs)
s = re.sub(r"\n                -- ghost rows are ORed in as each row arrives.*?\n                end if;\n",
           "\n", s, flags=re.S)

# 2. apply the ghost when merging each row into the red frame
s = s.replace("                    when 0      => frame_r(63 downto 56) <= cov;",
              "                    when 0      => frame_r(63 downto 56) <= cov or (tgtrow and (not cov));")
for row, sl in [(1, "55 downto 48"), (2, "47 downto 40"), (3, "39 downto 32"),
                (4, "31 downto 24"), (5, "23 downto 16"), (6, "15 downto 8")]:
    s = s.replace("                    when %d      => frame_r(%s) <= cov;" % (row, sl),
                  "                    when %d      => frame_r(%s) <= cov or (tgtrow and (not cov));" % (row, sl))
s = s.replace("                    when others => frame_r(7 downto 0) <= cov;",
              "                    when others => frame_r(7 downto 0) <= cov or (tgtrow and (not cov));")

# 3. drive the outputs from the frame registers
s = s.replace("o_scanrow <= std_logic_vector(scanrow);",
              "o_scanrow <= std_logic_vector(scanrow);\n"
              "    -- the frame registers ARE the outputs: the matrix driver slices them\n"
              "    o_rowr <= frame_r;\n"
              "    o_rowg <= frame_g;")

# 4. reset must clear the frame registers
s = s.replace("""                frow    <= (others => '0');
                frame_r <= (others => '0');
                frame_g <= (others => '0');
                warm    <= (others => '0');""",
              """                frow    <= (others => '0');
                frame_r <= (others => '0');
                frame_g <= (others => '0');""")

p.write_text(s, encoding="utf-8")
print("unified")
for i, l in enumerate(s.splitlines(), 1):
    if any(k in l for k in ("o_rowr", "o_rowg", "frame_r(63", "frow")):
        print(f"  {i}: {l.strip()[:88]}")
