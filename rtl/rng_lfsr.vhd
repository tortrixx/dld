-- ============================================================================
--  rng_lfsr  --  8 位伪随机数源
--  子系统：S5（图案与随机数据）
--
--  一个 8 位最大长度 LFSR（x^8 + x^6 + x^5 + x^4 + 1，即 8 位标准的
--  Xilinx xapp052 抽头），周期 255。
--
--  重要：本模块**不**由任何时钟节拍驱动。它只在消费者拉高
--  i_step 时才推进一步。自由运行的随机源会让散落无法复现、
--  也无法仿真，而且还会白白耗电。
--  需求 A3（随机散落）只在关卡开始的时刻
--  需要随机性。
--
--  复位时种子被强制为非零。全零 LFSR 是吸收态：
--  它会永远保持为零，每一片零片都会落到同一个
--  位置上。
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
