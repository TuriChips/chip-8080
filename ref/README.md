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
