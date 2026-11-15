#!/usr/bin/env bash
# Leo: generic Yosys synthesis of i8080 alone (i8080_mem and i8080_system are test fixtures, not synthesized).
# Usage: synth/run.sh   -> synth/report.txt, synth/logs/yosys.log
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p synth/logs
TOP=${TOP:-i8080}
[ -n "${SRC:-}" ] || [ -f rtl/top.v ] || { echo "rtl/top.v not on main yet (set SRC and TOP to try other sources)"; exit 2; }
SRC=${SRC:-"rtl/top.v $(ls rtl/control/i8080_*.v rtl/datapath/i8080_*.v | grep -v -e i8080_mem -e i8080_system | tr '\n' ' ')"}
yosys -q -l synth/logs/yosys.log -p "
read_verilog $SRC;
hierarchy -check -top $TOP;
proc; flatten; opt; memory -nomap; memory_map; opt; techmap; opt;
abc -g AND,NAND,OR,NOR,XOR,XNOR,ANDNOT,ORNOT,MUX; opt_clean -purge;
check -assert;
tee -o synth/report.txt stat;
tee -a synth/report.txt ltp -noff
"
echo "--- warnings ---"; grep -i warning synth/logs/yosys.log | grep -v 'combinational (run' || echo none
grep -E 'Number of cells|\$_' synth/report.txt; grep 'length=' synth/report.txt
