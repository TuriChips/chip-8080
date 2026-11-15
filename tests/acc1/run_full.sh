#!/usr/bin/env bash
# Homer: the full 8080 exerciser run for the nightly (chip-8080#18, Tesla's `make nightly`).
# Contract: fetch the pinned 8080EXM (sw/exerciser/fetch.sh), run it on Verilator, write logs/nightly/8080exm.log,
# exit 0 only on a full pass (judged by tests/acc1/check_log.py against the CRCs in the fetched source).
# The simulation step is tests/acc1/sim.sh <program.com> <log>: it builds i8080_system with the CP/M BDOS stub and runs the
# program on Verilator. It does not exist yet (i8080_system is not on main), and this script then exits 2 = NOT RUN,
# never 0, so a night with no simulator cannot look like a pass.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p logs/nightly build
./sw/exerciser/fetch.sh || exit 1
if [ ! -x tests/acc1/sim.sh ]; then echo "NOT RUN: tests/acc1/sim.sh is missing (needs i8080_system, chip-8080#9)" | tee logs/nightly/8080exm.log; exit 2; fi
stamp="main commit: $(git rev-parse HEAD)$(git diff --quiet HEAD -- . ':(exclude)logs' || echo ' (+ uncommitted changes)')"
{ echo "$stamp"; tests/acc1/sim.sh build/exerciser/8080EXM.COM /dev/stdout; } > logs/nightly/8080exm.log 2>&1 || { echo "simulation failed" >> logs/nightly/8080exm.log; tail -n 5 logs/nightly/8080exm.log; exit 1; }
python3 tests/acc1/check_log.py exm logs/nightly/8080exm.log build/exerciser/8080EXM.MAC | tee -a logs/nightly/8080exm.log
exit "${PIPESTATUS[0]}"
