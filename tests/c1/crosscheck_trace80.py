#!/usr/bin/env python3
"""Cross-check of a generated C1 program's expected OUT trace (.exp, `PPDD` words) against Beru's instruction-level
reference model (ref/ref8080.py): runs the program on ref8080.CPU (IN returns port ^ 5A, like the testbench) and compares
every OUT (port, data). Usage: crosscheck_trace80.py <prog.asm> <prog.exp> [refdir]  (SKIP if ref/ref8080.py is absent)."""
import os, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here + '/..')
import asm80
asm, exp = sys.argv[1], sys.argv[2]; ref = sys.argv[3] if len(sys.argv) > 3 else 'ref'
if not os.path.exists(os.path.join(ref, 'ref8080.py')): print("SKIP no", ref + "/ref8080.py"); sys.exit(0)
sys.path.insert(0, ref); import ref8080
want = [int(x, 16) for x in open(exp).read().split()]
src = open(asm).read().splitlines(); labels = {}; asm80.assemble(src, False, labels); mem = asm80.assemble(src, True, labels); img = bytearray(max(mem) + 1)
for a, b in mem.items(): img[a] = b
got = []; cpu = ref8080.CPU(bytes(img), inp=lambda p: p ^ 0x5A, out=lambda p, v: got.append(p << 8 | v))
steps = 0
while len(got) < len(want) and steps < 5_000_000: cpu.step(); steps += 1
bad = [i for i in range(len(want)) if i >= len(got) or got[i] != want[i]]
for i in bad[:10]: print(f"entry {i}: mine {want[i]:04X} ref {'%04X' % got[i] if i < len(got) else 'none'}")
print(f"{'PASS' if not bad else 'FAIL'} crosscheck_trace80 {os.path.basename(asm)}: {len(want)} entries, {len(bad)} differences")
sys.exit(1 if bad else 0)
