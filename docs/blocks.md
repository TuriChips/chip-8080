# Blocks: Intel 8080 (Chip #2)

Owner: Igris (Architect) · Spec: `docs/spec.md` · Status: draft with spec v1 (chip-8080#1); normative once Sai signs off the spec PR.

All blocks are synchronous to the single rising-edge `clk` (one clock per T state, spec §1). `reset` is synchronous and active high (spec §5). Only the pins of `i8080` (spec §2) and of `i8080_system` are normative for tests. The internal ports below are the contract **between Zura and Ada**: tests don't bind to them, but neither designer changes one without a PR the other reviews.

## 1. Block list

| Block | File | Owner | State it holds |
|-------|------|-------|----------------|
| `i8080_timing` | rtl/control/i8080_timing.v | Zura (A) | T-state and M-cycle counters, wait / halt / hold state |
| `i8080_control` | rtl/control/i8080_control.v | Zura (A) | instruction register, INTE, interrupt latch, cycle plan for the current instruction (spec §6.2) |
| `i8080_alu` | rtl/datapath/i8080_alu.v | Ada (B) | A, flags F (S Z AC P CY), ACT/TMP latches |
| `i8080_regs` | rtl/datapath/i8080_regs.v | Ada (B) | B C D E H L, W Z, SP, PC; 16-bit incrementer/decrementer |
| `i8080` | rtl/top.v | Zura (A) | none (wiring only) |
| `i8080_mem` | rtl/datapath/i8080_mem.v | Ada (B) | 64 KiB RAM for tests (`$readmemh`) |
| `i8080_system` | rtl/control/i8080_system.v | Zura (A) | status latch (the 8228's job), INTA → RST n, CP/M BDOS stub hooks, bus resolution |

## 2. Ports

### `i8080_timing` (Zura)
| Port | Dir | Width | Meaning |
|------|-----|-------|---------|
| `clk`, `reset` | in | 1, 1 | |
| `ready`, `hold` | in | 1, 1 | Pins, sampled in T2 / TW per spec §4 |
| `cyc_states` | in | 3 | From control: how many states the current M-cycle has (3, 4 or 5) |
| `cyc_last` | in | 1 | From control: this M-cycle is the instruction's last |
| `cyc_idle` | in | 1 | From control: bus-idle M-cycle (DAD M2/M3, spec §6.2) |
| `halt_req` | in | 1 | From control: HLT executed; enter TWH after T2 of the next cycle |
| `int_go` | in | 1 | From control: leave halt via INTA |
| `tstate` | out | 3 | 1–5 = T1–T5; 6 = TW; 7 = TWH |
| `mcycle` | out | 3 | 1–5 = M1–M5 |
| `held` | out | 1 | In the hold state (drives `hlda`, floats buses) |
| `sync`, `wait_o`, `hlda` | out | 1 each | Pins, exactly per spec §4 |

### `i8080_control` (Zura)
| Port | Dir | Width | Meaning |
|------|-----|-------|---------|
| `clk`, `reset` | in | 1, 1 | |
| `tstate`, `mcycle`, `held` | in | 3, 3, 1 | From timing |
| `d_in` | in | 8 | Pin (opcode, operands, data, the INTA instruction) |
| `int_req` | in | 1 | Pin |
| `flags` | in | 5 | From ALU: {S, Z, AC, P, CY} for condition codes |
| `cyc_states`, `cyc_last`, `cyc_idle`, `halt_req`, `int_go` | out | 3, 1, 1, 1, 1 | To timing |
| `status` | out | 8 | Status byte for T1 (spec §4 table: A2, 82, 00, 86, 04, 42, 10, 23, 8A, 2B) |
| `addr_sel` | out | 3 | Which address goes on `a`: 0 PC, 1 SP, 2 HL, 3 BC, 4 DE, 5 WZ, 6 {Z, Z} (I/O port) |
| `d_out_sel` | out | 2 | 0 status, 1 ALU result / A, 2 register byte (`reg_rd`), 3 PC/WZ byte for pushes |
| `d_oe`, `a_oe`, `dbin`, `wr_n` | out | 1 each | Pins, per spec §4 |
| `inte` | out | 1 | Pin: INTE flip-flop, set/cleared at T4 of EI/DI (spec §6.1) |
| `alu_op` | out | 5 | To ALU (table in §3) |
| `alu_we`, `alu_src` | out | 1, 3 | Write A/F; operand source: 0 register (`reg_rd`), 1 d_in, 2 constant 1 (INR/DCR), 3 TMP |
| `reg_rd_sel`, `reg_wr_sel`, `reg_we` | out | 4, 4, 1 | 8-bit register file access (codes: B C D E H L W Z, plus SP/PC halves) |
| `pair_op` | out | 4 | 16-bit ops on regs: PC+1, SP±1, rp±1 (INX/DCX), WZ+1, PC←WZ, PC←HL, SP←HL, XCHG, DAD step |

### `i8080_alu` (Ada)
| Port | Dir | Width | Meaning |
|------|-----|-------|---------|
| `clk`, `reset` | in | 1, 1 | `reset` does **not** clear A or F (spec §5) |
| `we` | in | 1 | Store result in A (or only F for CMP/CPI, per `op`) |
| `op` | in | 5 | §3 |
| `b` | in | 8 | Operand |
| `pop_f` | in | 1 | POP PSW: load F from `b` (bits per spec §3) |
| `a_out` | out | 8 | Current A |
| `f_out` | out | 8 | F as pushed by PUSH PSW: `S Z 0 AC 0 P 1 CY` |
| `flags` | out | 5 | {S, Z, AC, P, CY} |
| `result` | out | 8 | Combinational result (for INR/DCR M, written back to memory) |

### `i8080_regs` (Ada)
| Port | Dir | Width | Meaning |
|------|-----|-------|---------|
| `clk`, `reset` | in | 1, 1 | `reset` clears PC only (spec §5) |
| `rd_sel`, `wr_sel`, `we` | in | 4, 4, 1 | 8-bit access |
| `wdata` | in | 8 | |
| `rdata` | out | 8 | |
| `pair_op` | in | 4 | From control |
| `addr_sel` | in | 3 | From control |
| `addr` | out | 16 | Value for the `a` pins |
| `pc`, `sp`, `hl` | out | 16 each | For debug and the reference-model comparison of C1 |

### `i8080` (Zura, rtl/top.v)
Ports exactly spec §2, in that order. Wiring only.

### `i8080_mem` (Ada)
Parameter `INIT_FILE` (`$readmemh`, 65,536 bytes). Ports: `clk`, `addr[15:0]`, `rd` (DBIN and MEMR), `wr` (WR low and not OUT), `wdata[7:0]`, `rdata[7:0]`. Unwritten bytes read as 00.

### `i8080_system` (Zura)
Ports: `clk`, `reset`, `ready`, `hold`, `int_req`, `int_vector[2:0]` (RST n for INTA, spec §7), the CPU pins brought out for tests, `out_port[7:0]` and `out_strobe` (OUT writes), `in_port_data[7:0]` (IN reads), `bus_conflict`, and `bdos_char[7:0]` + `bdos_strobe` (the spec §9 CP/M stub: on a fetch from 0005h it performs functions 2 and 9 and returns, and a fetch from 0000h after start ends the run).

## 3. ALU `op` encoding (Ada)
| `op` | Operation (spec §6) |
|------|---------------------|
| 0–7 | ADD ADC SUB SBB ANA XRA ORA CMP (the `10 xxx SSS` field) |
| 8, 9 | INR, DCR (CY unchanged; AC per spec §6) |
| 10–13 | RLC, RRC, RAL, RAR |
| 14 | DAA |
| 15, 16, 17 | CMA, STC, CMC |
| 18 | pass `b` to A (MOV A,…, LDA, LDAX, IN, POP A) |

## 4. Who does what first
1. **Ada:** `i8080_alu` and `i8080_regs` (no dependencies), then `i8080_mem`.
2. **Zura:** `i8080_timing`, then `i8080_control` and `i8080`, then `i8080_system`.
3. **Titus:** C1–C7 tests on the `i8080` and `i8080_system` pins, and `tests/coverage.md` per spec §8.
4. **Beru:** reference model and C8 (chip-8080#2), acceptance test 4.
5. **Leo:** synthesis of `i8080` (Yosys) and the sky130 layout, timing target set in the issue.
6. **Homer:** acceptance tests 1 and 3 (exerciser fetch and run, manual examples), demo, write-up.
7. **Tesla:** toolchain wiring (chip-8080#3), Verilator nightly for the full 8080EXM.

These become issues titled `<Name>: <task>` once Sai signs off the spec PR.
