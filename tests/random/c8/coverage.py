#!/usr/bin/env python3
"""What C8 exercised (spec §8 coverage): replays C8 programs through ref/pins8080.py with the inputs the
testbench recorded, and counts opcodes, §4 cycle types, condition codes taken / not taken, and where
wait states, holds and interrupts landed. Owner: Beru. Model-only: the RTL agreement itself is C8's
log; this says what that agreement covered.
Usage: tests/random/c8/coverage.py --out DIR --seed S --nprog N --nst STATES   (same as the C8 run)
"""
import argparse, collections, importlib, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
run = importlib.import_module("run")
R, P = run.R, run.P

CC = "NZ Z NC C PO PE P M".split()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=100)
    ap.add_argument("--nprog", type=int, default=50); ap.add_argument("--nst", type=int, default=20000)
    a = ap.parse_args()
    ops = collections.Counter(); kinds = collections.Counter(); cond = collections.Counter()
    tw_by = collections.Counter(); hold_by = collections.Counter(); inta_after = collections.Counter()
    orig_step = R.CPU.step

    def step(self):
        pc = self.pc
        op = self.read(pc)
        flags = (self.z, self.cy, self.p, self.s)
        took = None
        n, cyc = orig_step(self)
        if cyc and cyc[0][0] in ("INTA",):
            inta_after[LAST[0]] += 1
        elif cyc:
            ops[op] += 1
            LAST[0] = op
            if (op & 0xC7) in (0xC2, 0xC4, 0xC0):                 # Jcc, Ccc, Rcc
                c = (op >> 3) & 7
                f = [flags[0], flags[0], flags[1], flags[1], flags[2], flags[2], flags[3], flags[3]][c]
                took = f == (c & 1)
                cond[(CC[c], {0xC2: "Jcc", 0xC4: "Ccc", 0xC0: "Rcc"}[op & 0xC7], took)] += 1
        for k, *_ in cyc:
            kinds[k] += 1
        return n, cyc
    LAST = [0]
    R.CPU.step = step

    orig_ip = P.PinModel.instruction_states

    def instr(self):
        n, pins = orig_ip(self)
        kind = None
        for p in pins:                                             # cycle type from each T1's status
            if p.state == "T1":
                kind = {0xA2: "fetch", 0x82: "mem read", 0x00: "mem write", 0x86: "stack read", 0x04: "stack write",
                        0x42: "input", 0x10: "output", 0x23: "INTA", 0x2B: "INTA (halted)", 0x8A: "halt ack"}.get(p.d_out, "?")
            if p.state == "TW":
                tw_by[kind] += 1
            if p.hlda and p.state != "HOLD":
                hold_by[kind] += 1
        return n, pins
    P.PinModel.instruction_states = instr

    for p in range(a.nprog):
        mem = run.gen(random.Random(a.seed + p))
        d = f"{a.out}/prog{p}"
        run.model_states(mem, a.nst, run.recorded_inputs(d), 1 + a.seed % 7)

    doc = [b for b in range(256) if b not in R.UNDOCUMENTED]
    missing = [f"{b:02X}" for b in doc if not ops[b]]
    print(f"opcodes executed: {sum(1 for b in doc if ops[b])}/244; never: {' '.join(missing) or 'none'}")
    print("rarest:", ", ".join(f"{b:02X}x{n}" for n, b in sorted((ops[b], b) for b in doc if ops[b])[:8]))
    print("cycle kinds:", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    combos = [(c, i, t) for c in CC for i in ("Jcc", "Ccc", "Rcc") for t in (True, False)]
    miss = [f"{i} {c} {'taken' if t else 'not taken'}" for c, i, t in combos if not cond[(c, i, t)]]
    print(f"condition codes: {sum(1 for x in combos if cond[x])}/48 (8 conditions x Jcc/Ccc/Rcc x taken/not); missing: {', '.join(miss) or 'none'}")
    print("wait states by cycle:", ", ".join(f"{k}={v}" for k, v in sorted(tw_by.items())))
    print("HLDA rises in cycle:", ", ".join(f"{k}={v}" for k, v in sorted(hold_by.items())))
    print(f"interrupts accepted: {sum(inta_after.values())}, after {len(inta_after)} distinct opcodes")


if __name__ == "__main__":
    main()
