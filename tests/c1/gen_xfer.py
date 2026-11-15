#!/usr/bin/env python3
"""Generates C1 tests for the data-transfer, pair, stack and misc rows of spec 6.1 (MOV, MVI, LXI, LDA, STA, LHLD, SHLD,
LDAX, STAX, XCHG, SPHL, XTHL, PUSH, POP incl. PSW, DAD, INX, DCX, CMA, STC, CMC, IN, OUT): seeded random straight-line
programs, with the expected trace from a small machine model below, written from spec 6 only (registers, 64 KiB memory,
SP, F with CY changed only by STC, CMC, DAD and POP PSW). The model reads no RTL and is not Beru's reference model.
Every 16 instructions the whole state is written out and left unchanged:
  PUSH PSW; OUT 0 (A); MOV A,B..L; OUT 1..6; LDA <SP-2> ; OUT 7 (F); POP PSW      (SP is known to the model).
Memory under test is the region 4000..40FF (HL/BC/DE/WZ-style addresses are loaded there first), the stack is at 4800.
Usage: gen_xfer.py [outdir]  -> xfer_s<seed>.asm/.exp for seeds 1..3 (4000 instructions each)."""
import os, random, sys
sys.dont_write_bytecode = True
d = sys.argv[1] if len(sys.argv) > 1 else "build/gen/c1"; os.makedirs(d, exist_ok=True)
R = 'BCDEHLMA'
class M:
    def __init__(s): s.r = {x: 0 for x in 'BCDEHLA'}; s.sp = 0x4800; s.f = 0x02; s.mem = {}; s.out = []
    def hl(s): return s.r['H'] << 8 | s.r['L']
    def get(s, x): return s.mem.get(s.hl(), 0) if x == 'M' else s.r[x]
    def put(s, x, v):
        if x == 'M': s.mem[s.hl()] = v & 255
        else: s.r[x] = v & 255
    def pair(s, p): return {'B': 'BC', 'D': 'DE', 'H': 'HL'}[p]
    def getp(s, p): return s.sp if p == 'SP' else s.r[p] << 8 | s.r[{'B': 'C', 'D': 'E', 'H': 'L'}[p]]
    def setp(s, p, v):
        v &= 0xFFFF
        if p == 'SP': s.sp = v
        else: s.r[p] = v >> 8; s.r[{'B': 'C', 'D': 'E', 'H': 'L'}[p]] = v & 255
    def push(s, hi, lo): s.mem[(s.sp - 1) & 0xFFFF] = hi; s.mem[(s.sp - 2) & 0xFFFF] = lo; s.sp = (s.sp - 2) & 0xFFFF
    def pop(s): lo = s.mem.get(s.sp, 0); hi = s.mem.get((s.sp + 1) & 0xFFFF, 0); s.sp = (s.sp + 2) & 0xFFFF; return hi, lo
