# Coverage: spec behaviour -> test (Intel 8080)

Spec: docs/spec.md (v1). Status per row: **done** (test written and passing, log cited), **partial**, **todo**. Nothing is "passing" until a log in `logs/` says so. The RTL is not on main yet, so nothing has run against a design.

## §6.1 opcode rows (C1, C5 for DAA)

| Encoding | Mnemonic | Test | Status |
|---|---|---|---|
| 01 DDD SSS (D, S ≠ 110) | MOV r1,r2 | | todo |
| 01 110 SSS (S ≠ 110) | MOV M,r | | todo |
| 01 DDD 110 (D ≠ 110) | MOV r,M | | todo |
| 01 110 110 | HLT | | todo |
| 00 DDD 110 b2 | MVI r / MVI M | | todo |
| 00 DDD 100 | INR r / INR M | | todo |
| 00 DDD 101 | DCR r / DCR M | | todo |
| 10 000 SSS | ADD | | todo |
| 10 001 SSS | ADC | | todo |
| 10 010 SSS | SUB | | todo |
| 10 011 SSS | SBB | | todo |
| 10 100 SSS | ANA | | todo |
| 10 101 SSS | XRA | | todo |
| 10 110 SSS | ORA | | todo |
| 10 111 SSS | CMP | | todo |
| 11 000 110 b2 | ADI | | todo |
| 11 001 110 b2 | ACI | | todo |
| 11 010 110 b2 | SUI | | todo |
| 11 011 110 b2 | SBI | | todo |
| 11 100 110 b2 | ANI | | todo |
| 11 101 110 b2 | XRI | | todo |
| 11 110 110 b2 | ORI | | todo |
| 11 111 110 b2 | CPI | | todo |
| 00 000 111 | RLC | | todo |
| 00 001 111 | RRC | | todo |
| 00 010 111 | RAL | | todo |
| 00 011 111 | RAR | | todo |
| 11 000 011 b2 b3 | JMP | | todo |
| 11 CCC 010 b2 b3 | Jcc | | todo |
| 11 001 101 b2 b3 | CALL | | todo |
| 11 CCC 100 b2 b3 | Ccc | | todo |
| 11 001 001 | RET | | todo |
| 11 CCC 000 | Rcc | | todo |
| 11 NNN 111 | RST n | | todo |
| 11 101 001 | PCHL | | todo |
| 11 011 011 b2 | IN | | todo |
| 11 010 011 b2 | OUT | | todo |
| 00 RP0 001 b2 b3 | LXI rp | | todo |
| 11 RP0 101 | PUSH rp / PUSH PSW | | todo |
| 11 RP0 001 | POP rp / POP PSW | | todo |
| 00 110 010 b2 b3 | STA | | todo |
| 00 111 010 b2 b3 | LDA | | todo |
| 11 101 011 | XCHG | | todo |
| 11 100 011 | XTHL | | todo |
| 11 111 001 | SPHL | | todo |
| 00 RP1 001 | DAD rp | | todo |
| 00 0X0 010 (X: 0 = B, 1 = D) | STAX B / STAX D | | todo |
| 00 0X1 010 | LDAX B / LDAX D | | todo |
| 00 RP0 011 | INX rp | | todo |
| 00 RP1 011 | DCX rp | | todo |
| 00 101 111 | CMA | | todo |
| 00 110 111 | STC | | todo |
| 00 111 111 | CMC | | todo |
| 00 100 111 | DAA | | todo |
| 00 100 010 b2 b3 | SHLD | | todo |
| 00 101 010 b2 b3 | LHLD | | todo |
| 11 111 011 | EI | | todo |
| 11 110 011 | DI | | todo |
| 00 000 000 | NOP | | todo |

## §8 behaviours

| ID | Behaviour | Test | Status |
|---|---|---|---|
| C1 | Every opcode: registers, memory and all five flags exactly per §6 | (the rows above) | todo |
| C2 | Pin timing per §4 for every machine-cycle type, incl. the status byte at SYNC | | todo |
| C3 | READY / wait states, HOLD / HLDA at every legal point | | todo |
| C4 | Interrupts: EI after the next instruction, RST via INTA, INT while halted | | todo |
| C5 | DAA and AC in every case | | todo |
| C6 | Reset | | todo |
| C7 | No X/Z on any output; no bus conflict, with a mutant and the positive `bus_conflict` case (two drivers on) | | todo |
| C8 | Random programs vs the reference model | Beru | n/a |

## Open spec question

- chip-8080#26: the spec's DAA text gives a wrong decimal sum for A = FA..FF (step 1 carries out of bit 7). The DAA test skips those 6 values until decided; DAA stays **partial** until then.

## Tools

- `tb/tb_prog80.sv` + `tests/run_prog80.sh`: trace testbench on the `i8080` pins (own memory and port model); the trace is every OUT's port and data. Compiles; not yet run against an RTL (no control RTL on main).
- `tests/model80.py`: expected-result model of the ALU group, DAA, INR/DCR and rotates written from spec §6 only, with a selftest of the spec's worked examples (PASS). `tests/c1/gen_alu.py`, `gen_misc.py` + `tests/c1/run_gen.sh` generate and run 24 ALU programs (8 ops × reg/M/imm × 392 cases), DAA (1000 cases), INR/DCR B and M (1024 cases each) and RLC/RRC/RAL/RAR (1024 each); `gen_xfer.py`: 3 seeded random programs (~2200 trace entries each) over MOV, MVI, LXI, LDA, STA, LHLD, SHLD, LDAX, STAX, XCHG, SPHL, XTHL, PUSH/POP (incl. PSW), DAD, INX, DCX, CMA, STC, CMC, IN, OUT with the whole state written out every 16 instructions. Rows ADD..CMP and ADI..CPI become done when a log says PASS.
- `tests/asm80.py`: assembler written from §6.1; `tests/asm80_selftest.py` checks that it produces exactly the 244 documented opcode bytes (PASS).
