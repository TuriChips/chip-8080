#!/usr/bin/env python3
"""C8 (spec §8): random programs, RTL (i8080_system) vs ref/pins8080.py, every pin §4 compares, every
state. Owner: Beru. READY, INT and HOLD random per the §7 stimulus rule (testbench-driven, model replays the log);
IN reads in_port_data = 5A.

The model mirrors i8080_system: 64 KiB RAM, the BDOS stub bytes at 0005h-001Eh (reads only, as the
fixture does), IN returns 5A. Each program: 0000 JMP 0100; at 0100 the §5 preamble (LXI SP, LXI B/D/H,
PUSH H, POP PSW, MVI A) and seeded returns, then random code kept inside 0100h-2100h; no undocumented
byte anywhere (§6). See gen().
Usage: tests/random/c8/run.py [--nprog N] [--nst STATES] [--seed S] [--rtl DIR]
"""
import argparse, os, random, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ref"))
import ref8080 as R  # noqa: E402
import pins8080 as P  # noqa: E402

STUB = [0x79, 0xFE, 0x02, 0xCA, 0x11, 0x00, 0xFE, 0x09, 0xCA, 0x15, 0x00, 0xC9, 0x7B, 0xD3, 0x00, 0xC9,
        0x1A, 0xFE, 0x24, 0xC8, 0xD3, 0x00, 0x13, 0xC3, 0x15, 0x00]          # 0005h-001Eh (#31)
IN_DATA = 0x5A
# HLT (halts the rest of the run) and RST 0 (restarts the program) are left out of the generator;
# both are covered by the model selftest and by directed tests.
EXCLUDED = R.UNDOCUMENTED | {0x76, 0xC7}
FIELDS = "sync a_oe a d_oe d_out dbin wr_n wait_o hlda inte".split()
CODE0, CODE1 = 0x0100, 0x2100                     # random code region
JUMPS = {0xC3, 0xCD} | {0xC2 | (c << 3) for c in range(8)} | {0xC4 | (c << 3) for c in range(8)}


def length(op):
    if op in (0x01, 0x11, 0x21, 0x31, 0x22, 0x2A, 0x32, 0x3A) or op in JUMPS:
        return 3
    if (op & 0xC7) == 0x06 or (op & 0xC7) == 0xC6 or op in (0xD3, 0xDB):
        return 2
    return 1


def gen(rng):
    """0000 JMP 0100; RST 4-7 vectors hold RET (RST 1-3 land in the BDOS stub, which also returns);
    at 0100 the §5 preamble plus 32 seeded return addresses, then random code that keeps jumps, calls
    and most register-pair values inside the code region and ends with a JMP back into it. No
    EXCLUDED byte anywhere, operands included (jumps land mid-instruction). Same ideas as acc4."""
    safe = [b for b in range(256) if b not in EXCLUDED]
    r8 = lambda: rng.choice(safe)

    def r16(lo, hi):
        while True:
            t = rng.randrange(lo, hi)
            if (t & 0xFF) not in EXCLUDED and (t >> 8) not in EXCLUDED:
                return t

    def pair():
        t = r16(CODE0, CODE1) if rng.random() < 0.9 else r16(0, 65536)
        return [t & 0xFF, t >> 8]

    mem = [0] * 65536
    mem[0:3] = [0xC3, 0x00, 0x01]
    for v in (0x20, 0x28, 0x30, 0x38):
        mem[v] = 0xC9
    prog = [0x31, 0x00, 0xF0]
    for _ in range(32):
        t = r16(CODE0, CODE1)
        prog += [0x21, t & 0xFF, t >> 8, 0xE5]
    prog += [0x01, *pair(), 0x11, *pair(), 0x21, *pair(), 0xE5, 0xF1, 0x3E, r8()]
    while len(prog) < (CODE1 - CODE0) - 6:
        if rng.random() < 0.02:
            prog.append(0xFB)                          # extra EIs, so random INT is actually taken
        op = rng.choice(safe)
        n = length(op)
        if op in JUMPS:
            t = r16(CODE0, CODE1)
            prog += [op, t & 0xFF, t >> 8]
        elif op == 0x31:                             # LXI SP: keep the stack away from the code
            t = r16(0xE000, 0xF000)
            prog += [op, t & 0xFF, t >> 8]
        elif op in (0x01, 0x11, 0x21):
            prog += [op, *pair()]
        else:
            prog += [op] + [r8() for _ in range(n - 1)]
    prog += [0] * ((CODE1 - CODE0) - 3 - len(prog))
    t = r16(CODE0, CODE1 - 3)
    prog += [0xC3, t & 0xFF, t >> 8]
    mem[CODE0:CODE1] = prog
    assert not EXCLUDED & set(prog)
    return mem


def model_states(mem, nst, inputs=None, vec=7):
    """inputs: per-state (ready, int_req) recorded by the testbench, from the first T1 on."""
    ram = bytearray(mem)
    def rd(a):
        return STUB[a - 5] if 5 <= a <= 0x1E else ram[a]
    def wr(a, v):
        ram[a] = v
    c = R.CPU(read=rd, write=wr, inp=lambda port: IN_DATA)
    if inputs:
        get = lambda n, k: inputs[n][k] if 0 <= n < len(inputs) else (1, 0, 0)[k]
        pm = P.PinModel(c, ready=lambda n: get(n, 0), int_req=lambda n: get(n, 1), hold=lambda n: get(n, 2),
                        int_vector=lambda n: vec)
    else:
        pm = P.PinModel(c)
    g = pm.states()
    out = []
    try:
        for _ in range(nst):
            out.append(next(g))
    except R.Undocumented:
        # random code wrote a byte the spec leaves undefined (§6) into its own code region and then
        # reached it: compare only up to there (counted as "stopped", not as a pass or a mismatch)
        STOPPED.append(len(out))
    return out


