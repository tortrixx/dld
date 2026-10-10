# 报告最差 setup 路径，细节足够到能据此修时序。
load_package sta
project_open -revision puzzle "C:/Users/sznnn/Desktop/dld/quartus/puzzle"
create_timing_netlist
read_sdc "C:/Users/sznnn/Desktop/dld/quartus/puzzle.sdc"
update_timing_netlist
report_timing -setup -npaths 3 -detail path_only -stdout
report_timing -setup -npaths 3 -detail summary -stdout
project_close
