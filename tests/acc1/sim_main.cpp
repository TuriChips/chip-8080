// Fast CP/M exerciser driver (Homer, chip-8080#64): toggles clk and calls eval() in a plain loop. Prints what the program prints
// through the BDOS stub and ends like tests/acc1/tb_cpm.sv: 'RUN DONE after N clocks, bus_conflict seen K times' at run_done, or
// 'RUN TIMEOUT after N clocks' at +MAXCLK=<n> (a failure). The judgement is check_log.py's.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "Vtb_cpm_top.h"
#include "verilated.h"

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    unsigned long long maxclk = 30000000000ULL;
    for (int i = 1; i < argc; i++)
        if (!strncmp(argv[i], "+MAXCLK=", 8)) maxclk = strtoull(argv[i] + 8, nullptr, 10);
    Vtb_cpm_top* top = new Vtb_cpm_top;
    top->clk = 0; top->reset = 1; top->eval();
    unsigned long long cyc = 0, conflicts = 0;
    int strobe_q = 0;
    // reset is held for 5 rising edges, then released at the falling edge after the 5th (as tb_cpm.sv does)
    for (int e = 0; e < 5; e++) { top->clk = 1; top->eval(); top->clk = 0; top->eval(); }
    top->reset = 0; top->eval();
    for (;;) {
        top->clk = 1; top->eval();
        top->clk = 0; top->eval();                      // Verilator needs the falling eval to see the next rising edge
        cyc++;
        int strobe = top->bdos_strobe;
        if (strobe && !strobe_q) { putchar(top->bdos_char); fflush(stdout); }
        strobe_q = strobe;
        if (top->bus_conflict) conflicts++;
        if (top->run_done) { printf("\nRUN DONE after %llu clocks, bus_conflict seen %llu times\n", cyc, conflicts); break; }
        if (cyc >= maxclk) { printf("\nRUN TIMEOUT after %llu clocks\n", cyc); break; }
    }
    delete top;
    return 0;
}
