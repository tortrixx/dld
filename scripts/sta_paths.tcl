# 报告最差 setup 路径，细节足够到能据此修时序。
#
# ⚠️ 路径**不写死**：仓库根由本脚本自身的位置推出（scripts/ 的上一级），
#    所以 clone 到任意目录都能跑。用法（在仓库根目录）：
#        & "$env:QUARTUS_ROOT\quartus\bin\quartus_sta.exe" -t scripts/sta_paths.tcl
load_package sta
set _root [file normalize [file join [file dirname [info script]] ..]]
project_open -revision puzzle [file join $_root quartus puzzle]
create_timing_netlist
read_sdc [file join $_root quartus puzzle.sdc]
update_timing_netlist
report_timing -setup -npaths 3 -detail path_only -stdout
report_timing -setup -npaths 3 -detail summary -stdout
project_close
