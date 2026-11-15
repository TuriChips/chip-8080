#!/usr/bin/env python3
"""C8 with mid-run resets (spec §5, §8): same comparison as run.py, plus RESET raised at random
states (tb_resets.sv) and held 3-5 states. Owner: Beru.

Reset abandons the instruction in progress (§5). The model executes whole instructions, so at a reset
the harness rolls back exactly the memory writes the RTL had not completed: a write cycle's write
happens at the closing edge of its first WR-low state (TW or T3), and RESET forces WR high at once, so
a write counts only if that state closed before the state in which RESET was raised. Registers are not
rolled forward or back: the program restarts at 0000 (JMP 0100, preamble), which writes every register
before reading it (§5). After the state where RESET is raised, the RTL must show the §5 reset pins
until its next T1, which is where the model resumes (PC 0, INTE 0, no pending INT, not halted).
Usage: tests/random/c8/run_resets.py [--nprog N] [--nst STATES] [--seed S] [--rtl DIR]
"""
import argparse, os, random, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import importlib
run = importlib.import_module("run")
R, P = run.R, run.P


def compare_one(g, w, i):
    """One state, the same rules as run.compare: '-' / None cells and a or d_out with their enable 0
    are not compared; bus_conflict must be 0."""
    wf = run.fmt(w)
    if w.a_oe == 0: wf[2] = "-"
    if w.d_oe == 0 or w.d_oe is None: wf[4] = "-"
    for k, name in enumerate(run.FIELDS):
        if wf[k] != "-" and g[k] != wf[k]:
            return f"state {i} ({w.state}): {name} rtl={g[k]} model={wf[k]}  | rtl {' '.join(g[:10])} | model {' '.join(wf)}"
    if g[10] != "0":
        return f"state {i} ({w.state}): bus_conflict = {g[10]}"
    return None


def rollback(records, ram, i, stats):
    """Undo the model's memory writes that the RTL hasn't completed by state i (a write completes at the
    closing edge of its cycle's first WR-low state). Returns True if state i is inside an instruction."""
    rec = next((r for r in reversed(records) if r[0] <= i), None)
    if not (rec and rec[2] and rec[0] < i < rec[0] + len(rec[2])):
        return False
    done = []                                       # completion state of each write cycle, in order
    pins = rec[2]
    for j, p in enumerate(pins):
        if p.state == "T1" and p.d_out in (0x00, 0x04):
            k = j
            while k < len(pins) and pins[k].wr_n != 0 and (k == j or pins[k].state != "T1"):
                k += 1
            done.append(rec[0] + k)
    for (addr, old), wdone in reversed(list(zip(rec[1], done))):
        if wdone >= i:
            ram[addr] = old
            stats["rolled_back"] += 1
    return True


def read_dump(path):
    m = [int(l, 16) for l in open(path) if l.strip() and not l.startswith("//")]
    assert len(m) == 65536, f"{path}: {len(m)} bytes"
    return m


