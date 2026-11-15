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
// NOT here yet: the CP/M BDOS hooks (bdos_char / bdos_strobe, and the end-of-run on a fetch from
// 0000h). They need C, E and DE from the CPU, which the pin-level CPU doesn't expose; filed with
// Ada (chip-8080#28). The two outputs are tied to 0 until then.
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
    output wire        bdos_strobe
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

    assign sys_d = !dbin ? 8'h00 :
                   st_inta ? {2'b11, int_vector, 3'b111} :
                   st_inp  ? in_port_data :
                   st_memr ? mem_rdata : 8'h00;
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

    assign bdos_char   = 8'h00;
    assign bdos_strobe = 1'b0;
endmodule
