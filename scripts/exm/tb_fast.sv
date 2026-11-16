// Tesla: same checks as tests/acc1/tb_cpm.sv, but clocked from C++ (scripts/exm/main.cpp) so Verilator needs no --timing. Faster; judged by the same check_log.py.
// CP/M exerciser testbench (Homer): runs a .COM image on i8080_system under Verilator and prints what the program prints
// through the BDOS stub (bdos_char on bdos_strobe) to stdout. Ends at run_done (a fetch from 0000h after the program started),
// or at +MAXCLK clocks, which counts as a failure. -DMEMFILE="image.hex" (see com2hex.py). The pass/fail judgement is
// check_log.py's, not this file's: it only says 'RUN DONE after N clocks' or 'RUN TIMEOUT'.
module tb_fast(input clk);
  reg reset = 1;
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte, out_strobe, bus_conflict, bdos_strobe, run_done;
  wire [7:0] d_out, bus, out_port, bdos_char;
  i8080_system #(.INIT_FILE(`MEMFILE)) dut (.clk(clk), .reset(reset), .ready(1'b1), .hold(1'b0), .int_req(1'b0), .int_vector(3'd1),
    .in_port_data(8'h00), .a(a), .a_oe(a_oe), .d_out(d_out), .d_oe(d_oe), .sync(sync), .dbin(dbin), .wr_n(wr_n), .wait_o(wait_o),
    .hlda(hlda), .inte(inte), .bus(bus), .out_port(out_port), .out_strobe(out_strobe), .bus_conflict(bus_conflict),
    .bdos_char(bdos_char), .bdos_strobe(bdos_strobe), .run_done(run_done));
  longint cyc = 0, maxclk = 64'd30000000000, conflicts = 0;
  reg strobe_q = 0;
  initial void'($value$plusargs("MAXCLK=%d", maxclk));
  integer rc = 0;   // same reset as tb_cpm: held through 5 posedges, released at the next negedge
  always @(posedge clk) if (rc < 5) rc <= rc + 1;
  always @(negedge clk) begin if (rc >= 5) reset = 0; if (!reset) begin
    cyc = cyc + 1;
    strobe_q <= bdos_strobe;
    if (bdos_strobe && !strobe_q) begin $write("%c", bdos_char); $fflush(); end
    if (bus_conflict === 1'b1) conflicts = conflicts + 1;
    if (run_done === 1'b1) begin
      $display("\nRUN DONE after %0d clocks, bus_conflict seen %0d times", cyc, conflicts); $finish;
    end
    if (cyc >= maxclk) begin $display("\nRUN TIMEOUT after %0d clocks", cyc); $finish; end
  end end
endmodule
