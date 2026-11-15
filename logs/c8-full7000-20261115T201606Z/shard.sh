#!/usr/bin/env bash
# shard.sh SHARD BASESEED NBATCH: 500-program batches x 7000 states (~1,000 instructions each)
s=$1; base=$2; nb=$3; cd /tmp/beru-c8full
for b in $(seq 0 $((nb-1))); do
  seed=$((base + b * 500)); out=/tmp/beru-c8full/out$s
  python3 -I tests/random/c8/run.py --nprog 500 --nst 7000 --seed $seed --rtl /tmp/beru-8080rtl/rtl --out $out > logs/shard$s-batch$b.log 2>&1
  python3 -I tests/random/c8/coverage.py --out $out --seed $seed --nprog 500 --nst 7000 > logs/shard$s-batch$b-coverage.log 2>&1
  grep -E '^(PASS|FAIL)' logs/shard$s-batch$b.log | sed "s/^/shard$s batch$b seed$seed: /" >> logs/progress.txt
  rm -rf $out
done
