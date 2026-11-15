# Coverage: spec behaviour -> test (Intel 8080)

Spec: docs/spec.md (v1). Status per row: **done** (test written and passing, log cited), **partial**, **todo**. Nothing is "passing" until a log in `logs/` says so. The RTL is not on main yet; the rows marked done ran on a local merge of PRs #31 and #32 (logs/rtl-run1/README.txt gives the heads).

## §6.1 opcode rows (C1, C5 for DAA)

| Encoding | Mnemonic | Test | Status |
|---|---|---|---|
| 01 DDD SSS (D, S ≠ 110) | MOV r1,r2 | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 01 110 SSS (S ≠ 110) | MOV M,r | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 01 DDD 110 (D ≠ 110) | MOV r,M | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 01 110 110 | HLT | tests/c4 `int_halt_k*` (halt entered, left through INTA, return address after HLT); its halt-acknowledge cycle and TWH pins: tests/c4 `int_halt_k*` pins | done (PASS, logs/rtl-run3, rtl-run4) |
| 00 DDD 110 b2 | MVI r / MVI M | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 DDD 100 | INR r / INR M | tests/c1 `inr_b, inr_m` | done (PASS, logs/rtl-run1) |
| 00 DDD 101 | DCR r / DCR M | tests/c1 `dcr_b, dcr_m` | done (PASS, logs/rtl-run1) |
| 10 000 SSS | ADD | tests/c1 `alu_add_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 001 SSS | ADC | tests/c1 `alu_adc_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 010 SSS | SUB | tests/c1 `alu_sub_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 011 SSS | SBB | tests/c1 `alu_sbb_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 100 SSS | ANA | tests/c1 `alu_ana_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 101 SSS | XRA | tests/c1 `alu_xra_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 110 SSS | ORA | tests/c1 `alu_ora_reg/mem` | done (PASS, logs/rtl-run1) |
| 10 111 SSS | CMP | tests/c1 `alu_cmp_reg/mem` | done (PASS, logs/rtl-run1) |
| 11 000 110 b2 | ADI | tests/c1 `alu_add_imm` | done (PASS, logs/rtl-run1) |
| 11 001 110 b2 | ACI | tests/c1 `alu_adc_imm` | done (PASS, logs/rtl-run1) |
| 11 010 110 b2 | SUI | tests/c1 `alu_sub_imm` | done (PASS, logs/rtl-run1) |
| 11 011 110 b2 | SBI | tests/c1 `alu_sbb_imm` | done (PASS, logs/rtl-run1) |
| 11 100 110 b2 | ANI | tests/c1 `alu_ana_imm` | done (PASS, logs/rtl-run1) |
| 11 101 110 b2 | XRI | tests/c1 `alu_xra_imm` | done (PASS, logs/rtl-run1) |
| 11 110 110 b2 | ORI | tests/c1 `alu_ora_imm` | done (PASS, logs/rtl-run1) |
| 11 111 110 b2 | CPI | tests/c1 `alu_cmp_imm` | done (PASS, logs/rtl-run1) |
| 00 000 111 | RLC | tests/c1 `rlc (rotate test)` | done (PASS, logs/rtl-run1) |
| 00 001 111 | RRC | tests/c1 `rrc (rotate test)` | done (PASS, logs/rtl-run1) |
| 00 010 111 | RAL | tests/c1 `ral (rotate test)` | done (PASS, logs/rtl-run1) |
| 00 011 111 | RAR | tests/c1 `rar (rotate test)` | done (PASS, logs/rtl-run1) |
| 11 000 011 b2 b3 | JMP | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 CCC 010 b2 b3 | Jcc | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 001 101 b2 b3 | CALL | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 CCC 100 b2 b3 | Ccc | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 001 001 | RET | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 CCC 000 | Rcc | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 NNN 111 | RST n | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 101 001 | PCHL | tests/c1 `branch` | done (PASS, logs/rtl-run2) |
| 11 011 011 b2 | IN | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 010 011 b2 | OUT | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 RP0 001 b2 b3 | LXI rp | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 RP0 101 | PUSH rp / PUSH PSW | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 RP0 001 | POP rp / POP PSW | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 110 010 b2 b3 | STA | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 111 010 b2 b3 | LDA | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 101 011 | XCHG | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 100 011 | XTHL | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 111 001 | SPHL | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 RP1 001 | DAD rp | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 0X0 010 (X: 0 = B, 1 = D) | STAX B / STAX D | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 0X1 010 | LDAX B / LDAX D | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 RP0 011 | INX rp | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 RP1 011 | DCX rp | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 101 111 | CMA | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 110 111 | STC | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 111 111 | CMC | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 100 111 | DAA | tests/c1 `daa` | done (PASS, logs/rtl-run1) |
| 00 100 010 b2 b3 | SHLD | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 00 101 010 b2 b3 | LHLD | tests/c1 `xfer_s1..3 (random)` | done (PASS, logs/rtl-run1) |
| 11 111 011 | EI | tests/c4 `int_inr_k*` (INT is accepted only after the instruction following EI), `int_halt_k*` | done (PASS, logs/rtl-run3) |
| 11 110 011 | DI | tests/c4 `int_di_k*` (INT ignored after EI; DI) | done (PASS, logs/rtl-run3) |
| 00 000 000 | NOP | tests/c1 `pins_s1..3 (every pin of NOP's fetch)` | done (PASS, logs/rtl-run2) |

