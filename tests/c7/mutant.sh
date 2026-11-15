#!/usr/bin/env bash
# C7 must be able to fail, and bus_conflict must be seen to rise (spec 8: the positive case). Each mutant is applied to a scratch copy of rtl/
# (build/c7/mut_*, never the tree):
#   dbin_on : DBIN stuck at 1, so the system drives the bus while the CPU also drives it  -> bus_conflict must rise (tb_sys80 +EXPECT_CONFLICT=1)
#   doe_on  : d_oe stuck at 1 (the CPU drives the data bus while DBIN is high)             -> bus_conflict must rise
#   dout_z  : d_out is Z when the CPU is not driving                                       -> the normal run must FAIL with 'FAIL C7 X/Z'
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
python3 tests/c1/gen_xfer.py build/gen/c1 >/dev/null; mkdir -p build/c7; ok=0
P=build/gen/c1/xfer_s1; sed '0,/\.org 0/s//.org 0\n        JMP 256\n        .org 256/' $P.asm > build/c7/mut.asm; python3 tests/asm80.py build/c7/mut.asm build/c7/mut.hex
try() { # name file sed-expr mode(conflict|xz)
  local d=build/c7/mut_$1; rm -rf "$d"; mkdir -p "$d"; cp -r rtl "$d/"; sed -i "$3" "$d/rtl/$2"
  cmp -s "rtl/$2" "$d/rtl/$2" && { echo "mutant $1: sed changed nothing"; ok=1; return; }
  iverilog -g2012 -DMEMFILE='"build/c7/mut.hex"' -o $d/sim.vvp tb/tb_sys80.sv $(find $d/rtl -name '*.v') || { echo "mutant $1: does not compile"; ok=1; return; }
  if [ "$4" = conflict ]; then out=$(vvp -n $d/sim.vvp +EXPECT_CONFLICT=1 +CLOCKS=20000); want='^PASS: bus_conflict rose'
  else out=$(vvp -n $d/sim.vvp +EXP=$P.exp +N=$(wc -l < $P.exp)); want='FAIL C7 X/Z'; fi
  if grep -q "$want" <<<"$out"; then echo "mutant $1: caught ($(grep -m1 "$want" <<<"$out" | cut -c1-70))"; else echo "mutant $1: NOT caught"; ok=1; fi
}
try dbin_on control/i8080_control.v 's/assign dbin = dbn;/assign dbin = 1'"'"'b1;/' conflict
try doe_on  control/i8080_control.v 's/assign d_oe = doe;/assign d_oe = 1'"'"'b1;/' conflict
try dout_z  top.v 's/assign d_out = (d_out_sel == 3'"'"'d0)/assign d_out = ~d_oe ? 8'"'"'hzz : (d_out_sel == 3'"'"'d0)/' xz
exit $ok
