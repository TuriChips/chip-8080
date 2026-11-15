#!/usr/bin/env python3
"""Pin-level reference model of the 8080 (spec §4, §5), built on ref8080.CPU. Owner: Beru.

One model clock = one T state. PinModel.states() yields, for every state, a Pins tuple with the
value of every pin §4 compares, or None where §4 says "–" (not compared):
  Pins(state, sync, a_oe, a, d_oe, d_out, dbin, wr_n, wait_o, hlda, inte)
Cycle shapes come from the instruction model's §6.2 cycle list:
  F4/F5   instruction fetch, T1-T4(/T5), status A2      R   memory read  T1-T3, status 82
  W       memory write T1-T3, status 00                 SR  stack read   T1-T3, status 86
  SW      stack write  T1-T3, status 04 (SW5: XTHL's last one, with T4, T5)   IN  input  T1-T3, status 42
  OUT     output       T1-T3, status 10                 I3  DAD bus-idle, 3 states (§6.2 Decision)
  INTA    interrupt acknowledge (RST n), T1-T5, status 23 (2B while halted)
  HLTA    halt acknowledge T1, T2, then TWH until left, status 8A
First version: READY = 1 and HOLD = 0 always (no TW, no hold states). Interrupts are honoured at
instruction boundaries and from the halt state.

Usage: pins8080.py selftest
"""
import sys
from collections import namedtuple
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref8080 as R  # noqa: E402

Pins = namedtuple("Pins", "state sync a_oe a d_oe d_out dbin wr_n wait_o hlda inte")
STATUS = {"F4": 0xA2, "F5": 0xA2, "R": 0x82, "W": 0x00, "SR": 0x86, "SW": 0x04, "IN": 0x42,
          "OUT": 0x10, "INTA": 0x23, "INTA_H": 0x2B, "HLTA": 0x8A, "SW5": 0x04}
READS = {"F4", "F5", "R", "SR", "IN", "INTA", "INTA_H"}
WRITES = {"W", "SW", "SW5", "OUT"}
LENGTH = {"F4": 4, "F5": 5, "R": 3, "W": 3, "SR": 3, "SW": 3, "IN": 3, "OUT": 3, "I3": 3,
          "INTA": 5, "INTA_H": 5, "HLTA": 3, "SW5": 5}   # SW5: XTHL's last stack write with T4, T5 (§6.2)   # HLTA: T1, T2 and the first TWH (HLT = 7 states)
RESET_PINS = Pins("RESET", 0, 0, None, 0, None, 0, 1, 0, 0, 0)    # §5, while reset = 1


def cycle_pins(kind, addr, data, inte):
    """Pins for each state of one machine cycle (§4 'Pins per state' table)."""
    out = []
    if kind == "I3":                                  # DAD M2/M3: bus idle, a not compared
        return [Pins(f"T{i + 1}", 0, 1, None, 0, None, 0, 1, 0, 0, inte) for i in range(3)]
    st = STATUS[kind]
    out.append(Pins("T1", 1, 1, addr, 1, st, 0, 1, 0, 0, inte))
    if kind == "HLTA":
        out.append(Pins("T2", 0, 1, addr, 0, None, 0, 1, 0, 0, inte))
        return out                                    # TWH states follow while halted
    if kind in READS:
        out.append(Pins("T2", 0, 1, addr, 0, None, 1, 1, 0, 0, inte))
        out.append(Pins("T3", 0, 1, addr, 0, None, 1, 1, 0, 0, inte))
    else:                                             # write: data from T2, WR low in T3
        out.append(Pins("T2", 0, 1, addr, 1, data, 0, 1, 0, 0, inte))
        out.append(Pins("T3", 0, 1, addr, 1, data, 0, 0, 0, 0, inte))
    for t in range(3, LENGTH[kind]):                  # T4, T5: a held, data bus not compared
        out.append(Pins(f"T{t + 1}", 0, 1, addr, None, None, 0, 1, 0, 0, inte))
    return out


