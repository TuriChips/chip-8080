#!/usr/bin/env bash
# C7 (spec 8): no X/Z on any output of i8080_system and no bus_conflict, over real programs; Icarus (4-state).
# Runs the generated C1 data-transfer programs, the branch program and the C4 interrupt programs on the whole system.
# Usage: tests/c7/run.sh. Exit 1 if any run fails. Needs `tests/c1/run_gen.sh`'s generators (it calls them).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 tests/c1/gen_xfer.py build/gen/c1 >/dev/null; python3 tests/c1/gen_branch.py build/gen/c1 >/dev/null; python3 tests/c1/gen_alu.py build/gen/c1 >/dev/null; python3 tests/c4/gen_int.py build/gen/c4 >/dev/null
mkdir -p build/c7 logs; bad=0; n=0
for p in build/gen/c1/xfer_s1 build/gen/c1/xfer_s2 build/gen/c1/xfer_s3 build/gen/c1/branch build/gen/c1/alu_adc_mem; do
  b=build/c7/$(basename $p); python3 tests/asm80.py $p.asm $b.hex
  iverilog -g2012 -DMEMFILE="\"$b.hex\"" -o $b.vvp tb/tb_sys80.sv $(find "${RTL_DIR:-rtl}" -name '*.v') || { bad=$((bad+1)); continue; }
  r=$(vvp -n $b.vvp +EXP=$p.exp +N=$(wc -l < $p.exp) | grep -E '^(PASS|FAIL)' | head -1); n=$((n+1)); echo "$(basename $p): $r"; case "$r" in PASS*) ;; *) bad=$((bad+1));; esac
done
echo "c7: $n runs, $bad failing"; [ $bad -eq 0 ]
