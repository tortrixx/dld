# -*- coding: utf-8 -*-
"""Remove the target "ghost" from the play field.

Design change, driven by the bench: the preview already shows the complete
picture (requirement B4), so drawing it again as a red ghost underneath the
pieces adds nothing and actively obscures them -- on the board the player could
not tell the scattered pieces from the target outline.

Requirement B4 is explicit that the complete pattern is shown for 5 s and THEN
the pieces appear, so the play field should contain the pieces only.

Implementation: the engine's i_target input is blanked while playing.  The engine
keeps its ghost logic (useful for diagnostics and used by the board test), it is
simply fed zeros during play.
"""
import pathlib

p = pathlib.Path(r"C:\Users\sznnn\Desktop\dld\rtl\puzzle_top.vhd")
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
