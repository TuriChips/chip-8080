#!/usr/bin/env python3
"""Reference model of the Intel 8080, instruction level. Owner: Beru.

Written from docs/spec.md (v0 draft) §3 and §6 only, never from RTL or other emulators.
Pin-level timing (§4) comes later, on top of this; each executed instruction already reports
its machine cycles per §6.2 so the pin model can be built from them.

  cpu = CPU(mem=bytes/bytearray of up to 64 KiB, inp=lambda port: value, out=lambda port, v: None)
  states, cycles = cpu.step()        # one instruction (or one interrupt acknowledge)
  cpu.request_interrupt(n)           # RST n via INTA at the next instruction boundary, if INTE

cycles: list of (kind, address) with kind in F4 F5 R W SR SW IN OUT I3 (§6.2 notation), and
'HLTA' for the halt-acknowledge cycle. IN/OUT addresses are {port, port} (§3).

Usage: ref8080.py selftest
"""
import sys

UNDOCUMENTED = {0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0xCB, 0xD9, 0xDD, 0xED, 0xFD}   # §6, not tested
REG = "BCDEHLMA"                                   # DDD/SSS codes; 6 = M = (HL)


def parity(v):
    return 1 if bin(v & 0xFF).count("1") % 2 == 0 else 0


class Undocumented(Exception):
    pass


