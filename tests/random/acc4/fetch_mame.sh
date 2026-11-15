#!/usr/bin/env bash
# Acceptance test 4 (Beru, same script as chip-4004): fetch MAME (Ubuntu package) plus the libraries this machine lacks,
# without root, into DIR (default build/mame). Nothing is installed system-wide or committed
# (rule 9). MAME is GPL-2.0+ as a whole; the 8080 core (i8085.cpp) is BSD-3-Clause.
# Usage: tests/random/acc4/fetch_mame.sh [DIR]   -> DIR/root/usr/games/mame
set -euo pipefail
d="${1:-build/mame}"
mkdir -p "$d/debs" "$d/root"
if [ ! -x "$d/root/usr/games/mame" ]; then
  pkgs=$(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks \
         --no-replaces --no-enhances mame | grep -E '^[a-z0-9]' | sort -u)
  need=""
  for p in $pkgs; do dpkg -s "$p" >/dev/null 2>&1 || need="$need $p"; done
  # shellcheck disable=SC2086
  (cd "$d/debs" && apt-get download $need >/dev/null)
  for f in "$d"/debs/*.deb; do dpkg-deb -x "$f" "$d/root"; done
fi
"$d/root/usr/games/mame" -version >/dev/null 2>&1 || {
  LD_LIBRARY_PATH=$(find "$d/root" -name '*.so*' -printf '%h\n' | sort -u | tr '\n' ':') \
    "$d/root/usr/games/mame" -version >/dev/null || { echo "mame does not start" >&2; exit 1; }; }
echo "$d/root/usr/games/mame"
