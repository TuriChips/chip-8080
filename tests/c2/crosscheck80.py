#!/usr/bin/env python3
"""Cross-check of my expected pins (gen_pins80.py, from mach80.py) against Beru's pin-level reference model
(ref/pins8080.py), two models written independently from spec 4 / 6.2. Usage: crosscheck80.py <prog.asm> <prog.pins> [refdir]
refdir defaults to ./ref (skips with exit 0 and a message if ref/pins8080.py is not there yet)."""
import os, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here + '/..')
import asm80
asm, pins = sys.argv[1], sys.argv[2]; ref = sys.argv[3] if len(sys.argv) > 3 else 'ref'
if not os.path.exists(os.path.join(ref, 'pins8080.py')): print("SKIP no", ref + "/pins8080.py"); sys.exit(0)
sys.path.insert(0, ref); import ref8080, pins8080
src = open(asm).read().splitlines(); labels = {}; asm80.assemble(src, False, labels); mem = asm80.assemble(src, True, labels); img = bytearray(max(mem) + 1)
for a, b in mem.items(): img[a] = b
rows = [l.split() for l in open(pins)]
cpu = ref8080.CPU(bytes(img), inp=lambda p: p ^ 0x5A); model = pins8080.PinModel(cpu, ready=lambda n: int(rows[n][4]) if n < len(rows) else 1, hold=lambda n: int(rows[n][5]) if n < len(rows) else 0).states()   # needs a ref/ with hold(n) (PR #29/#42)
bad = 0; n = 0
for line in open(pins):
    fl, mk, a, d, _r, _h = line.split(); fl = int(fl, 16); mk = int(mk, 16); p = next(model); n += 1
    exp = dict(sync=fl >> 7 & 1, a_oe=fl >> 6 & 1, d_oe=fl >> 5 & 1, dbin=fl >> 4 & 1, wr_n=fl >> 3 & 1, wait_o=fl >> 2 & 1, hlda=fl >> 1 & 1, inte=fl & 1)
    bits = dict(sync=7, a_oe=6, d_oe=5, dbin=4, wr_n=3, wait_o=2, hlda=1, inte=0)
    diff = [k for k, v in exp.items() if mk >> bits[k] & 1 and getattr(p, k) is not None and getattr(p, k) != v]
    diff += [k for k, v in exp.items() if mk >> bits[k] & 1 and getattr(p, k) is None and k in ('sync', 'wr_n', 'dbin', 'wait_o', 'a_oe')]
    if 'x' not in a and p.a is not None and p.a != int(a, 16): diff.append('a')
    if 'x' not in a and p.a is None: diff.append('a(model has none)')
    if 'x' not in d and p.d_out is not None and p.d_out != int(d, 16): diff.append('d_out')
    if 'x' not in d and p.d_out is None: diff.append('d_out(model has none)')
    if diff:
        bad += 1
        if bad < 15: print(f"state {n - 1}: differ in {diff}: mine {line.strip()} / ref {p}")
print(f"{'PASS' if not bad else 'FAIL'} crosscheck80: {n} states, {bad} differences")
sys.exit(1 if bad else 0)
