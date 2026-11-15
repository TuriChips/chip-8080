// System-level testbench on i8080_system (C7, spec 7/8): runs a program from a $readmemh image and checks, on every clock from the
// first T1: no X/Z on any output of the system (CPU pins, bus, out_port, out_strobe, bus_conflict, bdos_*), and bus_conflict = 0.
// Also compares the OUT data seen on out_port at each out_strobe with the low bytes of an expected trace (like tb_prog80).
// Defines: -DMEMFILE="path". Plusargs: +EXP=<file of PPDD words> +N=<entries> +CLOCKS=<limit>
//   +EXPECT_CONFLICT=1: mutant mode. The run PASSes only if bus_conflict was seen high at least once (the positive case: a check
//   that has never seen a 1 isn't proven, spec 8); the trace and X/Z checks are off.
`timescale 1ns/1ps
module tb_sys80;
  reg clk = 0, reset = 1, ready = 1, hold = 0, int_req = 0;
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte, out_strobe, bus_conflict, bdos_strobe, run_done;
  wire [7:0] d_out, bus, out_port, bdos_char;
  i8080_system #(.INIT_FILE(`MEMFILE)) dut (.clk(clk), .reset(reset), .ready(ready), .hold(hold), .int_req(int_req), .int_vector(3'd1),
    .in_port_data(8'h00), .a(a), .a_oe(a_oe), .d_out(d_out), .d_oe(d_oe), .sync(sync), .dbin(dbin), .wr_n(wr_n), .wait_o(wait_o),
    .hlda(hlda), .inte(inte), .bus(bus), .out_port(out_port), .out_strobe(out_strobe), .bus_conflict(bus_conflict),
    .bdos_char(bdos_char), .bdos_strobe(bdos_strobe), .run_done(run_done));
  always #5 clk = ~clk;
  reg [15:0] exp [0:65535]; integer n = 0, got = 0, errors = 0, cyc = 0, limit = 0, conflicts = 0, expect_conflict = 0, i; reg seen = 0; string expf;
  initial begin
    if (!$value$plusargs("CLOCKS=%d", limit)) limit = 3000000;
    if (!$value$plusargs("EXPECT_CONFLICT=%d", expect_conflict)) expect_conflict = 0;
    if (!expect_conflict) begin
      if (!$value$plusargs("EXP=%s", expf)) begin $display("FAIL no +EXP"); $finish; end
      if (!$value$plusargs("N=%d", n) || n == 0) begin $display("FAIL empty or missing +N"); $finish; end
      $readmemh(expf, exp);
    end
    repeat (5) @(posedge clk); @(negedge clk); reset = 0;
  end
  always @(negedge clk) if (!reset) begin
    cyc = cyc + 1; if (sync === 1'b1) seen = 1;
    if (bus_conflict === 1'b1) conflicts = conflicts + 1;
    if (seen && !expect_conflict) begin
      if (^{a, a_oe, d_out, d_oe, sync, dbin, wr_n, wait_o, hlda, inte, bus, out_port, out_strobe, bus_conflict, bdos_char, bdos_strobe} === 1'bx) begin
        errors = errors + 1; if (errors < 10) $display("FAIL C7 X/Z on an output at clock %0d", cyc); end
      if (bus_conflict !== 1'b0) begin errors = errors + 1; if (errors < 10) $display("FAIL C7 bus_conflict at clock %0d", cyc); end
      if (out_strobe === 1'b1) begin
        if (got < n) begin if (out_port !== exp[got][7:0]) begin errors = errors + 1; if (errors < 10) $display("FAIL trace[%0d]: expected %h got %h", got, exp[got][7:0], out_port); end end
        got = got + 1;
      end
    end
    if (expect_conflict && conflicts > 0) begin $display("PASS: bus_conflict rose (%0d clocks) as expected for the mutant", conflicts); $finish; end
    if (!expect_conflict && got == n && n > 0) begin $display("%s: trace=%0d expected=%0d errors=%0d bus_conflict_clocks=%0d", errors ? "FAIL" : "PASS", got, n, errors, conflicts); $finish; end
    if (cyc > limit) begin $display("FAIL timeout%0s", expect_conflict ? ": bus_conflict never rose" : ""); $finish; end
  end
endmodule
