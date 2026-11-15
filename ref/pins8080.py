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
READY wait states (TW), HOLD/HLDA and INT via ready(n), hold(n), int_req(n), int_vector(n)
callbacks (hold rules per §4 as refined by chip-8080#25).

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


def cycle_pins(kind, addr, data, inte, waits=0):
    """Pins for each state of one machine cycle (§4 'Pins per state' table). `waits` TW states go
    after T2 (READY low when sampled in T2 and in each TW); not in I3, HLTA, or T4/T5."""
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
        out += [Pins("TW", 0, 1, addr, 0, None, 1, 1, 1, 0, inte)] * waits
        out.append(Pins("T3", 0, 1, addr, 0, None, 1, 1, 0, 0, inte))
    else:                                             # write: data from T2, WR low in TW and T3
        out.append(Pins("T2", 0, 1, addr, 1, data, 0, 1, 0, 0, inte))
        out += [Pins("TW", 0, 1, addr, 1, data, 0, 0, 1, 0, inte)] * waits
        out.append(Pins("T3", 0, 1, addr, 1, data, 0, 0, 0, 0, inte))
    for t in range(3, LENGTH[kind]):                  # T4, T5: a held, data bus not compared
        out.append(Pins(f"T{t + 1}", 0, 1, addr, None, None, 0, 1, 0, 0, inte))
    return out


TWH = lambda inte: Pins("TWH", 0, 0, None, 0, None, 0, 1, 1, 0, inte)
HOLD = lambda inte: Pins("HOLD", 0, 0, None, 0, None, 0, 1, 0, 1, inte)          # §4 Hold row
HOLD_ENTRY = lambda addr, inte: Pins("HOLDE", 0, 1, addr, 0, None, 0, 1, 0, 1, inte)  # #25: write, no T4/T5


class PinModel:
    def __init__(self, cpu, ready=None, hold=None, int_req=None, int_vector=None):
        """ready(n), hold(n), int_req(n) -> 0/1 and int_vector(n) -> 0..7: inputs during absolute
        state n (defaults 1 / 0 / 0 / 7). Per the §7 stimulus rule a test changes them only on the
        edge starting a T1 or TW. INT is sampled in the last state of each instruction and in each
        halt state, gated by INTE (and EI's delay) and ignored while HLDA = 1 (§2, §4, p.2-11)."""
        self.cpu = cpu
        self.ready = ready or (lambda n: 1)
        self.hold = hold or (lambda n: 0)
        self.int_req = int_req or (lambda n: 0)
        self.int_vector = int_vector or (lambda n: 7)
        self.n = 0                                    # absolute state counter

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
            # READY: sampled in T2 (state n + 1 of this cycle) and in each TW after it
            waits = 0
            if kind not in ("I3", "HLTA"):
                t2 = self.n + len(out) + 1
                while not self.ready(t2 + waits):
                    waits += 1
            if kind in ("INTA", "INTA_H"):
                pins = cycle_pins(kind, addr, data, 0, waits)    # INTE reset at T1 of the INTA cycle
            elif i == 0:
                pins = cycle_pins(kind, addr, data, inte_before, waits)
                # the M1 of EI/DI: the flip-flop changes at T4 (state index 3 + waits)
                pins = [p._replace(inte=inte_after) if k >= 3 + waits else p for k, p in enumerate(pins)]
            else:
                pins = cycle_pins(kind, addr, data, inte_after, waits)
            # HOLD (§4 as refined by chip-8080#25/#39): recognised in T2, or in the TW where READY is
            # sampled high; not in DAD's bus-idle cycles or the halt acknowledge. The state where
            # hlda rises shows its normal row with hlda = 1; from the next state the Hold row applies
            # (T4/T5 included) for as long as HOLD was 1 at the closing edge of the previous held state.
            # If it's released while T4/T5 remain, those run with their normal rows (hlda = 0).
            base = self.n + len(out)
            if kind not in ("I3", "HLTA") and self.hold(base + 1 + waits):
                t3 = 2 + waits
                if kind in WRITES and len(pins) == t3 + 1:
                    rise = len(pins)                                 # 3-state write: hold-entry state
                    pins.append(HOLD_ENTRY(addr, pins[-1].inte))
                else:
                    rise = t3 if kind not in WRITES else t3 + 1      # read: T3; SW5: T4
                    pins[rise] = pins[rise]._replace(hlda=1)
                held = True
                for k in range(rise + 1, len(pins)):                 # remaining T4/T5 of this cycle
                    held = held and bool(self.hold(base + k - 1))
                    pins[k] = HOLD(pins[k].inte) if held else pins[k]
                out += pins
                while held and self.hold(self.n + len(out) - 1):     # held after the cycle ends
                    out.append(HOLD(out[-1].inte))
                continue
            out += pins
        if cycles and cycles[-1][0] == "HLTA":
            out.append(TWH(inte_after))                   # HLT's 7th state is the first TWH
        self.n += len(out)
        return states_count, out

    def sample_int(self, n, pin):
        """INT seen in state n (with that state's pins): latch RST n for the next instruction boundary,
        or clear the latch, so a request that wasn't accepted doesn't linger."""
        c = self.cpu
        c.int_req = self.int_vector(n) & 7 if (self.int_req(n) and not pin.hlda) else None

    def states(self):
        """Yield Pins for every state, forever (TWH while halted with no accepted interrupt)."""
        c = self.cpu
        while True:
            if c.halted and not (c.int_req is not None and c.inte):
                # HOLD sampled at the closing edge of each TWH / Hold state (#39): next state Hold or TWH
                pins = HOLD(c.inte) if self.hold(self.n - 1) else TWH(c.inte)
                self.sample_int(self.n, pins)            # accepted -> INTA from the next state
                self.n += 1
                yield pins
                continue
            n0 = self.n
            _, pins = self.instruction_states()
            # the instruction's last state: the last one before any trailing hold states (for HLT,
            # its first TWH, which is a halt state)
            k = len(pins) - 1
            while k > 0 and pins[k].state == "HOLD" and pins[k - 1].state in ("HOLD", "HOLDE", "T3", "T4", "T5"):
                k -= 1
            self.sample_int(n0 + k, pins[k])
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
    # READY: MVI M,5A with READY low during states 5-6 (T2 of the R cycle and one TW) and 8-9
    # (T2 of the W cycle and one TW): 2 TW each; read TW keeps dbin, write TW keeps data with WR low
    lows = {5, 6, 8 + 2, 9 + 2}
    c = R.CPU(bytes([0x36, 0x5A])); c.set_rp(2, 0x1234)
    pm = PinModel(c, ready=lambda n: 0 if n in lows else 1)
    n, p = pm.instruction_states()
    check("READY state names", [x.state for x in p],
          ["T1", "T2", "T3", "T4", "T1", "T2", "TW", "TW", "T3", "T1", "T2", "TW", "TW", "T3"])
    check("read TW pins", p[6], Pins("TW", 0, 1, 0x0001, 0, None, 1, 1, 1, 0, 0))
    check("write TW pins", p[11], Pins("TW", 0, 1, 0x1234, 1, 0x5A, 0, 0, 1, 0, 0))
    check("READY stretches, count = 10 + 4", len(p), n + 4)
    # READY low only in T1 (not sampled there) or in T4 (internal): no wait state
    c = R.CPU(bytes([0x00, 0x00]))
    pm = PinModel(c, ready=lambda n: 0 if n in (0, 3) else 1)
    check("READY not sampled in T1/T4", [x.state for x in pm.instruction_states()[1]], ["T1", "T2", "T3", "T4"])
    # DAD's idle cycles ignore READY
    c = R.CPU(bytes([0x09]))
    pm = PinModel(c, ready=lambda n: 0 if n >= 4 else 1)
    check("READY ignored in I3", [x.state for x in pm.instruction_states()[1]][4:], ["T1", "T2", "T3"] * 2)

    # HOLD in a read (fetch) cycle: high in states 0-4, low from 5 -> recognised in T2, hlda in T3
    # (T3 row kept), T4 a Hold row (HOLD was 1 at T3's end), states 4 and 5 Hold, released at the
    # end of state 5 (HOLD 0 there), next cycle's T1 at state 6
    c = R.CPU(bytes([0x00, 0x00]))
    pm = PinModel(c, hold=lambda n: 1 if n < 5 else 0)
    n, p = pm.instruction_states()
    check("HOLD read names", [x.state for x in p], ["T1", "T2", "T3", "HOLD", "HOLD", "HOLD"])
    check("HOLD read T3", p[2], Pins("T3", 0, 1, 0x0000, 0, None, 1, 1, 0, 1, 0))
    check("HOLD row", p[3], Pins("HOLD", 0, 0, None, 0, None, 0, 1, 0, 1, 0))
    nxt = pm.instruction_states()[1][0]
    check("resume T1 hlda 0", (nxt.state, nxt.hlda, nxt.a), ("T1", 0, 0x0001))
    # HOLD in a write cycle (MVI M's W): recognised at its T2 (state 8): T3 normal, then hold-entry
    # (a held, d_oe 0, hlda 1), then Hold rows
    c = R.CPU(bytes([0x36, 0x5A])); c.set_rp(2, 0x1234)
    pm = PinModel(c, hold=lambda n: 1 if 8 <= n < 12 else 0)
    n, p = pm.instruction_states()
    check("HOLD write names", [x.state for x in p][7:], ["T1", "T2", "T3", "HOLDE", "HOLD", "HOLD"])
    check("HOLD write T3", (p[9].wr_n, p[9].hlda), (0, 0))
    check("hold-entry row", p[10], Pins("HOLDE", 0, 1, 0x1234, 0, None, 0, 1, 0, 1, 0))
    # HOLD is not recognised in DAD's idle cycles; picked up at the next bus cycle's T2
    c = R.CPU(bytes([0x09, 0x00]))
    pm = PinModel(c, hold=lambda n: 1 if 4 <= n < 13 else 0)
    n, p = pm.instruction_states()
    check("HOLD ignored in I3", [x.hlda for x in p], [0] * 10)
    nxt = pm.instruction_states()[1]
    check("HOLD at next bus T2", [x.state for x in nxt][:4], ["T1", "T2", "T3", "HOLD"])
    # READY low + HOLD: recognised in the TW where READY is sampled high
    c = R.CPU(bytes([0x00]))
    pm = PinModel(c, ready=lambda n: 0 if n in (1, 2) else 1, hold=lambda n: 1 if n < 6 else 0)
    n, p = pm.instruction_states()
    check("HOLD after waits", [x.state for x in p], ["T1", "T2", "TW", "TW", "T3", "HOLD", "HOLD"])
    check("HOLD after waits: hlda from T3", [x.hlda for x in p], [0, 0, 0, 0, 1, 1, 1])
    # release while T4/T5 remain (#25): fetch, HOLD seen in T2, dropped by the end of T3 -> T4 normal
    c = R.CPU(bytes([0x00, 0x00]))
    pm = PinModel(c, hold=lambda n: 1 if n < 2 else 0)
    n, p = pm.instruction_states()
    check("released before T4", [(x.state, x.hlda) for x in p], [("T1", 0), ("T2", 0), ("T3", 1), ("T4", 0)])
    # XTHL's SW5: HOLD seen in its T2 -> T4 normal with hlda 1, T5 a Hold row (#25)
    c = R.CPU(bytes([0xE3])); c.sp = 0x100
    pm = PinModel(c, hold=lambda n: 1 if 14 <= n < 17 else 0)
    n, p = pm.instruction_states()
    check("SW5 hold", [(x.state, x.hlda) for x in p[13:]], [("T1", 0), ("T2", 0), ("T3", 0), ("T4", 1), ("HOLD", 1)])
    # HOLD from halt and back
    c = R.CPU(bytes([0x76])); g = PinModel(c, hold=lambda n: 1 if 8 <= n < 11 else 0).states()
    p = [next(g) for _ in range(14)]
    check("halt->hold->halt", [x.state for x in p[7:]], ["TWH", "TWH", "HOLD", "HOLD", "HOLD", "TWH", "TWH"])

    # INT: EI; NOP; NOP with INT high throughout and vector 3: not taken at the end of EI (delay),
    # taken at the end of the first NOP: INTA (status 23, a = PC not incremented, INTE 0), RST 3
    c = R.CPU(bytes([0xFB, 0x00, 0x00, 0x00])); c.sp = 0x8000
    g = PinModel(c, int_req=lambda n: 1, int_vector=lambda n: 3).states()
    p = [next(g) for _ in range(19)]
    check("INT after EI+1", [x.state for x in p[:13]],
          ["T1", "T2", "T3", "T4", "T1", "T2", "T3", "T4", "T1", "T2", "T3", "T4", "T5"])
    check("INTA T1", (p[8].d_out, p[8].a, p[8].inte), (0x23, 0x0002, 0))
    check("INTA pushes 0002, jumps to 0018", (p[14].d_out, p[17].d_out, c.pc), (0x00, 0x02, 0x18))
    # INT with INTE = 0 is never taken
    c = R.CPU(bytes([0x00] * 4)); g = PinModel(c, int_req=lambda n: 1).states()
    check("INT ignored with INTE 0", [next(g).d_out for _ in range(16)][::4], [0xA2] * 4)
    # INT high only mid-instruction (state 1 of EI;NOP;...) is not seen: sampled at instruction ends
    c = R.CPU(bytes([0xFB, 0x00, 0x00])); c.sp = 0x8000
    g = PinModel(c, int_req=lambda n: 1 if n in (5, 6) else 0).states()
    check("INT only mid-instruction", [next(g).d_out for _ in range(12)][::4], [0xA2] * 3)
    # from halt: EI; HLT; INT rises at state 13 (a TWH) -> INTA while halted (2B) at state 14
    c = R.CPU(bytes([0xFB, 0x76])); c.sp = 0x8000
    g = PinModel(c, int_req=lambda n: 1 if n >= 13 else 0, int_vector=lambda n: 1).states()
    p = [next(g) for _ in range(15)]
    check("INT from halt", [x.state for x in p[11:]], ["TWH", "TWH", "TWH", "T1"])
    check("INTA while halted", (p[14].d_out, p[14].a), (0x2B, 0x0002))
    # INT rising at the T1 of an instruction's later cycle is seen at the instruction's end:
    # EI; MVI A,1 (F4 at 4-7, R at 8-10): INT from state 8 -> INTA right after MVI
    c = R.CPU(bytes([0xFB, 0x3E, 0x01, 0x00])); c.sp = 0x8000
    g = PinModel(c, int_req=lambda n: 1 if n >= 8 else 0).states()
    p = [next(g) for _ in range(12)]
    check("INT sampled at the last state", (p[11].state, p[11].d_out), ("T1", 0x23))
    # a request seen while INTE = 0 and dropped before EI is not taken later (no stale latch)
    c = R.CPU(bytes([0x00, 0xFB, 0x00, 0x00, 0x00])); c.sp = 0x8000
    g = PinModel(c, int_req=lambda n: 1 if n < 4 else 0).states()
    check("no stale INT", [x.d_out for x in [next(g) for _ in range(20)] if x.state == "T1"], [0xA2] * 5)
    # INT is ignored while held: EI; NOP with HOLD across the NOP's end and INT high only then
    c = R.CPU(bytes([0xFB, 0x00, 0x00, 0x00])); c.sp = 0x8000
    pm = PinModel(c, hold=lambda n: 1 if 5 <= n < 9 else 0, int_req=lambda n: 1 if 6 <= n < 9 else 0)
    g = pm.states()
    check("INT ignored in HOLD", [x.d_out for x in [next(g) for _ in range(17)] if x.state == "T1"], [0xA2] * 4)

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
