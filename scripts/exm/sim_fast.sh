#!/usr/bin/env bash
# Tesla: faster drop-in for tests/acc1/sim.sh (C++ clock, no --timing). Usage: scripts/exm/sim_fast.sh <program.com|.hex> <log> [MAXCLK]
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
com=$1; log=$2; maxclk=${3:-30000000000}
d=${BUILD:-build/exmfast}; mkdir -p $d
if [[ "$com" == *.hex ]]; then cp "$com" $d/image.hex; else python3 tests/acc1/com2hex.py "$com" $d/image.hex; fi
img="$(pwd)/$d/image.hex"
verilator --cc --exe --build -Wno-fatal -Wno-lint -Wno-style -O3 --x-assign fast --x-initial fast --top-module tb_fast -Mdir $d/obj -DMEMFILE="\"$img\"" \
  -CFLAGS "-O3 -march=native" "$(pwd)/scripts/exm/main.cpp" scripts/exm/tb_fast.sv $(find rtl -name '*.v' | sort) > $d/verilator.log 2>&1 || { tail -n 20 $d/verilator.log >&2; echo "verilator build failed" >&2; exit 1; }
$d/obj/Vtb_fast +MAXCLK=$maxclk > "$log"
