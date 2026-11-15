#!/usr/bin/env python3
"""CP/M .COM -> $readmemh image for i8080_mem: the program at 0100h, and JMP 0100h at 0000h so the CPU (reset PC = 0) starts it.
A later fetch from 0000h (the program's 'jump to 0') is what i8080_system's run_done waits for. Usage: com2hex.py in.com out.hex"""
import sys
com = open(sys.argv[1], "rb").read()
if len(com) > 0xFE00: sys.exit("program too large for 0100h..FEFFh")
with open(sys.argv[2], "w") as f:
    f.write("@0000\nC3\n00\n01\n@0100\n" + "".join("%02X\n" % b for b in com))
