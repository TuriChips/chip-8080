# synth/ (Leo)
Scripts only so far: `rtl/top.v` is not on main yet (chip-8080#13 waits for it). Only `i8080` is synthesized; `i8080_mem` and `i8080_system` are test fixtures.

- `synth/run.sh`: generic Yosys (gate counts, flops, longest path), after `memory_map`. Writes `synth/report.txt`.
- `synth/sky130/run.sh`: Yosys map to `sky130_fd_sc_hd` (typical corner), OpenROAD place and route, KLayout GDS and `layout.png`. Needs `source <toolchain>/scripts/eda-env.sh`. Default clock period 500 ns (the original's 2 MHz); `PERIOD_NS=...` overrides. Expect the routed run to take tens of minutes.
- `TOP=` and `SRC=` override the top module and sources. Skeleton check: with the 74181 and 4004 sources the same scripts reproduce the numbers in those repos (74181: 44 cells, 302 µm² placed, 1.014 ns, 0 router DRC violations; 4004 generic: 1278 cells, path 25).

Results come with the RTL.
