#!/usr/bin/env python3
"""Generates the C4 pin-level interrupt tests (spec 4: interrupt-acknowledge cycle, halt, INTE) into build/gen/c4pins:
the programs of gen_int.py (inr: EI then an INR/NOP loop; halt: EI then HLT) run with INT raised at the start of state K, with the
expected value of every pin in every state: the instruction in progress completes; then the INTA cycle (5 states, status 23, or 2B when
halted, a = PC not incremented, DBIN in T2/T3), two stack writes of the return address, the handler at 0008 (MOV A,B; OUT 1; POP H; PUSH H;
MOV A,L; OUT 2; EI; RET) and the rest of the program through OUT 3. INTE (pin) follows spec 6.1: set from T4 of EI, cleared at DI's T4
(not used here), cleared at T1 of the INTA cycle. Halt: T1 (status 8A), T2, then TWH states (a_oe 0, d_oe 0, WAIT 1) until INT is raised.
Output: int_inr_k<K>.asm/.pins, int_halt_k<K>.asm/.pins and ks.txt (`name K`). .pins format as in gen_pins80.py: `FF MM AAAA DD R`."""
import os, sys
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here + '/..')
import mach80
from mach80 import Mach
d = sys.argv[1] if len(sys.argv) > 1 else "build/gen/c4pins"; os.makedirs(d, exist_ok=True)
SYNC, AOE, DOE, DBIN, WRN, WAIT, HLDA, INTE = (1 << i for i in range(7, -1, -1))
ST = dict(mach80.STATUS, INTA=0x23, INTA_H=0x2B, HLTA=0x8A)
HANDLER = ["JMP 256"]; HANDLER_BODY = ["MOV A,B", "OUT 1", "POP H", "PUSH H", "MOV A,L", "OUT 2", "EI", "RET"]
def cyc_states(cyc, inte_at):
    """cyc = (kind, addr, data, n); inte_at(i) = INTE pin value in state i of this cycle (i from 0). -> list of pin tuples."""
    kind, addr, data, n = cyc; a = None if addr is None else addr & 0xFFFF; out = []
    if kind == 'I3': return [(AOE | WRN | (INTE if inte_at(i) else 0), 0xFF, None, None, 1) for i in range(3)]
    rd = kind in ('F', 'R', 'SR', 'IN', 'INTA', 'INTA_H')
    ie = lambda i: INTE if inte_at(i) else 0
    if kind == 'HLTA':        # T1, T2, first TWH (HLT's 7th state)
        return [(SYNC | AOE | DOE | WRN | ie(0), 0xFF, a, ST['HLTA'], 1), (AOE | WRN | ie(1), 0xFF, a, None, 1), (WAIT | WRN | ie(2), 0xFF, None, None, 1)]
    out.append((SYNC | AOE | DOE | WRN | ie(0), 0xFF, a, ST[kind], 1))
    out.append(((AOE | DBIN | WRN) if rd else (AOE | DOE | WRN), 0xFF, a, None if rd else data, 1) if False else
               ((AOE | DBIN | WRN | ie(1), 0xFF, a, None, 1) if rd else (AOE | DOE | WRN | ie(1), 0xFF, a, data, 1)))
    out.append((AOE | DBIN | WRN | ie(2), 0xFF, a, None, 1) if rd else (AOE | DOE | ie(2), 0xFF, a, data, 1))
    for t in range(3, n): out.append((AOE | WRN | ie(t), 0xFF & ~DOE, a, None, 1))
    return out
TWH = lambda inte: (WAIT | WRN | (INTE if inte else 0), 0xFF, None, None, 1)
def build(prog):
    body = ["LXI SP,0x4800", "MVI B,0" if prog != 'halt' else "MVI B,7", "EI"]
    body += ["HLT"] if prog == 'halt' else ["INR B", "NOP"] * 60
    return body
