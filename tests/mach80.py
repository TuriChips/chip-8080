#!/usr/bin/env python3
"""A small 8080 machine model that returns, for each instruction, the machine cycles it runs (spec 6.2) with their
bus addresses and data, and updates registers, flags and memory (spec 6). Written from spec 6 only; reads no RTL.
Used by tests/c2/gen_pins80.py to build the expected pin timing. Instructions are asm80 source lines.
cycle = (kind, addr, data, states): kind F (fetch, status A2), R (82), W (00), SR (86), SW (04), IN (42), OUT (10), I3 (idle);
data = the byte written for W/SW/OUT (None otherwise); states = 3, 4 or 5 (T1..Tn, no wait states)."""
import sys
sys.dont_write_bytecode = True
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model80
CC = ['NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M']
def cond(c, f):
    s, z, p, cy = f >> 7 & 1, f >> 6 & 1, f >> 2 & 1, f & 1
    return [not z, z, not cy, cy, not p, p, not s, s][c]
STATUS = {'F': 0xA2, 'R': 0x82, 'W': 0x00, 'SR': 0x86, 'SW': 0x04, 'IN': 0x42, 'OUT': 0x10}
class Mach:
    def __init__(s, pc=0): s.r = dict.fromkeys('ABCDEHL', 0); s.sp = 0; s.f = 0x02; s.mem = {}; s.pc = pc
    def hl(s): return s.r['H'] << 8 | s.r['L']
    def rd(s, a): return s.mem.get(a & 0xFFFF, 0)
    def get(s, x): return s.rd(s.hl()) if x == 'M' else s.r[x]
    def put(s, x, v):
        if x == 'M': s.mem[s.hl()] = v & 255
        else: s.r[x] = v & 255
    P = {'B': ('B', 'C'), 'D': ('D', 'E'), 'H': ('H', 'L')}
    def getp(s, p): return s.sp if p == 'SP' else s.r[s.P[p][0]] << 8 | s.r[s.P[p][1]]
    def setp(s, p, v):
        v &= 0xFFFF
        if p == 'SP': s.sp = v
        else: s.r[s.P[p][0]] = v >> 8; s.r[s.P[p][1]] = v & 255
    def wr(s, a, v): s.mem[a & 0xFFFF] = v & 255
    def run(s, line):
        """Executes one source line; returns the list of cycles. PC is advanced (or replaced by a jump)."""
        op, _, rest = line.strip().partition(' '); op = op.upper(); a = [x.strip() for x in rest.split(',') if x.strip()]
        pc = s.pc; num = lambda t: int(t, 0)
        b2 = lambda: s.rd(pc + 1)
        w16 = lambda: s.rd(pc + 1) | s.rd(pc + 2) << 8
        F = ('F', pc, None, 4); F5 = ('F', pc, None, 5); n = 1
        def done(cyc, length): s.pc = (pc + length) & 0xFFFF; return cyc
        # --- data transfer
        if op == 'MOV':
            d, sr = a
            if 'M' not in (d, sr): s.put(d, s.get(sr)); return done([F5], 1)
            if sr == 'M': h = s.hl(); s.put(d, s.get('M')); return done([F, ('R', h, None, 3)], 1)   # address taken before MOV H,M / MOV L,M change HL
            v = s.get(sr); s.put('M', v); return done([F, ('W', s.hl(), v, 3)], 1)
        if op == 'MVI':
            v = num(a[0 + 1]) & 255; s.pre = None
            if a[0] == 'M': h = s.hl(); s.put('M', v); return done([F, ('R', pc + 1, None, 3), ('W', h, v, 3)], 2)
            s.put(a[0], v); return done([F, ('R', pc + 1, None, 3)], 2)
        if op == 'LXI':
            v = num(a[1]); s.setp(a[0], v); return done([F, ('R', pc + 1, None, 3), ('R', pc + 2, None, 3)], 3)
        if op in ('LDA', 'STA'):
            ad = num(a[0]); c = [F, ('R', pc + 1, None, 3), ('R', pc + 2, None, 3)]
            if op == 'LDA': s.r['A'] = s.rd(ad); c.append(('R', ad, None, 3))
            else: s.wr(ad, s.r['A']); c.append(('W', ad, s.r['A'], 3))
            return done(c, 3)
        if op in ('LHLD', 'SHLD'):
            ad = num(a[0]); c = [F, ('R', pc + 1, None, 3), ('R', pc + 2, None, 3)]
            if op == 'LHLD': s.r['L'] = s.rd(ad); s.r['H'] = s.rd(ad + 1); c += [('R', ad, None, 3), ('R', ad + 1, None, 3)]
            else: s.wr(ad, s.r['L']); s.wr(ad + 1, s.r['H']); c += [('W', ad, s.r['L'], 3), ('W', ad + 1, s.r['H'], 3)]
            return done(c, 3)
        if op in ('LDAX', 'STAX'):
            ad = s.getp(a[0])
            if op == 'LDAX': s.r['A'] = s.rd(ad); return done([F, ('R', ad, None, 3)], 1)
            s.wr(ad, s.r['A']); return done([F, ('W', ad, s.r['A'], 3)], 1)
        if op == 'XCHG': s.r['D'], s.r['H'] = s.r['H'], s.r['D']; s.r['E'], s.r['L'] = s.r['L'], s.r['E']; return done([F], 1)
        if op == 'SPHL': s.sp = s.hl(); return done([F5], 1)
        if op == 'XTHL':
            sp = s.sp; l, h = s.rd(sp), s.rd(sp + 1); wl, wh = s.r['L'], s.r['H']; s.wr(sp + 1, wh); s.wr(sp, wl); s.r['L'], s.r['H'] = l, h
            return done([F, ('SR', sp, None, 3), ('SR', sp + 1, None, 3), ('SW', sp + 1, wh, 3), ('SW', sp, wl, 5)], 1)
        if op == 'PUSH':
            if a[0] == 'PSW': hi, lo = s.r['A'], s.f
            else: v = s.getp(a[0]); hi, lo = v >> 8, v & 255
            s.wr(s.sp - 1, hi); s.wr(s.sp - 2, lo); c = [F5, ('SW', s.sp - 1, hi, 3), ('SW', s.sp - 2, lo, 3)]; s.sp = (s.sp - 2) & 0xFFFF; return done(c, 1)
        if op == 'POP':
            lo, hi = s.rd(s.sp), s.rd(s.sp + 1); c = [F, ('SR', s.sp, None, 3), ('SR', s.sp + 1, None, 3)]; s.sp = (s.sp + 2) & 0xFFFF
            if a[0] == 'PSW': s.r['A'] = hi; s.f = (lo & 0xD5) | 2
            else: s.setp(a[0], hi << 8 | lo)
            return done(c, 1)
        if op == 'DAD': t = s.hl() + s.getp(a[0]); s.setp('H', t); s.f = (s.f & 0xFE) | (t >> 16); return done([F, ('I3', None, None, 3), ('I3', None, None, 3)], 1)
        if op in ('INX', 'DCX'): s.setp(a[0], s.getp(a[0]) + (1 if op == 'INX' else -1)); return done([F5], 1)
        if op == 'CMA': s.r['A'] ^= 255; return done([F], 1)
        if op == 'STC': s.f |= 1; return done([F], 1)
        if op == 'CMC': s.f ^= 1; return done([F], 1)
        if op == 'NOP': return done([F], 1)
        if op in ('EI', 'DI'): return done([F], 1)           # INTE is not modelled here
        if op == 'HLT': return done([F, ('HLTA', pc + 1, None, 3)], 1)   # F4, then the halt-acknowledge cycle: T1, T2, first TWH = 7 states (spec 6.2)
        if op == 'IN': p = num(a[0]); s.r['A'] = p ^ 0x5A; return done([F, ('R', pc + 1, None, 3), ('IN', p << 8 | p, None, 3)], 2)
        if op == 'OUT': p = num(a[0]); return done([F, ('R', pc + 1, None, 3), ('OUT', p << 8 | p, s.r['A'], 3)], 2)
        # --- arithmetic / logic
        ALU = ['ADD', 'ADC', 'SUB', 'SBB', 'ANA', 'XRA', 'ORA', 'CMP']; IMM = ['ADI', 'ACI', 'SUI', 'SBI', 'ANI', 'XRI', 'ORI', 'CPI']
        if op in ALU or op in IMM:
            name = op if op in ALU else ALU[IMM.index(op)]
            if op in IMM: v = num(a[0]) & 255; c = [F, ('R', pc + 1, None, 3)]; ln = 2
            elif a[0] == 'M': v = s.get('M'); c = [F, ('R', s.hl(), None, 3)]; ln = 1
            else: v = s.get(a[0]); c = [F]; ln = 1
            r, f = model80.alu(name, s.r['A'], v, s.f & 1)
            if name != 'CMP': s.r['A'] = r
            s.f = f; return done(c, ln)
        if op in ('INR', 'DCR'):
            fn = model80.inr if op == 'INR' else model80.dcr
            if a[0] == 'M': h = s.hl(); r, f = fn(s.get('M'), s.f); s.put('M', r); s.f = f; return done([F, ('R', h, None, 3), ('W', h, r, 3)], 1)
            r, f = fn(s.get(a[0]), s.f); s.put(a[0], r); s.f = f; return done([F5], 1)
        if op == 'DAA': s.r['A'], s.f = model80.daa(s.r['A'], s.f, carry1=True); return done([F], 1)
        if op in ('RLC', 'RRC', 'RAL', 'RAR'): s.r['A'], s.f = model80.rot(op, s.r['A'], s.f); return done([F], 1)
        # --- branches
        if op in ('JMP',) or (op[0] == 'J' and op[1:] in CC):
            t = num(a[0]); c = [F, ('R', pc + 1, None, 3), ('R', pc + 2, None, 3)]
            take = op == 'JMP' or cond(CC.index(op[1:]), s.f); s.pc = t & 0xFFFF if take else (pc + 3) & 0xFFFF; return c
        if op == 'CALL' or (op[0] == 'C' and op[1:] in CC and op != 'CMA' and op != 'CMC'):
            t = num(a[0]); take = op == 'CALL' or cond(CC.index(op[1:]), s.f); c = [F5, ('R', pc + 1, None, 3), ('R', pc + 2, None, 3)]
            if take:
                ra = (pc + 3) & 0xFFFF; s.wr(s.sp - 1, ra >> 8); s.wr(s.sp - 2, ra & 255); c += [('SW', s.sp - 1, ra >> 8, 3), ('SW', s.sp - 2, ra & 255, 3)]; s.sp = (s.sp - 2) & 0xFFFF; s.pc = t & 0xFFFF
            else: s.pc = (pc + 3) & 0xFFFF
            if op == 'CALL': c[0] = F5
            else: c[0] = F5
            return c
        if op == 'RET' or (op[0] == 'R' and op[1:] in CC):
            take = op == 'RET' or cond(CC.index(op[1:]), s.f); c = [F if op == 'RET' else F5]
            if take:
                lo, hi = s.rd(s.sp), s.rd(s.sp + 1); c += [('SR', s.sp, None, 3), ('SR', s.sp + 1, None, 3)]; s.sp = (s.sp + 2) & 0xFFFF; s.pc = hi << 8 | lo
            else: s.pc = (pc + 1) & 0xFFFF
            return c
        if op == 'RST':
            ra = (pc + 1) & 0xFFFF; s.wr(s.sp - 1, ra >> 8); s.wr(s.sp - 2, ra & 255)
            c = [F5, ('SW', s.sp - 1, ra >> 8, 3), ('SW', s.sp - 2, ra & 255, 3)]; s.sp = (s.sp - 2) & 0xFFFF; s.pc = 8 * num(a[0]); return c
        if op == 'PCHL': s.pc = s.hl(); return [F5]
        raise SystemExit(f"mach80: unsupported {line!r}")
if __name__ == '__main__':
    m = Mach(); m.sp = 0x4800
    for l, states in (("MVI A,5", 7), ("MOV B,A", 5), ("LXI H,0x4000", 10), ("MOV M,B", 7), ("MVI M,3", 10), ("PUSH PSW", 11), ("POP D", 10), ("XTHL", 18),
                      ("DAD SP", 10), ("INX H", 5), ("STA 0x4001", 13), ("LHLD 0x4000", 16), ("SHLD 0x4010", 16), ("INR M", 10), ("ADD M", 7), ("ADI 3", 7), ("DAA", 4),
                      ("CALL 0x200", 17), ("RET", 10), ("JNZ 0x300", 10), ("CNZ 0x300", 17), ("RST 3", 11), ("PCHL", 5), ("IN 3", 10), ("OUT 3", 10), ("SPHL", 5), ("XCHG", 4)):
        m.pc = 0x100 if l != "RET" else m.pc
        if l == "RET": pass
        cyc = m.run(l)
        got = sum(c[3] for c in cyc)
        if l.startswith("CNZ") and not cond(0, m.f): states = 11
        assert got == states, f"{l}: {got} states, spec 6.1 says {states}"
    print("PASS mach80 selftest: state counts of 27 instructions match spec 6.1")
