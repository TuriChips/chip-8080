// Ada: 8080 accumulator and flags. Ports and op table: docs/blocks.md (v1.1) sections 2 and 3. Flag rules: spec section 6.
// Flags F = S Z 0 AC 0 P 1 CY. Update priority per clock edge: pop_f, else f_we flag update, then cy_load overrides CY.
module i8080_alu (
    input  wire       clk,
    input  wire       reset,
    input  wire       a_we,
    input  wire       f_we,
    input  wire       cy_load,
    input  wire       cy_val,
    input  wire [4:0] op,
    input  wire [7:0] b,
    input  wire       pop_f,
    output wire [7:0] a_out,
    output wire [7:0] f_out,
    output wire [4:0] flags,        // {S, Z, AC, P, CY}
    output wire [7:0] result
);
    reg [7:0] a;
    reg       s, z, ac, p, cy;

    assign a_out = a;
    assign flags = {s, z, ac, p, cy};
    assign f_out = {s, z, 1'b0, ac, 1'b0, p, 1'b1, cy};

    // ---- combinational: result and the flags this op would produce
    reg [7:0] res;
    reg       n_ac, n_cy;
    reg       upd_szp, upd_ac, upd_cy;      // which flags the op changes when f_we = 1
    reg       wr_a;                         // the op may write A (a_we still needed)
    reg [8:0] t;
    reg [7:0] t2;
    reg [7:0] bn;

    always @* begin
        res = a; n_ac = ac; n_cy = cy;
        upd_szp = 1'b0; upd_ac = 1'b0; upd_cy = 1'b0; wr_a = 1'b1;
        t = 9'd0; t2 = 8'd0; bn = ~b;
        case (op)
            5'd0, 5'd1: begin                                   // ADD, ADC
                t = {1'b0, a} + {1'b0, b} + {8'd0, (op == 5'd1) & cy};
                res = t[7:0];
                n_ac = ({1'b0, a[3:0]} + {1'b0, b[3:0]} + {4'd0, (op == 5'd1) & cy}) > 5'd15;
                n_cy = t[8];
                upd_szp = 1'b1; upd_ac = 1'b1; upd_cy = 1'b1;
            end
            5'd2, 5'd3, 5'd7: begin                             // SUB, SBB, CMP: A + ~b + (NOT borrow)
                t = {1'b0, a} + {1'b0, bn} + {8'd0, ~((op == 5'd3) & cy)};
                res = t[7:0];
                n_ac = ({1'b0, a[3:0]} + {1'b0, bn[3:0]} + {4'd0, ~((op == 5'd3) & cy)}) > 5'd15;
                n_cy = ~t[8];
                upd_szp = 1'b1; upd_ac = 1'b1; upd_cy = 1'b1;
                if (op == 5'd7) wr_a = 1'b0;                    // CMP never writes A
            end
            5'd4: begin                                         // ANA: AC = bit 3 of A OR bit 3 of operand
                res = a & b; n_ac = a[3] | b[3]; n_cy = 1'b0;
                upd_szp = 1'b1; upd_ac = 1'b1; upd_cy = 1'b1;
            end
            5'd5: begin                                         // XRA
                res = a ^ b; n_ac = 1'b0; n_cy = 1'b0;
                upd_szp = 1'b1; upd_ac = 1'b1; upd_cy = 1'b1;
            end
            5'd6: begin                                         // ORA
                res = a | b; n_ac = 1'b0; n_cy = 1'b0;
                upd_szp = 1'b1; upd_ac = 1'b1; upd_cy = 1'b1;
            end
            5'd8: begin                                         // INR: b + 1, CY unchanged
                res = b + 8'd1; n_ac = (b[3:0] == 4'hF);
                upd_szp = 1'b1; upd_ac = 1'b1;
            end
            5'd9: begin                                         // DCR: b + FF, AC = carry out of bit 3 (low nibble != 0)
                res = b - 8'd1; n_ac = (b[3:0] != 4'h0);
                upd_szp = 1'b1; upd_ac = 1'b1;
            end
            5'd10: begin res = {a[6:0], a[7]}; n_cy = a[7]; upd_cy = 1'b1; end   // RLC
            5'd11: begin res = {a[0], a[7:1]}; n_cy = a[0]; upd_cy = 1'b1; end   // RRC
            5'd12: begin res = {a[6:0], cy};   n_cy = a[7]; upd_cy = 1'b1; end   // RAL
            5'd13: begin res = {cy, a[7:1]};   n_cy = a[0]; upd_cy = 1'b1; end   // RAR
            5'd14: begin                                        // DAA (spec section 6, incl. chip-8080#26)
                if (a[3:0] > 4'd9 || ac) begin
                    t = {1'b0, a} + 9'd6;
                    n_ac = ({1'b0, a[3:0]} + 5'd6) > 5'd15;
                end else begin
                    t = {1'b0, a};
                    n_ac = 1'b0;
                end
                if (t[8] || t[7:4] > 4'd9 || cy) begin
                    t2 = t[7:0] + 8'h60;
                    res = t2;
                    n_cy = 1'b1;                                // CY_in OR carry of step 1 or 2; set whenever step 2 fires
                end else begin
                    res = t[7:0];
                    n_cy = cy | t[8];
                end
                upd_szp = 1'b1; upd_ac = 1'b1; upd_cy = 1'b1;
            end
            5'd15: begin res = ~a; end                          // CMA, no flags
            5'd16: begin res = a; n_cy = 1'b1; upd_cy = 1'b1; end   // STC
            5'd17: begin res = a; n_cy = ~cy;  upd_cy = 1'b1; end   // CMC
            5'd18: begin res = b; end                           // pass b to A, no flags
            default: begin wr_a = 1'b0; end
        endcase
    end

    assign result = res;

    always @(posedge clk) begin
        if (reset) begin
            a <= 8'd0;
            {s, z, ac, p, cy} <= 5'd0;
        end else begin
            if (a_we && wr_a) a <= res;
            if (pop_f) begin
                s <= b[7]; z <= b[6]; ac <= b[4]; p <= b[2]; cy <= b[0];
            end else begin
                if (f_we) begin
                    if (upd_szp) begin s <= res[7]; z <= (res == 8'd0); p <= ~^res; end
                    if (upd_ac)  ac <= n_ac;
                    if (upd_cy)  cy <= n_cy;
                end
                if (cy_load) cy <= cy_val;
            end
        end
    end
endmodule
