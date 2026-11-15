# ref/: reference model for the 8080 (owner: Beru)

`ref8080.py`: the 8080 at **instruction level**, written from `docs/spec.md` §3 and §6 only.
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

Not yet: the pin-level model (waits for §4 v1), random tests (`tests/random/`), the acceptance-3
emulator choice.

## Acceptance test 3: independent emulator (feasibility checked 2026-11-15)
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
Busicom board: ROM read-only at 0000–1FFF, RAM only at F000–F3FF (so the preamble's SP points
there), the unmapped read value, and the 8255 at F4–F7. `ref8080.CPU` will take memory/I/O
callbacks for that. Flags are compared on S, Z, AC, P, CY only (MAME's internal F doesn't keep
bit 1 = 1).
