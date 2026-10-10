# -*- coding: utf-8 -*-
"""修复 4 —— 引擎配色：被选中的零片永远不可能是绿色。

已确认的缺陷：渲染器算的是
    redrow := cov or (tgtrow and (not cov))
其中 'cov' 是每一个零片单元，而绿色通道只由已经在 'cov' 里的
单元构成。于是绿色永远是红色的子集，纯绿的点根本不可能存在：
被选中的零片渲染出来是红+绿 = 黄，
与已锁定的零片完全一样。需求 B6（「被选中的零片变为绿色」）
没有被满足，B6/B8 在视觉上无法区分。

修复：为被选中的零片单独构造一行 'sel'，并把它从红色中排除。
    green = selected OR locked
    red   = (all piece cells AND NOT selected) OR target-ghost
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_ctrl.vhd")
s = p.read_text(encoding="utf-8")

# --- 累加一行专用的选中掩码 -------------------------------
for k, (issel) in enumerate(['(sel = "00")', '(sel = "01")',
                             '(sel = "10")', '(sel = "11")']):
    old = "                    if (locked(%d) = '1') or %s then kc := kc or rw; end if;" % (k, issel)
    new = ("                    if (locked(%d) = '1') then kc := kc or rw; end if;\n"
           "                    if %s then selrow := selrow or rw; end if;" % (k, issel))
    assert old in s, "slot %d not found" % k
    s = s.replace(old, new)

# 声明该变量
s = s.replace("        variable redrow : std_logic_vector(7 downto 0);",
              "        variable redrow : std_logic_vector(7 downto 0);\n"
              "        variable selrow : std_logic_vector(7 downto 0);")

# 在 cov/kc 旁边初始化它
s = s.replace("                cov := (others => '0');\n                kc  := (others => '0');",
              "                cov    := (others => '0');\n"
              "                kc     := (others => '0');\n"
              "                selrow := (others => '0');")

# --- 颜色混合 ----------------------------------------------------------
s = s.replace("""                -- colour of this row: green = selected or locked cells, red = any
                -- piece cell plus the part of the target no piece covers
                redrow := cov or (tgtrow and (not cov));
                grnrow := kc;""",
              """                -- Colour of this row.
                --   green = selected piece OR locked piece
                --   red   = every OTHER piece cell, plus the part of the target
                --           that no piece covers (the ghost)
                -- Excluding exactly the selected cells from red is what makes the
                -- selected piece pure GREEN; without it green was a subset of red
                -- and the piece showed up as yellow, the same as a locked one.
                redrow := (cov and (not selrow)) or (tgtrow and (not cov));
                grnrow := kc or selrow;""")

p.write_text(s, encoding="utf-8")
print("engine colour fixed")