## §8 behaviours

| ID | Behaviour | Test | Status |
|---|---|---|---|
| C1 | Every opcode: registers, memory and all five flags exactly per §6 | all 59 rows above, each with a test and a PASS log (ALU, DAA, INR/DCR, rotates, data transfer, pairs, stack, I/O, branches, EI/DI/HLT via C4) | done (PASS, logs/rtl-run1..3) |
| C2 | Pin timing per §4 for every machine-cycle type, incl. the status byte at SYNC | Types 1-7 (fetch with 4 and 5 states, memory and stack read/write incl. XTHL's 5-state write, input, output) and DAD's idle cycles: `tests/c2/gen_pins80.py` seeds 1-6 (12,626 to 16,612 states each), taken and not-taken Jcc/Ccc/Rcc, with `tb/tb_pins80.sv`; types 8-10 (INTA, halt acknowledge, INTA while halted): `tests/c4/gen_int_pins.py`; hold states: C3. All agree with Beru's pin model | done (PASS, logs/rtl-run2, rtl-run4, rtl-run7, rtl-run8) |
| C3 | READY / wait states, HOLD / HLDA at every legal point | `tests/c2/gen_pins80.py` seeds 3-6: READY wait states at every cycle type (seed 3); HOLD in a fifth of the bus cycles, held 1-6 hold states, with hold-entry row, Hold rows, release and the rest of T4/T5 (seed 4); HOLD in cycles that have wait states, recognised in the TW where READY is high (seed 5); HOLD taken from the halt state twice (seed 6). HOLD is not recognised in DAD's idle cycles (never raised there). `pins_s4` found two RTL bugs first (chip-8080#41, fixed). All agree with Beru's pin model (0 differences) | done (PASS, logs/rtl-run7, rtl-run8) |
| C4 | Interrupts: EI after the next instruction, RST via INTA, INT while halted | `tests/c4/gen_int.py` + `run.sh`: 206 runs with INT raised at 132 different states of an INR/NOP loop (EI's delay, every state of several instruction types), INT ignored without EI and after DI, INT during halt (40 states); the handler writes B and the pushed return address. Pins: `tests/c4/gen_int_pins.py` + `run_pins.sh`, 15 runs (INTA cycle with status 23 and 2B, a = PC not incremented, the two stack writes, INTE set at EI's T4 and cleared at INTA's T1, HLT's halt-acknowledge cycle and TWH states), PASS and equal to Beru's pin model | done (PASS, logs/rtl-run3, rtl-run4) |
| C5 | DAA and AC in every case | tests/c1 `daa`: all 256 A × CY × AC (1024 cases, flags included); the DAA ANA/ANI/INR/DCR AC cases are in the alu_ and inr/dcr programs | done (PASS, logs/rtl-run2; model agrees with Beru's ref, #26/#27) |
| C6 | Reset | `tests/c6/reset_mid` via `tests/c6/run.sh` (reset lands on 16 consecutive clocks mid-run, incl. mid-instruction; reset pins of spec §5; INTE cleared; first T1 after reset is a fetch from 0000; program restarts) and the pin cases `pins_r1_hold`, `pins_r2_wait`, `pins_r3_halt`, `pins_r4_halthold` (reset during a hold, a wait state, TWH, and a hold taken from the halt state: hlda and the other pins go to the §5 reset values, the run restarts) | done (PASS, logs/rtl-run2, rtl-run8) |
| C7 | No X/Z on any output; no bus conflict, with a mutant and the positive `bus_conflict` case | System level: `tb/tb_sys80.sv` + `tests/c7/run.sh` (5 programs on `i8080_system`, every output incl. bus, out_port, bdos_* checked each clock, bus_conflict must stay 0). `tests/c7/mutant.sh`: DBIN stuck 1 and d_oe stuck 1 make bus_conflict rise (the positive case, `+EXPECT_CONFLICT`), d_out Z when idle fails the X/Z check. CPU pins are also checked for X/Z in every `tb_prog80` / `tb_pins80` run | done (PASS, logs/rtl-run5) |
| C8 | Random programs vs the reference model | Beru | n/a |

## Open spec question

- chip-8080#26 (resolved by #27): the spec's DAA text gives a wrong decimal sum for A = FA..FF (step 1 carries out of bit 7). Decided in #27 (step 1's carry out of bit 7 sets CY); the DAA test now covers all 256 values of A.

## Cross-check against Beru's reference models (once ref/ is on main)

`tests/crosscheck_all.sh` runs my generated expectations through `ref/ref8080.py` and `ref/pins8080.py`. Run on PR #29's ref/: all 37 C1/C5 trace programs (about 70,000 trace entries) and all three C2 pin programs (40,172 states, one with wait states): 0 differences. The cross-check found two bugs in my own generators, both fixed: MOV r,M took the bus address after the destination L/H changed, and the M-form programs put their scratch byte at 4000 inside their own code.

## Tools

- `tests/mach80.py`: machine model giving each instruction's machine cycles (spec §6.2) and effects; its selftest checks 27 state counts against §6.1 (PASS). `tests/c2/gen_pins80.py` + `tb/tb_pins80.sv` + `tests/run_pins80.sh`: expected pins per clock state from §4's table.

- `tb/tb_prog80.sv` + `tests/run_prog80.sh`: trace testbench on the `i8080` pins (own memory and port model); the trace is every OUT's port and data. Compiles; not yet run against an RTL (no control RTL on main).
- `tests/model80.py`: expected-result model of the ALU group, DAA, INR/DCR and rotates written from spec §6 only, with a selftest of the spec's worked examples (PASS). `tests/c1/gen_alu.py`, `gen_misc.py` + `tests/c1/run_gen.sh` generate and run 24 ALU programs (8 ops × reg/M/imm × 392 cases), DAA (1000 cases), INR/DCR B and M (1024 cases each) and RLC/RRC/RAL/RAR (1024 each); `gen_xfer.py`: 3 seeded random programs (~2200 trace entries each) over MOV, MVI, LXI, LDA, STA, LHLD, SHLD, LDAX, STAX, XCHG, SPHL, XTHL, PUSH/POP (incl. PSW), DAD, INX, DCX, CMA, STC, CMC, IN, OUT with the whole state written out every 16 instructions; `gen_branch.py`: JMP, PCHL, CALL/RET (SP checked), Jcc/Ccc/Rcc for all 8 conditions × all 16 S/Z/P/CY combinations (taken and not), RST 1-7 (pushed return address checked) and RST 0. Rows ADD..CMP and ADI..CPI become done when a log says PASS.
- `tests/asm80.py`: assembler written from §6.1; `tests/asm80_selftest.py` checks that it produces exactly the 244 documented opcode bytes (PASS).
