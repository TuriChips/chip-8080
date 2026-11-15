# ref/: reference model for the 8080 (owner: Beru)

`ref8080.py`: the 8080 at **instruction level** (memory map and I/O through callbacks, default 64 KiB RAM), written from `docs/spec.md` §3 and §6 only.
`CPU.step()` runs one instruction (or an interrupt acknowledge) and returns the state count (§6.1)
and the machine cycles it performed (§6.2 notation: F4/F5, R, W, SR, SW, IN, OUT, I3, HLTA, INTA,
with addresses). The pin-level model (§4) will be built on those cycles once §4 is signed off.

`python3 ref/ref8080.py selftest` checks: all 244 documented opcodes run with the p.4-15 state count
(conditionals both ways, patterns written independently of the decoder) and the 12 undocumented
bytes are rejected (§6); state counts, including conditional taken/not taken; the manual examples
quoted in §6 (SUB A with A = 3E, SBB 4−2−1, ADI 08 + DAA → 01 with CY = AC = 1); the SBB op = FF
Decision; DAA keeping CY; ANA's AC rule; ORA clearing CY/AC; CMP; INR/DCR AC and CY; DAD CY only;
PUSH/POP PSW fixed bits; CALL/RET/RST; XTHL; IN/OUT port on both address halves; EI setting INTE at once but delaying acceptance by one instruction, DI immediate;
INTA and leaving HLT by interrupt; §6.2 cycle lists for CALL, DAD and XTHL.

Not yet: the pin-level model (waits for §4 v1), random tests (`tests/random/`), the acceptance-4
emulator choice.

## Pin level: `pins8080.py` (spec v1 §4, §5)
`PinModel(cpu).states()` yields every T state's pins (`sync a_oe a d_oe d_out dbin wr_n wait_o
hlda inte`, with None where §4 says "not compared"), built from the instruction model's §6.2 cycle
list: every cycle type with its status byte, T4/T5 with the data bus not compared, DAD's two bus-idle
cycles (§6.2 Decision), XTHL's 5-state last stack write, the INTE pin changing at T4 of EI/DI and
reset at T1 of INTA, HLT → halt acknowledge → TWH, leaving halt by interrupt (status 2B), and the §5
reset pins. `python3 ref/pins8080.py selftest` checks, for **every documented opcode** (conditionals
both ways), that the states generated from §6.2 add up to p.4-15's count, plus the pins state by state
for NOP, MVI M, PUSH, POP, OUT, IN, DAD, EI, DI, HLT and an interrupt out of halt.
READY wait states: `PinModel(cpu, ready=f)` with READY sampled in T2 and each TW (§4/§7), TW pins
per read/write type, not in I3/HLTA/T4/T5. Not yet: HOLD/HLDA, and INT arriving mid-instruction.

## Acceptance test 4 (spec §9 numbering): independent emulator
Renamed from "acceptance test 3" after spec v1 (#5); log folders were renamed to `logs/acc4-*`, and
the files inside keep their original names and contents (they print `acc3:`), since they are evidence. (feasibility checked 2026-11-15)
**Candidate: MAME's 8080 core** (`src/devices/cpu/i8085/i8085.cpp`, BSD-3-Clause, Juergen Buchmueller
and hap; it implements the 8080, 8080A and 8085). MAME is fetched at test time with the 4004's
`fetch_mame.sh` method (Ubuntu `mame` 0.264, no root) and never committed (rule 9).

Machine: **`intel02`** (Intellect-02, `src/mame/ussr/intellect02.cpp`, BSD-3). It needs **no ROM
images at all**: the program is a cartridge (`-cart prog.bin`) mapped at 0000–1FFF, RAM at
F000–F3FF, I/O = one 8255 at ports F4–F7, and no interrupt source. So our own random program is
the cartridge, and no third-party ROM is involved.

Checked on the lab VM: `mame intel02 -cart prog.bin` with a headless debugger trace
(`QT_QPA_PLATFORM=offscreen`, `-debugger qt`, `trace … {tracelog …}`) logs the state before each
instruction. Symbols that work: `a`, `f`, `af`, `bc`, `hl`, `sp` (and `pc`). A 10-instruction test
program (LXI SP; LXI B; MVI A,0F; ADI 1; DAA; STA/LDA F000; JMP) traced as expected.

For the comparison the harness has to model the machine, as acceptance 3 did for the 4004's
Busicom board. Measured in MAME with probe programs (traces in my scratch dir, 2026-11-15):
- cartridge ROM 0000–1FFF, read-only (writes there are dropped);
- RAM F000–F3FF, starts all 0, **not mirrored** (reads of F400, F800, FC00, E000 and 7000 return 0
  after F000 = 5A);
- **unmapped reads return 00** (so code that runs off the cartridge executes NOPs), and unmapped
  writes are dropped;
- the 8255 at ports F4–F7 (the random programs leave IN out; OUT doesn't change CPU state).
The preamble's `LXI SP` points into RAM (e.g. F400). `ref8080.CPU` will take memory/I/O
callbacks for that. Flags are compared on S, Z, AC, P, CY only (MAME's internal F doesn't keep
bit 1 = 1).

**Runner:** `tests/random/acc4/run.py` (MAME from `tests/random/acc4/fetch_mame.sh`). Evidence
`logs/acc4-20261115T093724Z/`: 40 programs × 3,000 instructions, **all agree**. MAME independently agrees with three of
the spec's rules: ANA's OR-of-bit-3 AC, the DCR AC *Decision* and DAA keeping CY (mutants of each
caught by 26, 34 and 3 programs of 40, see `notes.txt`). Generator: preamble at 0040 behind a JMP,
RST vectors hold RET, 32 cartridge return addresses seeded on the stack, register pairs mostly point
into the cartridge, the cartridge ends with a JMP back into the code, and no undocumented/IN/HLT/RST 0
byte anywhere. **241 of 244** documented opcodes execute as cartridge code (≥ 18 times each); the
missing three are the excluded HLT, RST 0 and IN, which the selftest covers. **Known weakness** (`notes.txt`): a median of 136 distinct cartridge addresses per
program, and 49% of traced instructions are NOP slides after wild jumps. Earlier runs in
`logs/acc4-*` are superseded.
