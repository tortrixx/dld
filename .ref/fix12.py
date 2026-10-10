# -*- coding: utf-8 -*-
"""从游戏区中去掉目标「幽灵」。

由实测驱动的设计变更：预览已经展示了完整图案（需求 B4），所以在零片
下方再以红色幽灵重绘一遍既无增益，反而会主动遮挡零片——
在板上，玩家无法分辨散落的零片
与目标轮廓。

需求 B4 明确规定完整图案先显示 5 s，然后零片才出现，
所以游戏区只应包含零片。

实现方式：游戏进行中把引擎的 i_target 输入置空。引擎保留其幽灵
逻辑（对诊断有用，板级测试也在用），它只是在对局期间
被喂以零。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

p = ROOT / "rtl" / "puzzle_top.vhd"
s = p.read_text(encoding="utf-8")

s = s.replace("    signal tgt_mask : std_logic_vector(63 downto 0);",
              "    signal tgt_mask : std_logic_vector(63 downto 0);\n"
              "    -- what the ENGINE is shown as the target: blank while playing, so the\n"
              "    -- play field contains only the scattered pieces (requirement B4 shows\n"
              "    -- the complete picture during the PREVIEW, not during play)\n"
              "    signal tgt_play : std_logic_vector(63 downto 0);")

s = s.replace("            i_target  => tgt_mask,",
              "            i_target  => tgt_play,")

s = s.replace("    -- S4 : puzzle engine",
              "    -- The engine sees the target only during the preview; during play it is\n"
              "    -- blanked so the pieces are not hidden under a red outline.\n"
              "    tgt_play <= tgt_mask when (state = S_PREVIEW or state = S_SELF_TEST)\n"
              "                else (others => '0');\n\n"
              "    -- S4 : puzzle engine")

p.write_text(s, encoding="utf-8")
print("ghost disabled during play")
