#!/usr/bin/env python3
"""Checks tests/asm80.py against docs/spec.md section 6.1/10: assembling every documented instruction form must
produce exactly the 244 documented opcode bytes (all of 00-FF except the 12 undocumented ones), each once, and
the operand lengths must be right. Expected encodings are written here independently, as bit patterns."""
import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asm80
UNDOC = {0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0xCB, 0xD9, 0xDD, 0xED, 0xFD}
R = 'BCDEHLMA'; RP = ['B', 'D', 'H', 'SP']; CC = ['NZ', 'Z', 'NC', 'C', 'PO', 'PE', 'P', 'M']
forms = []   # (source line, expected bytes)
for d in range(8):
    for s in range(8):
        if d == 6 and s == 6: forms.append(("HLT", [0x76]))
        else: forms.append((f"MOV {R[d]},{R[s]}", [0b01000000 | d << 3 | s]))
for r in range(8):
    forms += [(f"MVI {R[r]},0x5A", [0b00000110 | r << 3, 0x5A]), (f"INR {R[r]}", [0b00000100 | r << 3]), (f"DCR {R[r]}", [0b00000101 | r << 3])]
for i, m in enumerate(['ADD', 'ADC', 'SUB', 'SBB', 'ANA', 'XRA', 'ORA', 'CMP']):
    for s in range(8): forms.append((f"{m} {R[s]}", [0b10000000 | i << 3 | s]))
    forms.append((f"{['ADI','ACI','SUI','SBI','ANI','XRI','ORI','CPI'][i]} 0x33", [0b11000110 | i << 3, 0x33]))
forms += [("RLC", [0x07]), ("RRC", [0x0F]), ("RAL", [0x17]), ("RAR", [0x1F]), ("JMP 0x1234", [0xC3, 0x34, 0x12]), ("CALL 0x1234", [0xCD, 0x34, 0x12]),
          ("RET", [0xC9]), ("PCHL", [0xE9]), ("IN 0x12", [0xDB, 0x12]), ("OUT 0x12", [0xD3, 0x12]), ("STA 0x1234", [0x32, 0x34, 0x12]),
          ("LDA 0x1234", [0x3A, 0x34, 0x12]), ("XCHG", [0xEB]), ("XTHL", [0xE3]), ("SPHL", [0xF9]), ("CMA", [0x2F]), ("STC", [0x37]),
          ("CMC", [0x3F]), ("DAA", [0x27]), ("SHLD 0x1234", [0x22, 0x34, 0x12]), ("LHLD 0x1234", [0x2A, 0x34, 0x12]), ("EI", [0xFB]),
          ("DI", [0xF3]), ("NOP", [0x00]), ("STAX B", [0x02]), ("STAX D", [0x12]), ("LDAX B", [0x0A]), ("LDAX D", [0x1A])]
for c in range(8):
    forms += [(f"J{CC[c]} 0x1234", [0b11000010 | c << 3, 0x34, 0x12]), (f"C{CC[c]} 0x1234", [0b11000100 | c << 3, 0x34, 0x12]), (f"R{CC[c]}", [0b11000000 | c << 3])]
for n in range(8): forms.append((f"RST {n}", [0b11000111 | n << 3]))
for p, name in enumerate(RP):
    forms += [(f"LXI {name},0x1234", [0b00000001 | p << 4, 0x34, 0x12]), (f"DAD {name}", [0b00001001 | p << 4]),
              (f"INX {name}", [0b00000011 | p << 4]), (f"DCX {name}", [0b00001011 | p << 4])]
for p, name in enumerate(['B', 'D', 'H', 'PSW']):
    forms += [(f"PUSH {name}", [0b11000101 | p << 4]), (f"POP {name}", [0b11000001 | p << 4])]
seen = {}
for src, exp in forms:
    got = asm80.assemble([src], True, {})
    got = [got[i] for i in range(len(got))]
    assert got == exp, f"{src}: assembled {got}, expected {exp}"
    assert exp[0] not in seen or seen[exp[0]] == src, f"opcode {exp[0]:02X} from both {seen[exp[0]]!r} and {src!r}"
    seen[exp[0]] = src
documented = set(range(256)) - UNDOC
assert set(seen) == documented, f"missing {sorted(documented - set(seen))}, extra {sorted(set(seen) - documented)}"
assert len(seen) == 244
for bad in ("MOV M,M", "MVI A,300", "RST 8", "LXI PSW,1", "PUSH SP", "STAX H", "JMP 0x10000"):
    try: asm80.assemble([bad], True, {}); raise AssertionError(f"{bad!r} should be rejected")
    except SystemExit: pass
print(f"PASS asm80 selftest: {len(forms)} forms, 244 documented opcodes each assembled once, 12 undocumented absent")
