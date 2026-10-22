#!/bin/zsh
# pretrain-v1 latency benchmark on the Mac (benchmark-only; files under ~/clasher-pretrain-bench only).
# Sequential, one process at a time, each bounded by a perl alarm; existing venv read-only.
cd ~/clasher-pretrain-bench/code || exit 1
PY=~/clasher-live/venv/bin/python
mkdir -p ../results
for sz in S:192,4,6,576 M:320,6,8,1280; do
  n=${sz%%:*}; s=${sz#*:}
  for cfg in "cpu 1" "cpu 4" "mps 1"; do
    set -- ${=cfg}
    perl -e 'alarm shift; exec @ARGV' 400 $PY -m bot.pretrain_v1.bench_device --records ../records --size $s \
      --device $1 --threads $2 --polls 3000 --out ../results/$n-$1-t$2.json > /dev/null 2> ../results/$n-$1-t$2.err
    echo "$n $1 t$2 exit $?"
  done
done
uptime
