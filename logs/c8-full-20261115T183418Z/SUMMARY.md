# C8 full-scale run (spec §8 C8)

- 20 batches × 500 programs = **10,000 programs**, 6,000 states each, random READY/INT/HOLD (§7 rule),
  RTL vs `ref/pins8080.py`, every compared pin every state: **0 mismatching programs**.
- 74 programs stopped early: their random code wrote an undocumented byte into itself and reached it (§6).
- **Instructions per program: ~930 on average** (9.30 M fetches / 10,000), so slightly **under** the
  spec's "≥ 1,000 instructions". A rerun at 7,000 states meets it; until then this run is reported as
  10,000 × 6,000 states.
- Compared: 2,955,582 wait states, 20,921 interrupts accepted, 2,042,468 states with HLDA = 1,
  3,417 halts, 3,353 wake-ups by INT, 69,901 held states taken from halt.
- Coverage (union of the per-batch `*-coverage.log`): 243/244 opcodes (RST 0 excluded on purpose),
  all 48 condition-code × Jcc/Ccc/Rcc × taken/not-taken combinations, every §4 cycle type, wait states
  and HLDA in every bus-cycle type, including INTA taken from halt.
- Seeds: shard 0 = 100000 + 500·b, shard 1 = 200000 + 500·b, b = 0..9 (programs seed+p).
- History: a first attempt stopped at batch 1, where 3 programs exposed a model bug (EI; EI), fixed in #47.
  The RTL was right. This run uses the fixed model.
