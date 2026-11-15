// Pin-timing testbench for the i8080 (C2, spec 4): compares sync, a_oe, d_oe, dbin, wr_n, wait_o, hlda, inte (masked),
// a and d_out (where not 'x') in every clock state, from the first T1 after reset, against an expected file made by
// tests/c2/gen_pins80.py. Own memory (the program image) and input-port model as in tb_prog80.sv.
// Defines: -DMEMFILE="path". Plusargs: +EXP=<file of `FF MM AAAA DD` lines> +N=<lines> 
// Fifth column: READY, sixth: HOLD, driven during each state (applied at the edge starting that state).
// FF = {sync, a_oe, d_oe, dbin, wr_n, wait_o, hlda, inte}, MM = mask of compared FF bits.
// Also: no X/Z on any output at every clock (C7). +INT_AT=<state> raises INT at the start of that state (C4); INTA puts RST <VEC> on the bus.
`timescale 1ns/1ps
module tb_pins80;
  reg clk = 0, reset = 1, ready = 1, hold = 0, int_req = 0;
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte; wire [7:0] d_out; wire [7:0] d_in;
  reg [7:0] mem [0:65535]; reg [7:0] stat = 0;
  i8080 dut (.clk(clk), .reset(reset), .a(a), .a_oe(a_oe), .d_in(d_in), .d_out(d_out), .d_oe(d_oe), .sync(sync),
             .dbin(dbin), .wr_n(wr_n), .ready(ready), .wait_o(wait_o), .hold(hold), .hlda(hlda), .int_req(int_req), .inte(inte));
  integer int_at = -1, vec = 1; reg int_clear = 0;     // C4 pins: +INT_AT=<state from the first T1> +VEC=<RST n put on the bus at INTA>
  assign d_in = dbin ? (stat[0] ? (8'hC7 | (vec[2:0] << 3)) : (stat[6] ? (a[7:0] ^ 8'h5A) : mem[a])) : 8'h00;
  always #5 clk = ~clk;
  reg [7:0] ef [0:65535]; reg [7:0] em [0:65535]; reg [15:0] ea [0:65535]; reg [7:0] ed [0:65535]; reg er [0:65535]; reg eh [0:65535];
  integer n = 0, idx = 0, errors = 0, cyc = 0, i, fd, r; string expf; reg logged = 0;
  reg [7:0] fl;
  initial begin
    for (i = 0; i < 65536; i = i + 1) mem[i] = 8'h00;
    $readmemh(`MEMFILE, mem);
    if (!$value$plusargs("EXP=%s", expf)) begin $display("FAIL no +EXP"); $finish; end
    if (!$value$plusargs("INT_AT=%d", int_at)) int_at = -1;
    if (!$value$plusargs("VEC=%d", vec)) vec = 1;
    if (!$value$plusargs("N=%d", n) || n == 0) begin $display("FAIL empty or missing +N (no expected pins)"); $finish; end
    fd = $fopen(expf, "r"); for (i = 0; i < n; i = i + 1) r = $fscanf(fd, "%h %h %h %h %d %d\n", ef[i], em[i], ea[i], ed[i], er[i], eh[i]);
    repeat (5) @(posedge clk); @(negedge clk); reset = 0;
  end
  // READY: the value for the state that starts at this edge (changes only at state starts, spec 7 stimulus rule)
  reg started = 0;
  always @(posedge clk) if (!reset && started && idx < n) begin
    ready <= er[idx]; hold <= eh[idx];            // HOLD: legal changes only at T1/TW starts or while hlda = 1 (the generator obeys this)
    if (int_at >= 0 && idx == int_at) int_req <= 1;     // INT changes only at the edge that starts a state (spec 7)
    if (int_clear) begin int_req <= 0; int_clear <= 0; end
  end
  always @(negedge clk) if (!reset) begin
    cyc = cyc + 1; fl = {sync, a_oe, d_oe, dbin, wr_n, wait_o, hlda, inte};
    if (!started && sync === 1'b1) started = 1;       // comparison starts at the first T1 after reset (spec 5), whichever clock it falls on
    if (started) begin
    if (sync === 1'b1) begin stat = d_out; logged = 0; if (d_out[0] === 1'b1 && started) int_clear <= 1; end
    if (wr_n === 1'b0 && d_oe === 1'b1 && !logged) begin logged = 1; if (!stat[4]) mem[a] = d_out; end   // memory write (not OUT)
    if (^{a, a_oe, d_out, d_oe, sync, dbin, wr_n, wait_o, hlda, inte} === 1'bx) begin errors = errors + 1; $display("FAIL C7 X/Z on an output at state %0d", idx); end
    if ((fl & em[idx]) !== (ef[idx] & em[idx]) || (^ea[idx] !== 1'bx && a !== ea[idx]) || (^ed[idx] !== 1'bx && d_out !== ed[idx])) begin
      errors = errors + 1;
      if (errors < 20) $display("FAIL state %0d: expected flags %b/%b a=%h d=%h, got flags %b a=%h d=%h", idx, ef[idx], em[idx], ea[idx], ed[idx], fl, a, d_out);
    end
    idx = idx + 1;
    end
    if (started && idx == n) begin $display("%s: states=%0d errors=%0d", errors ? "FAIL" : "PASS", n, errors); $finish; end
    if (cyc > 10 * n + 200) begin $display("FAIL timeout"); $finish; end
  end
endmodule
