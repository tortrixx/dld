# ============================================================================
#  build.tcl -- full Quartus II 9.1 flow for the puzzle project
#  Run with:  quartus_sh -t scripts/build.tcl
#
#  Runs map -> fit -> asm -> sta and prints the numbers that actually matter:
#  logic element usage (the EPM1270 has only 1270 LEs) and Fmax.
#
#  NOTE: Fmax comes from quartus_sta (TimeQuest).  The classic quartus_tan does
#  not read the .sdc, so its Fmax column is empty and proves nothing.
# ============================================================================

# execute_module lives in the ::quartus::flow package, which is NOT loaded by
# default in a bare quartus_sh -t session.  Without this line every build fails
# with 'Tcl command "execute_module" belongs to the "::quartus::flow" package
# which is currently not loaded'.
load_package flow

set script_dir [file dirname [info script]]
set root       [file normalize [file join $script_dir ..]]
set proj_dir   [file join $root quartus]

puts "=============================================================="
puts " puzzle build : root=$root"
puts "=============================================================="

if {[catch {

    project_open -revision puzzle [file join $proj_dir puzzle]

    # ---- 1. analysis & synthesis -------------------------------------------
    execute_module -tool map

    # ---- 2. fitter (pins are applied here) ---------------------------------
    execute_module -tool fit

    # ---- 3. assembler (.pof for the USB-Blaster) ---------------------------
    execute_module -tool asm

    # ---- 4. classic timing analyser (kept for the resource summary) --------
    execute_module -tool tan

    project_close

} err]} {
    puts "*** BUILD FAILED ***"
    puts $err
    project_close
    exit 1
}
puts ""
puts "=============================================================="
puts " build finished -- check the report below"
puts "=============================================================="