TWH = lambda inte: Pins("TWH", 0, 0, None, 0, None, 0, 1, 1, 0, inte)


class PinModel:
    def __init__(self, cpu):
        self.cpu = cpu

    def instruction_states(self):
        """Run one instruction (or INTA); return its states. EI/DI change INTE at T4 of their M1;
        INTA resets INTE at its T1 (§4, §6.1)."""
        c = self.cpu
        inte_before = c.inte
        was_halted = c.halted
        states_count, cycles = c.step()
        inte_after = c.inte
        out = []
        for i, (kind, addr, data) in enumerate(cycles):
            if kind == "INTA" and was_halted:
                kind = "INTA_H"
            if kind in ("INTA", "INTA_H"):
                pins = cycle_pins(kind, addr, data, 0)    # INTE reset at T1 of the INTA cycle
            elif i == 0:
                pins = cycle_pins(kind, addr, data, inte_before)
                # the M1 of EI/DI: the flip-flop changes at T4
                pins = [p._replace(inte=inte_after) if k >= 3 else p for k, p in enumerate(pins)]
            else:
                pins = cycle_pins(kind, addr, data, inte_after)
            out += pins
        if cycles and cycles[-1][0] == "HLTA":
            out.append(TWH(inte_after))                   # HLT's 7th state is the first TWH
        return states_count, out

    def states(self):
        """Yield Pins for every state, forever (TWH while halted with no accepted interrupt)."""
        c = self.cpu
        while True:
            if c.halted and not (c.int_req is not None and c.inte):
                yield TWH(c.inte)
                continue
            _, pins = self.instruction_states()
            yield from pins


