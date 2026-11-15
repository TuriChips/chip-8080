// C8 testbench (Beru): runs NPROG programs on i8080_system and dumps every pin §4 compares, every
// state, for tests/random/c8/run.py to compare with ref/pins8080.py.
// Files in +dir=<d>: prog<p>/mem.hex (64 KiB $readmemh image). Output prog<p>/pins.txt, one line per
// state after reset: sync a_oe a d_oe d_out dbin wr_n wait_o hlda inte bus_conflict (binary/hex, X shows).
module tb;
  reg clk = 0, reset = 1, ready = 1, hold = 0, int_req = 0;
  reg [2:0] int_vector = 7; reg [7:0] in_port_data = 8'h5A;
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte, out_strobe, bus_conflict, bdos_strobe, run_done;
  wire [7:0] d_out, bus, out_port, bdos_char;
  i8080_system dut (.clk(clk), .reset(reset), .ready(ready), .hold(hold), .int_req(int_req),
    .int_vector(int_vector), .in_port_data(in_port_data), .a(a), .a_oe(a_oe), .d_out(d_out), .d_oe(d_oe), .sync(sync),
    .dbin(dbin), .wr_n(wr_n), .wait_o(wait_o), .hlda(hlda), .inte(inte), .bus(bus), .out_port(out_port),
    .out_strobe(out_strobe), .bus_conflict(bus_conflict), .bdos_char(bdos_char), .bdos_strobe(bdos_strobe), .run_done(run_done));
  string dir, pdir; integer nprog, nst, p, i, fd;
  initial begin
    if (!$value$plusargs("dir=%s", dir)) $fatal(1, "need +dir=");
    if (!$value$plusargs("nprog=%d", nprog)) $fatal(1, "need +nprog=");
    if (!$value$plusargs("nst=%d", nst)) $fatal(1, "need +nst=");
    for (p = 0; p < nprog; p = p + 1) begin
      pdir = $sformatf("%s/prog%0d", dir, p);
      $readmemh({pdir, "/mem.hex"}, dut.mem.mem);
      reset = 1; repeat (4) begin #5 clk = 1; #5 clk = 0; end
      reset = 0;
      fd = $fopen({pdir, "/pins.txt"}, "w");
      for (i = 0; i < nst; i = i + 1) begin
        #4 $fdisplay(fd, "%b %b %h %b %h %b %b %b %b %b %b", sync, a_oe, a, d_oe, d_out, dbin, wr_n, wait_o, hlda, inte, bus_conflict);
        #1 clk = 1; #5 clk = 0;
      end
      $fclose(fd);
    end
    $display("DONE c8 tb: %0d programs x %0d states", nprog, nst);
    $finish;
  end
endmodule
