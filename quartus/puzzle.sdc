# ============================================================================
#  puzzle.sdc  --  TimeQuest timing constraints
#  Quartus II 9.1 / MAX II EPM1270T144C5
#
#  The board clock is fed by the on-board oscillator selected with USER_BTN.
#  This design assumes the 50 MHz position (verify on the FREQ LED row before
#  trusting any Fmax number).
#
#  NOTE: the classic timing analyser (quartus_tan) does NOT read an .sdc file,
#  so Fmax must be read from quartus_sta (TimeQuest).  Running quartus_tan
#  gives an empty Fmax column and is not evidence of anything.
# ============================================================================

# 50 MHz board clock on PIN_18
create_clock -name clk -period 20.000 [get_ports {clk}]

# Keep the input/output delays honest but loose: every peripheral here is a
# slow human-interface device (keys, LEDs, matrix, 7-segment), so the only real
# constraint that matters is the internal 50 MHz clock.
set_input_delay  -clock clk 5.000 [get_ports {sw7 btn kp_row[*]}]
set_output_delay -clock clk 5.000 [get_ports {kp_col[*] dot_row[*] dot_colr[*] \
                                               dot_colg[*] seg[*] cat[*] buzz}]
