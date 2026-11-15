#!/usr/bin/env bash
# C4 pins: generates tests/c4/gen_int_pins.py's programs and runs each with INT raised at its state K (+INT_AT=K). Exit 1 if any fails.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 tests/c4/gen_int_pins.py build/gen/c4pins >/dev/null; bad=0; n=0
while read -r name k; do
  n=$((n+1)); out=$(EXTRA_PLUS="+INT_AT=$k" tests/run_pins80.sh build/gen/c4pins/$name 2>&1); r=$(grep -E '^(PASS|FAIL)' <<<"$out" | head -1)
  echo "$name (INT_AT=$k): $r"; case "$r" in PASS*) ;; *) bad=$((bad+1)); grep -E '^FAIL state' <<<"$out" | head -3;; esac
done < build/gen/c4pins/ks.txt
echo "c4 pins: $n runs, $bad failing"; [ $bad -eq 0 ]
