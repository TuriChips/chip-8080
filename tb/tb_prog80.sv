// Program-trace testbench on the i8080 pins (spec sections 2, 4, 8). It supplies its own 64 KiB memory and an
// input-port model, so tests bind only to the CPU's pins.
// Defines: -DMEMFILE="path" ($readmemh image with @addr records, from tests/asm80.py)
// Plusargs: +EXP=<file, one 16-bit hex word {port, data} per OUT, in order>  +N=<number of entries>  +TIMEOUT=<clocks>  +RESET_AT=<clock, reset again mid-run, C6>  +INT_AT=<state, raise INT, C4>  +VEC=<RST n put on the bus at INTA>
// Trace = every OUT instruction's port (a[7:0]) and data (d_out at the cycle with status 10), so a program
// shows registers and flags by moving them to A and writing them out (PUSH PSW / POP rp / MOV A,r / OUT).
// IN returns {port ^ 5A} (so a read of port p gives p ^ 0x5A). Memory writes land in mem[].
// Checks on every clock from the first T1 after reset: no X/Z on any output of i8080 (C7).
`timescale 1ns/1ps
module tb_prog80;
  reg clk = 0, reset = 1, ready = 1, hold = 0, int_req = 0;
  wire [15:0] a; wire a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte; wire [7:0] d_out; wire [7:0] d_in;
  reg [7:0] mem [0:65535]; reg [7:0] stat = 0;
  i8080 dut (.clk(clk), .reset(reset), .a(a), .a_oe(a_oe), .d_in(d_in), .d_out(d_out), .d_oe(d_oe), .sync(sync),
             .dbin(dbin), .wr_n(wr_n), .ready(ready), .wait_o(wait_o), .hold(hold), .hlda(hlda), .int_req(int_req), .inte(inte));
  integer int_at = -1, vec = 1, sc = 0, n_inta = 0; reg int_clear = 0;     // C4: +INT_AT=<state number from the first T1> +VEC=<0..7>
  // INTA (status bit 0): the interrupt logic puts RST n on the bus (spec 7, i8080_system does the same); INP (bit 6): port ^ 5A; else memory
  assign d_in = dbin ? (stat[0] ? (8'hC7 | (vec[2:0] << 3)) : (stat[6] ? (a[7:0] ^ 8'h5A) : mem[a])) : 8'h00;
  // INT is driven only at the edge that starts a state (spec 7 stimulus rule): raised at the start of state INT_AT, dropped after the INTA cycle starts
  always @(posedge clk) if (!reset) begin
    if (int_at >= 0 && sc == int_at && seen_t1) int_req <= 1;
    if (int_clear) begin int_req <= 0; int_clear <= 0; end
  end
  always #5 clk = ~clk;
  integer i; reg [15:0] exp [0:65535]; integer n = 0, got = 0, errors = 0, cyc = 0, timeout = 0; reg seen_t1 = 0, logged = 0;
  string expf;
  initial begin
    for (i = 0; i < 65536; i = i + 1) mem[i] = 8'h00;
    $readmemh(`MEMFILE, mem);
    if (!$value$plusargs("EXP=%s", expf)) begin $display("FAIL no +EXP"); $finish; end
    if (!$value$plusargs("N=%d", n) || n == 0) begin $display("FAIL empty or missing +N (no expected trace)"); $finish; end
    if (!$value$plusargs("TIMEOUT=%d", timeout)) timeout = 2000000;
    if (!$value$plusargs("INT_AT=%d", int_at)) int_at = -1;
    if (!$value$plusargs("VEC=%d", vec)) vec = 1;
    if (!$value$plusargs("RESET_AT=%d", rst_at)) rst_at = -1;
    $readmemh(expf, exp);
    repeat (5) @(posedge clk);       // RESET held >= 3 clocks (spec section 5)
    @(negedge clk); reset = 0;
  end
  // Optional mid-run reset (C6): +RESET_AT=<clock> asserts reset there for 5 clocks (>= 3, spec 5). While reset = 1 the pins must
  // be a_oe 0, d_oe 0, sync 0, dbin 0, wr_n 1, wait_o 0, hlda 0, inte 0 (spec 5, checked from the 2nd reset clock). After it falls the first
  // T1 is an M1 fetch from 0000 with status A2 and INTE = 0: checked.
  integer rst_at = -1, rcnt = 0; reg in_mid = 0, mid_done = 0, first_after = 0;
  always @(negedge clk) if (in_mid || (rst_at >= 0 && cyc == rst_at && !mid_done)) begin
    if (!in_mid) begin in_mid = 1; mid_done = 1; reset = 1; rcnt = 0; end
    else begin
      rcnt = rcnt + 1;
      if (rcnt >= 2 && ({a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte} !== 8'b0000_1000)) begin
        errors = errors + 1; $display("FAIL reset pins at reset clock %0d: a_oe=%b d_oe=%b sync=%b dbin=%b wr_n=%b wait=%b hlda=%b inte=%b", rcnt, a_oe, d_oe, sync, dbin, wr_n, wait_o, hlda, inte); end
      if (rcnt == 5) begin reset = 0; in_mid = 0; first_after = 1; logged = 0; end
    end
  end else if (!reset) begin
    cyc = cyc + 1;
    if (first_after && sync === 1'b1) begin     // the first T1 after reset (spec 5), whichever clock it falls on
      first_after = 0;
      if (!(a === 16'h0000 && d_out === 8'hA2 && inte === 1'b0)) begin errors = errors + 1;
        $display("FAIL after reset: the first T1 is not an M1 fetch from 0000 with INTE 0 (a=%h status=%h inte=%b)", a, d_out, inte); end
    end
    if (sync === 1'b1) begin stat = d_out; seen_t1 = 1; logged = 0; if (d_out[0] === 1'b1) begin n_inta = n_inta + 1; int_clear <= 1; end end
    if (seen_t1) sc = sc + 1;
    if (seen_t1 && (^{a, a_oe, d_out, d_oe, sync, dbin, wr_n, wait_o, hlda, inte} === 1'bx)) begin
      errors = errors + 1; $display("FAIL C7 X/Z on an output at clock %0d", cyc); end
    if (wr_n === 1'b0 && d_oe === 1'b1 && !logged) begin
      logged = 1;
      if (stat[4]) begin                         // OUT cycle (status 10)
        if (got < n) begin
          if ({a[7:0], d_out} !== exp[got]) begin errors = errors + 1;
            $display("FAIL trace[%0d]: expected port %h data %h, got port %h data %h (clock %0d)", got, exp[got][15:8], exp[got][7:0], a[7:0], d_out, cyc); end
        end else begin errors = errors + 1; $display("FAIL extra OUT %h at clock %0d", d_out, cyc); end
        got = got + 1;
      end else mem[a] = d_out;                    // memory write
    end
    if (got == n) begin $display("%s: trace=%0d expected=%0d errors=%0d", errors ? "FAIL" : "PASS", got, n, errors); $finish; end
    if (cyc > timeout) begin $display("FAIL timeout: %0d of %0d trace entries", got, n); $finish; end
  end
endmodule
