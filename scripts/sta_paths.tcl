# Report the worst setup path with enough detail to fix it.
load_package sta
project_open -revision puzzle "C:/Users/sznnn/Desktop/dld/quartus/puzzle"
create_timing_netlist
read_sdc "C:/Users/sznnn/Desktop/dld/quartus/puzzle.sdc"
update_timing_netlist
report_timing -setup -npaths 3 -detail path_only -stdout
report_timing -setup -npaths 3 -detail summary -stdout
project_close
