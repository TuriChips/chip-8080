// Program-trace testbench on the i8080 pins (spec sections 2, 4, 8). It supplies its own 64 KiB memory and an
// input-port model, so tests bind only to the CPU's pins.
// Defines: -DMEMFILE="path" ($readmemh image with @addr records, from tests/asm80.py)
// Plusargs: +EXP=<file, one 16-bit hex word {port, data} per OUT, in order>  +N=<number of entries>  +TIMEOUT=<clocks>
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
  assign d_in = dbin ? (stat[6] ? (a[7:0] ^ 8'h5A) : mem[a]) : 8'h00;   // INP = status bit 6
  always #5 clk = ~clk;
  integer i; reg [15:0] exp [0:65535]; integer n = 0, got = 0, errors = 0, cyc = 0, timeout = 0; reg seen_t1 = 0, logged = 0;
  string expf;
  initial begin
    for (i = 0; i < 65536; i = i + 1) mem[i] = 8'h00;
    $readmemh(`MEMFILE, mem);
    if (!$value$plusargs("EXP=%s", expf)) begin $display("FAIL no +EXP"); $finish; end
    if (!$value$plusargs("N=%d", n) || n == 0) begin $display("FAIL empty or missing +N (no expected trace)"); $finish; end
    if (!$value$plusargs("TIMEOUT=%d", timeout)) timeout = 2000000;
    $readmemh(expf, exp);
    repeat (5) @(posedge clk);       // RESET held >= 3 clocks (spec section 5)
    @(negedge clk); reset = 0;
  end
  always @(negedge clk) if (!reset) begin
    cyc = cyc + 1;
    if (sync === 1'b1) begin stat = d_out; seen_t1 = 1; logged = 0; end
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
