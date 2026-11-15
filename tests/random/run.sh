#!/usr/bin/env bash
# Beru's random tests for the 8080, run by the toolchain's `make all` (run_tests.sh).
#   1. ref/ref8080.py selftest (spec §6 rules; all 244 opcodes' state counts vs User's Manual p.4-15)
#   2. Acceptance test 3: model vs MAME's 8080 core on the intel02 machine, 5 programs x 2,000
#      instructions. SKIP (not PASS) when MAME isn't fetched (tests/random/acc3/fetch_mame.sh; CI caches it).
#   C8 (RTL vs model, every pin) is added here once the RTL exists.
# Usage: tests/random/run.sh   Logs: $RUN_DIR/random-*.log (default logs/<timestamp>/)
set -u
cd "$(git rev-parse --show-toplevel)"
run="${RUN_DIR:-logs/$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$run"
ok=0
step() { # name log cmd...
  local name=$1 log=$2; shift 2
  if "$@" >"$log" 2>&1 && grep -q '^PASS' "$log" && ! grep -q -E '^(FAIL|MISMATCH)' "$log"; then
    echo "PASS $name"
  else
    echo "FAIL $name ($log)"; ok=1
  fi
}
step ref-selftest "$run/random-ref-selftest.log" python3 -I ref/ref8080.py selftest
MAME_DIR="${MAME_DIR:-build/mame}"
if [ -x "$MAME_DIR/root/usr/games/mame" ]; then
  step acc3 "$run/random-acc3.log" env MAME_DIR="$MAME_DIR" python3 -I tests/random/acc3/run.py 5 2000 100
else
  echo "SKIP acc3 (no MAME at $MAME_DIR; run tests/random/acc3/fetch_mame.sh)"
fi
exit $ok
