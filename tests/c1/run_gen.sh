#!/usr/bin/env bash
# C1/C5 generated programs (ALU group, DAA, INR/DCR, rotates): generate from tests/model80.py and run each. Exit 1 if any fails.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 tests/c1/gen_alu.py build/gen/c1 >/dev/null; python3 tests/c1/gen_misc.py build/gen/c1 >/dev/null; bad=0
for f in build/gen/c1/*.asm; do
  n=${f%.asm}; out=$(tests/run_prog80.sh "$n" 2>&1); r=$(grep -E '^(PASS|FAIL)' <<<"$out" | head -1)
  echo "$(basename "$n") $r"; case "$r" in PASS*) ;; *) bad=$((bad+1));; esac
done
echo "c1 generated programs: $bad failing"; [ $bad -eq 0 ]
