#!/usr/bin/env python3
"""Acceptance test 3 for the 8080 (spec §9): random programs on an independent emulator, MAME's
8080 core (i8085.cpp, BSD-3-Clause), compared with ref/ref8080.py before every instruction on
pc, A, flags (S Z AC P CY), BC, DE, HL, SP. Owner: Beru. Details: ref/README.md.

MAME runs its ROM-less "intel02" machine with OUR program as the cartridge (0000-1FFF). The model
gets the same memory map: cartridge read-only, RAM F000-F3FF (not mirrored), unmapped reads 00,
unmapped writes dropped (all measured in MAME). Get MAME first: tests/random/acc3/fetch_mame.sh.
Usage: tests/random/acc3/run.py [NPROG] [NINSTR] [SEED0]   (env MAME_DIR, default build/mame)
"""
import os, random, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.environ.get("REF", os.path.join(ROOT, "ref")))
import ref8080 as R  # noqa: E402

MAME_DIR = os.path.abspath(os.environ.get("MAME_DIR", os.path.join(ROOT, "build", "mame")))
CART = 0x2000
# Spec §6 undocumented; IN (the 8255 drives it); HLT (nothing wakes intel02); RST 0 (restarts the
# program, so random code loops back to the preamble). RST 0 is still covered by the model selftest and C8.
EXCLUDED = R.UNDOCUMENTED | {0xDB, 0x76, 0xC7}
JUMPS = {0xC3, 0xCD} | {0xC2 | (c << 3) for c in range(8)} | {0xC4 | (c << 3) for c in range(8)}
DIRECT = {0x22, 0x2A, 0x32, 0x3A}              # SHLD LHLD STA LDA
LINE = re.compile(r"pc=([0-9A-F]{4}) a=([0-9A-F]{2}) f=([0-9A-F]{2}) bc=([0-9A-F]{4}) "
                  r"de=([0-9A-F]{4}) hl=([0-9A-F]{4}) sp=([0-9A-F]{4}) \|")
FMASK = 0xD5                                   # S Z AC P CY (MAME's internal F doesn't keep bit 1)


def length(op):
    if op in (0x01, 0x11, 0x21, 0x31, 0x22, 0x2A, 0x32, 0x3A) or op in JUMPS:
        return 3
    if (op & 0xC7) == 0x06 or (op & 0xC7) == 0xC6 or op in (0xD3, 0xDB):
        return 2
    return 1


def gen(rng):
    """Preamble (spec §5) at 0040 writes every register, then random instructions. Jump/call targets stay
    in the cartridge; half of the direct memory accesses point at RAM. No byte in the cartridge is
    an EXCLUDED opcode, operands included: jumps land mid-instruction, so any byte can execute."""
    safe = [b for b in range(256) if b not in EXCLUDED]
    r8 = lambda: rng.choice(safe)

    def r16(lo, hi):                           # a 16-bit value in [lo, hi) whose bytes are both safe
        while True:
            t = rng.randrange(lo, hi)
            if (t & 0xFF) not in EXCLUDED and (t >> 8) not in EXCLUDED:
                return t
    def pair():                                # register-pair value: half point into the cartridge, so a
        t = r16(0, CART) if rng.random() < 0.9 else r16(0, 65536)   # RET/PCHL of a pushed pair stays in code
        return [t & 0xFF, t >> 8]
    # Layout like a real system: 0000 JMP to the preamble at 0040; each RST vector 0008..0038 holds
    # a RET, so a random RST n acts as a call and returns (without this, RSTs jumping back into the
    # first bytes made tiny loops, and most runs repeated the same 10 instructions).
    prog = [0xC3, 0x40, 0x00] + [0x00] * 5
    for n in range(1, 8):
        prog += [0xC9] + [0x00] * 7
    # Stack seeded with 32 cartridge addresses, so RET/Rcc lands in code (with an empty stack it read
    # 0000 from unmapped space and restarted the program, replaying the same path: another loop).
    prog += [0x31, 0x00, 0xF4]
    for _ in range(32):
        t = r16(0x0040, CART)
        prog += [0x21, t & 0xFF, t >> 8, 0xE5]
    prog += [0x01, *pair(), 0x11, *pair(), 0x21, *pair(), 0xE5, 0xF1, 0x3E, r8()]
    ops = [b for b in range(256) if b not in EXCLUDED]
    while len(prog) < CART - 6:
        op = rng.choice(ops)
        n = length(op)
        if op in JUMPS:
            t = r16(0, CART)
            prog += [op, t & 0xFF, t >> 8]
        elif op == 0x31:                       # LXI SP: keep the stack in RAM
            t = r16(0xF002, 0xF400)
            prog += [op, t & 0xFF, t >> 8]
        elif op in (0x01, 0x11, 0x21):         # LXI B/D/H
            prog += [op, *pair()]
        elif op in DIRECT:
            t = r16(0xF000, 0xF400) if rng.random() < 0.5 else r16(0, 65536)
            prog += [op, t & 0xFF, t >> 8]
        else:
            prog += [op] + [r8() for _ in range(n - 1)]
    prog += [0] * (CART - 3 - len(prog))
    t = r16(0x0040, CART - 3)                  # the last bytes jump back into the code, so execution
    prog += [0xC3, t & 0xFF, t >> 8]           # doesn't run off the cartridge into unmapped space
    assert not EXCLUDED & set(prog), "excluded byte in the cartridge"
    return prog