def compare_with_resets(mem, got, vec, mem_end=None, pdir=None):
    """got: RTL lines from the first T1 on (15 fields: 11 pins, ready, int_req, hold, reset)."""
    ram = bytearray(mem)
    cur = {"undo": None}

    def rd(a):
        return run.STUB[a - 5] if 5 <= a <= 0x1E else ram[a]

    def wr(a, v):
        if cur["undo"] is not None:
            cur["undo"].append((a, ram[a]))
        ram[a] = v

    c = R.CPU(read=rd, write=wr, inp=lambda port: run.IN_DATA)
    inp = lambda n, k: int(got[n][11 + k]) if 0 <= n < len(got) else (1, 0, 0)[k]
    pm = P.PinModel(c, ready=lambda n: inp(n, 0), int_req=lambda n: inp(n, 1), hold=lambda n: inp(n, 2),
                    int_vector=lambda n: vec)
    records = []                                       # [start state, undo log, pins] per instruction
    orig_ip = pm.instruction_states

    def ip():
        rec = [pm.n, [], None]
        cur["undo"] = rec[1]
        records.append(rec)
        n, pins = orig_ip()
        rec[2] = pins
        return n, pins
    pm.instruction_states = ip

    stats = {"resets": 0, "mid_instruction": 0, "rolled_back": 0}
    g = pm.states()
    i = 0
    while i < len(got):
        w = next(g)
        err = compare_one(got[i], w, i)
        if err:
            return err, stats
        if got[i][14] == "1":                           # RESET raised in state i
            stats["resets"] += 1
            if rollback(records, ram, i, stats):
                stats["mid_instruction"] += 1
            if pdir:                                    # RAM right after the abandoned instruction
                dump = read_dump(f"{pdir}/mem_rst{stats['resets'] - 1}.hex")
                diff = [a for a in range(65536) if ram[a] != dump[a]]
                if diff:
                    a = diff[0]
                    return (f"state {i}: RAM after RESET differs at {len(diff)} addresses, first {a:04X}: "
                            f"rtl {dump[a]:02X} model {ram[a]:02X}"), stats
            # §5: after reset the program must write every register before reading it. That holds
            # only if the reset vector (0000-0002) and the preamble (0100-) are still the generated
            # code; random code may have overwritten them. If so, stop comparing this program.
            pre_len = 3 + 32 * 4 + 12
            if bytes(ram[0:3]) != bytes(mem[0:3]) or bytes(ram[0x100:0x100 + pre_len]) != bytes(mem[0x100:0x100 + pre_len]):
                stats["stopped_vector"] = stats.get("stopped_vector", 0) + 1
                return None, stats
            c.pc = 0; c.inte = 0; c.halted = False; c.int_req = None; c.int_inhibit = 0
            j = i + 1
            while j < len(got) and got[j][0] != "1":
                bad = [run.FIELDS[k] for k, v in enumerate(run.RESET_ROW) if v is not None and got[j][k] != v]
                if bad:
                    return f"state {j}: after RESET, not reset-valued ({' '.join(got[j][:10])}; {bad})", stats
                j += 1
            if j - i - 1 < 3:
                return f"state {i}: RESET run shorter than 3 states", stats
            pm.n = j
            g = pm.states()
            i = j
            continue
        i += 1
    if mem_end is not None:                          # final RAM: RTL vs model, after undoing writes the
        rollback(records, ram, len(got), stats)      # RTL hadn't completed by the last state
        diff = [a for a in range(65536) if ram[a] != mem_end[a]]
        if diff:
            a = diff[0]
            return (f"final RAM differs at {len(diff)} addresses, first {a:04X}: rtl {mem_end[a]:02X} "
                    f"model {ram[a]:02X}"), stats
    return None, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nprog", type=int, default=20)
    ap.add_argument("--nst", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rtl", default=os.path.join(run.ROOT, "rtl"))
    ap.add_argument("--out", default=os.path.join(run.ROOT, "build", "c8r"))
    a = ap.parse_args()
    progs = []
    for p in range(a.nprog):
        mem = run.gen(random.Random(a.seed + p))
        d = f"{a.out}/prog{p}"
        os.makedirs(d, exist_ok=True)
        open(f"{d}/mem.hex", "w").write("\n".join("%02x" % v for v in mem) + "\n")
        progs.append(mem)
    rtl = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(a.rtl) for f in fs if f.endswith(".v"))
    vvp = f"{a.out}/c8r.vvp"
    subprocess.run(["iverilog", "-g2012", "-o", vvp, *rtl, os.path.join(HERE, "tb_resets.sv")], check=True)
    vec = 1 + a.seed % 7
    sim = subprocess.run(["vvp", "-n", vvp, f"+dir={a.out}", f"+nprog={a.nprog}", f"+nst={a.nst}",
                          "+stim=1", f"+seed={a.seed}", f"+vec={vec}", "+hold=1"], capture_output=True, text=True)
    if "DONE c8 tb" not in sim.stdout or "ERROR" in sim.stdout:
        print(sim.stdout[-2000:], sim.stderr[-2000:]); print("FAIL: simulator problems"); return 1
    bad = 0; tot = {"resets": 0, "mid_instruction": 0, "rolled_back": 0, "stopped_vector": 0}; stopped = 0
    for p, mem in enumerate(progs):
        got = [l.split() for l in open(f"{a.out}/prog{p}/pins.txt")]
        lead = 0
        while lead < len(got) and got[lead][0] != "1":
            lead += 1
        try:
            mem_end = read_dump(f"{a.out}/prog{p}/mem_end.hex")
            err, st = compare_with_resets(mem, got[lead:], vec, mem_end, f"{a.out}/prog{p}")
        except R.Undocumented:
            stopped += 1; continue
        for k in tot: tot[k] += st.get(k, 0)
        if err:
            bad += 1
            if bad <= 10:
                print(f"MISMATCH prog{p} (seed {a.seed + p}): {err}")
    print(f"resets: {tot['resets']} ({tot['mid_instruction']} mid-instruction), memory writes rolled back: {tot['rolled_back']}")
    if stopped or tot["stopped_vector"]:
        print(f"stopped early: {stopped} programs reached a self-written undocumented byte (§6), "
              f"{tot['stopped_vector']} had overwritten their reset vector or preamble before a reset (§5)")
    print(f"c8 resets: seed={a.seed} programs={a.nprog} states={a.nst} mismatching_programs={bad}")
    print("PASS" if bad == 0 else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
