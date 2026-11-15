// Ada: 8080 register file: B C D E H L, W Z (temporaries), SP, PC and the 16-bit ops.
// Ports and codes: docs/blocks.md (v1.1) sections 2 and 2a. reset clears everything (PC is required by spec section 5; the rest is allowed).
// An 8-bit write (we) and a pair_op may happen in the same cycle; control never aims them at the same register.
module i8080_regs (
    input  wire        clk,
    input  wire        reset,
    input  wire [3:0]  rd_sel,
    input  wire [3:0]  wr_sel,
    input  wire        we,
    input  wire [7:0]  wdata,
    output reg  [7:0]  rdata,
    input  wire [3:0]  pair_op,
    input  wire [1:0]  rp_sel,
    output reg         carry16,
    input  wire [2:0]  addr_sel,
    output reg  [15:0] addr,
    output wire [15:0] pc,
    output wire [15:0] sp,
    output wire [15:0] hl
);
    reg [7:0]  r_b, r_c, r_d, r_e, r_h, r_l, r_w, r_z;
    reg [15:0] r_sp, r_pc;

    assign pc = r_pc;
    assign sp = r_sp;
    assign hl = {r_h, r_l};

    wire [15:0] bc = {r_b, r_c};
    wire [15:0] de = {r_d, r_e};
    wire [15:0] wz = {r_w, r_z};

    // selected pair for pair_op 4, 5, 12
    reg [15:0] rp;
    always @* begin
        case (rp_sel)
            2'd0: rp = bc;
            2'd1: rp = de;
            2'd2: rp = hl;
            default: rp = r_sp;
        endcase
    end

    always @* begin
        case (rd_sel)
            4'd0: rdata = r_b;
            4'd1: rdata = r_c;
            4'd2: rdata = r_d;
            4'd3: rdata = r_e;
            4'd4: rdata = r_h;
            4'd5: rdata = r_l;
            4'd6: rdata = r_w;
            4'd7: rdata = r_z;
            4'd8: rdata = r_sp[15:8];
            4'd9: rdata = r_sp[7:0];
            4'd10: rdata = r_pc[15:8];
            4'd11: rdata = r_pc[7:0];
            default: rdata = 8'd0;
        endcase
    end

    always @* begin
        case (addr_sel)
            3'd0: addr = r_pc;
            3'd1: addr = r_sp;
            3'd2: addr = hl;
            3'd3: addr = bc;
            3'd4: addr = de;
            3'd5: addr = wz;
            3'd6: addr = {r_z, r_z};
            default: addr = 16'd0;
        endcase
    end

    wire [16:0] dad_sum = {1'b0, hl} + {1'b0, rp};
    wire [15:0] rp_inc  = rp + 16'd1;
    wire [15:0] rp_dec  = rp - 16'd1;

    task set_rp(input [1:0] sel, input [15:0] v);
        begin
            case (sel)
                2'd0: {r_b, r_c} <= v;
                2'd1: {r_d, r_e} <= v;
                2'd2: {r_h, r_l} <= v;
                default: r_sp <= v;
            endcase
        end
    endtask

    always @(posedge clk) begin
        if (reset) begin
            r_b <= 8'd0; r_c <= 8'd0; r_d <= 8'd0; r_e <= 8'd0;
            r_h <= 8'd0; r_l <= 8'd0; r_w <= 8'd0; r_z <= 8'd0;
            r_sp <= 16'd0; r_pc <= 16'd0;
            carry16 <= 1'b0;
        end else begin
            if (we) begin
                case (wr_sel)
                    4'd0: r_b <= wdata;
                    4'd1: r_c <= wdata;
                    4'd2: r_d <= wdata;
                    4'd3: r_e <= wdata;
                    4'd4: r_h <= wdata;
                    4'd5: r_l <= wdata;
                    4'd6: r_w <= wdata;
                    4'd7: r_z <= wdata;
                    4'd8: r_sp[15:8] <= wdata;
                    4'd9: r_sp[7:0]  <= wdata;
                    4'd10: r_pc[15:8] <= wdata;
                    4'd11: r_pc[7:0]  <= wdata;
                    default: ;
                endcase
            end
            case (pair_op)
                4'd1:  r_pc <= r_pc + 16'd1;
                4'd2:  r_sp <= r_sp + 16'd1;
                4'd3:  r_sp <= r_sp - 16'd1;
                4'd4:  set_rp(rp_sel, rp_inc);
                4'd5:  set_rp(rp_sel, rp_dec);
                4'd6:  {r_w, r_z} <= wz + 16'd1;
                4'd7:  r_pc <= wz;
                4'd8:  r_pc <= hl;
                4'd9:  r_sp <= hl;
                4'd10: begin {r_d, r_e} <= hl; {r_h, r_l} <= de; end
                4'd11: {r_h, r_l} <= wz;
                4'd12: begin {r_h, r_l} <= dad_sum[15:0]; carry16 <= dad_sum[16]; end
                default: ;
            endcase
        end
    end
endmodule