STOPPED = []


def recorded_inputs(pdir):
    got = [l.split() for l in open(f"{pdir}/pins.txt")]
    lead = 0
    while lead < len(got) and got[lead][0] != "1":
        lead += 1
    return [(int(g[11]), int(g[12]), int(g[13])) for g in got[lead:]]


def fmt(p):
    """Model pins in the testbench's text format; None (not compared) as '-'."""
    def b(v): return "-" if v is None else str(v)
    return [b(p.sync), b(p.a_oe), "-" if p.a is None else "%04x" % p.a, b(p.d_oe),
            "-" if p.d_out is None else "%02x" % p.d_out, b(p.dbin), b(p.wr_n), b(p.wait_o), b(p.hlda), b(p.inte)]


RESET_ROW = ["0", "0", None, "0", None, "0", "1", "0", "0", "0"]   # §5 pins while reset = 1 (a, d_out: not compared)


def compare(pdir, want):
    got = [l.split() for l in open(f"{pdir}/pins.txt")]
    # §5: comparison starts at the first T1 after reset falls. The RTL may show reset-valued states
    # before it (i8080_timing's reset state, chip-8080#34): at most 2, each with exactly the §5 pins.
    lead = 0
    while lead < len(got) and got[lead][0] != "1":
        g = got[lead]
        bad = [FIELDS[k] for k, v in enumerate(RESET_ROW) if v is not None and g[k] != v]
        if bad or lead >= 2:
            return f"state {lead} before the first T1: not reset-valued ({' '.join(g[:10])}; {bad or 'more than 2'})"
        lead += 1
    got = got[lead:]
    for i, (g, w) in enumerate(zip(got, want)):
        wf = fmt(w)
        if w.a_oe == 0: wf[2] = "-"                   # a not compared when a_oe = 0
        if w.d_oe == 0: wf[4] = "-"                   # d_out not compared when d_oe = 0
        if w.d_oe is None: wf[4] = "-"
        for k, name in enumerate(FIELDS):
            if wf[k] != "-" and g[k] != wf[k]:
                return f"state {i} ({w.state}): {name} rtl={g[k]} model={wf[k]}  | rtl {' '.join(g[:10])} | model {' '.join(wf)}"
        if g[10] != "0":
            return f"state {i} ({w.state}): bus_conflict = {g[10]}"
    if len(got) < len(want) - 2 and len(want) >= 1:
        return f"rtl dumped {len(got)} states, model {len(want)}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nprog", type=int, default=20)
    ap.add_argument("--nst", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rtl", default=os.path.join(ROOT, "rtl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "c8"))
    ap.add_argument("--stim", type=int, default=1, help="1: random READY/INT/HOLD per the §7 rule (default); 0: none")
    ap.add_argument("--hold", type=int, default=1, help="0: leave HOLD out of the stimulus")
    a = ap.parse_args()
    progs = []
    for p in range(a.nprog):
        mem = gen(random.Random(a.seed + p))
        d = f"{a.out}/prog{p}"
        os.makedirs(d, exist_ok=True)
        open(f"{d}/mem.hex", "w").write("\n".join("%02x" % v for v in mem) + "\n")
        progs.append(mem)
    rtl = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(a.rtl) for f in fs if f.endswith(".v"))
    vvp = f"{a.out}/c8.vvp"
    subprocess.run(["iverilog", "-g2012", "-o", vvp, *rtl, os.path.join(ROOT, "tests/random/c8/tb.sv")], check=True)
    sim = subprocess.run(["vvp", "-n", vvp, f"+dir={a.out}", f"+nprog={a.nprog}", f"+nst={a.nst}",
                          f"+stim={a.stim}", f"+seed={a.seed}", f"+vec={1 + a.seed % 7}",
                          f"+hold={a.hold}"],
                         capture_output=True, text=True)
    if "DONE c8 tb" not in sim.stdout or "ERROR" in sim.stdout:
        print(sim.stdout[-2000:], sim.stderr[-2000:]); print("FAIL: simulator problems"); return 1
    bad = 0
    for p, mem in enumerate(progs):
        d = f"{a.out}/prog{p}"
        err = compare(d, model_states(mem, a.nst, recorded_inputs(d) if a.stim else None, 1 + a.seed % 7))
        if err:
            bad += 1
            if bad <= 20:
                print(f"MISMATCH prog{p} (seed {a.seed + p}): {err}")
    tw = ints = holds = 0
    for p in range(a.nprog):
        for l in open(f"{a.out}/prog{p}/pins.txt"):
            f = l.split(); tw += f[7] == "1" and f[1] == "1"; ints += f[0] == "1" and f[4] in ("23", "2b")
            holds += f[8] == "1"
    print(f"coverage: {tw} wait states (TW), {ints} interrupt acknowledges (INTA), {holds} states with HLDA = 1")
    if STOPPED:
        print(f"stopped early (self-modified code reached an undocumented byte, §6): {len(STOPPED)} programs, after {sorted(STOPPED)} states")
    print(f"c8: seed={a.seed} stim={a.stim} programs={a.nprog} states={a.nst} mismatching_programs={bad}")
    print("PASS" if bad == 0 else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
