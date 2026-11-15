#!/usr/bin/env bash
# Usage: tests/run_pins80.sh build/gen/c2/pins_s1      (needs <name>.asm and <name>.pins from tests/c2/gen_pins80.py)
set -euo pipefail
name=$1; b=build/pins80/$(basename "$name"); mkdir -p "$b" logs
python3 tests/asm80.py "$name.asm" "$b/mem.hex"
iverilog -g2012 -DMEMFILE="\"$b/mem.hex\"" -o "$b/sim.vvp" tb/tb_pins80.sv $(find "${RTL_DIR:-rtl}" -name '*.v' ! -name i8080_system.v)
vvp -n "$b/sim.vvp" +EXP="$name.pins" +N=$(wc -l < "$name.pins") ${EXTRA_PLUS:-} 2>&1 | tee "logs/pins80_$(basename "$name").log"
grep -q '^PASS' "logs/pins80_$(basename "$name").log"
