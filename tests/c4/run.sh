#!/usr/bin/env bash
# C4: generates the interrupt programs (tests/c4/gen_int.py) and runs each with INT raised at its start state (+INT_AT=K).
# Exit 1 if any run fails. Usage: tests/c4/run.sh [name-filter]
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 tests/c4/gen_int.py build/gen/c4 >/dev/null; bad=0; n=0
while read -r name k; do
  [[ -n "${1:-}" && "$name" != *$1* ]] && continue
  n=$((n+1)); out=$(EXTRA_PLUS="+INT_AT=$k" LOGSUFFIX="" tests/run_prog80.sh build/gen/c4/$name 2>&1); r=$(grep -E '^(PASS|FAIL)' <<<"$out" | head -1)
  [ -n "${VERBOSE:-}" ] && echo "$name (INT_AT=$k): $r"
  case "$r" in PASS*) ;; *) bad=$((bad+1)); echo "$name (INT_AT=$k): $r";; esac
done < build/gen/c4/ks.txt
echo "c4: $n runs, $bad failing"; [ $bad -eq 0 ]
