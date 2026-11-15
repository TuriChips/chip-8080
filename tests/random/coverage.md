# Random-test coverage of the 8080 spec (owner: Beru)

What the random tests exercise (spec §8: counts, and an empty Gaps section). Directed tests are
Titus's, tracked in `tests/coverage.md`. Measured with `tests/random/c8/coverage.py`, which replays
the C8 programs through `ref/pins8080.py` with the inputs the testbench recorded. The RTL's agreement
on those same states is C8's log.

**Measured on:** the full-scale C8 run `logs/c8-full-20261115T183418Z/` (10,000 programs × 6,000 states, ≈ 930 instructions
each, random READY/INT/HOLD, 0 mismatches against the RTL). The table is the union of its per-batch
coverage logs.

| Spec | Behaviour | Count | Note |
|------|-----------|-------|------|
| §6.1 | Documented opcodes executed | 243 / 244 | RST 0 (C7) excluded on purpose |
| §4 | Cycle types | F4 7,581,013 · F5 1,718,501 · mem read 3,409,062 · mem write 71,677 · stack read 260,646 · stack write 1,347,975 (+ XTHL 5-state 4,689) · input 5,207 · output 314,373 · DAD idle 40,102 · INTA 20,921 · halt ack 3,411 | every type |
| §6.1 | Condition codes × Jcc/Ccc/Rcc × taken / not taken | 48 / 48 | |
| §4/§7 | Wait states by cycle | fetch 1,857,214 · mem read 681,247 · mem write 14,648 · stack read 52,552 · stack write 269,728 · input 1,031 · output 63,102 · INTA 3,316 · INTA (halted) 702 | none in DAD idle or halt ack (READY not sampled there) |
| §4/§7 | HLDA rising, by cycle | fetch 371,497 · mem read 136,150 · mem write 2,888 · stack read 10,363 · stack write 54,129 · input 176 · output 12,579 · INTA 737 · INTA (halted) 117 | every bus-cycle type |
| §4 | Halts / wake-ups by INT / held states from halt | 3,417 / 3,353 / 69,901 | |
| §2/§4 | Interrupts accepted | 20,921 | |
| §5/§8 | Mid-run resets (`run_resets.py`) | 135 resets, 114 mid-instruction, 45 unfinished writes rolled back; RAM compared at every reset and at the end; 0 mismatches (20 × 20,000 states, `logs/c8-resets-20261115T185949Z/`) | mutants: reset not forcing WR high 7/20, no rollback 5/20 |
| §8 | Positive `bus_conflict` case (`c8/conflict_check.py`) | faulty CPU driving during DBIN: flag = 1 in 1,248 states, all with `d_oe` = `dbin` = 1; clean RTL: 0 | flag tied to 0 makes the check FAIL |

## Excluded on purpose (not gaps)
- The 12 undocumented bytes (spec §6: not tested). Self-modifying code that writes one and reaches
  it stops that program's comparison (counted as "stopped" in the C8 log).
- RST 0 (C7): restarts the program, so random code would loop back to the preamble. Covered by the
  model selftest and by Titus's directed tests.

## Gaps
1. **Instructions per program:** ≈ 930 on average at 6,000 states, just under the spec's 1,000. Next:
   rerun at 7,000 states.
2. **Gate-level variant** (§8): waits for Leo's synthesized netlist (#22).

Closed: mid-run reset (`run_resets.py`), positive `bus_conflict` (`c8/conflict_check.py`). Closed by the full-scale run: per-program depth (now many short programs), the three missing
condition-code combinations, and HOLD during an INTA taken from halt.
