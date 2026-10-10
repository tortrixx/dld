# ============================================================================
#  puzzle.sdc  --  TimeQuest 时序约束
#  Quartus II 9.1 / MAX II EPM1270T144C5
#
#  开发板时钟由板载振荡器提供，用 USER_BTN 选择。
#  本设计假定选在 50 MHz 档（在相信任何 Fmax 数字之前，
#  先核对 FREQ LED 那一排的指示）。
#
#  注意：经典时序分析器（quartus_tan）**不读** .sdc 文件，
#  所以 Fmax 必须从 quartus_sta（TimeQuest）读取。跑 quartus_tan
#  只会得到空的 Fmax 列，证明不了任何事。
# ============================================================================

# PIN_18 上的 50 MHz 开发板时钟
create_clock -name clk -period 20.000 [get_ports {clk}]

# 输入/输出延时给得宽松但如实：这里每个外设都是
# 慢速人机接口器件（按键、LED、点阵、数码管），所以真正
# 起作用的唯一约束是内部 50 MHz 时钟。
set_input_delay  -clock clk 5.000 [get_ports {sw7 btn kp_row[*]}]
set_output_delay -clock clk 5.000 [get_ports {kp_col[*] dot_row[*] dot_colr[*] \
                                               dot_colg[*] seg[*] cat[*] buzz}]
