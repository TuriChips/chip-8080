#!/usr/bin/env python3
"""Judges the log of an 8080 exerciser run (spec section 9, acceptance test 1). Homer.
Usage: check_log.py pre  <log>                  8080PRE: its completion line is present and nothing else went wrong
       check_log.py exm  <log> <8080EXM.MAC>    8080EXM: every test printed '  PASS! crc is:' with the CRC the source expects
The expected test names and CRCs are read from the fetched 8080EXM.MAC (build/exerciser/), never typed here.
Exit 0 only on a full pass. A run that stops early (no 'Tests complete'), a missing test, a wrong CRC or any ERROR line fails."""
import re, sys
def fail(msg): print("FAIL:", msg); sys.exit(1)
mode, log = sys.argv[1], open(sys.argv[2], errors="replace").read()
if mode == "pre":
    if "8080 Preliminary tests complete" not in log: fail("8080PRE did not print its completion line")
    if "ERROR" in log.upper(): fail("an ERROR appears in the 8080PRE log")
    print("PASS: 8080PRE completed"); sys.exit(0)
if mode != "exm": sys.exit("mode must be pre or exm")
src = open(sys.argv[3], errors="replace").read().splitlines()
tests, crc = [], None
for ln in src:      # '	db	014h, 047h, 04Bh, 0A6h	; expected crc' then "	tmsg	'name'"
    m = re.match(r"\s*db\s+((?:[0-9A-Fa-f]+h,?\s*){4})\s*;\s*expected crc", ln)
    if m: crc = "".join("%02x" % int(x[:-1], 16) for x in re.findall(r"[0-9A-Fa-f]+h", m[1])); continue
    m = re.match(r"\s*tmsg\s+'([^']*)'", ln)
    if m and crc: tests.append((m[1], crc)); crc = None
# A future source change must not silently drop a test: every 'db ... ; expected crc' data line and every
# "tmsg '<name>'" line must have been paired (the other two 'expected crc' words in the source are comments).
n_db = sum(1 for ln in src if re.match(r"\s*db\s+(?:[0-9A-Fa-f]+h,?\s*){4}\s*;\s*expected crc", ln))
n_msg = sum(1 for ln in src if re.match(r"\s*tmsg\s+'", ln))
if not (n_db == n_msg == len(tests)): fail("source has %d expected-crc lines and %d tmsg lines but %d were paired: the parser is out of date" % (n_db, n_msg, len(tests)))
if len(tests) < 20: fail("found only %d tests in the .MAC source, the parser is out of date" % len(tests))
if "8080 instruction exerciser" not in log: fail("banner missing")
bad = [l for l in log.splitlines() if "ERROR" in l]
if bad: fail("%d ERROR line(s), first: %s" % (len(bad), bad[0].strip()))
missing = []
for name, crc in tests:
    if not re.search(re.escape(name) + r"\.*\s+PASS! crc is:" + crc + r"\b", log): missing.append(name)
if missing: fail("%d of %d tests did not print PASS with the expected CRC: %s" % (len(missing), len(tests), ", ".join(missing)))
if "Tests complete" not in log: fail("the run did not reach 'Tests complete'")
print("PASS: all %d 8080EXM tests printed PASS with the expected CRC and the run completed" % len(tests))
