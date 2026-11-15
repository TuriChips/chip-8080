// i8080: CPU top level. Pins per spec section 2. Wiring and the data muxes named in blocks.md and chip-8080#28.
// verilator lint_off DECLFILENAME
module i8080 (
    input  wire        clk,
    input  wire        reset,
    output wire [15:0] a,
    output wire        a_oe,
    input  wire [7:0]  d_in,
    output wire [7:0]  d_out,
    output wire        d_oe,
    output wire        sync,
    output wire        dbin,
    output wire        wr_n,
    input  wire        ready,
    output wire        wait_o,
    input  wire        hold,
    output wire        hlda,
    input  wire        int_req,
    output wire        inte
);
    wire [2:0] tstate, mcycle, cyc_states, d_out_sel, wdata_sel, addr_sel, rst_vec;
    wire       held, cyc_last, cyc_idle, cyc_wr, halt_req, int_go;
    wire [7:0] status, tmp, rdata, a_out, f_out, result, wdata;
    wire [4:0] flags, alu_op;
    wire       alu_a_we, alu_f_we, alu_cy_load, alu_pop_f, reg_we, carry16;
    wire [1:0] alu_src, rp_sel;
    wire [3:0] reg_rd_sel, reg_wr_sel, pair_op;
    wire [7:0] alu_b;
    wire [15:0] pc, sp, hl;
    wire        a_hold;
    wire [15:0] a_int;
    reg  [15:0] a_q;

    i8080_timing u_timing (
        .clk(clk), .reset(reset), .ready(ready), .hold(hold),
        .cyc_states(cyc_states), .cyc_last(cyc_last), .cyc_idle(cyc_idle), .cyc_wr(cyc_wr),
        .halt_req(halt_req), .int_go(int_go),
        .tstate(tstate), .mcycle(mcycle), .held(held), .sync(sync), .wait_o(wait_o), .hlda(hlda)
    );

    i8080_control u_control (
        .clk(clk), .reset(reset), .tstate(tstate), .mcycle(mcycle), .held(held),
        .d_in(d_in), .int_req(int_req), .flags(flags),
        .cyc_states(cyc_states), .cyc_last(cyc_last), .cyc_idle(cyc_idle), .cyc_wr(cyc_wr),
        .halt_req(halt_req), .int_go(int_go),
        .status(status), .addr_sel(addr_sel), .d_out_sel(d_out_sel),
        .d_oe(d_oe), .a_oe(a_oe), .dbin(dbin), .wr_n(wr_n), .inte(inte), .a_hold(a_hold),
        .alu_op(alu_op), .alu_a_we(alu_a_we), .alu_f_we(alu_f_we), .alu_cy_load(alu_cy_load),
        .alu_pop_f(alu_pop_f), .alu_src(alu_src),
        .reg_rd_sel(reg_rd_sel), .reg_wr_sel(reg_wr_sel), .reg_we(reg_we),
        .wdata_sel(wdata_sel), .rp_sel(rp_sel), .pair_op(pair_op), .tmp(tmp), .rst_vec(rst_vec)
    );

    // operand b of the ALU: 0 regs rdata, 1 d_in, 2 tmp, 3 A
    assign alu_b = (alu_src == 2'd0) ? rdata : (alu_src == 2'd1) ? d_in :
                   (alu_src == 2'd2) ? tmp : a_out;
    // write data of the register file: 0 d_in, 1 ALU result, 2 RST vector, 3 A, 4 zero
    assign wdata = (wdata_sel == 3'd0) ? d_in : (wdata_sel == 3'd1) ? result :
                   (wdata_sel == 3'd2) ? {2'b00, rst_vec, 3'b000} :
                   (wdata_sel == 3'd3) ? a_out : 8'h00;
    // data bus out (blocks.md v1.1): 0 status, 1 ALU result, 2 regs rdata, 4 A, 5 F, 6 tmp (3, 7 reserved)
    assign d_out = (d_out_sel == 3'd0) ? status : (d_out_sel == 3'd1) ? result :
                   (d_out_sel == 3'd2) ? rdata : (d_out_sel == 3'd4) ? a_out :
                   (d_out_sel == 3'd5) ? f_out : (d_out_sel == 3'd6) ? tmp : 8'h00;

    i8080_alu u_alu (
        .clk(clk), .reset(reset), .a_we(alu_a_we), .f_we(alu_f_we),
        .cy_load(alu_cy_load), .cy_val(carry16), .op(alu_op), .b(alu_b), .pop_f(alu_pop_f),
        .a_out(a_out), .f_out(f_out), .flags(flags), .result(result)
    );

    i8080_regs u_regs (
        .clk(clk), .reset(reset), .rd_sel(reg_rd_sel), .wr_sel(reg_wr_sel), .we(reg_we),
        .wdata(wdata), .rdata(rdata), .pair_op(pair_op), .rp_sel(rp_sel), .carry16(carry16),
        .addr_sel(addr_sel), .addr(a_int), .pc(pc), .sp(sp), .hl(hl)
    );
    // `a` of the previous state, shown in the hold-entry state of a 3-state write (the address has
    // already moved on by then: SP, PC and WZ change at the end of T3)
    always @(posedge clk) a_q <= a;
    assign a = a_hold ? a_q : a_int;
    // pc, sp, hl are debug outputs of regs (blocks.md); unused here.
    wire _unused = &{1'b0, pc, sp, hl};
endmodule
