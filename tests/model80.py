#!/usr/bin/env python3
"""Expected-result model of the 8080's ALU group, written from docs/spec.md section 6 only (flag rules, quirks,
Decisions), used to generate expected traces for tests. It is NOT Beru's reference model (ref/) and reads no RTL.
Flags are returned as the F byte as PUSH PSW pushes it: S Z 0 AC 0 P 1 CY (spec section 3).
`python3 tests/model80.py` runs a selftest against the worked examples quoted in the spec (section 6 / 10)."""
import sys
sys.dont_write_bytecode = True

def parity(v): return 1 if bin(v & 255).count('1') % 2 == 0 else 0
def mkf(s, z, ac, p, cy): return s << 7 | z << 6 | ac << 4 | p << 2 | 1 << 1 | cy
def szp(v): return (v >> 7) & 1, 1 if v & 255 == 0 else 0, parity(v)
def cy_of(f): return f & 1

def add(a, b, cin=0):
    t = a + b + cin; r = t & 255; s, z, p = szp(r)
    return r, mkf(s, z, 1 if (a & 15) + (b & 15) + cin > 15 else 0, p, t >> 8)
def sub(a, b, bin_=0):             # t = A + ~op + (1 - borrow-in): spec 6, CY = NOT t[8], AC = carry out of bit 3, not complemented
    nb = (~b) & 255; c = 1 - bin_; t = a + nb + c; r = t & 255; s, z, p = szp(r)
    return r, mkf(s, z, 1 if (a & 15) + (nb & 15) + c > 15 else 0, p, 1 - (t >> 8))
def logic(op, a, b):
    if op == 'ANA': r = a & b; ac = ((a | b) >> 3) & 1          # AC = bit 3 of A OR bit 3 of operand (spec 6, ALP p.1-11)
    elif op == 'XRA': r = a ^ b; ac = 0
    else: r = a | b; ac = 0
    s, z, p = szp(r); return r, mkf(s, z, ac, p, 0)

def alu(op, a, b, cy=0):
    """op: ADD ADC SUB SBB ANA XRA ORA CMP (register and immediate forms share the rules). Returns (A, F)."""
    if op == 'ADD': return add(a, b)
    if op == 'ADC': return add(a, b, cy)
    if op == 'SUB': return sub(a, b)
    if op == 'SBB': return sub(a, b, cy)
    if op == 'CMP': return a, sub(a, b)[1]
    return logic(op, a, b)

def inr(r, f):                      # Z S P AC from the result; CY unchanged; AC = 1 exactly when low nibble was F
    v = (r + 1) & 255; s, z, p = szp(v)
    return v, mkf(s, z, 1 if r & 15 == 15 else 0, p, cy_of(f))
def dcr(r, f):                      # r + FF; AC = carry out of bit 3 of r[3:0] + F, i.e. 1 exactly when the low nibble was not 0 (Decision)
    v = (r - 1) & 255; s, z, p = szp(v)
    return v, mkf(s, z, 1 if (r & 15) + 15 > 15 else 0, p, cy_of(f))

def daa(a, f):
    cy = f & 1; ac = (f >> 4) & 1
    if (a & 15) > 9 or ac: t = a + 6; ac2 = 1 if (a & 15) + 6 > 15 else 0; a = t & 255
    else: ac2 = 0
    cy2 = cy
    if (a >> 4) > 9 or cy: t = a + 0x60; cy2 = 1 if (t >> 8) or cy else 0; a = t & 255   # CY = CY_in OR carry out (Decision)
    s, z, p = szp(a); return a, mkf(s, z, ac2, p, cy2)

def rot(op, a, f):                  # only CY changes; S Z AC P keep their values
    cy = f & 1
    if op == 'RLC': c = a >> 7; a = ((a << 1) | c) & 255
    elif op == 'RRC': c = a & 1; a = (a >> 1) | (c << 7)
    elif op == 'RAL': c = a >> 7; a = ((a << 1) | cy) & 255
    else: c = a & 1; a = (a >> 1) | (cy << 7)
    return a, (f & 0xFE) | c

if __name__ == '__main__':
    # worked examples quoted in the spec
    assert alu('SUB', 0x3E, 0x3E, 0)[1] == mkf(0, 1, 1, 1, 0), "SUB A with 3E: CY 0, S 0, Z 1, P 1, AC 1 (ALP p.3-64)"
    r, f = alu('SBB', 4, 2, 1); assert (r, f) == (1, mkf(0, 0, 1, 0, 0)), "SBB: A=4 B=2 CY=1 -> 1, CY 0, S 0, Z 0, P 0, AC 1 (ALP p.3-57)"
    r, f = alu('ADD', 0x93, 0x08, 0); assert r == 0x9B and not f & 1
    r, f = daa(r, f); assert (r, f) == (0x01, mkf(0, 0, 1, 0, 1)), "DAA: 93+08 -> 9B -> 01, CY = AC = 1 (ALP p.3-19)"
    assert alu('SBB', 0, 0xFF, 1)[0] == 0 and alu('SBB', 0, 0xFF, 1)[1] & 1 == 1, "SBB with op FF, CY 1: true A-op-CY mod 256, CY = borrow (Decision)"
    assert alu('ANA', 0x08, 0x00)[1] >> 4 & 1 == 1 and alu('ANA', 0x00, 0x00)[1] >> 4 & 1 == 0, "ANA AC = OR of bit 3"
    assert inr(0x0F, 0)[1] >> 4 & 1 == 1 and inr(0x0E, 0)[1] >> 4 & 1 == 0 and inr(0xFF, 1)[1] & 1 == 1, "INR AC, CY kept"
    assert dcr(0x10, 0)[1] >> 4 & 1 == 0 and dcr(0x11, 0)[1] >> 4 & 1 == 1 and dcr(0x00, 1)[0] == 0xFF, "DCR AC rule"
    assert rot('RLC', 0x81, 0)[0] == 0x03 and rot('RLC', 0x81, 0)[1] & 1 == 1 and rot('RAR', 0x01, 1)[0] == 0x80 and rot('RAR', 0x01, 1)[1] & 1 == 1
    print("PASS model80 selftest (spec worked examples)")
