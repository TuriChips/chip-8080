#!/usr/bin/env bash
# C6: reset_mid with the reset landing on 16 consecutive clocks (every state of the M cycles of the spin loop and the
# preamble). Exit 1 if any run fails (pipefail and an explicit PASS check per run).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
for k in $(seq 200 215); do
  out=$(EXTRA_PLUS="+RESET_AT=$k" LOGSUFFIX="_r$k" tests/run_prog80.sh tests/c6/reset_mid | grep -E '^(PASS|FAIL)' || true)
  echo "RESET_AT=$k $out"
  case "$out" in PASS*) ;; *) echo "c6: run RESET_AT=$k did not pass"; exit 1;; esac
done
