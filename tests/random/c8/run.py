#!/usr/bin/env python3
"""C8 (spec §8): random programs, RTL (i8080_system) vs ref/pins8080.py, every pin §4 compares, every
state. Owner: Beru. First version: READY = 1, HOLD = 0, INT = 0; IN reads in_port_data = 5A.

The model mirrors i8080_system: 64 KiB RAM, the BDOS stub bytes at 0005h-001Eh (reads only, as the
fixture does), IN returns 5A. Each program: 0000 JMP 0100; at 0100 the §5 preamble (LXI SP, LXI B/D/H,
PUSH H, POP PSW, MVI A), then random code; no undocumented byte anywhere (§6).
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
EXCLUDED = R.UNDOCUMENTED | {0x76}                # HLT left out for now (halts the rest of the run)
FIELDS = "sync a_oe a d_oe d_out dbin wr_n wait_o hlda inte".split()


def gen(rng):
    safe = [b for b in range(256) if b not in EXCLUDED]
    r8 = lambda: rng.choice(safe)
    mem = [0] * 65536
    mem[0:3] = [0xC3, 0x00, 0x01]
    pre = [0x31, 0x00, 0xF0, 0x01, r8(), r8(), 0x11, r8(), r8(), 0x21, r8(), r8(), 0xE5, 0xF1, 0x3E, r8()]
    mem[0x100:0x100 + len(pre)] = pre
    for a in range(0x100 + len(pre), 0x2100):
        mem[a] = r8()
    return mem


def model_states(mem, nst):
    ram = bytearray(mem)
    def rd(a):
        return STUB[a - 5] if 5 <= a <= 0x1E else ram[a]
    def wr(a, v):
        ram[a] = v
    c = R.CPU(read=rd, write=wr, inp=lambda port: IN_DATA)
    g = P.PinModel(c).states()
    return [next(g) for _ in range(nst)]


def fmt(p):
    """Model pins in the testbench's text format; None (not compared) as '-'."""
    def b(v): return "-" if v is None else str(v)
    return [b(p.sync), b(p.a_oe), "-" if p.a is None else "%04x" % p.a, b(p.d_oe),
            "-" if p.d_out is None else "%02x" % p.d_out, b(p.dbin), b(p.wr_n), b(p.wait_o), b(p.hlda), b(p.inte)]


def compare(pdir, want):
    got = [l.split() for l in open(f"{pdir}/pins.txt")]
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
    if len(got) < len(want):
        return f"rtl dumped {len(got)} states, model {len(want)}"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nprog", type=int, default=20)
    ap.add_argument("--nst", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rtl", default=os.path.join(ROOT, "rtl"))
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "c8"))
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
    sim = subprocess.run(["vvp", "-n", vvp, f"+dir={a.out}", f"+nprog={a.nprog}", f"+nst={a.nst}"],
                         capture_output=True, text=True)
    if "DONE c8 tb" not in sim.stdout or "ERROR" in sim.stdout:
        print(sim.stdout[-2000:], sim.stderr[-2000:]); print("FAIL: simulator problems"); return 1
    bad = 0
    for p, mem in enumerate(progs):
        err = compare(f"{a.out}/prog{p}", model_states(mem, a.nst))
        if err:
            bad += 1
            if bad <= 8:
                print(f"MISMATCH prog{p} (seed {a.seed + p}): {err}")
    print(f"c8: seed={a.seed} programs={a.nprog} states={a.nst} mismatching_programs={bad}")
    print("PASS" if bad == 0 else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
