# -*- coding: utf-8 -*-
"""收尾帧渲染器：统一成**一对** 64 位帧寄存器，
并让引擎直接输出它们。"""
import pathlib, re

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# 1. 删掉多余的 o_rowr/o_rowg 影子写入（帧寄存器**就是**输出）
s = re.sub(r"\n                -- ghost rows are ORed in as each row arrives.*?\n                end if;\n",
           "\n", s, flags=re.S)

# 2. 把每一行并进红色帧时就地叠加幽灵
s = s.replace("                    when 0      => frame_r(63 downto 56) <= cov;",
              "                    when 0      => frame_r(63 downto 56) <= cov or (tgtrow and (not cov));")
for row, sl in [(1, "55 downto 48"), (2, "47 downto 40"), (3, "39 downto 32"),
                (4, "31 downto 24"), (5, "23 downto 16"), (6, "15 downto 8")]:
    s = s.replace("                    when %d      => frame_r(%s) <= cov;" % (row, sl),
                  "                    when %d      => frame_r(%s) <= cov or (tgtrow and (not cov));" % (row, sl))
s = s.replace("                    when others => frame_r(7 downto 0) <= cov;",
              "                    when others => frame_r(7 downto 0) <= cov or (tgtrow and (not cov));")

# 3. 由帧寄存器驱动输出
s = s.replace("o_scanrow <= std_logic_vector(scanrow);",
              "o_scanrow <= std_logic_vector(scanrow);\n"
              "    -- the frame registers ARE the outputs: the matrix driver slices them\n"
              "    o_rowr <= frame_r;\n"
              "    o_rowg <= frame_g;")

# 4. 复位必须清空帧寄存器
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
