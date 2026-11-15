// i8080_timing: T-state and M-cycle counters, WAIT/READY, HOLD/HLDA, halt (spec section 4).
// Ports per docs/blocks.md section 2, plus `cyc_wr` (see below).
//
// tstate: 1-5 = T1-T5, 6 = TW, 7 = TWH.  mcycle: 1-5 = M1-M5.
// Control contract (control must drive these from state it already has):
//   cyc_states  states in this M-cycle without TW (3, 4 or 5). Must be valid in T3 (for an M1 it
//               depends on the opcode on d_in at T3), and stay valid until the cycle's last state.
//   cyc_last    this M-cycle is the last of the instruction; the next cycle is M1.
//   cyc_idle    bus-idle cycle (DAD M2/M3): no SYNC, no READY sampling, 3 states.
//   cyc_wr      this cycle is a write/output cycle: HLDA rises the state after T3, not at T3.
//               (Not in blocks.md; needed by spec section 4 "Hold", flagged to Igris.)
//   halt_req    high from T3 of HLT's M1 until the halt is left; the CPU enters TWH after T2 of
//               the next cycle.
//   int_go      leave TWH: next state is T1 of M1 (the INTA cycle). Control gates it with INTE and
//               int_req, timing ignores it while held.
// While `held` = 1 the CPU still runs out the remaining internal states of the cycle (T4/T5),
// then freezes at T1 of the next cycle until HOLD falls. Control must not start that cycle's bus
// activity while `held` = 1.
module i8080_timing (
    input  wire       clk,
    input  wire       reset,
    input  wire       ready,
    input  wire       hold,
    input  wire [2:0] cyc_states,
    input  wire       cyc_last,
    input  wire       cyc_idle,
    input  wire       cyc_wr,
    input  wire       halt_req,
    input  wire       int_go,
    output wire [2:0] tstate,
    output wire [2:0] mcycle,
    output wire       held,
    output wire       sync,
    output wire       wait_o,
    output wire       hlda
);
    localparam [2:0] T0 = 3'd0, T1 = 3'd1, T2 = 3'd2, T3 = 3'd3, TW = 3'd6, TWH = 3'd7;

    reg [2:0] ts;
    reg [2:0] mc;
    reg       held_r;
    reg       frz;        // held and the cycle is finished: waiting for HOLD to fall
    reg       hold_pend;  // HOLD recognised in T2/TW of a write cycle; HLDA rises after T3

    // tstate 0 = reset state (before the first T1): control keeps the pins at their reset values
    wire last_state = (ts == cyc_states) && (ts >= T3) && (ts <= 3'd5);

    always @(posedge clk) begin
        if (reset) begin
            ts <= T0; mc <= 3'd1;
            held_r <= 1'b0; frz <= 1'b0; hold_pend <= 1'b0;
        end else if (frz) begin
            // Frozen at the end of a cycle (or in TWH): leave when HOLD falls.
            if (!hold) begin held_r <= 1'b0; frz <= 1'b0; end
        end else begin
            case (ts)
                T0: ts <= T1;           // first clock after reset: reset state -> T1
                T1: ts <= T2;
                T2: begin
                    if (cyc_idle) ts <= T3;
                    else if (halt_req) ts <= TWH;
                    else if (!ready) ts <= TW;
                    else begin
                        ts <= T3;
                        if (hold) begin
                            if (cyc_wr) hold_pend <= 1'b1; else held_r <= 1'b1;
                        end
                    end
                end
                TW: if (ready) begin
                    ts <= T3;
                    if (hold) begin
                        if (cyc_wr) hold_pend <= 1'b1; else held_r <= 1'b1;
                    end
                end
                TWH: begin
                    if (hold) begin held_r <= 1'b1; frz <= 1'b1; end
                    else if (int_go) begin ts <= T1; mc <= 3'd1; end
                end
                default: ;   // T3, T4, T5: below
            endcase

            if (ts >= T3 && ts <= 3'd5) begin
                // HOLD is sampled at the closing edge of every hold state (spec 4 Release): low means
                // the next state has hlda = 0 and the cycle carries on (rest of T4/T5, or the next T1).
                if (held_r && !hold) held_r <= 1'b0;
                // a write cycle's hold starts the state after T3: hlda rises there
                if (hold_pend && ts == T3) begin held_r <= 1'b1; hold_pend <= 1'b0; end
                if (last_state) begin
                    ts <= T1;
                    mc <= cyc_last ? 3'd1 : mc + 3'd1;
                    // still held at the end of the cycle: freeze at the next T1 until HOLD falls
                    if ((held_r && hold) || (hold_pend && ts == T3)) frz <= 1'b1;
                end else begin
                    ts <= ts + 3'd1;
                end
            end
        end
    end

    assign tstate = ts;
    assign mcycle = mc;
    assign held   = held_r & ~reset;
    assign hlda   = held_r & ~reset;
    assign sync   = (ts == T1) & ~cyc_idle & ~held_r & ~reset;
    assign wait_o = ((ts == TW) | (ts == TWH)) & ~held_r & ~reset;
endmodule
