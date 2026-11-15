#!/usr/bin/env python3
"""Tiny 8080 assembler for the tests. Written from docs/spec.md section 6.1 (the opcode table) only.
Usage: asm80.py prog.asm out.hex       -> $readmemh image with @address records (unlisted bytes are 00)
Syntax: one statement per line, ';' starts a comment, 'label:' defines a label, '.org N', '.byte V[,V..]',
        '.word V[,V..]' (little-endian). Numbers: decimal, 0x.., 0b..; label names as operands; 'A+1' style sums allowed.
Registers B C D E H L M A; pairs B D H SP (PUSH/POP: PSW instead of SP). Conditions as in Jcc/Ccc/Rcc: NZ Z NC C PO PE P M."""
import sys, re
sys.dont_write_bytecode = True

REG = {'B': 0, 'C': 1, 'D': 2, 'E': 3, 'H': 4, 'L': 5, 'M': 6, 'A': 7}
PAIR = {'B': 0, 'D': 1, 'H': 2, 'SP': 3, 'PSW': 3}
CC = ['NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M']
ALU = ['ADD', 'ADC', 'SUB', 'SBB', 'ANA', 'XRA', 'ORA', 'CMP']
IMM = {'ADI': 0xC6, 'ACI': 0xCE, 'SUI': 0xD6, 'SBI': 0xDE, 'ANI': 0xE6, 'XRI': 0xEE, 'ORI': 0xF6, 'CPI': 0xFE}
NOARG = {'RLC': 0x07, 'RRC': 0x0F, 'RAL': 0x17, 'RAR': 0x1F, 'RET': 0xC9, 'PCHL': 0xE9, 'XCHG': 0xEB, 'XTHL': 0xE3,
         'SPHL': 0xF9, 'CMA': 0x2F, 'STC': 0x37, 'CMC': 0x3F, 'DAA': 0x27, 'EI': 0xFB, 'DI': 0xF3, 'NOP': 0x00, 'HLT': 0x76}
ADDR16 = {'JMP': 0xC3, 'CALL': 0xCD, 'STA': 0x32, 'LDA': 0x3A, 'SHLD': 0x22, 'LHLD': 0x2A}
BYTE1 = {'IN': 0xDB, 'OUT': 0xD3}

def val(tok, labels, final):
    tok = tok.strip()
    total = 0
    for sign, t in re.findall(r'([+-]?)\s*([^+-]+)', tok):
        t = t.strip()
        if t in labels: v = labels[t]
        else:
            try: v = int(t, 0)
            except ValueError:
                if final: raise SystemExit(f"unknown symbol {t!r}")
                v = 0
        total += -v if sign == '-' else v
    return total

def r8(t):
    t = t.strip().upper()
    if t not in REG: raise SystemExit(f"bad register {t!r}")
    return REG[t]

def rng(v, lo, hi, what):
    if not lo <= v <= hi: raise SystemExit(f"{what} {v} out of range {lo}..{hi}")
    return v

def assemble(lines, final, labels):
    mem = {}; pc = 0
    def emit(*bs):
        nonlocal pc
        for b in bs:
            if pc in mem: raise SystemExit(f"overlap at {pc:#06x}")
            if not 0 <= pc <= 0xFFFF: raise SystemExit(f"address {pc:#x} out of range")
            mem[pc] = b & 0xFF; pc += 1
    for ln in lines:
        ln = ln.split(';')[0].strip()
        while ':' in ln:
            l, ln = ln.split(':', 1); labels[l.strip()] = pc; ln = ln.strip()
        if not ln: continue
        op, _, rest = ln.partition(' '); op = op.upper(); args = [a.strip() for a in rest.split(',') if a.strip()]
        v = lambda i: val(args[i], labels, final)
        if op == '.ORG': pc = v(0)
        elif op == '.BYTE': [emit(rng(val(a, labels, final), -128, 255, '.byte')) for a in args]
        elif op == '.WORD': [emit(val(a, labels, final) & 255, (val(a, labels, final) >> 8) & 255) for a in args]
        elif op in NOARG: emit(NOARG[op])
        elif op == 'MOV':
            d, s = r8(args[0]), r8(args[1])
            if d == 6 and s == 6: raise SystemExit("MOV M,M is HLT; write HLT")
            emit(0x40 | d << 3 | s)
        elif op == 'MVI': emit(0x06 | r8(args[0]) << 3, rng(v(1), -128, 255, 'MVI byte'))
        elif op == 'INR': emit(0x04 | r8(args[0]) << 3)
        elif op == 'DCR': emit(0x05 | r8(args[0]) << 3)
        elif op in ALU: emit(0x80 | ALU.index(op) << 3 | r8(args[0]))
        elif op in IMM: emit(IMM[op], rng(v(0), -128, 255, op + ' byte'))
        elif op in BYTE1: emit(BYTE1[op], rng(v(0), 0, 255, op + ' port'))
        elif op in ADDR16: a = rng(v(0), 0, 0xFFFF, 'address'); emit(ADDR16[op], a & 255, a >> 8)
        elif op[0] == 'J' and op[1:] in CC: a = rng(v(0), 0, 0xFFFF, 'address'); emit(0xC2 | CC.index(op[1:]) << 3, a & 255, a >> 8)
        elif op[0] == 'C' and op[1:] in CC: a = rng(v(0), 0, 0xFFFF, 'address'); emit(0xC4 | CC.index(op[1:]) << 3, a & 255, a >> 8)
        elif op[0] == 'R' and op[1:] in CC: emit(0xC0 | CC.index(op[1:]) << 3)
        elif op == 'RST': emit(0xC7 | rng(v(0), 0, 7, 'RST number') << 3)
        elif op == 'LXI':
            a = rng(v(1), 0, 0xFFFF, 'LXI value'); p = args[0].upper()
            if p not in ('B', 'D', 'H', 'SP'): raise SystemExit(f"LXI {p}")
            emit(0x01 | PAIR[p] << 4, a & 255, a >> 8)
        elif op in ('PUSH', 'POP'):
            p = args[0].upper()
            if p not in ('B', 'D', 'H', 'PSW'): raise SystemExit(f"{op} {p}")
            emit((0xC5 if op == 'PUSH' else 0xC1) | PAIR[p] << 4)
        elif op in ('DAD', 'INX', 'DCX'):
            p = args[0].upper()
            if p not in ('B', 'D', 'H', 'SP'): raise SystemExit(f"{op} {p}")
            emit({'DAD': 0x09, 'INX': 0x03, 'DCX': 0x0B}[op] | PAIR[p] << 4)
        elif op in ('STAX', 'LDAX'):
            p = args[0].upper()
            if p not in ('B', 'D'): raise SystemExit(f"{op} {p}")
            emit({'STAX': 0x02, 'LDAX': 0x0A}[op] | PAIR[p] << 4)
        else: raise SystemExit(f"unknown mnemonic {op!r}")
    return mem

def write_hex(mem, path):
    with open(path, 'w') as f:
        prev = None
        for a in sorted(mem):
            if prev is None or a != prev + 1: f.write(f"@{a:04X}\n")
            f.write(f"{mem[a]:02X}\n"); prev = a

def main():
    src, out = sys.argv[1], sys.argv[2]
    lines = open(src).read().splitlines(); labels = {}
    assemble(lines, False, labels)
    write_hex(assemble(lines, True, labels), out)

if __name__ == '__main__': main()
