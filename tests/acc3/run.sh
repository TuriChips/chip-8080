#!/usr/bin/env bash
# Homer: acceptance test 3 (spec section 9 item 3): worked programs from the Intel 8080/8085 Assembly Language Programming
# Manual, run on the RTL under Verilator. For each program: assemble (tests/asm80.py), run (tests/acc1/sim.sh), compare what it
# printed with <name>.expected. Log: logs/acc3/run.log (first line = commit). Exit 0 only if every program matches.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p logs/acc3 build/acc3
stamp="main commit: $(git rev-parse HEAD)$(git diff --quiet HEAD -- . ':(exclude)logs' || echo ' (+ uncommitted changes)')"
fail=0; out=""
for p in madd msub adsub dsub dadd; do
  python3 tests/asm80.py tests/acc3/$p.asm build/acc3/$p.hex || { out+="$p: ASSEMBLY FAILED\n"; fail=1; continue; }
  tests/acc1/sim.sh build/acc3/$p.hex build/acc3/$p.console 5000000 || { out+="$p: SIMULATION FAILED\n"; fail=1; continue; }
  got=$(grep -v -E '^(RUN DONE|RUN TIMEOUT|- tests/)' build/acc3/$p.console | tr -d '\r' | sed '/^$/d')
  grep -q '^RUN DONE' build/acc3/$p.console || { out+="$p: FAIL, did not end by itself\n"; fail=1; continue; }
  if [ "$got" = "$(grep -v "^#" tests/acc3/$p.expected)" ]; then out+="$p: PASS printed $got, expected $(grep -v "^#" tests/acc3/$p.expected)\n"
  else out+="$p: FAIL printed '$got', expected '$(grep -v "^#" tests/acc3/$p.expected)'\n"; fail=1; fi
done
{ echo "$stamp"; printf "$out"; [ $fail = 0 ] && echo "ACC3 PASS" || echo "ACC3 FAIL"; } | tee logs/acc3/run.log
exit $fail
