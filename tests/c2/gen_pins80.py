#!/usr/bin/env python3
"""Generates C2 pin-timing tests for the i8080 (spec 4, 6.2): seeded random straight-line programs; the expected
value of every pin in every clock state comes from tests/mach80.py (cycles per instruction, spec 6.2) and the
state/pin table of spec 4, written from the spec only. Output: <outdir>/pins_s<seed>.asm and .pins, one line per
clock state from the first T1 after reset: `FF MM AAAA DD R H`: FF = {sync, a_oe, d_oe, dbin, wr_n, wait_o, hlda, inte},
MM = which FF bits are compared, AAAA = a (x = not compared), DD = d_out (x = not compared), R = the READY value driven during that state
(seed 3 inserts 1-2 wait states in a quarter of the cycles), H = the HOLD value driven during that state (seed 4: HOLD in a fifth of the bus cycles, held 1-6 hold states).
Instruction mix: data transfer, pairs, stack, ALU, INR/DCR, rotates, DAA, I/O, plus control flow whose target is the
next instruction (JMP, Jcc, CALL, Ccc, Rcc after pushing the return address, PCHL), so the program stays straight-line.
Seeds 1-2: no wait states; seed 3 has wait states. No holds or interrupts here (C3 HOLD, C4); INTE stays 0 (no EI)."""
import os, random, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here + '/..')
import mach80, asm80
from mach80 import Mach, STATUS
d = sys.argv[1] if len(sys.argv) > 1 else "build/gen/c2"; os.makedirs(d, exist_ok=True)
SYNC, AOE, DOE, DBIN, WRN, WAIT, HLDA, INTE = (1 << i for i in range(7, -1, -1))
def states(cyc, w=0):
    """Pins of each state of one machine cycle with w wait states after T2 (READY low in T1/T2 and in TW1..TW(w-1)).
    Returns (flags, mask, a, d, ready, hold) per state (hold = 0 here); `ready` is the value the testbench drives during that state."""
    kind, addr, data, n = cyc; out = []
    wr = kind in ('W', 'SW', 'OUT')
    if kind == 'I3':
        return [(AOE | WRN, 0xFF, None, None, 1, 0)] * 3
    a = addr & 0xFFFF
    r12 = 0 if w else 1                       # READY for T1 and T2: low when a wait follows (same value in T1 and T2: stimulus rule)
    out.append((SYNC | AOE | DOE | WRN, 0xFF, a, STATUS[kind], r12, 0))
    out.append(((AOE | DOE | WRN, 0xFF, a, data, r12, 0) if wr else (AOE | DBIN | WRN, 0xFF, a, None, r12, 0)))
    for k in range(1, w + 1):                 # TW: WAIT = 1; write: WR low and data held, read: DBIN high
        rk = 0 if k < w else 1
        out.append(((AOE | DOE | WAIT, 0xFF, a, data, rk, 0) if wr else (AOE | DBIN | WRN | WAIT, 0xFF, a, None, rk, 0)))
    out.append(((AOE | DOE, 0xFF, a, data, 1, 0) if wr else (AOE | DBIN | WRN, 0xFF, a, None, 1, 0)))     # T3: write: WR low
    for t in range(4, n + 1): out.append((AOE | WRN, 0xFF & ~DOE, a, None, 1, 0))                      # T4/T5: d_oe and d_out not compared
    return out
HOLD_ROW = (WRN | HLDA, 0xFF, None, None, 1)                  # sync 0, a_oe 0, d_oe 0, dbin 0, wr_n 1, wait 0, hlda 1; a, d_out not compared
def hold_states(cyc, extra):
    """One machine cycle with HOLD raised at the start of T1 (so it is seen at the closing edge of T2) and released at the start edge
    of the `extra`-th state after the hlda-entry state (extra >= 1: the stimulus rule lets HOLD change only while hlda = 1, spec 7).
    Spec 4 (Hold, chip-8080#20/#39): hlda rises in T3 of a read/input and in the state after T3 of a write/output; that state shows its
    normal row with hlda = 1 (a 3-state write: the hold-entry row); from the next state on the Hold row applies, even while T4/T5 run
    internally; HOLD is sampled at the closing edge of each hold state and, if low, the next state has hlda = 0 and is T1 of the next cycle,
    or the not yet used rest of T4/T5 with their normal rows (each hold state consumes one internal T state)."""
    kind, addr, data, n = cyc; base = states(cyc); wr = kind in ('W', 'SW', 'OUT'); a = addr & 0xFFFF
    e = 3 if wr else 2                                         # index of the state in which hlda rises
    out = [(f, m, ad, dv, 1, 1) for (f, m, ad, dv, r, h) in base[:min(e, n)]]            # states before it, HOLD high
    if e < n: f, m, ad, dv, r, h = base[e]; out.append((f | HLDA, m, ad, dv, 1, 1)); remaining = n - 1 - e
    else: out.append((AOE | WRN | HLDA, 0xFF, a, None, 1, 1)); remaining = 0              # 3-state write: the hold-entry row
    nxt = e + 1
    for k in range(1, extra + 1):                              # hold states; HOLD is low during the last one
        out.append(HOLD_ROW + (0 if k == extra else 1,))
        if remaining > 0: remaining -= 1; nxt += 1
    while remaining > 0:                                       # the rest of T4/T5, normal rows, hlda = 0
        f, m, ad, dv, r, h = base[nxt]; out.append((f, m, ad, dv, 1, 0)); nxt += 1; remaining -= 1
    return out
