#!/usr/bin/env bash
# Cross-checks every generated expectation against Beru's reference models (ref/ref8080.py, ref/pins8080.py),
# two independent models of the spec: C1/C5 traces (instruction level) and C2 pins (pin level). SKIPs if ref/ is absent.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
[ -f ref/ref8080.py ] || { echo "SKIP no ref/ref8080.py"; exit 0; }
python3 tests/c1/gen_alu.py build/gen/c1 >/dev/null; python3 tests/c1/gen_misc.py build/gen/c1 >/dev/null
python3 tests/c1/gen_xfer.py build/gen/c1 >/dev/null; python3 tests/c1/gen_branch.py build/gen/c1 >/dev/null; python3 tests/c2/gen_pins80.py build/gen/c2 >/dev/null
bad=0; n=0
for f in build/gen/c1/*.asm; do b=${f%.asm}; n=$((n+1)); python3 tests/c1/crosscheck_trace80.py "$f" "$b.exp" ref >/tmp/cc.$$ 2>&1 || { bad=$((bad+1)); cat /tmp/cc.$$; }; done
for f in build/gen/c2/*.asm; do b=${f%.asm}; case "$(basename $b)" in pins_r*) continue;; esac   # reset cases: Beru's pin model has no mid-run reset
  n=$((n+1)); python3 tests/c2/crosscheck80.py "$f" "$b.pins" ref >/tmp/cc.$$ 2>&1 || { bad=$((bad+1)); cat /tmp/cc.$$; }; done
rm -f /tmp/cc.$$; echo "crosscheck: $n programs, $bad differing"; [ $bad -eq 0 ]
