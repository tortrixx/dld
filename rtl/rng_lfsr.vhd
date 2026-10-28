-- ============================================================================
--  rng_lfsr  ——  8 位伪随机数源
--  所属子系统：S5（图案与随机数据）
--
--  8 位最大长度线性反馈移位寄存器，抽头 x^8 + x^6 + x^5 + x^4 + 1，
--  周期 255，用于零片散落的随机候选位置。
--
--  · 不自由运行：只有 i_step 拉高时才推进一步。这样散落过程可复现、
--    可仿真，也不会产生无谓的翻转功耗。
--  · 复位种子强制非零：全零是 LFSR 的吸收态，一旦进入就永远出不来，
--    所有零片都会落到同一个位置。
-- ============================================================================

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use work.puzzle_pkg.ALL;

entity rng_lfsr is
    port (
        i_clk  : in  std_logic;
        i_rst  : in  std_logic;                      -- 高电平有效
        i_step : in  std_logic;                      -- 推进一步
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
                -- 防御性措施：绝不让寄存器变成全零
                if ((sr(6 downto 0) & fb) = "00000000") then
                    sr <= SEED_DEFAULT;
                end if;
            end if;
        end if;
    end process;

    o_val <= sr;

end architecture rtl;
