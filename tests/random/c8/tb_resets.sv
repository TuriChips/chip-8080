// C8 testbench with mid-run resets (Beru): same as tb.sv, plus RESET raised at random states and
// held 3-5 states (spec §5), logged as a last column. Original header:
// C8 testbench (Beru): runs NPROG programs on i8080_system and dumps every pin §4 compares, every
// state, for tests/random/c8/run.py to compare with ref/pins8080.py.
// Files in +dir=<d>: prog<p>/mem.hex (64 KiB $readmemh image). Output prog<p>/pins.txt, one line per
// state after reset: sync a_oe a d_oe d_out dbin wr_n wait_o hlda inte bus_conflict ready int_req hold
// (binary/hex, X shows). With +stim=1 READY, INT and HOLD are randomised per the §7 stimulus rule and logged;
// the model replays the logged values.
module tb;
  reg clk = 0, reset = 1, ready = 1, hold = 0, int_req = 0;
  reg [2:0] int_vector = 7; reg [7:0] in_port_data = 8'h5A;
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte, out_strobe, bus_conflict, bdos_strobe, run_done;
  wire [7:0] d_out, bus, out_port, bdos_char;
  i8080_system dut (.clk(clk), .reset(reset), .ready(ready), .hold(hold), .int_req(int_req),
    .int_vector(int_vector), .in_port_data(in_port_data), .a(a), .a_oe(a_oe), .d_out(d_out), .d_oe(d_oe), .sync(sync),
    .dbin(dbin), .wr_n(wr_n), .wait_o(wait_o), .hlda(hlda), .inte(inte), .bus(bus), .out_port(out_port),
    .out_strobe(out_strobe), .bus_conflict(bus_conflict), .bdos_char(bdos_char), .bdos_strobe(bdos_strobe), .run_done(run_done));
  string dir, pdir, pins_line; integer nprog, nst, p, i, fd, stim, seed, vec, hold_en, rst_left, rst_dump, nrst;
  initial begin
    if (!$value$plusargs("dir=%s", dir)) $fatal(1, "need +dir=");
    if (!$value$plusargs("nprog=%d", nprog)) $fatal(1, "need +nprog=");
    if (!$value$plusargs("nst=%d", nst)) $fatal(1, "need +nst=");
    if (!$value$plusargs("stim=%d", stim)) stim = 0;
    if (!$value$plusargs("seed=%d", seed)) seed = 1;
    if (!$value$plusargs("vec=%d", vec)) vec = 7;
    if (!$value$plusargs("hold=%d", hold_en)) hold_en = 1;
    int_vector = vec[2:0];
    void'($urandom(seed));
    for (p = 0; p < nprog; p = p + 1) begin
      pdir = $sformatf("%s/prog%0d", dir, p);
      $readmemh({pdir, "/mem.hex"}, dut.mem.mem);
      reset = 1; ready = 1; int_req = 0; hold = 0; rst_left = 0; rst_dump = 0; nrst = 0; repeat (4) begin #5 clk = 1; #5 clk = 0; end
      reset = 0;
      fd = $fopen({pdir, "/pins.txt"}, "w");
      for (i = 0; i < nst; i = i + 1) begin
        #3;
        pins_line = $sformatf("%b %b %h %b %h %b %b %b %b %b %b", sync, a_oe, a, d_oe, d_out, dbin, wr_n, wait_o, hlda, inte, bus_conflict);
        // §7 stimulus rule: inputs change only in a T1 (sync) or TW (wait_o) state. The value set
        // here is the value present for the rest of this state, sampled at its closing edge.
        if (stim && sync === 1'b1) begin
          ready = ($urandom % 100) >= 10;                   // 10%: wait states in this cycle
          if (!int_req && d_out === 8'h8A) int_req = ($urandom % 100) < 50;   // halt ack's T1: 50%, to wake it
          else if (!int_req) int_req = ($urandom % 100) < 3;     // INT rises in 3% of cycles
          else int_req = ($urandom % 100) >= 30;            // ... and falls in 30%
          if (!hold && hold_en) hold = ($urandom % 100) < 4; // HOLD requested in 4% of cycles
        end else if (stim && wait_o === 1'b1 && a_oe === 1'b1) begin
          ready = ($urandom % 100) >= 50;                   // each TW: 50% another wait
        end
        // §7 (#45): INT may also change on the edge that starts a TWH (wait_o with buses off, not held)
        if (stim && wait_o === 1'b1 && a_oe === 1'b0 && hlda !== 1'b1 && !int_req) int_req = ($urandom % 100) < 20;
        // §7 (#39): HOLD may also change in any state while hlda = 1 or in TWH (wait_o with buses off)
        if (stim && (hlda === 1'b1 || (wait_o === 1'b1 && a_oe === 1'b0))) begin
          if (hold) hold = ($urandom % 100) >= 30;          // held: released with 30% per state
          else if (!hlda && hold_en) hold = ($urandom % 100) < 10;  // halted: a hold starts with 10%
        end
        // mid-run reset (§5): raised in 1 of 2,500 states, held 3-5 states; pins of this state were
        // sampled before the change, so the first reset-valued state is the next one
        if (rst_dump) begin $writememh($sformatf("%s/mem_rst%0d.hex", pdir, nrst), dut.mem.mem); nrst = nrst + 1; rst_dump = 0; end
        if (rst_left > 0) begin reset = 1; rst_left = rst_left - 1; end
        else if (stim && ($urandom % 2500) == 0) begin reset = 1; rst_left = 2 + ($urandom % 3); rst_dump = 1; end
        else reset = 0;
        #1 $fdisplay(fd, "%s %b %b %b %b", pins_line, ready, int_req, hold, reset);
        #1 clk = 1; #5 clk = 0;
      end
      $fclose(fd);
      $writememh({pdir, "/mem_end.hex"}, dut.mem.mem);   // final RAM, compared with the model's
    end
    $display("DONE c8 tb: %0d programs x %0d states", nprog, nst);
    $finish;
  end
endmodule
