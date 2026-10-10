# ============================================================================
#  build.tcl —— 拼图项目的完整 Quartus II 9.1 流程
#  运行方式： quartus_sh -t scripts/build.tcl
#
#  依次执行 map -> fit -> asm -> sta，并打印真正重要的数字：
#  逻辑单元用量（EPM1270 只有 1270 个 LE）与 Fmax。
#
#  注意：Fmax 来自 quartus_sta（TimeQuest）。经典的 quartus_tan 不读 .sdc，
#  所以它的 Fmax 列是空的，证明不了任何事。
# ============================================================================

# execute_module 位于 ::quartus::flow 包中，而裸的 quartus_sh -t 会话
# 默认不加载该包。没有这一行，每次编译都会失败并报
# 'Tcl command "execute_module" belongs to the "::quartus::flow" package
# which is currently not loaded'。
load_package flow

set script_dir [file dirname [info script]]
set root       [file normalize [file join $script_dir ..]]
set proj_dir   [file join $root quartus]

puts "=============================================================="
puts " puzzle build : root=$root"
puts "=============================================================="

if {[catch {

    project_open -revision puzzle [file join $proj_dir puzzle]

    # ---- 1. 分析与综合 -------------------------------------------
    execute_module -tool map

    # ---- 2. 布局布线器（引脚在此应用） ---------------------------------
    execute_module -tool fit

    # ---- 3. 汇编器（为 USB-Blaster 生成 .pof） ---------------------------
    execute_module -tool asm

    # ---- 4. 经典时序分析器（保留用于资源汇总） --------
    execute_module -tool tan

    # ---- 5. TimeQuest 静态时序分析 ------------------------------
    #  ⚠️⚠️ 2026-10-10 修正（**脚本的注释与代码互相矛盾**）：
    #     本文件头部一直写着 "Runs map -> fit -> asm -> **sta**"、
    #     并注明 "Fmax comes from quartus_sta (TimeQuest)"，
    #     但**代码里从来只跑 `-tool tan`、不跑 `-tool sta`** ——
    #     于是 `quartus/output_files/puzzle.sta.rpt` **根本不会由这条命令生成**，
    #     而 README §2 / docs/05 / HANDOFF 引用的每一个时序读数
    #     （setup slack、hold slack、Fmax）都来自那个文件。
    #     也就是说："照文档的命令做一次清洁重编译"**复现不出文档里的时序数字**，
    #     必须再手工补跑一次 quartus_sta（上一轮的 .sta.rpt 就是这么来的）。
    #     现在补上这一步，让"清洁重编译"这条命令**真的**产出全部证据。
    execute_module -tool sta

    project_close

} err]} {
    puts "*** BUILD FAILED ***"
    puts $err
    project_close
    exit 1
}

# ---------------------------------------------------------------------------
# 收尾汇总：把"每次编译后必读"的几行直接打出来（免得再去报告里翻）
#   ⚠️ 面积要读**两行**：Total logic elements **和** LAB 占用 ——
#      本器件 LAB 已满 127/127，"剩几个 LE"在装箱层面≈0（ERR-046）。
# ---------------------------------------------------------------------------
proc _first_line {path needle} {
    if {![file exists $path]} { return "(缺 [file tail $path])" }
    set fh [open $path r]
    while {[gets $fh line] >= 0} {
        if {[string first $needle $line] >= 0} { close $fh; return [string trim $line] }
    }
    close $fh
    return "(未找到: $needle)"
}

# 按**正则**找第一行匹配（Fmax 汇总行的第一个字段就是 MHz 值，
# 而约束行里也有 "50.0 MHz"，所以用正则区分：行首 `; <数字> MHz ;`）
proc _first_line_re {path pattern} {
    if {![file exists $path]} { return "(缺 [file tail $path])" }
    set fh [open $path r]
    while {[gets $fh line] >= 0} {
        if {[regexp $pattern $line]} { close $fh; return [string trim $line] }
    }
    close $fh
    return "(未匹配: $pattern)"
}

set outf [file join $proj_dir output_files]
puts ""
puts "---- 关键读数（照抄进 docs/05 / README / HANDOFF）----"
foreach needle {"Fitter Status" "Total logic elements" "Total LABs" "Total pins"} {
    puts "  [_first_line [file join $outf puzzle.fit.rpt] $needle]"
}
puts "  Fmax: [_first_line_re [file join $outf puzzle.sta.rpt] {^;\s*[0-9.]+\s*MHz\s*;}]"
puts "  → 完整时序见 quartus/output_files/puzzle.sta.rpt"
puts "  → 编译成功后请跑 `python scripts/record_build.py` 记录固件身份与读数"
puts "     （audit_evidence.py 的 E 段据此按**内容**核对固件与 RTL）。"
