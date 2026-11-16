#!/usr/bin/env bash
# C8 on the sky130 gate-level netlist (Beru, #59): synth/sky130/i8080_sky130.v in place of the RTL
# i8080, with the RTL i8080_system/i8080_mem around it, PDK functional cell models, zero delay,
# Icarus (4-state, so X/Z after reset shows up as a mismatch). Runs C8 (random READY/INT/HOLD per §7)
# and then C8 with mid-run resets. Each run is cut off after GL_TIMEOUT seconds (default 3600) and counts as FAIL.
# Usage: tests/random/gl_sky130.sh [NPROG NST SEED]   default: 50 3000 1
set -u
cd "$(git rev-parse --show-toplevel)"
cells="${PDK_ROOT:-/nonexistent}/sky130A/libs.ref/sky130_fd_sc_hd/verilog"
net=synth/sky130/i8080_sky130.v
if [ ! -f "$cells/sky130_fd_sc_hd.v" ] || [ ! -f "$net" ]; then
  echo "SKIP gate-level sky130 (need $net and PDK_ROOT with sky130A cell models)"; exit 0
fi
dir=build/gl_sky130/src; rm -rf "$dir"; mkdir -p "$dir"
cp rtl/control/i8080_system.v rtl/datapath/i8080_mem.v "$net" "$dir/"
n=${1:-50}; st=${2:-3000}; seed=${3:-1}
gl=(--timeout "${GL_TIMEOUT:-3600}" --rtl "$dir" --extra "$cells/primitives.v" "$cells/sky130_fd_sc_hd.v" --define FUNCTIONAL UNIT_DELAY=)
rc=0
python3 -I tests/random/c8/run.py "${gl[@]}" --out build/gl_sky130/c8 --nprog "$n" --nst "$st" --seed "$seed" || rc=1
python3 -I tests/random/c8/run_resets.py "${gl[@]}" --out build/gl_sky130/c8r --nprog "$((n / 5 + 1))" --nst "$((st * 2))" --seed "$((seed + 1000))" || rc=1
[ $rc -eq 0 ] && echo "PASS gate-level sky130 C8" || echo "FAIL gate-level sky130 C8"
exit $rc
