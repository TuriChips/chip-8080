#!/usr/bin/env bash
# Homer: the 8080 demo. From the repo root: ./sw/run_demo.sh   Output: logs/demo/demo.log (first line = the commit)
# Assembles sw/demo.asm (tests/asm80.py), runs it on the RTL under Verilator (tests/acc1/sim.sh) and compares what it
# printed with sw/demo.expected.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p logs/demo build
stamp="main commit: $(git rev-parse HEAD)$(git diff --quiet HEAD -- . ':(exclude)logs' || echo ' (+ uncommitted changes)')"
python3 tests/asm80.py sw/demo.asm build/demo.hex || exit 1
tests/acc1/sim.sh build/demo.hex build/demo.console 5000000 || exit 1
got=$(grep -v -E '^(RUN DONE|RUN TIMEOUT|- tests/)' build/demo.console | tr -d '\r' | sed '/^$/d')
{ echo "$stamp"; cat build/demo.console; } > logs/demo/demo.log
grep -q '^RUN DONE' build/demo.console || { echo "DEMO FAIL: did not end by itself" | tee -a logs/demo/demo.log; exit 1; }
if [ "$got" = "$(cat sw/demo.expected)" ]; then echo "DEMO PASS: printed '$got'" | tee -a logs/demo/demo.log
else echo "DEMO FAIL: printed '$got', expected '$(cat sw/demo.expected)'" | tee -a logs/demo/demo.log; exit 1; fi
