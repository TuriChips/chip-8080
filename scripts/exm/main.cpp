#include "Vtb_fast.h"
#include "verilated.h"
int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  Vtb_fast* t = new Vtb_fast;
  t->clk = 0;
  while (!Verilated::gotFinish()) { t->clk = 1; t->eval(); t->clk = 0; t->eval(); }
  t->final(); delete t; return 0;
}
