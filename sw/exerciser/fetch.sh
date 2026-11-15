#!/usr/bin/env bash
# Homer: fetch the 8080 exercisers (spec section 9, acceptance test 1) into build/exerciser/. Nothing is committed.
# 8080PRE and 8080EXM: Frank D. Cringle's zexlax (c) 1994, modified for the 8080 by Ian Bartholomew (2009);
# GNU GPL v2 or later (header of the .MAC source). The "M" variant has the CRCs of an Intel 8080 built in:
# Mike Douglas (May 2013) added the success CRCs shown on http://www.idb.me.uk/sunhillow/8080.html (see 8080EXM.MAC, header lines 43-46).
# Do NOT use 8080EX1: its CRCs are for the Soviet KR580VM80A clone. TST8080 and CPUTEST are excluded: no licence found.
# Files are pinned by commit and sha256; a mismatch stops the run. Run from the repo root: ./sw/exerciser/fetch.sh
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
REPO=superzazu/8080            # a mirror of the files (MIT for the mirror's own code; the exercisers keep their GPL header)
COMMIT=c5d403ce7ac967b6ec4980a45b5447d8880888b0
OUT=build/exerciser; mkdir -p "$OUT"
fetch() {   # name sha256
  curl -fsS --max-time 60 -o "$OUT/$1" "https://raw.githubusercontent.com/$REPO/$COMMIT/cpu_tests/$1"
  echo "$2  $OUT/$1" | sha256sum -c --quiet - || { echo "sha256 mismatch for $1: refusing to use it" >&2; rm -f "$OUT/$1"; exit 1; }
}
fetch 8080PRE.COM 18eb3c79cba42c0718f160be6a1853cb64cdce7aa47d65780189a57bdd98c4e0
fetch 8080EXM.COM 6e3286e11bb1a8f47b8ee1280b4a067be813193363e3223c99b0d21912f44aeb
fetch 8080EXM.MAC 806d3a069b0021e9925c0b7c26fd74a3c397ca7f618a599ab4a8396ebcd1f3f3   # the source, kept to show the licence and CRC provenance
grep -q 'GNU General Public License' "$OUT/8080EXM.MAC" && grep -q 'Ian Bartholomew' "$OUT/8080EXM.MAC" \
  || { echo "8080EXM.MAC header is not what the spec section 9 recorded: ask Sai" >&2; exit 1; }
echo "fetched 8080PRE.COM, 8080EXM.COM and 8080EXM.MAC from $REPO@${COMMIT:0:7}, hashes match"