# ==================================================================== selftest
def selftest():
    fails = []

    def check(name, got, want):
        if got != want:
            fails.append(f"{name}: got {got!r}, want {want!r}")

    def first(prog, n, setup=None):
        c = R.CPU(bytes(prog)); c.sp = 0x8000
        if setup: setup(c)
        g = PinModel(c).states()
        return [next(g) for _ in range(n)]

    # every documented opcode: states generated from the §6.2 cycles add up to p.4-15's count
    for op in range(256):
        if op in R.UNDOCUMENTED:
            continue
        for taken in (0, 1):
            c = R.CPU(bytes([op, 0, 0])); c.sp = 0x8000
            ccc = (op >> 3) & 7
            c.z = c.cy = c.p = c.s = (ccc & 1) if taken else 1 - (ccc & 1)
            n, pins = PinModel(c).instruction_states()
            check(f"states {op:02X} taken={taken}", len(pins), n)

    # NOP at 0000: fetch, read type, T4 data bus not compared
    p = first([0x00], 4)
    check("NOP T1", p[0], Pins("T1", 1, 1, 0x0000, 1, 0xA2, 0, 1, 0, 0, 0))
    check("NOP T2", p[1], Pins("T2", 0, 1, 0x0000, 0, None, 1, 1, 0, 0, 0))
    check("NOP T3", p[2], Pins("T3", 0, 1, 0x0000, 0, None, 1, 1, 0, 0, 0))
    check("NOP T4", p[3], Pins("T4", 0, 1, 0x0000, None, None, 0, 1, 0, 0, 0))
    # MVI M,5A with HL = 1234: F4, R(PC), W(HL): write data on d_out from T2, WR low in T3
    p = first([0x36, 0x5A], 10, lambda c: c.set_rp(2, 0x1234))
    check("MVI M read T1", p[4], Pins("T1", 1, 1, 0x0001, 1, 0x82, 0, 1, 0, 0, 0))
    check("MVI M write T1", p[7], Pins("T1", 1, 1, 0x1234, 1, 0x00, 0, 1, 0, 0, 0))
    check("MVI M write T2", p[8], Pins("T2", 0, 1, 0x1234, 1, 0x5A, 0, 1, 0, 0, 0))
    check("MVI M write T3", p[9], Pins("T3", 0, 1, 0x1234, 1, 0x5A, 0, 0, 0, 0, 0))
    # PUSH B: stack writes, status 04, SP-1 then SP-2
    p = first([0xC5], 11, lambda c: c.set_rp(0, 0xBEEF))
    check("PUSH SW1", (p[5].d_out, p[5].a, p[6].d_out), (0x04, 0x7FFF, 0xBE))
    check("PUSH SW2", (p[8].d_out, p[8].a, p[9].d_out), (0x04, 0x7FFE, 0xEF))
    # POP B: stack reads, status 86, SP then SP+1 (read type: d_oe 0, dbin 1 in T2/T3)
    p = first([0xC1], 10)
    check("POP SR1", (p[4].d_out, p[4].a, p[5].dbin, p[5].d_oe), (0x86, 0x8000, 1, 0))
    check("POP SR2", (p[7].d_out, p[7].a), (0x86, 0x8001))
    # OUT 07 with A = 3C: output status 10, a = {port, port}, data = A
    p = first([0xD3, 0x07], 10, lambda c: setattr(c, "a", 0x3C))
    check("OUT T1", (p[7].d_out, p[7].a), (0x10, 0x0707)); check("OUT T2 data", p[8].d_out, 0x3C)
    # IN 05: input status 42, a = 0505
    p = first([0xDB, 0x05], 10)
    check("IN T1", (p[7].d_out, p[7].a), (0x42, 0x0505))
    # DAD: two 3-state bus-idle cycles, a not compared
    p = first([0x09], 10)
    check("DAD I3", p[4:10], [Pins(f"T{i}", 0, 1, None, 0, None, 0, 1, 0, 0, 0) for i in (1, 2, 3)] * 2)
    # EI: INTE pin rises at T4 of EI's M1
    p = first([0xFB, 0x00], 5)
    check("EI inte by state", [x.inte for x in p], [0, 0, 0, 1, 1])
    # DI: falls at T4
    p = first([0xFB, 0xF3, 0x00], 9)
    check("DI inte by state", [x.inte for x in p[4:9]], [1, 1, 1, 0, 0])
    # HLT at 0000: F4, then HLTA T1 (status 8A, a = 0001), T2, then TWH forever
    p = first([0x76], 10)
    check("HLT count to first TWH", [x.state for x in p[:7]], ["T1", "T2", "T3", "T4", "T1", "T2", "TWH"])
    check("HLTA T1", (p[4].d_out, p[4].a), (0x8A, 0x0001))
    check("TWH pins", p[9], Pins("TWH", 0, 0, None, 0, None, 0, 1, 1, 0, 0))
    # leaving halt by interrupt: EI; HLT; INT -> INTA while halted (status 2B), PC not incremented,
    # INTE reset at T1, then SW SW of RST 1
    c = R.CPU(bytes([0xFB, 0x76])); c.sp = 0x8000
    g = PinModel(c).states()
    pre = [next(g) for _ in range(4 + 7 + 3)]          # EI, HLT (to first TWH), 3 more TWH
    c.request_interrupt(1)
    p = [next(g) for _ in range(11)]
    check("INTA_H T1", (p[0].state, p[0].d_out, p[0].a, p[0].inte), ("T1", 0x2B, 0x0002, 0))
    check("INTA_H length", [x.state for x in p[:5]], ["T1", "T2", "T3", "T4", "T5"])
    check("RST pushes return address", (p[6].d_out, p[9].d_out), (0x00, 0x02))
    check("after RST pc", c.pc, 0x0008)
    # reset pins (§5)
    check("reset pins", RESET_PINS, Pins("RESET", 0, 0, None, 0, None, 0, 1, 0, 0, 0))

    if fails:
        for f in fails:
            print("FAIL", f)
        print(f"FAIL pins8080 selftest: {len(fails)} failed")
        return 1
    print("PASS pins8080 selftest")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "selftest":
        sys.exit(selftest())
    print(__doc__)
    sys.exit(2)