class CPU:
    def __init__(self, mem=b"", inp=None, out=None, read=None, write=None):
        """read(addr) -> byte and write(addr, v) model a system's memory map (default: 64 KiB RAM in
        self.mem). inp(port) / out(port, v) are the I/O ports."""
        self.mem = bytearray(65536)
        self.mem[:len(mem)] = mem
        self.read = read or (lambda addr: self.mem[addr])
        self.write = write or self.mem.__setitem__
        self.inp = inp or (lambda port: 0)
        self.out = out or (lambda port, v: None)
        self.r = [0] * 8                           # B C D E H L (unused) A ; index 6 unused
        self.sp = 0
        self.pc = 0
        self.cy = self.p = self.ac = self.z = self.s = 0
        self.inte = 0
        self.int_inhibit = 0                       # EI: no interrupt accepted until the next instruction ends
        self.halted = False
        self.int_req = None                        # RST number requested
        self.cycles = []

    # ------------------------------------------------------------ state helpers
    @property
    def a(self):
        return self.r[7]

    @a.setter
    def a(self, v):
        self.r[7] = v & 0xFF

    def hl(self):
        return (self.r[4] << 8) | self.r[5]

    def rp(self, code):                            # 0 BC, 1 DE, 2 HL, 3 SP
        if code == 3:
            return self.sp
        return (self.r[2 * code] << 8) | self.r[2 * code + 1]

    def set_rp(self, code, v):
        v &= 0xFFFF
        if code == 3:
            self.sp = v
        else:
            self.r[2 * code], self.r[2 * code + 1] = v >> 8, v & 0xFF

    def flags(self):                               # §3: S Z 0 AC 0 P 1 CY
        return (self.s << 7) | (self.z << 6) | (self.ac << 4) | (self.p << 2) | 0x02 | self.cy

    def set_flags(self, f):                        # POP PSW loads only CY, P, AC, Z, S
        self.s, self.z, self.ac, self.p, self.cy = (f >> 7) & 1, (f >> 6) & 1, (f >> 4) & 1, (f >> 2) & 1, f & 1

    def szp(self, v):
        v &= 0xFF
        self.s, self.z, self.p = v >> 7, int(v == 0), parity(v)

    # ------------------------------------------------------------ bus helpers (record §6.2 cycles)
    def rd(self, addr, kind="R"):
        addr &= 0xFFFF
        self.cycles.append((kind, addr))
        return self.read(addr)

    def wr(self, addr, v, kind="W"):
        addr &= 0xFFFF
        self.cycles.append((kind, addr))
        self.write(addr, v & 0xFF)

    def imm8(self):
        v = self.rd(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def imm16(self):
        lo = self.imm8()
        return lo | (self.imm8() << 8)

    def push16(self, v):
        self.sp = (self.sp - 1) & 0xFFFF
        self.wr(self.sp, v >> 8, "SW")
        self.sp = (self.sp - 1) & 0xFFFF
        self.wr(self.sp, v & 0xFF, "SW")

    def pop16(self):
        lo = self.rd(self.sp, "SR")
        self.sp = (self.sp + 1) & 0xFFFF
        hi = self.rd(self.sp, "SR")
        self.sp = (self.sp + 1) & 0xFFFF
        return lo | (hi << 8)

    def get(self, code):                           # register or M
        return self.rd(self.hl()) if code == 6 else self.r[code]

    def put(self, code, v):
        if code == 6:
            self.wr(self.hl(), v)
        else:
            self.r[code] = v & 0xFF

    def cond(self, ccc):                           # NZ Z NC C PO PE P M
        f = [self.z, self.z, self.cy, self.cy, self.p, self.p, self.s, self.s][ccc]
        return f == (ccc & 1)

    # ------------------------------------------------------------ ALU (§6 flag rules)
    def add(self, op, c=0):
        t = self.a + op + c
        self.ac = int((self.a & 0xF) + (op & 0xF) + c > 0xF)
        self.cy = t >> 8
        self.a = t
        self.szp(self.a)

    def sub(self, op, borrow=0, store=True):
        # §6: t = A + ~op + (NOT borrow), 9 bits; CY = NOT t[8]; AC = carry out of bit 3, not complemented
        nop = ~op & 0xFF
        cin = 1 - borrow
        t = self.a + nop + cin
        self.ac = int((self.a & 0xF) + (nop & 0xF) + cin > 0xF)
        self.cy = 1 - (t >> 8)
        self.szp(t)
        if store:
            self.a = t

    def logic(self, kind, op):
        if kind == "and":
            self.ac = ((self.a | op) >> 3) & 1         # §6 quirk: OR of bit 3 of both operands
            self.a = self.a & op
        else:
            self.ac = 0
            self.a = (self.a ^ op) if kind == "xor" else (self.a | op)
        self.cy = 0
        self.szp(self.a)

    def alu(self, k, op):                          # k = bits 5:3 of an ALU opcode
        if k == 0: self.add(op)
        elif k == 1: self.add(op, self.cy)
        elif k == 2: self.sub(op)
        elif k == 3: self.sub(op, self.cy)
        elif k == 4: self.logic("and", op)
        elif k == 5: self.logic("xor", op)
        elif k == 6: self.logic("or", op)
        else: self.sub(op, store=False)            # CMP

    def daa(self):
        a, cy = self.a, self.cy
        if (a & 0xF) > 9 or self.ac:
            self.ac = int((a & 0xF) + 6 > 0xF)
            a += 6
        else:
            self.ac = 0                            # spec: "else AC = 0" [check in spec]
        if ((a >> 4) & 0x1F) > 9 or cy:
            a += 0x60
        self.cy = cy | int(a > 0xFF)               # spec Decision: CY = CY_in OR carry-out
        self.a = a
        self.szp(self.a)

    # ------------------------------------------------------------ execution
    def request_interrupt(self, n):
        self.int_req = n & 7

    def step(self):
        """Execute one instruction (or an interrupt acknowledge). Returns (states, cycles)."""
        self.cycles = []
        if self.int_req is not None and self.inte and not self.int_inhibit:
            n, self.int_req = self.int_req, None
            self.inte = 0                          # INTE reset at T1 of the INTA cycle
            self.halted = False
            self.cycles.append(("INTA", self.pc))   # PC not incremented; RST n supplied by the system
            self.push16(self.pc)
            self.pc = 8 * n
            return 11, self.cycles
        if self.halted:
            return 0, self.cycles
        inhibited = self.int_inhibit               # set by an EI before this instruction
        op = self.read(self.pc)
        if op in UNDOCUMENTED:
            raise Undocumented(f"undocumented opcode {op:02X} at {self.pc:04X} (spec §6: not tested)")
        states = self._exec(op)
        if inhibited:
            self.int_inhibit = 0                   # the instruction after EI has completed (ALP p.3-24)
        return states, self.cycles

    def _fetch(self, five=False):
        self.cycles.append(("F5" if five else "F4", self.pc))
        op = self.read(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return op

    def _exec(self, op):
        hi, d, s = op >> 6, (op >> 3) & 7, op & 7
        if hi == 1:                                # MOV / HLT
            if op == 0x76:
                self._fetch()
                self.cycles.append(("HLTA", self.pc))
                self.halted = True
                return 7
            if d != 6 and s != 6:
                self._fetch(five=True); self.r[d] = self.r[s]; return 5
            self._fetch(); self.put(d, self.get(s)); return 7
        if hi == 2:                                # ALU r/M
            self._fetch(); self.alu(d, self.get(s)); return 7 if s == 6 else 4
        if hi == 0:
            if s == 6:                             # MVI
                self._fetch(); v = self.imm8(); self.put(d, v); return 10 if d == 6 else 7
            if s == 4 or s == 5:                   # INR / DCR
                if d == 6:
                    self._fetch(); v = self.rd(self.hl())
                else:
                    self._fetch(five=True); v = self.r[d]
                if s == 4:
                    res = (v + 1) & 0xFF; self.ac = int((v & 0xF) == 0xF)
                else:
                    res = (v - 1) & 0xFF; self.ac = int((v & 0xF) != 0)   # v + 0xFF: carry out of bit 3
                self.szp(res)
                if d == 6:
                    self.wr(self.hl(), res); return 10
                self.r[d] = res; return 5
            if s == 1:
                if d & 1 == 0:                     # LXI
                    self._fetch(); self.set_rp(d >> 1, self.imm16()); return 10
                self._fetch()                      # DAD
                self.cycles += [("I3", None), ("I3", None)]
                t = self.hl() + self.rp(d >> 1)
                self.cy = t >> 16; self.set_rp(2, t); return 10
            if s == 3:                             # INX / DCX
                self._fetch(five=True)
                self.set_rp(d >> 1, self.rp(d >> 1) + (1 if d & 1 == 0 else -1)); return 5
            if s == 2:
                if d in (0, 2):                    # STAX B / D
                    self._fetch(); self.wr(self.rp(d >> 1), self.a); return 7
                if d in (1, 3):                    # LDAX B / D
                    self._fetch(); self.a = self.rd(self.rp(d >> 1)); return 7
                self._fetch(); addr = self.imm16()
                if d == 4:                         # SHLD
                    self.wr(addr, self.r[5]); self.wr(addr + 1, self.r[4]); return 16
                if d == 5:                         # LHLD
                    self.r[5] = self.rd(addr); self.r[4] = self.rd(addr + 1); return 16
                if d == 6:                         # STA
                    self.wr(addr, self.a); return 13
                self.a = self.rd(addr); return 13  # LDA
            if s == 7:                             # rotates, DAA, CMA, STC, CMC
                self._fetch(); a = self.a
                if d == 0: self.cy = a >> 7; self.a = (a << 1) | (a >> 7)
                elif d == 1: self.cy = a & 1; self.a = (a >> 1) | ((a & 1) << 7)
                elif d == 2: c = self.cy; self.cy = a >> 7; self.a = (a << 1) | c
                elif d == 3: c = self.cy; self.cy = a & 1; self.a = (a >> 1) | (c << 7)
                elif d == 4: self.daa()
                elif d == 5: self.a = ~a
                elif d == 6: self.cy = 1
                else: self.cy ^= 1
                return 4
            self._fetch(); return 4                # NOP (s == 0, d == 0)
        # hi == 3
        if s == 0:                                 # Rcc
            self._fetch(five=True)
            if self.cond(d):
                self.pc = self.pop16(); return 11
            return 5
        if s == 1:
            if d & 1 == 0:                         # POP
                self._fetch(); v = self.pop16()
                if d >> 1 == 3:
                    self.set_flags(v & 0xFF); self.a = v >> 8
                else:
                    self.set_rp(d >> 1, v)
                return 10
            if d == 1: self._fetch(); self.pc = self.pop16(); return 10       # RET
            if d == 5: self._fetch(five=True); self.pc = self.hl(); return 5  # PCHL
            if d == 7: self._fetch(five=True); self.sp = self.hl(); return 5  # SPHL
        if s == 2:                                 # Jcc
            self._fetch(); addr = self.imm16()
            if self.cond(d):
                self.pc = addr
            return 10
        if s == 3:
            if d == 0: self._fetch(); self.pc = self.imm16(); return 10       # JMP
            if d == 2:                                                        # OUT
                self._fetch(); port = self.imm8()
                self.cycles.append(("OUT", (port << 8) | port)); self.out(port, self.a); return 10
            if d == 3:                                                        # IN
                self._fetch(); port = self.imm8()
                self.cycles.append(("IN", (port << 8) | port)); self.a = self.inp(port) & 0xFF; return 10
            if d == 4:                                                        # XTHL
                self._fetch()
                lo = self.rd(self.sp, "SR"); hi_ = self.rd(self.sp + 1, "SR")
                self.wr(self.sp + 1, self.r[4], "SW"); self.wr(self.sp, self.r[5], "SW")
                self.r[4], self.r[5] = hi_, lo
                return 18
            if d == 5:                                                        # XCHG
                self._fetch(); de, hl = self.rp(1), self.rp(2); self.set_rp(1, hl); self.set_rp(2, de); return 4
            # EI/DI: the INTE flip-flop (and pin) change at T4 of their own M1 (p.2-18); after EI,
            # acceptance waits for the end of the next instruction (ALP p.3-24); DI is immediate
            if d == 6: self._fetch(); self.inte = 0; self.int_inhibit = 0; return 4   # DI
            if d == 7: self._fetch(); self.inte = 1; self.int_inhibit = 1; return 4   # EI
        if s == 4:                                 # Ccc
            self._fetch(five=True); addr = self.imm16()
            if self.cond(d):
                self.push16(self.pc); self.pc = addr; return 17
            return 11
        if s == 5:
            if d & 1 == 0:                         # PUSH
                self._fetch(five=True)
                v = ((self.a << 8) | self.flags()) if d >> 1 == 3 else self.rp(d >> 1)
                self.push16(v); return 11
            self._fetch(five=True); addr = self.imm16(); self.push16(self.pc); self.pc = addr; return 17  # CALL
        if s == 6:                                 # ALU immediate
            self._fetch(); self.alu(d, self.imm8()); return 7
        # s == 7: RST
        self._fetch(five=True); self.push16(self.pc); self.pc = 8 * d; return 11


# ==================================================================== selftest (spec examples)
def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: got {got!r}, want {want!r}")

    def run(prog, n, setup=None, **kw):
        c = CPU(bytes(prog), **kw)
        if setup:
            setup(c)
        st = [c.step()[0] for _ in range(n)]
        return c, st

    # 244 documented opcodes, 12 undocumented rejected (§6)
    ok = 0
    for op in range(256):
        c = CPU(bytes([op, 0, 0]))
        c.sp = 0x8000
        try:
            c.step(); ok += 1
        except Undocumented:
            check(f"undocumented {op:02X} expected", op in UNDOCUMENTED, True)
            continue
        check(f"documented {op:02X} expected", op in UNDOCUMENTED, False)
    check("documented opcode count", ok, 244)

    # §6.1 state counts (spot checks incl. conditional false/true)
    tbl = [([0x41], 5), ([0x46], 7), ([0x70], 7), ([0x3E, 0], 7), ([0x36, 0], 10), ([0x04], 5),
           ([0x34], 10), ([0x80], 4), ([0x86], 7), ([0xC6, 0], 7), ([0x07], 4), ([0xC3, 0, 0], 10),
           ([0xCD, 0, 0], 17), ([0xC9], 10), ([0xC7], 11), ([0xE9], 5), ([0xDB, 0], 10), ([0xD3, 0], 10),
           ([0x01, 0, 0], 10), ([0xC5], 11), ([0xC1], 10), ([0x32, 0, 0], 13), ([0x3A, 0, 0], 13),
           ([0xEB], 4), ([0xE3], 18), ([0xF9], 5), ([0x09], 10), ([0x02], 7), ([0x0A], 7), ([0x03], 5),
           ([0x0B], 5), ([0x2F], 4), ([0x37], 4), ([0x3F], 4), ([0x27], 4), ([0x22, 0, 0], 16),
           ([0x2A, 0, 0], 16), ([0xFB], 4), ([0xF3], 4), ([0x00], 4), ([0x76], 7)]
    for prog, want in tbl:
        c = CPU(bytes(prog)); c.sp = 0x8000
        check(f"states {prog[0]:02X}", c.step()[0], want)
    # conditional: JZ/CZ/RZ with Z = 0 (false) and Z = 1 (true)
    for z, wc, wr in [(0, 11, 5), (1, 17, 11)]:
        c = CPU(bytes([0xCC, 0x10, 0])); c.sp = 0x8000; c.z = z
        check(f"CZ z={z}", c.step()[0], wc)
        c = CPU(bytes([0xC8])); c.sp = 0x8000; c.z = z
        check(f"RZ z={z}", c.step()[0], wr)

    # All 244 documented opcodes: state counts from the p.4-15 table (spec §6.1), written as
    # encoding patterns independent of the decoder above; conditionals checked false and true.
    def p415(op, taken):
        hi, d, s_ = op >> 6, (op >> 3) & 7, op & 7
        if op == 0x76: return 7
        if hi == 1: return 7 if 6 in (d, s_) else 5
        if hi == 2: return 7 if s_ == 6 else 4
        if hi == 0:
            return {6: 10 if d == 6 else 7, 4: 10 if d == 6 else 5, 5: 10 if d == 6 else 5,
                    1: 10, 3: 5, 7: 4, 0: 4,
                    2: {0: 7, 1: 7, 2: 7, 3: 7, 4: 16, 5: 16, 6: 13, 7: 13}[d]}[s_]
        if s_ == 0: return 11 if taken else 5                      # Rcc
        if s_ == 1: return {1: 10, 5: 5, 7: 5}.get(d, 10)           # RET PCHL SPHL / POP
        if s_ == 2: return 10                                      # Jcc
        if s_ == 3: return {0: 10, 2: 10, 3: 10, 4: 18}.get(d, 4)  # JMP OUT IN XTHL / XCHG DI EI
        if s_ == 4: return 17 if taken else 11                     # Ccc
        if s_ == 5: return 17 if d == 1 else 11                    # CALL / PUSH
        if s_ == 6: return 7                                       # ALU immediate
        return 11                                                  # RST
    for op in range(256):
        if op in UNDOCUMENTED:
            continue
        for taken in (False, True):
            c = CPU(bytes([op, 0, 0])); c.sp = 0x8000
            ccc = (op >> 3) & 7
            want_flag = (ccc & 1) if taken else 1 - (ccc & 1)       # make the condition true/false
            c.z = c.cy = c.p = c.s = want_flag
            check(f"p.4-15 states {op:02X} taken={taken}", c.step()[0], p415(op, taken))

    # SUB A with A = 3E: CY 0, S 0, Z 1, P 1, AC 1 (ALP p.3-64, quoted in §6)
    c, _ = run([0x97], 1, lambda c: setattr(c, "a", 0x3E))
    check("SUB A (3E)", (c.a, c.cy, c.s, c.z, c.p, c.ac), (0, 0, 0, 1, 1, 1))
    # SBB: A = 4, B = 2, CY = 1 -> A = 1, CY 0, S 0, Z 0, P 0, AC 1 (ALP p.3-57)
    def sbb_setup(c): c.a = 4; c.r[0] = 2; c.cy = 1
    c, _ = run([0x98], 1, sbb_setup)
    check("SBB B", (c.a, c.cy, c.s, c.z, c.p, c.ac), (1, 0, 0, 0, 0, 1))
    # SBB with op = FF, CY = 1 (spec Decision: true A - op - CY mod 256, CY = borrow)
    def sbb_ff(c): c.a = 0x10; c.r[0] = 0xFF; c.cy = 1
    c, _ = run([0x98], 1, sbb_ff)
    check("SBB FF with CY", (c.a, c.cy), ((0x10 - 0xFF - 1) & 0xFF, 1))
    # DAA: 93 + 08 -> 9B -> A1 -> 01, CY = AC = 1 (ALP example in §6)
    c, _ = run([0x3E, 0x93, 0xC6, 0x08, 0x27], 3)
    check("ADI then DAA", (c.a, c.cy, c.ac), (0x01, 1, 1))
    # DAA: step 1's carry out of bit 7 sets CY (spec #27 Decision): 60 + 99 + 1 (ADC) -> FA -> 60, CY 1
    c, _ = run([0x3E, 0x60, 0x37, 0xCE, 0x99, 0x27], 4)
    check("DAA after 60+99+1", (c.a, c.cy), (0x60, 1))
    # DAA keeps an incoming CY (spec Decision)
    def daa_cy(c): c.a = 0x12; c.cy = 1
    c, _ = run([0x27], 1, daa_cy)
    check("DAA with CY in", (c.a, c.cy), (0x72, 1))
    # ANA AC = OR of bit 3 of both operands; CY = 0
    def ana(c): c.a = 0x08; c.r[0] = 0x00; c.cy = 1
    c, _ = run([0xA0], 1, ana)
    check("ANA AC", (c.a, c.ac, c.cy), (0, 1, 0))
    # ORA/XRA clear CY and AC
    def ora(c): c.a = 0x0F; c.r[0] = 0x01; c.cy = 1; c.ac = 1
    c, _ = run([0xB0], 1, ora)
    check("ORA", (c.a, c.cy, c.ac), (0x0F, 0, 0))
    # CMP: flags like SUB, A unchanged; CY = borrow
    def cmp_(c): c.a = 0x05; c.r[0] = 0x07
    c, _ = run([0xB8], 1, cmp_)
    check("CMP", (c.a, c.cy, c.z), (0x05, 1, 0))
    # INR/DCR leave CY; AC rules; DCR 00 -> FF
    def inr(c): c.r[0] = 0x0F; c.cy = 1
    c, _ = run([0x04], 1, inr)
    check("INR 0F", (c.r[0], c.ac, c.cy), (0x10, 1, 1))
    def dcr(c): c.r[0] = 0x00; c.cy = 0
    c, _ = run([0x05], 1, dcr)
    check("DCR 00", (c.r[0], c.ac, c.cy, c.s, c.p), (0xFF, 0, 0, 1, 1))
    # DAD: only CY
    def dad(c): c.set_rp(2, 0xFFFF); c.set_rp(0, 1); c.z = 1
    c, _ = run([0x09], 1, dad)
    check("DAD", (c.hl(), c.cy, c.z), (0, 1, 1))
    # PUSH PSW format: bit 1 = 1, bits 3, 5 = 0; POP PSW loads only CY P AC Z S
    def psw(c): c.sp = 0x100; c.a = 0xAA; c.cy = 1; c.z = 1
    c, _ = run([0xF5], 1, psw)
    check("PUSH PSW", (c.mem[0xFF], c.mem[0xFE]), (0xAA, 0x43))
    c = CPU(bytes([0xF1])); c.sp = 0x100; c.mem[0x100] = 0xFF; c.mem[0x101] = 0x12; c.step()
    check("POP PSW", (c.a, c.flags()), (0x12, 0xD7))
    # CALL / RET / RST push order and return
    c = CPU(bytes([0xCD, 0x10, 0x00] + [0] * 13 + [0xC9])); c.sp = 0x100
    c.step(); check("CALL", (c.pc, c.sp, c.mem[0xFF], c.mem[0xFE]), (0x10, 0xFE, 0x00, 0x03))
    c.step(); check("RET", (c.pc, c.sp), (0x03, 0x100))
    c = CPU(bytes([0xFF])); c.sp = 0x100; c.step()
    check("RST 7", (c.pc, c.mem[0xFE]), (0x38, 0x01))
    # XTHL
    def xthl(c): c.sp = 0x100; c.mem[0x100] = 0x34; c.mem[0x101] = 0x12; c.set_rp(2, 0xABCD)
    c, _ = run([0xE3], 1, xthl)
    check("XTHL", (c.hl(), c.mem[0x100], c.mem[0x101]), (0x1234, 0xCD, 0xAB))
    # IN/OUT: port on both halves of the address (§3)
    outs = []
    c = CPU(bytes([0xDB, 0x05, 0xD3, 0x07]), inp=lambda p: 0x5A, out=lambda p, v: outs.append((p, v)))
    st, cyc = c.step(); check("IN cycles", cyc[-1], ("IN", 0x0505)); check("IN value", c.a, 0x5A)
    st, cyc = c.step(); check("OUT cycles", cyc[-1], ("OUT", 0x0707)); check("OUT", outs, [(7, 0x5A)])
    # EI takes effect after the next instruction (ALP p.3-24); INTA pushes PC, jumps to 8n, clears INTE
    c = CPU(bytes([0xFB, 0x00, 0x00])); c.sp = 0x100; c.request_interrupt(2)
    c.step(); check("EI sets INTE at once", (c.pc, c.inte), (1, 1))          # p.2-18: SET INTE F/F in T4 of EI
    st, cyc = c.step(); check("no INTA right after EI", (c.pc, cyc[0][0]), (2, "F4"))   # the next instruction runs first
    st, cyc = c.step(); check("INTA", (c.pc, c.inte, c.mem[0xFE], st), (0x10, 0, 0x02, 11))
    # DI is immediate: EI; DI with an INT pending is never accepted
    c = CPU(bytes([0xFB, 0xF3, 0x00, 0x00])); c.sp = 0x100; c.request_interrupt(3)
    for _ in range(4): c.step()
    check("DI immediate", (c.pc, c.inte), (4, 0))
    # HLT, then leave by interrupt
    c = CPU(bytes([0xFB, 0x76])); c.sp = 0x100
    c.step(); c.step(); check("halted", c.halted, True)
    c.request_interrupt(1); c.step(); check("INT leaves halt", (c.pc, c.halted, c.mem[0xFE]), (0x08, False, 0x02))
    # memory-map callbacks: ROM 0000-1FFF read-only, RAM F000-F3FF, unmapped reads FF
    rom = bytes([0x31, 0x00, 0xF4, 0x3E, 0x5A, 0x32, 0x00, 0xF0, 0x32, 0x00, 0x10, 0x3A, 0x00, 0x10,
                 0x47, 0x3A, 0x00, 0xF0, 0xF5])
    ram = bytearray(0x400)
    def rd_map(a): return rom[a] if a < len(rom) else (0 if a < 0x2000 else (ram[a - 0xF000] if 0xF000 <= a < 0xF400 else 0xFF))
    def wr_map(a, v):
        if 0xF000 <= a < 0xF400: ram[a - 0xF000] = v
    c = CPU(read=rd_map, write=wr_map)
    for _ in range(8): c.step()
    check("map: ROM write ignored, ROM read back", c.r[0], rom[0x1000] if 0x1000 < len(rom) else 0)
    check("map: RAM write and read", (c.a, ram[0]), (0x5A, 0x5A))
    check("map: PUSH PSW into RAM", (c.sp, ram[0x3FF], ram[0x3FE]), (0xF3FE, 0x5A, c.flags()))

    # §6.2 cycle lists, spot checks
    c = CPU(bytes([0xCD, 0x10, 0x00])); c.sp = 0x100
    check("CALL cycles", [k for k, _ in c.step()[1]], ["F5", "R", "R", "SW", "SW"])
    c = CPU(bytes([0x09]))
    check("DAD cycles", [k for k, _ in c.step()[1]], ["F4", "I3", "I3"])
    c = CPU(bytes([0xE3])); c.sp = 0x100
    check("XTHL cycles", [k for k, _ in c.step()[1]], ["F4", "SR", "SR", "SW", "SW"])

    if fails:
        for f in fails:
            print("FAIL", f)
        print(f"FAIL ref8080 selftest: {len(fails)} failed")
        return 1
    print("PASS ref8080 selftest")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    print(__doc__)
    sys.exit(2)
