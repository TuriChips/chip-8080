# Random-test coverage of the 8080 spec (owner: Beru)

What the random tests exercise (spec §8: counts, and an empty Gaps section). Directed tests are
Titus's, tracked in `tests/coverage.md`. Measured with `tests/random/c8/coverage.py`, which replays
the C8 programs through `ref/pins8080.py` with the inputs the testbench recorded. The RTL's agreement
on those same states is C8's log.

**Measured on:** the C8 run in `logs/c8-halt-20261115T*/` (50 programs × 20,000 states, seed 100,
random READY/INT/HOLD, 0 mismatches against the RTL).

| Spec | Behaviour | Count | Note |
|------|-----------|-------|------|
| §6.1 | Documented opcodes executed | 243 / 244 | RST 0 (C7) excluded on purpose, see below |
| §4 | Cycle types | fetch F4 130,503 · F5 28,574 · mem read 67,042 · mem write 284 · stack read 1,880 · stack write 7,339 (+ XTHL's 5-state write 9) · input 118 · output 11,090 · DAD idle 346 · INTA 59 · halt ack 9 | every type seen |
| §6.1 | Condition codes × Jcc/Ccc/Rcc × taken / not taken | 45 / 48 | gaps below |
| §4/§7 | Wait states (TW) by cycle | fetch 32,021 · mem read 13,560 · mem write 49 · stack read 387 · stack write 1,483 · input 26 · output 2,290 · INTA 12 · INTA (halted) 2 | none in DAD idle or halt ack (spec: READY isn't sampled there) |
| §4/§7 | HLDA rising, by cycle | fetch 6,379 · mem read 2,764 · mem write 16 · stack read 73 · stack write 326 · input 6 · output 456 · INTA 2 | |
| §4 | Halt: halts / wake-ups by INT / held states from halt | 9 / 9 / 9 (20 programs at seed 1: 24 / 24 / 14) | |
| §2/§4 | Interrupts accepted | 59, after 41 distinct opcodes | |
| §8 | Positive `bus_conflict` case | not yet | needs a mutant CPU that drives during DBIN (see #31) |

## Excluded on purpose (not gaps)
- The 12 undocumented bytes (spec §6: not tested). Self-modifying code that writes one and reaches
  it stops that program's comparison (counted as "stopped" in the C8 log).
- RST 0 (C7): restarts the program, so random code would loop back to the preamble. Covered by the
  model selftest and by Titus's directed tests.

## Gaps
1. **Depth per program:** a median of 202 distinct instruction addresses per program, against ~2,500
   instructions executed. Most of a 20,000-state run is loops, so rare opcodes are thin (SHLD ran
   once; several ran 5–7 times). Next: the spec's target shape, ≥ 10,000 programs × 1,000
   instructions, which gets breadth from many short programs. This table will be re-measured on it.
2. **Condition codes:** Jcc NZ not taken, Ccc Z taken, Jcc P not taken were never seen.
3. **HOLD during an INTA cycle taken from halt** never occurred.
4. **Positive `bus_conflict` case:** not yet in C8.
5. **Mid-run reset** (§5, part of the C8 target): not yet in C8.
6. **Gate-level variant** (§8): waits for Leo's synthesized netlist (#22).
