// verilator lint_off UNOPTFLAT
// (the bus feedback d_in -> control/ALU -> d_out -> bus is structural only: the muxes that close it
// are never selected in the same state. It exists only in this fixture, not in the synthesized i8080.)
// i8080_system: CPU + 64 KiB RAM + status latch (the 8228's job) + console ports + INTA -> RST n
// (spec section 7, blocks.md section 2). Test fixture, not synthesized.
//
// Bus: bus = d_oe ? d_out : (dbin ? what the system drives : 0). `bus_conflict` = the CPU and the
// system drive in the same state. The system drives only while DBIN = 1:
//   INTA (status D0)  RST n opcode, n = int_vector
//   INP  (status D6)  in_port_data
//   MEMR (status D7)  RAM byte at `a`
// Status is latched at SYNC (T1) and used from T2 on. OUT cycles don't write RAM (status D4).
//
// CP/M BDOS stub (spec 9), as 8080 code (Beru's suggestion on #31): reads of 0005h..001Ch return the
// routine below instead of RAM, so `CALL 5` with C = 2 prints E and C = 9 prints the '$'-string at DE,
// through OUT port 0 (bdos_char / bdos_strobe). It clobbers A, flags and DE, as the real BDOS may.
//   0005 MOV A,C; CPI 2; JZ 0011; CPI 9; JZ 0015; RET
//   0011 MOV A,E; OUT 0; RET
//   0015 LDAX D; CPI '$'; RZ; OUT 0; INX D; JMP 0015
// run_done goes high (and stays) at the first instruction fetch from 0000h after a fetch from 0100h or
// above, which is how an exerciser ends (spec 9). Nothing in the CPU is touched.
module i8080_system #(
    parameter INIT_FILE = ""
) (
    input  wire        clk,
    input  wire        reset,
    input  wire        ready,
    input  wire        hold,
    input  wire        int_req,
    input  wire [2:0]  int_vector,
    input  wire [7:0]  in_port_data,
    // CPU pins brought out for tests
    output wire [15:0] a,
    output wire        a_oe,
    output wire [7:0]  d_out,
    output wire        d_oe,
    output wire        sync,
    output wire        dbin,
    output wire        wr_n,
    output wire        wait_o,
    output wire        hlda,
    output wire        inte,
    output wire [7:0]  bus,
    output wire [7:0]  out_port,
    output wire        out_strobe,
    output wire        bus_conflict,
    output wire [7:0]  bdos_char,
    output wire        bdos_strobe,
    output reg         run_done
);
    wire [7:0] sys_d;
    wire [7:0] mem_rdata;

    i8080 cpu (
        .clk(clk), .reset(reset), .a(a), .a_oe(a_oe), .d_in(bus), .d_out(d_out), .d_oe(d_oe),
        .sync(sync), .dbin(dbin), .wr_n(wr_n), .ready(ready), .wait_o(wait_o),
        .hold(hold), .hlda(hlda), .int_req(int_req), .inte(inte)
    );

    // status latch: the status byte is on d_out while SYNC = 1
    // verilator lint_off UNUSEDSIGNAL
    reg [7:0] status_r;
    // verilator lint_on UNUSEDSIGNAL
    always @(posedge clk) begin
        if (reset) status_r <= 8'h00;
        else if (sync) status_r <= d_out;
    end
    wire st_inta = status_r[0];
    wire st_out  = status_r[4];
    wire st_inp  = status_r[6];
    wire st_memr = status_r[7];

    i8080_mem #(.INIT_FILE(INIT_FILE)) mem (
        .clk(clk), .addr(a), .rd(dbin & st_memr & ~st_inta),
        .wr(~wr_n & ~st_out), .wdata(d_out), .rdata(mem_rdata)
    );

    // BDOS stub bytes
    wire stub_hit = (a >= 16'h0005) && (a <= 16'h001E);
    reg [7:0] stub_byte;
    always @(*) begin
        case (a[4:0])
            5'h05: stub_byte = 8'h79; 5'h06: stub_byte = 8'hFE; 5'h07: stub_byte = 8'h02;
            5'h08: stub_byte = 8'hCA; 5'h09: stub_byte = 8'h11; 5'h0A: stub_byte = 8'h00;
            5'h0B: stub_byte = 8'hFE; 5'h0C: stub_byte = 8'h09; 5'h0D: stub_byte = 8'hCA;
            5'h0E: stub_byte = 8'h15; 5'h0F: stub_byte = 8'h00; 5'h10: stub_byte = 8'hC9;
            5'h11: stub_byte = 8'h7B; 5'h12: stub_byte = 8'hD3; 5'h13: stub_byte = 8'h00;
            5'h14: stub_byte = 8'hC9; 5'h15: stub_byte = 8'h1A; 5'h16: stub_byte = 8'hFE;
            5'h17: stub_byte = 8'h24; 5'h18: stub_byte = 8'hC8; 5'h19: stub_byte = 8'hD3;
            5'h1A: stub_byte = 8'h00; 5'h1B: stub_byte = 8'h13; 5'h1C: stub_byte = 8'hC3;
            5'h1D: stub_byte = 8'h15; default: stub_byte = 8'h00;
        endcase
    end
    wire [7:0] mem_or_stub = stub_hit ? stub_byte : mem_rdata;

    assign sys_d = !dbin ? 8'h00 :
                   st_inta ? {2'b11, int_vector, 3'b111} :
                   st_inp  ? in_port_data :
                   st_memr ? mem_or_stub : 8'h00;
    assign bus = d_oe ? d_out : sys_d;
    assign bus_conflict = d_oe & dbin;

    // OUT port: data captured while WR is low in an output cycle, strobe one clock after WR rises
    reg [7:0] out_r;
    reg       out_wr_d;
    reg       out_strobe_r;
    always @(posedge clk) begin
        if (reset) begin out_r <= 8'h00; out_wr_d <= 1'b0; out_strobe_r <= 1'b0; end
        else begin
            if (!wr_n && st_out) out_r <= d_out;
            out_strobe_r <= out_wr_d && wr_n;
            out_wr_d <= !wr_n && st_out;
        end
    end
    assign out_port   = out_r;
    assign out_strobe = out_strobe_r;

    // BDOS output = OUT port 0
    reg [7:0] out_pn;
    always @(posedge clk) begin
        if (reset) out_pn <= 8'h00;
        else if (!wr_n && st_out) out_pn <= a[7:0];
    end
    assign bdos_char   = out_r;
    assign bdos_strobe = out_strobe_r && (out_pn == 8'h00);

    // run_done: a fetch (M1, not INTA) from 0000h after a fetch from 0100h or above
    reg sync_d, started;
    wire fetch_t2 = sync_d && status_r[5] && !st_inta;
    always @(posedge clk) begin
        if (reset) begin sync_d <= 1'b0; started <= 1'b0; run_done <= 1'b0; end
        else begin
            sync_d <= sync;
            if (fetch_t2 && a >= 16'h0100) started <= 1'b1;
            if (fetch_t2 && a == 16'h0000 && started) run_done <= 1'b1;
        end
    end
endmodule
