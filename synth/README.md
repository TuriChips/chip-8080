# synth/ (Leo)
Only `i8080` is synthesized. `i8080_mem` and `i8080_system` are test fixtures.

## Generic Yosys (`synth/run.sh` → `synth/report.txt`, `synth/logs/yosys.log`)
Gate set AND/NAND/OR/NOR/XOR/XNOR/ANDNOT/ORNOT/MUX.

| Item | Result |
|------|--------|
| Cells | 3183: 157 flops and 3026 gates |
| Longest path (flop to flop, `ltp -noff`) | 53 cells |
| Warnings, latches | none inferred, `check -assert` clean |

The real 8080 has about 4,500 transistors, so the counts are not comparable.

## sky130 layout (`synth/sky130/run.sh`, needs `source <toolchain>/scripts/eda-env.sh`)
Yosys maps `i8080` to `sky130_fd_sc_hd` at the typical corner (`lpflow_*`, probe and delay cells filtered out by `filter_lib.py`), OpenROAD places and routes (`flow.tcl`), KLayout writes `i8080.gds` and `layout.png`. Clock 500 ns (the original's 2 MHz). The routed run takes tens of minutes on the lab VM. Tools: OpenROAD 2.0_3175, KLayout 0.30.13, sky130A PDK 1.0.471 (pinned in the toolchain `VERSIONS`).

| Item | Result | Log |
|------|--------|-----|
| Cells after mapping | 2,340, of which 157 are `dfxtp_1` flops (generic gate set above: 3,183) | `sky130/logs/stat.txt` |
| Cell area | 15,939 µm² (16,596 µm² placed with 525 tap cells, 42% utilization) | `sky130/logs/stat.txt`, `sky130/logs/openroad.log` |
| Die | 209.6 × 209.6 µm | `sky130/logs/openroad.log` |
| Routed wire length, vias | 93,666 µm, 21,844 | `sky130/logs/openroad.log` |
| Longest path (typical corner, ideal clock) | 12.913 ns data arrival + 0.088 ns setup, 29 gates from `_4368_` to `_4488_`; slack 487.0 ns at the 500 ns clock (met) | `sky130/logs/openroad.log` |
| Fmax estimate | about 77 MHz (1 / 13.0 ns), 38 times the original's 2 MHz | derived from the line above |
| Router DRC violations | 0 (the router's own count, not a signoff) | `sky130/logs/openroad.log` |

Not done: timing closure, power, clock tree (ideal clock), signoff DRC and LVS, gate-level simulation of `i8080_sky130.v`. Power is met1 rails plus met4 straps, 525 tap cells, no fill or decap: fine for a picture and a first run, not for fabrication. `synth/sky130/layout.png` is the image for the website card.

## Scripts
`TOP=` and `SRC=` override the top module and sources, `PERIOD_NS=` the clock period. With the 74181 and 4004 sources the same scripts reproduce the numbers in those repos.
