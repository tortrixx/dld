-- ============================================================================
--  piece_rom  --  piece-shape lookup table
--  Subsystem : S5 (pictures and random data)
--
--  Pure combinational.  Returns all four piece shapes at once (not "give me
--  shape number k"): the engine needs all of them every frame anyway, and
--  returning them together means the engine never has to instantiate the ROM
--  four times internally -- which would put a hidden block inside puzzle_ctrl
--  and break the rule that the system diagram matches the code.
--
--  Level 1 shapes come from figure 4-2, decoded pixel-exactly: 3 + 6 + 3 = 12
--  cells, which conserves area with the 12-cell figure-4-1 picture.
--  Level 2 **and level 3** use the same four SELF-DESIGNED IRREGULAR pieces
--  (3 + 2 + 5 + 6 = 16 cells, 2026-10-09 第 11 工作阶段; before that they were
--  four identical 2x2 squares -- see rtl/puzzle_pkg.vhd L2_P0..P3 and docs/02 §9.2).
--  ⚠️ 第 12 工作阶段（D2）把游戏变成三关：**第三关沿用同一套四块异形零片**，
--     所以这里仍然是"两级分支"（i_level='0' = 第一关三块；'1' = 第二/三关四块）。
--
--  All shapes fit in a 3x3 bounding box (constant PIECE_MAX_DIM), which is what
--  lets the engine scan a 3x3 neighbourhood instead of the whole panel.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use work.puzzle_pkg.ALL;

entity piece_rom is
    port (
        i_level : in  std_logic;                      -- '0' = level 1, '1' = level 2/3
        o_mask  : out mask_arr_t;                     -- 4 relative shape masks
        o_h     : out dim_arr_t;                      -- 4 bounding-box heights
        o_w     : out dim_arr_t;                      -- 4 bounding-box widths
        o_n     : out std_logic_vector(2 downto 0)    -- how many pieces this level uses
    );
end entity piece_rom;

architecture rtl of piece_rom is
begin

    process (i_level)
    begin
        if (i_level = '0') then
            -- ---------------- level 1 : 3 pieces (slot 3 unused) -------------
            o_mask <= (L1_P0, L1_P1, L1_P2, MASK_ZERO);
            o_h    <= ("001", "011", "010", "000");   -- 1, 3, 2, -
            o_w    <= ("011", "011", "010", "000");   -- 3, 3, 2, -
            o_n    <= "011";                          -- 3
        else
            -- ---------------- level 2/3 : 4 pieces (self-designed, 2026-10-09) -----
            --   Q0 1x3 bar (3) / Q1 1x2 domino (2) / Q2 J-pentomino (5) /
            --   Q3 six-cell block (6) = 16 cells, one orientation each (no rotation).
            --   scripts/check_geometry.py enumerates every exact translation tiling
            --   of each pattern with these four shapes (第二关固定 PAT3、第三关四幅随机).
            o_mask <= (L2_P0, L2_P1, L2_P2, L2_P3);
            o_h    <= ("001", "010", "011", "011");   -- 1, 2, 3, 3
            o_w    <= ("011", "001", "011", "011");   -- 3, 1, 3, 3
            o_n    <= "100";                          -- 4
        end if;
    end process;

end architecture rtl;
