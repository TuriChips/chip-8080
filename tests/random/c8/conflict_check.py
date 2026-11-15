#!/usr/bin/env python3
"""Positive bus_conflict check (spec §8: "a test where two drivers are on at once, checking that
bus_conflict rises"). Owner: Beru.

Builds a copy of the RTL with one deliberate fault: in T2 of a read cycle, i8080_control also drives the
data bus (doe = 1) while the system drives it for DBIN. Runs a short C8 on it and checks, from the
dumped pins, that bus_conflict = 1 in at least one state, and only in states where both d_oe and dbin
are 1. Then runs the same programs on the unmodified RTL and checks bus_conflict is never 1.
The mutant is built under build/, never committed. Usage: tests/random/c8/conflict_check.py [--rtl DIR]
"""
import argparse, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

FAULT_FROM = "else if (is_rd_k) dbn = 1'b1;\n                else if (cyc_wr) doe = 1'b1;"
FAULT_TO = "else if (is_rd_k) begin dbn = 1'b1; doe = 1'b1; end   // FAULT (conflict_check): CPU drives during DBIN\n                else if (cyc_wr) doe = 1'b1;"


def run_c8(rtl, out):
    r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "run.py"), "--nprog", "3", "--nst", "2000",
                        "--seed", "7", "--rtl", rtl, "--out", out], capture_output=True, text=True)
    conflicts = both = 0
    for p in range(3):
        for l in open(f"{out}/prog{p}/pins.txt"):
            f = l.split()
            if f[10] == "1":
                conflicts += 1
                both += f[3] == "1" and f[5] == "1"
    return r.stdout, conflicts, both


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtl", default=os.path.join(ROOT, "rtl"))
    a = ap.parse_args()
    work = os.path.join(ROOT, "build", "conflict_check")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(a.rtl, f"{work}/rtl")
    ctl = f"{work}/rtl/control/i8080_control.v"
    src = open(ctl).read()
    if FAULT_FROM not in src:
        print("FAIL conflict_check: the T2 read/write lines in i8080_control.v changed; update FAULT_FROM")
        return 1
    open(ctl, "w").write(src.replace(FAULT_FROM, FAULT_TO, 1))
    _, conf_m, both_m = run_c8(f"{work}/rtl", f"{work}/out_fault")
    _, conf_ok, _ = run_c8(a.rtl, f"{work}/out_clean")
    print(f"faulty RTL: bus_conflict = 1 in {conf_m} states, {both_m} of them with d_oe = dbin = 1")
    print(f"clean RTL:  bus_conflict = 1 in {conf_ok} states")
    ok = conf_m > 0 and both_m == conf_m and conf_ok == 0
    print(("PASS" if ok else "FAIL") + " conflict_check: bus_conflict rises exactly when two drivers are on")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
