#!/usr/bin/env python3
"""Cross-check of gen_int_pins.py's expected pins against Beru's pin-level model (ref/pins8080.py) with an interrupt injected: the model
is driven instruction by instruction; INT is requested right after the instruction in which state K falls (the model accepts at the next boundary), or, while halted, after TWH state K.
Usage: crosscheck_int_pins.py <prog.asm> <prog.pins> <K> [refdir]   (SKIP if refdir has no pins8080.py)"""
import os, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here + '/..')
import asm80
asm, pins, K = sys.argv[1], sys.argv[2], int(sys.argv[3]); ref = sys.argv[4] if len(sys.argv) > 4 else 'ref'
if not os.path.exists(os.path.join(ref, 'pins8080.py')): print("SKIP no", ref + "/pins8080.py"); sys.exit(0)
sys.path.insert(0, ref); import ref8080, pins8080
src = open(asm).read().splitlines(); labels = {}; asm80.assemble(src, False, labels); mem = asm80.assemble(src, True, labels)
img = bytearray(max(mem) + 1)
for a, b in mem.items(): img[a] = b
out3 = []; cpu = ref8080.CPU(bytes(img), inp=lambda p: p ^ 0x5A, out=lambda p, v: out3.append((p, v)))
pm = pins8080.PinModel(cpu); seq = []; requested = False; n = 0
while not any(p == 3 for p, _ in out3):
    if cpu.halted and not (cpu.int_req is not None and cpu.inte):
        seq.append(pins8080.TWH(cpu.inte)); pm.n += 1; n += 1
        if not requested and n == K + 1: cpu.request_interrupt(1); requested = True
        continue
    _, ps = pm.instruction_states(); seq += ps; n += len(ps)
    if not requested and K <= n - 1: cpu.request_interrupt(1); requested = True    # INT rose during the instruction just run: accepted at its end
rows = [l.split() for l in open(pins)]; bad = 0
bits = dict(sync=7, a_oe=6, d_oe=5, dbin=4, wr_n=3, wait_o=2, hlda=1, inte=0)
for i, row in enumerate(rows):
    if i >= len(seq): bad += 1; print("model ended early at", i); break
    fl, mk, a, d, _r, _h = row; fl = int(fl, 16); mk = int(mk, 16); p = seq[i]; diff = []
    for k, bt in bits.items():
        v = getattr(p, k)
        if mk >> bt & 1 and v is not None and v != (fl >> bt & 1): diff.append(k)
        if mk >> bt & 1 and v is None and k != 'd_oe': diff.append(k + '(model none)')
    if 'x' not in a and p.a is not None and p.a != int(a, 16): diff.append('a')
    if 'x' not in a and p.a is None: diff.append('a(model none)')
    if 'x' not in d and p.d_out is not None and p.d_out != int(d, 16): diff.append('d_out')
    if 'x' not in d and p.d_out is None: diff.append('d_out(model none)')
    if diff:
        bad += 1
        if bad < 8: print(f"state {i}: differ in {diff}: mine {' '.join(row)} / ref {p}")
if len(seq) != len(rows): print(f"length: mine {len(rows)} states, model {len(seq)}"); bad += 1
print(f"{'PASS' if not bad else 'FAIL'} crosscheck_int_pins K={K}: {len(rows)} states, {bad} differences")
sys.exit(1 if bad else 0)