def gen(seed, n=4000):
    rnd = random.Random(seed); m = M(); asm = []; i = 0
    def emit(line): asm.append("        " + line)
    def lxi(p, v): emit(f"LXI {p},{v}"); m.setp(p, v)
    emit("LXI SP,0x4800")
    for x in 'BCDEHL': v = rnd.randrange(256); emit(f"MVI {x},{v}"); m.r[x] = v
    f0 = rnd.choice([0x02, 0x03, 0xD6, 0xD7]); a0 = rnd.randrange(256); emit(f"LXI D,{a0 << 8 | f0}"); emit("PUSH D"); emit("POP PSW"); m.setp('D', a0 << 8 | f0); m.r['A'] = a0; m.f = f0
    lxi('D', rnd.randrange(0x4000, 0x4100))
    def dump():
        emit("PUSH PSW"); m.push(m.r['A'], m.f)
        emit("OUT 0"); m.out.append(0x0000 | m.r['A'])
        for k, x in enumerate('BCDEHL', 1): emit(f"MOV A,{x}"); emit(f"OUT {k}"); m.out.append(k << 8 | m.r[x])
        emit(f"LDA {(m.sp) & 0xFFFF}"); emit("OUT 7"); m.out.append(0x0700 | m.mem[m.sp])      # F is at SP after the PUSH
        emit("POP PSW"); hi, lo = m.pop(); m.r['A'] = hi; m.f = (lo & 0xD5) | 0x02
    kinds = ['mov', 'mvi', 'lxi', 'lda', 'sta', 'lhld', 'shld', 'ldax', 'stax', 'xchg', 'sphl', 'xthl', 'push', 'pop', 'dad', 'inx', 'dcx', 'cma', 'stc', 'cmc', 'in', 'out']
    while i < n:
        if i % 64 == 0: lxi('SP', 0x4800)
        k = rnd.choice(kinds)
        if k == 'mov':
            dd, ss = rnd.choice(R), rnd.choice(R)
            if dd == 'M' and ss == 'M': continue
            if 'M' in (dd, ss): lxi('H', rnd.randrange(0x4000, 0x4100))
            emit(f"MOV {dd},{ss}"); m.put(dd, m.get(ss))
        elif k == 'mvi':
            dd = rnd.choice(R); v = rnd.randrange(256)
            if dd == 'M': lxi('H', rnd.randrange(0x4000, 0x4100))
            emit(f"MVI {dd},{v}"); m.put(dd, v)
        elif k == 'lxi':
            p = rnd.choice(['B', 'D', 'H']); lxi(p, rnd.randrange(65536)) if rnd.random() < .7 else lxi(p, rnd.randrange(0x4000, 0x4100))
        elif k == 'lda': a = rnd.randrange(0x4000, 0x4100); emit(f"LDA {a}"); m.r['A'] = m.mem.get(a, 0)
        elif k == 'sta': a = rnd.randrange(0x4000, 0x4100); emit(f"STA {a}"); m.mem[a] = m.r['A']
        elif k == 'lhld': a = rnd.randrange(0x4000, 0x40FF); emit(f"LHLD {a}"); m.r['L'] = m.mem.get(a, 0); m.r['H'] = m.mem.get(a + 1, 0)
        elif k == 'shld': a = rnd.randrange(0x4000, 0x40FF); emit(f"SHLD {a}"); m.mem[a] = m.r['L']; m.mem[a + 1] = m.r['H']
        elif k in ('ldax', 'stax'):
            p = rnd.choice(['B', 'D']); lxi(p, rnd.randrange(0x4000, 0x4100)); a = m.getp(p)
            emit(f"{k.upper()} {p}")
            if k == 'ldax': m.r['A'] = m.mem.get(a, 0)
            else: m.mem[a] = m.r['A']
        elif k == 'xchg': emit("XCHG"); m.r['D'], m.r['H'] = m.r['H'], m.r['D']; m.r['E'], m.r['L'] = m.r['L'], m.r['E']
        elif k == 'sphl': lxi('H', rnd.randrange(0x4700, 0x4900)); emit("SPHL"); m.sp = m.hl()
        elif k == 'xthl':
            emit("XTHL"); l, h = m.mem.get(m.sp, 0), m.mem.get((m.sp + 1) & 0xFFFF, 0)
            m.mem[m.sp] = m.r['L']; m.mem[(m.sp + 1) & 0xFFFF] = m.r['H']; m.r['L'], m.r['H'] = l, h
        elif k == 'push':
            p = rnd.choice(['B', 'D', 'H', 'PSW']); emit(f"PUSH {p}")
            if p == 'PSW': m.push(m.r['A'], m.f)
            else: m.push(m.getp(p) >> 8, m.getp(p) & 255)
        elif k == 'pop':
            p = rnd.choice(['B', 'D', 'H', 'PSW']); emit(f"POP {p}"); hi, lo = m.pop()
            if p == 'PSW': m.r['A'] = hi; m.f = (lo & 0xD5) | 0x02
            else: m.setp(p, hi << 8 | lo)
        elif k == 'dad':
            p = rnd.choice(['B', 'D', 'H', 'SP']); emit(f"DAD {p}"); t = m.hl() + m.getp(p); m.setp('H', t); m.f = (m.f & 0xFE) | (t >> 16)
        elif k in ('inx', 'dcx'):
            p = rnd.choice(['B', 'D', 'H', 'SP']); emit(f"{k.upper()} {p}"); m.setp(p, m.getp(p) + (1 if k == 'inx' else -1))
        elif k == 'cma': emit("CMA"); m.r['A'] ^= 255
        elif k == 'stc': emit("STC"); m.f |= 1
        elif k == 'cmc': emit("CMC"); m.f ^= 1
        elif k == 'in': p = rnd.randrange(256); emit(f"IN {p}"); m.r['A'] = p ^ 0x5A
        elif k == 'out': p = rnd.randrange(256); emit(f"OUT {p}"); m.out.append(p << 8 | m.r['A'])
        i += 1
        if i % 16 == 0: dump()
    dump()
    return asm, m.out
for seed in (1, 2, 3):
    asm, out = gen(seed)
    asm = [f"; C1 data transfer / pairs / stack / misc, seed {seed}, generated by gen_xfer.py", "        .org 0"] + asm + ["end:    JMP end"]
    open(f"{d}/xfer_s{seed}.asm", "w").write("\n".join(asm) + "\n")
    open(f"{d}/xfer_s{seed}.exp", "w").write("\n".join("%04X" % e for e in out) + "\n")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); import asm80
for seed in (1, 2, 3):   # the program must stay below the data region 4000
    top = max(asm80.assemble(open(f"{d}/xfer_s{seed}.asm").read().splitlines(), True, {}))
    assert top < 0x3F00, f"seed {seed}: program reaches {top:#x}"
print("wrote xfer programs")