def mame_env():
    root = os.path.join(MAME_DIR, "root")
    libs = sorted({dp for dp, _, fs in os.walk(root) for f in fs if ".so" in f})
    plat = next((dp for dp, ds, _ in os.walk(root) if os.path.basename(dp) == "platforms"), None)
    xdg = os.path.join(MAME_DIR, "xdg")
    os.makedirs(xdg, mode=0o700, exist_ok=True)
    env = dict(os.environ, LD_LIBRARY_PATH=":".join(libs), QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=xdg)
    if plat:
        env["QT_PLUGIN_PATH"] = os.path.dirname(plat)
    return os.path.join(root, "usr", "games", "mame"), env


def run_mame(prog, work, seconds=1):
    os.makedirs(work, exist_ok=True)
    cart = os.path.join(work, "prog.bin")
    open(cart, "wb").write(bytes(prog))
    log, script = os.path.join(work, "trace.log"), os.path.join(work, "s.txt")
    if os.path.exists(log):
        os.remove(log)
    open(script, "w").write(f'trace {log},maincpu,noloop,{{tracelog "pc=%04X a=%02X f=%02X bc=%04X '
                            f'de=%04X hl=%04X sp=%04X | ",pc,a,f,bc,de,hl,sp}}\ngo\n')
    mame, env = mame_env()
    # SIGKILL: with the Qt debugger MAME ignores SIGTERM
    subprocess.run(["timeout", "-s", "KILL", "30", mame, "intel02", "-cart", cart, "-video", "none",
                    "-sound", "none", "-nothrottle", "-seconds_to_run", str(seconds), "-debug",
                    "-debugger", "qt", "-debugscript", script, "-skip_gameinfo"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    out = []
    for i, l in enumerate(open(log)):
        m = LINE.match(l)
        if not m:
            raise SystemExit(f"unparsable trace line {i + 1} in {log}: {l.rstrip()}")
        out.append(tuple(int(x, 16) for x in m.groups()) + (l.split("|", 1)[1].strip(),))
    return out


def model(prog):
    ram = bytearray(0x400)
    def rd(a):
        return prog[a] if a < CART else (ram[a - 0xF000] if 0xF000 <= a < 0xF400 else 0x00)
    def wr(a, v):
        if 0xF000 <= a < 0xF400:
            ram[a - 0xF000] = v
    return R.CPU(read=rd, write=wr)


def state(c):
    return (c.pc, c.a, c.flags() & FMASK, c.rp(0), c.rp(1), c.rp(2), c.sp)


def compare(prog, tr, n):
    c = model(prog)
    # MAME's trace may start after the first instruction(s): step until the pc lines up
    k = 0
    while c.pc != tr[0][0] and k < 4:
        c.step(); k += 1
    if c.pc != tr[0][0]:
        return 0, ("align", tr[0][0], c.pc)
    for i in range(min(n, len(tr))):
        pc, a, f, bc, de, hl, sp, dis = tr[i]
        got, want = (pc, a, f & FMASK, bc, de, hl, sp), state(c)
        if got != want:
            return i, (got, want, dis, tr[i - 1][7] if i else "")
        c.step()
    return None


def fmt(s):
    return "pc=%04X a=%02X f=%02X bc=%04X de=%04X hl=%04X sp=%04X" % s


def main():
    nprog = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    work = os.path.join(ROOT, "build", "acc3")
    bad = 0
    for p in range(nprog):
        prog = gen(random.Random(seed0 + p))
        tr = run_mame(prog, work)
        if len(tr) < n:
            bad += 1
            print(f"FAIL seed {seed0 + p}: only {len(tr)} trace lines (need {n})")
            continue
        res = compare(prog, tr, n)
        if res:
            bad += 1
            i, info = res
            if info[0] == "align":
                print(f"MISMATCH seed {seed0 + p}: can't align on the first traced pc {info[1]:04X}")
            else:
                got, want, dis, prev = info
                print(f"MISMATCH seed {seed0 + p} instr {i}: prev [{prev}] now [{dis}]\n"
                      f"  mame  {fmt(got)}\n  model {fmt(want)}")
        else:
            print(f"ok seed {seed0 + p}: {n} instructions")
    print(f"acc3: seed0={seed0} programs={nprog} instructions={n} agree={nprog - bad}")
    print("PASS" if bad == 0 else "FAIL")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