def gen(seed, n=1200, wait_mode=False, hold_mode=False):
    rnd = random.Random(seed); m = Mach(0); lines = []; pins = []
    def ex(line):
        lines.append("        " + line)
        for c in m.run(line):
            if hold_mode and c[0] != 'I3' and rnd.random() < 0.2: pins.extend(hold_states(c, rnd.choice([1, 1, 2, 3, 6]))); continue
            for st in states(c, rnd.choice([0, 0, 0, 1, 2]) if wait_mode and c[0] != 'I3' else 0): pins.append(st)
    ex("LXI SP,0x4800")
    for x in 'BCDEHLA': ex(f"MVI {x},{rnd.randrange(256)}")
    ex(f"LXI D,{rnd.randrange(65536) & 0xFFD7 | 2}"); ex("PUSH D"); ex("POP PSW")
    R = 'BCDEHLMA'
    mem_hl = lambda: ex(f"LXI H,{rnd.randrange(0x4000, 0x4100)}")
    i = 0
    while i < n:
        if i % 48 == 0: ex("LXI SP,0x4800")
        k = rnd.randrange(30)
        if k == 0:
            dd, ss = rnd.choice(R), rnd.choice(R)
            if dd == ss == 'M': continue
            if 'M' in (dd, ss): mem_hl()
            ex(f"MOV {dd},{ss}")
        elif k == 1:
            r = rnd.choice(R)
            if r == 'M': mem_hl()
            ex(f"MVI {r},{rnd.randrange(256)}")
        elif k == 2: ex(f"LXI {rnd.choice(['B', 'D', 'H'])},{rnd.randrange(0x4000, 0x4100)}")
        elif k == 3: ex(f"{rnd.choice(['LDA', 'STA'])} {rnd.randrange(0x4000, 0x4100)}")
        elif k == 4: ex(f"{rnd.choice(['LHLD', 'SHLD'])} {rnd.randrange(0x4000, 0x40FF)}")
        elif k == 5:
            p = rnd.choice(['B', 'D']); ex(f"LXI {p},{rnd.randrange(0x4000, 0x4100)}"); ex(f"{rnd.choice(['LDAX', 'STAX'])} {p}")
        elif k == 6: ex(rnd.choice(["XCHG", "CMA", "STC", "CMC", "NOP", "DAA"]))
        elif k == 7: mem_hl(); ex(rnd.choice(["INX H", "DCX H"]))
        elif k == 8: ex(f"{rnd.choice(['PUSH', 'POP'])} {rnd.choice(['B', 'D', 'H', 'PSW'])}")
        elif k == 9: ex("XTHL")
        elif k == 10: ex(f"{rnd.choice(['DAD', 'INX', 'DCX'])} {rnd.choice(['B', 'D', 'H', 'SP'])}")
        elif k in (11, 12, 13):
            op = rnd.choice(['ADD', 'ADC', 'SUB', 'SBB', 'ANA', 'XRA', 'ORA', 'CMP']); r = rnd.choice(R)
            if r == 'M': mem_hl()
            ex(f"{op} {r}")
        elif k == 14: ex(f"{rnd.choice(['ADI', 'ACI', 'SUI', 'SBI', 'ANI', 'XRI', 'ORI', 'CPI'])} {rnd.randrange(256)}")
        elif k in (15, 16):
            r = rnd.choice(R)
            if r == 'M': mem_hl()
            ex(f"{rnd.choice(['INR', 'DCR'])} {r}")
        elif k == 17: ex(rnd.choice(["RLC", "RRC", "RAL", "RAR"]))
        elif k == 18: ex(f"IN {rnd.randrange(256)}")
        elif k == 19: ex(f"OUT {rnd.randrange(256)}")
        elif k == 20: ex(f"JMP {m.pc + 3}")
        elif k == 21: ex(f"J{rnd.choice(mach80.CC)} {m.pc + 3}")
        elif k == 22: ex(f"C{rnd.choice(mach80.CC)} {m.pc + 3}")
        elif k == 23: ex(f"CALL {m.pc + 3}")
        elif k == 24:
            cc = rnd.choice(mach80.CC); ex(f"LXI H,{m.pc + 3 + 1 + 1}"); ex("PUSH H"); ex(f"R{cc}")   # return address = the next instruction
        elif k == 25: ex(f"LXI H,{m.pc + 3 + 1}"); ex("PCHL")          # HL = the next instruction
        elif k == 26: ex(f"LXI H,{rnd.randrange(0x4780, 0x4880)}"); ex("SPHL")
        else: ex(rnd.choice(["INR A", "DCR A", "RLC", "CMA"]))
        i += 1
    return lines, pins
for seed, wm, hm in ((1, False, False), (2, False, False), (3, True, False), (4, False, True)):   # seed 3: wait states (C3 READY); seed 4: HOLD (C3 HOLD/HLDA)
    lines, pins = gen(seed, wait_mode=wm, hold_mode=hm)
    asm = [f"; C2 pin timing, seed {seed}, generated by gen_pins80.py", "        .org 0"] + lines
    top = max(asm80.assemble(asm, True, {}))
    assert top < 0x3F00, top
    open(f"{d}/pins_s{seed}.asm", "w").write("\n".join(asm) + "\n")
    with open(f"{d}/pins_s{seed}.pins", "w") as f:
        for fl, mask, a, dv, rdy, hld in pins:
            f.write("%02X %02X %s %s %d %d\n" % (fl, mask, "xxxx" if a is None else "%04X" % a, "xx" if dv is None else "%02X" % dv, rdy, hld))
print("wrote pins programs")
