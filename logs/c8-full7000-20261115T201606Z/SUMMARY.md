# C8 at the spec target (§8): >= 10,000 programs x >= 1,000 instructions

- programs 10000, states 7000 each, mismatching 0, stopped early 77
- instructions per program (fetches/programs): 1101
- compared: 3442236 TW, 22779 interrupts, 2384976 HLDA states, 3736 halts, 3668 wake-ups, 89333 held-from-halt
- opcodes never: ['C7']; condition combos missing in every batch: none
- Random READY/INT/HOLD per §7; every compared pin every state; RTL vs ref/pins8080.py (with the #47 EI;EI fix).
- Seeds: shard 0 = 100000 + 500*b, shard 1 = 200000 + 500*b, b = 0..9 (program p of a batch: seed + p).
- Mid-run resets: run_resets.py (logs/c8-resets-*); positive bus_conflict: conflict_check.py (logs/c8-conflict-*).
