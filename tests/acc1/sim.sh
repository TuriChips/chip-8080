#!/usr/bin/env bash
# Homer: run a CP/M .COM on i8080_system under Verilator. Usage: tests/acc1/sim.sh <program.com> <log-file> [MAXCLK]
# Prints the program's console output to <log-file> followed by 'RUN DONE after N clocks' (or 'RUN TIMEOUT'); the judgement is check_log.py's.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
com=$1; log=$2; maxclk=${3:-30000000000}   # the full 8080EXM is about 10^9 instructions, several 10^9 clocks
d=build/acc1; mkdir -p $d
if [[ "$com" == *.hex ]]; then cp "$com" $d/image.hex; else python3 tests/acc1/com2hex.py "$com" $d/image.hex; fi   # a .hex is a ready memory image (tests/asm80.py output)
img="$(pwd)/$d/image.hex"
# Verilator with its own C++ driver (sim_main.cpp): no --timing scheduler, and the C++ is compiled with -O2 (the default was -Os).
verilator --cc --exe -Wno-fatal -Wno-lint -Wno-style -O3 --top-module tb_cpm_top -Mdir $d/obj -DMEMFILE="\"$img\"" \
  -CFLAGS "-O2" tests/acc1/tb_cpm_top.sv $(find rtl -name '*.v' | sort) "$(pwd)/tests/acc1/sim_main.cpp" > $d/verilator.log 2>&1 \
  && make -C $d/obj -f Vtb_cpm_top.mk -j"$(nproc)" >> $d/verilator.log 2>&1 \
  || { tail -n 20 $d/verilator.log >&2; echo "verilator build failed" >&2; exit 1; }
$d/obj/Vtb_cpm_top +MAXCLK=$maxclk > "$log"
