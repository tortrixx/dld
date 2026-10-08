-- ============================================================================
--  rng_lfsr  --  8-bit pseudo-random source
--  Subsystem : S5 (pictures and random data)
--
--  An 8-bit maximal-length LFSR (x^8 + x^6 + x^5 + x^4 + 1, the standard
--  Xilinx xapp052 taps for 8 bits), period 255.
--
--  IMPORTANT: this module is NOT driven by any clock tick.  It only advances
--  when its consumer asserts i_step.  A free-running random source would make
--  the scatter impossible to reproduce and impossible to simulate, and it also
--  wastes power.  Requirement A3 (random scatter) needs randomness only at the
--  moments a level starts.
--
--  The seed is forced non-zero on reset.  An all-zero LFSR is the absorbing
--  state: it would stay zero forever and every piece would land in the same
--  spot.
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use work.puzzle_pkg.ALL;

entity rng_lfsr is
    port (
        i_clk  : in  std_logic;
        i_rst  : in  std_logic;                      -- active HIGH
        i_step : in  std_logic;                      -- advance one step
        o_val  : out std_logic_vector(7 downto 0)
    );
end entity rng_lfsr;

architecture rtl of rng_lfsr is
    signal sr : std_logic_vector(7 downto 0) := SEED_DEFAULT;
begin

    process (i_clk)
        variable fb : std_logic;
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                sr <= SEED_DEFAULT;
            elsif (i_step = '1') then
                fb := sr(7) xor sr(5) xor sr(4) xor sr(3);
                sr <= sr(6 downto 0) & fb;
                -- defensive: never let the register become all zero
                if ((sr(6 downto 0) & fb) = "00000000") then
                    sr <= SEED_DEFAULT;
                end if;
            end if;
        end if;
    end process;

    o_val <= sr;

end architecture rtl;
