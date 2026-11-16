// CP/M exerciser top for Verilator (Homer; replaces the timing-mode tb_cpm.sv, chip-8080#64): the clock and reset come from sim_main.cpp, so there is no
// timing scheduler. Same i8080_system and the same BDOS stub as tb_cpm.sv; sim_main.cpp does what tb_cpm.sv's always block did.
module tb_cpm_top (
  input  wire       clk,
  input  wire       reset,
  output wire [7:0] bdos_char,
  output wire       bdos_strobe,
  output wire       run_done,
  output wire       bus_conflict
);
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte, out_strobe;
  wire [7:0] d_out, bus, out_port;
  i8080_system #(.INIT_FILE(`MEMFILE)) dut (.clk(clk), .reset(reset), .ready(1'b1), .hold(1'b0), .int_req(1'b0), .int_vector(3'd1),
    .in_port_data(8'h00), .a(a), .a_oe(a_oe), .d_out(d_out), .d_oe(d_oe), .sync(sync), .dbin(dbin), .wr_n(wr_n), .wait_o(wait_o),
    .hlda(hlda), .inte(inte), .bus(bus), .out_port(out_port), .out_strobe(out_strobe), .bus_conflict(bus_conflict),
    .bdos_char(bdos_char), .bdos_strobe(bdos_strobe), .run_done(run_done));
endmodule
