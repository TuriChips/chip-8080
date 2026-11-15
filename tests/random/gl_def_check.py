#!/usr/bin/env python3
"""DEF vs netlist check (Beru, #59): the routed layout (synth/sky130/i8080.def) must be the netlist the
gate-level C8 simulates (synth/sky130/i8080_sky130.v). Checks that
  1. every netlist cell instance is placed in the DEF with the same cell type, and every other DEF
     component is a tap/fill/decap cell (no logic added or lost);
  2. every net connects the same set of (instance, pin) and top-level pins in both files.
Power/ground nets and tap cells are left out (the netlist has no power pins). Exits 1 on any difference.
Usage: tests/random/gl_def_check.py [--net FILE] [--def FILE]
"""
import argparse, collections, os, re, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PHYS = re.compile(r"sky130_fd_sc_hd__(tapvpwrvgnd|fill|decap|tap)")


def read_netlist(path):
    src = open(path).read()
    ports = {}
    for m in re.finditer(r"^\s*(input|output|inout)\s*(\[(\d+):(\d+)\])?\s*([\w$]+)\s*;", src, re.M):
        if m.group(2):
            hi, lo = int(m.group(3)), int(m.group(4))
            for k in range(min(hi, lo), max(hi, lo) + 1):
                ports[f"{m.group(5)}[{k}]"] = m.group(1)
        else:
            ports[m.group(5)] = m.group(1)
    cells, nets = {}, collections.defaultdict(set)
    for m in re.finditer(r"^\s*(sky130_fd_sc_hd__\w+)\s+([\w$\\\[\].]+)\s*\((.*?)\);", src, re.M | re.S):
        typ, inst, body = m.group(1), m.group(2).lstrip("\\").strip(), m.group(3)
        cells[inst] = typ
        for pm in re.finditer(r"\.(\w+)\(\s*([^()]*?)\s*\)", body):
            net = pm.group(2).lstrip("\\").replace(" ", "")
            if net:
                nets[net].add((inst, pm.group(1)))
    assigns = re.findall(r"^\s*assign\s+(.*?);", src, re.M)
    for net in list(nets):
        if net in ports:
            nets[net].add(("PIN", net))
    return cells, nets, ports, assigns


def read_def(path):
    txt = open(path).read()
    comps = {}
    sec = re.search(r"^COMPONENTS \d+ ;(.*?)^END COMPONENTS", txt, re.M | re.S).group(1)
    for m in re.finditer(r"^\s*-\s+(\S+)\s+(\S+)", sec, re.M):
        comps[m.group(1).replace("\\", "")] = m.group(2)
    nets = {}
    sec = re.search(r"^NETS \d+ ;(.*?)^END NETS", txt, re.M | re.S).group(1)
    for m in re.finditer(r"^\s*-\s+(\S+)(.*?)(?=\+|;)", sec, re.M | re.S):
        conns = set()
        for c in re.finditer(r"\(\s*(\S+)\s+(\S+)\s*\)", m.group(2)):
            conns.add((c.group(1).replace("\\", ""), c.group(2).replace("\\", "")))
        nets[m.group(1).replace("\\", "")] = conns
    return comps, nets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default=os.path.join(ROOT, "synth/sky130/i8080_sky130.v"))
    ap.add_argument("--def", dest="deff", default=os.path.join(ROOT, "synth/sky130/i8080.def"))
    a = ap.parse_args()
    cells, vnets, ports, assigns = read_netlist(a.net)
    comps, dnets = read_def(a.deff)
    errs = []
    if assigns:
        errs.append(f"netlist has {len(assigns)} assign statements; this check doesn't model them: {assigns[:3]}")
    for inst, typ in cells.items():
        if inst not in comps:
            errs.append(f"netlist cell {inst} ({typ}) not placed in the DEF")
        elif comps[inst] != typ:
            errs.append(f"cell {inst}: netlist {typ}, DEF {comps[inst]}")
    phys = 0
    for inst, typ in comps.items():
        if inst in cells:
            continue
        if PHYS.match(typ):
            phys += 1
        else:
            errs.append(f"DEF component {inst} ({typ}) is not in the netlist")
    # nets: compare by connection set, so net renames don't matter
    vsets = collections.Counter(frozenset(c) for c in vnets.values() if len(c) > 1)
    dsets = collections.Counter(frozenset(c) for n, c in dnets.items()
                                if len(c) > 1 and not any(PHYS.match(comps.get(i, "")) for i, _ in c))
    for s in (vsets - dsets):
        errs.append(f"net in netlist, not in DEF: {sorted(s)[:6]}")
    for s in (dsets - vsets):
        errs.append(f"net in DEF, not in netlist: {sorted(s)[:6]}")
    pins_def = {p for c in dnets.values() for i, p in c if i == "PIN"}
    missing_pins = sorted(set(ports) - pins_def)
    if missing_pins:
        errs.append(f"top-level ports with no DEF net: {missing_pins}")
    print(f"netlist: {len(cells)} cells, {sum(vsets.values())} nets with 2+ connections, {len(ports)} port bits")
    print(f"DEF: {len(comps)} components ({phys} tap/fill), {sum(dsets.values())} signal nets with 2+ connections, "
          f"{len(pins_def)} pins")
    for e in errs[:30]:
        print("DIFF", e)
    print(("PASS" if not errs else f"FAIL ({len(errs)} differences)") + " gl_def_check: DEF matches the netlist")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
