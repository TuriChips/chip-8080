#!/usr/bin/env bash
# Usage: tests/run_prog80.sh tests/c1/alu_add_reg     (needs <name>.asm and <name>.exp; optional <name>.plus)
# Assembles, builds with Icarus (4-state) against rtl/, runs; log in logs/<name>.log (move into a logs/rtl-run* dir as evidence).
set -euo pipefail
name=$1; b=build/prog80/$(basename "$name"); mkdir -p "$b" logs
python3 tests/asm80.py "$name.asm" "$b/mem.hex"
iverilog -g2012 -DMEMFILE="\"$b/mem.hex\"" -o "$b/sim.vvp" tb/tb_prog80.sv $(find "${RTL_DIR:-rtl}" -name '*.v')
plus=""; [ -f "$name.plus" ] && plus=$(cat "$name.plus")
vvp -n "$b/sim.vvp" +EXP="$name.exp" +N=$(wc -l < "$name.exp") $plus ${EXTRA_PLUS:-} 2>&1 | tee "logs/$(basename "$name")${LOGSUFFIX:-}.log"
grep -q '^PASS' "logs/$(basename "$name")${LOGSUFFIX:-}.log"
