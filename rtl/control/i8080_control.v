// i8080_control: instruction register, INTE, interrupt latch, cycle plan (spec sections 4, 6, 6.2).
// Ports per docs/blocks.md section 2 / 2a, plus the additions listed in chip-8080#28:
//   tmp[7:0]         TMP latch (d_in at T3 of a read) for INR/DCR M and MVI M write-back
//   alu_pop_f        POP PSW: load F from b
//   d_out_sel        3 bits (blocks.md v1.1): 0 status, 1 ALU result, 2 regs rdata, 4 ALU a_out, 5 ALU f_out, 6 tmp
//   wdata_sel        3 bits: 0 d_in, 1 ALU result, 2 {00,NNN,000}, 3 ALU a_out, 4 zero
//   alu_src          2 bits: 0 regs rdata, 1 d_in, 2 tmp, 3 ALU a_out
//   pair_op 13       PC <- {wdata, Z}, W <- wdata (JMP, taken Jcc, RET, taken Rcc)
// Schedule rules (so `a` stays stable through T4 as spec 4 requires):
//   PC+1 fires in the LAST state of every cycle that fetches through PC; F4 instructions do their
//   internal work at T3 (the opcode is live on d_in), F5 instructions at T4/T5.
//   The final SP+1 of RET/Rcc is deferred to T2 of the next M1 (invisible at the pins).
module i8080_control (
    input  wire        clk,
    input  wire        reset,
    input  wire [2:0]  tstate,
    input  wire [2:0]  mcycle,
    input  wire        held,
    input  wire [7:0]  d_in,
    input  wire        int_req,
    // verilator lint_off UNUSEDSIGNAL
    input  wire [4:0]  flags,          // {S, Z, AC, P, CY}; AC is not needed for conditions
    // verilator lint_on UNUSEDSIGNAL
    output wire [2:0]  cyc_states,
    output wire        cyc_last,
    output wire        cyc_idle,
    output wire        cyc_wr,
    output wire        halt_req,
    output wire        int_go,
    output reg  [7:0]  status,
    output reg  [2:0]  addr_sel,
    output reg  [2:0]  d_out_sel,
    output wire        d_oe,
    output wire        a_oe,
    output wire        dbin,
    output wire        wr_n,
    output wire        inte,
    output wire        a_hold,         // 3-state write held: show the previous cycle's address (hold-entry row)
    output reg  [4:0]  alu_op,
    output reg         alu_a_we,
    output reg         alu_f_we,
    output reg         alu_cy_load,
    output reg         alu_pop_f,
    output reg  [1:0]  alu_src,
    output reg  [3:0]  reg_rd_sel,
    output reg  [3:0]  reg_wr_sel,
    output reg         reg_we,
    output reg  [2:0]  wdata_sel,
    output reg  [1:0]  rp_sel,
    output reg  [3:0]  pair_op,
    output wire [7:0]  tmp,
    output wire [2:0]  rst_vec         // NNN of the current RST (wdata_sel 2)
);
    localparam [2:0] T1 = 3'd1, T2 = 3'd2, T3 = 3'd3, T4 = 3'd4, T5 = 3'd5, TW = 3'd6, TWH = 3'd7;
    localparam [3:0] K_F = 0, K_RD = 1, K_WR = 2, K_SR = 3, K_SW = 4, K_IN = 5, K_OUT = 6,
                     K_INTA = 7, K_HLTA = 8, K_IDLE = 9;
    // pair_op codes (blocks.md 2a)
    localparam [3:0] P_NONE = 0, P_PCINC = 1, P_SPINC = 2, P_SPDEC = 3, P_RPINC = 4, P_RPDEC = 5,
                     P_WZINC = 6, P_PCWZ = 7, P_PCHL = 8, P_SPHL = 9, P_XCHG = 10, P_HLWZ = 11,
                     P_DAD = 12, P_PCJMP = 13;
    // register codes (blocks.md 2a)
    localparam [3:0] R_L = 5, R_H = 4, R_W = 6, R_Z = 7, R_SPH = 8, R_SPL = 9, R_PCH = 10, R_PCL = 11;

    // ---------------- state ----------------
    reg [7:0] ir;
    reg       inte_r;
    reg       inta_cyc;     // the coming/current M1 is an interrupt-acknowledge cycle
    reg       inta_halt;    // ... entered from the halt state (status 2B)
    reg       halt_r;       // HLT executed, waiting in / heading for TWH
    reg       def_sp;       // deferred SP+1 (RET/Rcc)
    reg       held_d;       // held, one state later
    reg [7:0] tmp_r;
    assign tmp  = tmp_r;
    assign rst_vec = ir[5:3];   // valid from T4 of M1 (ir latched at the T3 edge)
    assign inte = inte_r & ~reset;

    // ---------------- decode ----------------
    wire        live = (mcycle == 3'd1) && (tstate == T3);
    wire [7:0]  op   = live ? d_in : ir;
    wire [1:0]  g    = op[7:6];
    wire [2:0]  dd   = op[5:3];
    wire [2:0]  ss   = op[2:0];
    wire [1:0]  rp   = op[5:4];

    wire is_hlt  = (op == 8'h76);
    wire mov_rr  = (g == 2'b01) && !is_hlt && (dd != 3'd6) && (ss != 3'd6);
    wire mov_rm  = (g == 2'b01) && (dd != 3'd6) && (ss == 3'd6);
    wire mov_mr  = (g == 2'b01) && (dd == 3'd6) && (ss != 3'd6);
    wire alu_rr  = (g == 2'b10) && (ss != 3'd6);
    wire alu_mm  = (g == 2'b10) && (ss == 3'd6);
    wire alu_imm = (g == 2'b11) && (ss == 3'd6);
    wire is_lxi  = (g == 2'b00) && (ss == 3'd1) && !dd[0];
    wire is_dad  = (g == 2'b00) && (ss == 3'd1) &&  dd[0];
    wire is_stax = (g == 2'b00) && (ss == 3'd2) && !dd[2] && !dd[0];
    wire is_ldax = (g == 2'b00) && (ss == 3'd2) && !dd[2] &&  dd[0];
    wire is_shld = (g == 2'b00) && (op[5:0] == 6'h22);
    wire is_lhld = (g == 2'b00) && (op[5:0] == 6'h2A);
    wire is_sta  = (g == 2'b00) && (op[5:0] == 6'h32);
    wire is_lda  = (g == 2'b00) && (op[5:0] == 6'h3A);
    wire is_inx  = (g == 2'b00) && (ss == 3'd3) && !dd[0];
    wire is_dcx  = (g == 2'b00) && (ss == 3'd3) &&  dd[0];
    wire is_inr  = (g == 2'b00) && (ss == 3'd4);
    wire is_dcr  = (g == 2'b00) && (ss == 3'd5);
    wire is_mvi  = (g == 2'b00) && (ss == 3'd6);
    wire is_acc  = (g == 2'b00) && (ss == 3'd7);          // RLC RRC RAL RAR DAA CMA STC CMC
    wire is_rcc  = (g == 2'b11) && (ss == 3'd0);
    wire is_pop  = (g == 2'b11) && (ss == 3'd1) && !dd[0];
    wire is_ret  = (op == 8'hC9);
    wire is_pchl = (op == 8'hE9);
    wire is_sphl = (op == 8'hF9);
    wire is_jcc  = (g == 2'b11) && (ss == 3'd2);
    wire is_jmp  = (op == 8'hC3);
    wire is_out  = (op == 8'hD3);
    wire is_in   = (op == 8'hDB);
    wire is_xthl = (op == 8'hE3);
    wire is_xchg = (op == 8'hEB);
    wire is_di   = (op == 8'hF3);
    wire is_ei   = (op == 8'hFB);
    wire is_ccc  = (g == 2'b11) && (ss == 3'd4);
    wire is_push = (g == 2'b11) && (ss == 3'd5) && !dd[0];
    wire is_call = (op == 8'hCD);
    wire is_rst  = (g == 2'b11) && (ss == 3'd7);
    wire psw     = (rp == 2'b11);

    // condition code (spec 6.1): CCC = NZ Z NC C PO PE P M
    reg  flag_sel;
    always @(*) begin
        case (dd[2:1])
            2'b00: flag_sel = flags[3];   // Z
            2'b01: flag_sel = flags[0];   // CY
            2'b10: flag_sel = flags[1];   // P
            default: flag_sel = flags[4]; // S
        endcase
    end
    wire cond = dd[0] ? flag_sel : ~flag_sel;

    wire [3:0] rhi = (rp == 2'b11) ? R_SPH : {1'b0, rp, 1'b0};
    wire [3:0] rlo = (rp == 2'b11) ? R_SPL : {1'b0, rp, 1'b1};

    // ---------------- cycle plan ----------------
    reg [2:0] ncyc;
    always @(*) begin
        ncyc = 3'd1;
        if (is_hlt) ncyc = 3'd2;
        else if (mov_rm || mov_mr || alu_mm || alu_imm || is_stax || is_ldax) ncyc = 3'd2;
        else if (is_mvi) ncyc = (dd == 3'd6) ? 3'd3 : 3'd2;
        else if ((is_inr || is_dcr) && dd == 3'd6) ncyc = 3'd3;
        else if (is_lxi || is_dad || is_pop || is_ret || is_jcc || is_jmp || is_in || is_out ||
                 is_push || is_rst) ncyc = 3'd3;
        else if (is_lda || is_sta) ncyc = 3'd4;
        else if (is_lhld || is_shld || is_xthl || is_call) ncyc = 3'd5;
        else if (is_rcc) ncyc = cond ? 3'd3 : 3'd1;
        else if (is_ccc) ncyc = cond ? 3'd5 : 3'd3;
    end
    wire inta_cyc_now = inta_cyc && (mcycle == 3'd1);
    wire f5 = mov_rr || ((is_inr || is_dcr) && dd != 3'd6) || is_inx || is_dcx || is_call ||
              is_ccc || is_rst || is_rcc || is_push || is_pchl || is_sphl || inta_cyc_now;

    reg [3:0] kind;
    reg [2:0] nst;
    reg       uses_pc;
    always @(*) begin
        kind = K_F; nst = 3'd3; uses_pc = 1'b0; addr_sel = 3'd0;
        case (mcycle)
            3'd1: begin
                kind = inta_cyc ? K_INTA : K_F;
                nst = f5 ? 3'd5 : 3'd4;
                uses_pc = !inta_cyc;
            end
            3'd2: begin
                if (is_hlt) begin kind = K_HLTA; end
                else if (is_dad) begin kind = K_IDLE; end
                else if (mov_rm || alu_mm || (is_inr || is_dcr)) begin kind = K_RD; addr_sel = 3'd2; end
                else if (mov_mr) begin kind = K_WR; addr_sel = 3'd2; end
                else if (is_ldax) begin kind = K_RD; addr_sel = dd[1] ? 3'd4 : 3'd3; end
                else if (is_stax) begin kind = K_WR; addr_sel = dd[1] ? 3'd4 : 3'd3; end
                else if (is_pop || is_ret || is_rcc || is_xthl) begin kind = K_SR; addr_sel = 3'd1; end
                else if (is_push) begin kind = K_SW; addr_sel = 3'd1; end
                else if (is_rst) begin kind = K_SW; addr_sel = 3'd1; end
                else begin kind = K_RD; uses_pc = 1'b1; end   // operand byte through PC
            end
            3'd3: begin
                if (is_dad) begin kind = K_IDLE; end
                else if (is_inr || is_dcr) begin kind = K_WR; addr_sel = 3'd2; end
                else if (is_mvi) begin kind = K_WR; addr_sel = 3'd2; end
                else if (is_pop || is_ret || is_rcc || is_xthl) begin kind = K_SR; addr_sel = 3'd1; end
                else if (is_push || is_rst) begin kind = K_SW; addr_sel = 3'd1; end
                else if (is_in) begin kind = K_IN; addr_sel = 3'd6; end
                else if (is_out) begin kind = K_OUT; addr_sel = 3'd6; end
                else begin kind = K_RD; uses_pc = 1'b1; end
            end
            3'd4: begin
                if (is_lda) begin kind = K_RD; addr_sel = 3'd5; end
                else if (is_sta) begin kind = K_WR; addr_sel = 3'd5; end
                else if (is_lhld) begin kind = K_RD; addr_sel = 3'd5; end
                else if (is_shld) begin kind = K_WR; addr_sel = 3'd5; end
                else begin kind = K_SW; addr_sel = 3'd1; end    // CALL, XTHL
            end
            default: begin   // M5: LHLD, SHLD, XTHL, CALL
                if (is_lhld) begin kind = K_RD; addr_sel = 3'd5; end
                else if (is_shld) begin kind = K_WR; addr_sel = 3'd5; end
                else begin kind = K_SW; addr_sel = 3'd1; end
                if (is_xthl) nst = 3'd5;
            end
        endcase
        // CALL / Ccc / RST stack writes in M4/M5 (M2/M3 for RST) use SP; XTHL's M3 reads SP (+1 done)
        if (mcycle == 3'd3 && (is_jmp || is_jcc || is_lxi || is_call || is_ccc || is_lda || is_sta ||
                               is_lhld || is_shld)) begin kind = K_RD; uses_pc = 1'b1; addr_sel = 3'd0; end
        if (mcycle == 3'd3 && is_xthl) begin kind = K_SR; addr_sel = 3'd1; end
        if (mcycle == 3'd2 && (is_in || is_out || is_jmp || is_jcc || is_lxi || is_call || is_ccc ||
                               is_lda || is_sta || is_lhld || is_shld || is_mvi || alu_imm)) begin
            kind = K_RD; uses_pc = 1'b1; addr_sel = 3'd0;
        end
    end

    assign cyc_states = nst;
    assign cyc_last   = (mcycle >= ncyc) && !is_hlt;
    assign cyc_idle   = (kind == K_IDLE);
    assign cyc_wr     = (kind == K_WR) || (kind == K_SW) || (kind == K_OUT);
    assign halt_req   = halt_r || (live && is_hlt) || (mcycle == 3'd1 && tstate > T3 && is_hlt);

    wire st_last = (tstate == nst) && (tstate >= T3) && (tstate <= T5);
    wire ex_t    = (nst == 3'd5) ? (tstate == T4) : (tstate == T3);   // M1 internal-work state
    wire m1      = (mcycle == 3'd1);
    wire is_rd_k = (kind == K_F) || (kind == K_RD) || (kind == K_SR) || (kind == K_IN) || (kind == K_INTA);

    // ---------------- pins ----------------
    always @(*) begin
        case (kind)
            K_F:    status = 8'hA2;
            K_RD:   status = 8'h82;
            K_WR:   status = 8'h00;
            K_SR:   status = 8'h86;
            K_SW:   status = 8'h04;
            K_IN:   status = 8'h42;
            K_OUT:  status = 8'h10;
            K_INTA: status = inta_halt ? 8'h2B : 8'h23;
            K_HLTA: status = 8'h8A;
            default: status = 8'h00;
        endcase
    end

    // Hold row from the state AFTER hlda rises (spec 4); the state where it rises shows its normal row,
    // except the first held state of a 3-state write, which is the hold-entry row (a_oe = 1, a held, d_oe = 0).
    wire pin_hold   = held && held_d;
    wire hold_entry = held && !held_d && (tstate == T1);
    assign a_hold   = hold_entry;
    wire in_twh   = (tstate == TWH);
    wire idle     = (kind == K_IDLE);
    reg  doe, aoe, dbn, wrn;
    always @(*) begin
        aoe = 1'b1; doe = 1'b0; dbn = 1'b0; wrn = 1'b1;
        case (tstate)
            T1: doe = !idle;
            T2: begin
                if (kind == K_HLTA) begin end
                else if (is_rd_k) dbn = 1'b1;
                else if (cyc_wr) doe = 1'b1;
            end
            TW: begin
                if (is_rd_k) dbn = 1'b1;
                else if (cyc_wr) begin doe = 1'b1; wrn = 1'b0; end
            end
            T3: begin
                if (is_rd_k) dbn = 1'b1;
                else if (cyc_wr) begin doe = 1'b1; wrn = 1'b0; end
            end
            default: ;
        endcase
        if (hold_entry) begin aoe = 1'b1; doe = 1'b0; dbn = 1'b0; wrn = 1'b1; end
        if (in_twh || pin_hold) begin aoe = 1'b0; doe = 1'b0; dbn = 1'b0; wrn = 1'b1; end
        if (reset || tstate == 3'd0) begin aoe = 1'b0; doe = 1'b0; dbn = 1'b0; wrn = 1'b1; end
    end
    assign a_oe = aoe;
    assign d_oe = doe;
    assign dbin = dbn;
    assign wr_n = wrn;

    // interrupt handling
    wire single_cycle_last = (mcycle >= ncyc);
    wire blk_ei_di = m1 && (is_ei || is_di);
    wire accept = inte_r && int_req && !held && !blk_ei_di && st_last && single_cycle_last && !is_hlt;
    assign int_go = (tstate == TWH) && inte_r && int_req && !held;

    // ---------------- strobes ----------------
    reg [3:0] sp_o;
    always @(*) begin
        alu_op = 5'd0; alu_a_we = 1'b0; alu_f_we = 1'b0; alu_cy_load = 1'b0; alu_pop_f = 1'b0;
        alu_src = 2'd0; reg_rd_sel = {1'b0, ss}; reg_wr_sel = 4'd0; reg_we = 1'b0; wdata_sel = 3'd0;
        rp_sel = rp; sp_o = P_NONE; d_out_sel = 3'd0;
        if (cyc_wr && (tstate != T1)) d_out_sel = 3'd4;     // default write data: A
        if (reset) begin end
        else begin
        // deferred SP+1 (RET / Rcc)
        if (m1 && tstate == T2 && def_sp && !held) sp_o = P_SPINC;

        case (mcycle)
        3'd1: begin
            // ---- internal work of the first cycle ----
            if (ex_t) begin
                if (mov_rr) begin
                    if (dd != 3'd7 && ss != 3'd7) begin
                        alu_op = 5'd18; reg_rd_sel = {1'b0, ss}; wdata_sel = 3'd1;
                        reg_wr_sel = {1'b0, dd}; reg_we = 1'b1;
                    end else if (dd != 3'd7) begin
                        wdata_sel = 3'd3; reg_wr_sel = {1'b0, dd}; reg_we = 1'b1;
                    end else if (ss != 3'd7) begin
                        alu_op = 5'd18; reg_rd_sel = {1'b0, ss}; alu_a_we = 1'b1;
                    end
                end
                if (alu_rr) begin
                    alu_op = {2'b00, dd}; alu_a_we = (dd != 3'd7); alu_f_we = 1'b1;
                    if (ss == 3'd7) alu_src = 2'd3;
                end
                if (is_inr || is_dcr) begin
                    if (dd != 3'd6) begin
                        alu_op = is_inr ? 5'd8 : 5'd9; alu_f_we = 1'b1;
                        reg_rd_sel = {1'b0, dd};
                        if (dd == 3'd7) begin alu_src = 2'd3; alu_a_we = 1'b1; end
                        else begin wdata_sel = 3'd1; reg_wr_sel = {1'b0, dd}; reg_we = 1'b1; end
                    end
                end
                if (is_acc) begin
                    case (dd)
                        3'd0: begin alu_op = 5'd10; alu_a_we = 1'b1; alu_f_we = 1'b1; end
                        3'd1: begin alu_op = 5'd11; alu_a_we = 1'b1; alu_f_we = 1'b1; end
                        3'd2: begin alu_op = 5'd12; alu_a_we = 1'b1; alu_f_we = 1'b1; end
                        3'd3: begin alu_op = 5'd13; alu_a_we = 1'b1; alu_f_we = 1'b1; end
                        3'd4: begin alu_op = 5'd14; alu_a_we = 1'b1; alu_f_we = 1'b1; end
                        3'd5: begin alu_op = 5'd15; alu_a_we = 1'b1; end
                        3'd6: begin alu_op = 5'd16; alu_f_we = 1'b1; end
                        default: begin alu_op = 5'd17; alu_f_we = 1'b1; end
                    endcase
                end
                if (is_inx) begin sp_o = P_RPINC; end
                if (is_dcx) begin sp_o = P_RPDEC; end
                if (is_xchg) sp_o = P_XCHG;
                if (is_sphl) sp_o = P_SPHL;
                if (is_push || is_call || (is_ccc && cond)) sp_o = P_SPDEC;
                if (is_rst) begin
                    // Z = 8*NNN at T4; SP-1 at T4. (W = 0 at T5, below)
                    sp_o = P_SPDEC; wdata_sel = 3'd2; reg_wr_sel = R_Z; reg_we = 1'b1;
                end
            end
            if (is_pchl && tstate == T5) sp_o = P_PCHL;
            if (is_rst && tstate == T5) begin wdata_sel = 3'd4; reg_wr_sel = R_W; reg_we = 1'b1; end
        end
        3'd2: begin
            if (tstate == T3) begin
                if (mov_rm || is_mvi || is_ldax) begin
                    // data from d_in into DDD (A for LDAX)
                    if (is_ldax || dd == 3'd7) begin alu_op = 5'd18; alu_src = 2'd1; alu_a_we = 1'b1; end
                    else if (dd != 3'd6) begin wdata_sel = 3'd0; reg_wr_sel = {1'b0, dd}; reg_we = 1'b1; end
                    else begin /* MVI M: only tmp */ end
                end
                if (alu_mm || alu_imm) begin
                    alu_op = {2'b00, dd}; alu_src = 2'd1; alu_a_we = (dd != 3'd7); alu_f_we = 1'b1;
                end
                if ((is_inr || is_dcr) && dd == 3'd6) begin
                    alu_op = is_inr ? 5'd8 : 5'd9; alu_src = 2'd1; alu_f_we = 1'b1;
                end
                if (is_lxi) begin reg_wr_sel = rlo; reg_we = 1'b1; wdata_sel = 3'd0; end
                if (is_lda || is_sta || is_lhld || is_shld || is_jmp || is_jcc || is_call || is_ccc ||
                    is_in || is_out) begin reg_wr_sel = R_Z; reg_we = 1'b1; wdata_sel = 3'd0; end
                if (is_pop || is_ret || is_rcc || is_xthl) begin
                    if (is_pop) begin
                        if (psw) begin alu_pop_f = 1'b1; alu_src = 2'd1; end
                        else begin reg_wr_sel = rlo; reg_we = 1'b1; wdata_sel = 3'd0; end
                    end else begin reg_wr_sel = R_Z; reg_we = 1'b1; wdata_sel = 3'd0; end
                    sp_o = P_SPINC;
                end
                if (is_push || is_rst) begin sp_o = P_SPDEC; end
                if (is_dad) begin sp_o = P_DAD; rp_sel = rp; end
            end
            // write data for this cycle
            if (mov_mr) begin
                if (ss == 3'd7) d_out_sel = 3'd4; else begin d_out_sel = 3'd2; reg_rd_sel = {1'b0, ss}; end
            end
            if (is_push) begin
                if (psw) d_out_sel = 3'd4; else begin d_out_sel = 3'd2; reg_rd_sel = rhi; end
            end
            if (is_call || is_ccc || is_rst) begin d_out_sel = 3'd2; reg_rd_sel = R_PCH; end
        end
        3'd3: begin
            if (tstate == T3) begin
                if (is_lxi) begin reg_wr_sel = rhi; reg_we = 1'b1; wdata_sel = 3'd0; end
                if (is_lda || is_sta || is_lhld || is_shld || is_call || is_ccc) begin
                    reg_wr_sel = R_W; reg_we = 1'b1; wdata_sel = 3'd0;
                end
                if (is_jmp || (is_jcc && cond)) begin sp_o = P_PCJMP; wdata_sel = 3'd0; end
                if (is_pop) begin
                    if (psw) begin alu_op = 5'd18; alu_src = 2'd1; alu_a_we = 1'b1; end
                    else begin reg_wr_sel = rhi; reg_we = 1'b1; wdata_sel = 3'd0; end
                    sp_o = P_SPINC;
                end
                if (is_ret || is_rcc) begin sp_o = P_PCJMP; wdata_sel = 3'd0; end
                if (is_xthl) begin reg_wr_sel = R_W; reg_we = 1'b1; wdata_sel = 3'd0; end
                if (is_in) begin alu_op = 5'd18; alu_src = 2'd1; alu_a_we = 1'b1; end
                if (is_dad) alu_cy_load = 1'b1;
                if (is_mvi) begin end
                if (is_push) sp_o = P_NONE;
                if (is_rst) sp_o = P_PCWZ;
            end
            if (is_inr || is_dcr) begin
                d_out_sel = 3'd1; alu_src = 2'd2; alu_op = is_inr ? 5'd8 : 5'd9;
            end
            if (is_mvi) d_out_sel = 3'd6;
            if (is_push) begin
                if (psw) d_out_sel = 3'd5; else begin d_out_sel = 3'd2; reg_rd_sel = rlo; end
            end
            if (is_rst) begin d_out_sel = 3'd2; reg_rd_sel = R_PCL; end
        end
        3'd4: begin
            if (is_lda && tstate == T3) begin alu_op = 5'd18; alu_src = 2'd1; alu_a_we = 1'b1; end
            if (is_lhld && tstate == T3) begin reg_wr_sel = R_L; reg_we = 1'b1; wdata_sel = 3'd0; sp_o = P_WZINC; end
            if (is_shld) begin d_out_sel = 3'd2; reg_rd_sel = R_L; if (tstate == T3) sp_o = P_WZINC; end
            if (is_call || is_ccc) begin
                d_out_sel = 3'd2; reg_rd_sel = R_PCH; if (tstate == T3) sp_o = P_SPDEC;
            end
            if (is_xthl) begin d_out_sel = 3'd2; reg_rd_sel = R_H; if (tstate == T3) sp_o = P_SPDEC; end
        end
        default: begin   // M5
            if (is_lhld && tstate == T3) begin reg_wr_sel = R_H; reg_we = 1'b1; wdata_sel = 3'd0; end
            if (is_shld) begin d_out_sel = 3'd2; reg_rd_sel = R_H; end
            if (is_call || is_ccc) begin
                d_out_sel = 3'd2; reg_rd_sel = R_PCL; if (tstate == T3) sp_o = P_PCWZ;
            end
            if (is_xthl) begin d_out_sel = 3'd2; reg_rd_sel = R_L; if (tstate == T4) sp_o = P_HLWZ; end
        end
        endcase
        if (mcycle == 3'd4 && is_sta) d_out_sel = 3'd4;
        if (mcycle == 3'd2 && is_stax) d_out_sel = 3'd4;
        if (mcycle == 3'd3 && is_out) d_out_sel = 3'd4;
        if (mcycle == 3'd5 && is_shld) begin d_out_sel = 3'd2; reg_rd_sel = R_H; end
        if (tstate == T1) d_out_sel = 3'd0;
        end
        // PC+1 in the last state of every PC-fetching cycle unless another pair op fires then
        pair_op = sp_o;
        if (sp_o == P_NONE && uses_pc && st_last && !reset && !(m1 && is_pchl)) pair_op = P_PCINC;
    end

    // ---------------- state update ----------------
    always @(posedge clk) begin
        if (reset) begin
            ir <= 8'd0; inte_r <= 1'b0; inta_cyc <= 1'b0; inta_halt <= 1'b0;
            halt_r <= 1'b0; def_sp <= 1'b0; held_d <= 1'b0; tmp_r <= 8'd0;
        end else begin
            held_d <= held;
            if (live) ir <= d_in;
            // TMP: latch d_in at T3 of a read cycle
            if (tstate == T3 && is_rd_k && !m1) tmp_r <= d_in;
            // HLT
            if (live && is_hlt) halt_r <= 1'b1;
            // INTE: EI/DI at T3 edge (visible in T4), cleared on accept
            if (m1 && tstate == T3 && is_ei) inte_r <= 1'b1;
            if (m1 && tstate == T3 && is_di) inte_r <= 1'b0;
            // deferred SP+1 for RET/Rcc: set in the last cycle's last state
            if (m1 == 1'b0 && st_last && (is_ret || is_rcc) && mcycle == 3'd3) def_sp <= 1'b1;
            if (m1 && tstate == T2 && def_sp && !held) def_sp <= 1'b0;
            // interrupt accepted at the end of an instruction
            if (accept) begin inta_cyc <= 1'b1; inta_halt <= 1'b0; inte_r <= 1'b0; end
            // interrupt accepted from halt
            if (int_go) begin inta_cyc <= 1'b1; inta_halt <= 1'b1; halt_r <= 1'b0; inte_r <= 1'b0; end
            // the INTA cycle flag lasts until the end of its M1
            if (m1 && inta_cyc && st_last) begin inta_cyc <= 1'b0; inta_halt <= 1'b0; end
        end
    end
endmodule
