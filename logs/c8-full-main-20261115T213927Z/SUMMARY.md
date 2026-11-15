# C8 full scale on main itself

- programs 10000, states 7000 each, mismatching 0, stopped early 77
- instructions per program (fetches/programs): 1101
- compared: 3442236 TW, 22883 INTA, 2384976 HLDA states, 3736 halts, 3668 wake-ups, 89333 held-from-halt
- opcodes never: ['C7']; condition combos missing in every batch: none
- RTL, model and harness all from main fddf108 (no local merge). Seeds as in logs/c8-full7000-*.