def run_flow(prog, K):
    """Walk the program with an INT raised at the start of state K; returns the pin tuples."""
    m = Mach(0); pins = []; inte = 0; pend = False; main = ["JMP 256"] + build(prog) + (["MOV A,B"] if prog != 'halt' else []) + ["OUT 3"]
    idx = 0; hq = []; in_handler = False
    def emit(cycles, inte_fn_list):
        for c, f in zip(cycles, inte_fn_list): pins.extend(cyc_states(c, f))
    while True:
        if in_handler and not hq: in_handler = False
        line = hq.pop(0) if in_handler else (main[idx] if idx < len(main) else None)
        if line is None: break
        op = line.split()[0]; start = len(pins)
        was_inte = inte; cycles = m.run(line)
        # INTE pin per state of the first cycle (M1): EI sets it from T4 (state 3), DI clears it from T4
        new_inte = 1 if op == 'EI' else 0 if op == 'DI' else inte
        fns = [(lambda i, f=was_inte, t=new_inte: t if i >= 3 else f) if j == 0 else (lambda i, t=new_inte: t) for j in range(len(cycles))]
        for c, f in zip(cycles, fns): pins.extend(cyc_states(c, f))
        inte = new_inte
        if not in_handler: idx += 1
        if line == "OUT 3": break
        if op == 'HLT':                                   # halted: TWH states until INT (raised at start of state K, K >= here)
            while len(pins) <= K: pins.append(TWH(inte))  # state index len(pins) is the next state; INT starts at K, so states up to K are TWH
            pend = True
        elif K >= 0 and not pend and len(pins) > K: pend = True      # INT was raised during or before this instruction
        # accept at the end of this instruction: INTE set, and the instruction is not EI
        if pend and inte and op != 'EI':
            halted = op == 'HLT'
            sp = m.sp; pc = m.pc
            m.wr(sp - 1, pc >> 8); m.wr(sp - 2, pc & 255)
            pins.extend(cyc_states(('INTA_H' if halted else 'INTA', pc, None, 5), lambda i: 0))
            pins.extend(cyc_states(('SW', sp - 1, pc >> 8, 3), lambda i: 0)); pins.extend(cyc_states(('SW', sp - 2, pc & 255, 3), lambda i: 0))
            m.sp = (sp - 2) & 0xFFFF; m.pc = 8; inte = 0; pend = False; K = -1
            in_handler = True; hq = list(HANDLER_BODY)
            if halted: main_halt_done = True
    return pins
def asm_text(prog):
    HAND = ["        .org 0", "        JMP 256", "        .org 8"] + ["        " + x for x in HANDLER_BODY] + ["        .org 256"]
    return "\n".join([f"; C4 pins {prog}, generated by gen_int_pins.py"] + HAND + ["        " + t for t in build(prog)] + (["        MOV A,B"] if prog != 'halt' else []) + ["        OUT 3", "end:    JMP end"]) + "\n"
ks = []
def emit_case(prog, K):
    pins = run_flow(prog, K); name = f"int_{prog}_k{K}"
    open(f"{d}/{name}.asm", "w").write(asm_text(prog))
    with open(f"{d}/{name}.pins", "w") as f:
        for fl, mask, a, dv, rdy in pins: f.write("%02X %02X %s %s %d\n" % (fl, mask, "xxxx" if a is None else "%04X" % a, "xx" if dv is None else "%02X" % dv, rdy))
    ks.append((name, K))
for K in (1, 2, 5, 13, 14, 20, 21, 25, 100, 301, 333): emit_case('inr', K)
for K in (7 + 4 + 3 + 10 + 7 + 4 + 7 + 3, ): pass
# halt: HLT's 7 states end at index L (see gen_int.py); INT while halted at several K after that
m = Mach(0); n = 0
for t in ["JMP 256"] + build('halt'):
    c = m.run(t); n += sum(x[3] for x in c)
L = n - 1
for K in (L + 1, L + 2, L + 7, L + 30): emit_case('halt', K)
with open(f"{d}/ks.txt", "w") as f:
    for name, K in ks: f.write(f"{name} {K}\n")
print("wrote", len(ks), "interrupt pin programs")
