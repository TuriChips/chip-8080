#!/usr/bin/env bash
# Tesla: copy of tests/acc1/run_full.sh using the faster C++-clocked simulator (scripts/exm). Same contract and same check_log.py judgement.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p logs/nightly build
./sw/exerciser/fetch.sh || exit 1
if [ ! -x scripts/exm/sim_fast.sh ]; then echo "NOT RUN: scripts/exm/sim_fast.sh is missing (needs i8080_system, chip-8080#9)" | tee logs/nightly/8080exm.log; exit 2; fi
stamp="main commit: $(git rev-parse HEAD)$(git diff --quiet HEAD -- . ':(exclude)logs' || echo ' (+ uncommitted changes)')"
if scripts/exm/sim_fast.sh build/exerciser/8080EXM.COM build/acc1/exm.console; then ok=1; else ok=0; fi
{ echo "$stamp"; cat build/acc1/exm.console 2>/dev/null; } > logs/nightly/8080exm.log
[ $ok = 1 ] || { echo "simulation failed" >> logs/nightly/8080exm.log; tail -n 5 logs/nightly/8080exm.log; exit 1; }
python3 tests/acc1/check_log.py exm logs/nightly/8080exm.log build/exerciser/8080EXM.MAC | tee -a logs/nightly/8080exm.log
exit "${PIPESTATUS[0]}"
