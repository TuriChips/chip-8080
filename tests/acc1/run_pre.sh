#!/usr/bin/env bash
# Homer: 8080PRE, the short preliminary exerciser, on the RTL under Verilator (per-push CI). Log: logs/acc1/8080pre.log
# Exit 0 only if check_log.py says the run completed with no ERROR. Takes seconds.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p logs/acc1 build
./sw/exerciser/fetch.sh || exit 1
stamp="main commit: $(git rev-parse HEAD)$(git diff --quiet HEAD -- . ':(exclude)logs' || echo ' (+ uncommitted changes)')"   # before the log is written
if tests/acc1/sim.sh build/exerciser/8080PRE.COM build/acc1/pre.console 50000000; then ok=1; else ok=0; fi
{ echo "$stamp"; cat build/acc1/pre.console 2>/dev/null; } > logs/acc1/8080pre.log
[ $ok = 1 ] || { tail -n 5 logs/acc1/8080pre.log; echo "simulation failed"; exit 1; }
python3 tests/acc1/check_log.py pre logs/acc1/8080pre.log | tee -a logs/acc1/8080pre.log
grep -q "^RUN DONE" logs/acc1/8080pre.log || { echo "FAIL: the run did not end by itself" | tee -a logs/acc1/8080pre.log; exit 1; }
exit "${PIPESTATUS[0]}"
