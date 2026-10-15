#!/bin/bash
# Pinned to 56-63,112-119; <= 8 processes at any time.
set -uo pipefail
cd /mpac/sdicks02/repos/clasher-bot
B=/mpac/sdicks02/jobs/clasher/bot-native-total
R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
T=/mpac/sdicks02/repos/clasher-bot-native-total/native
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
TS="taskset -c 56-63,112-119 nice -n 10"
echo "fixtures start $(date -u +%FT%TZ)"
for n in pinned:$R1/native total:$T; do tag=${n%%:*}; dir=${n#*:}
  PYTHONPATH=$dir:$B/repro/src-orig:$R1/src:$R1/reports/strategy_council_20260928/engine-speed:/mpac/sdicks02/repos/clasher-bot \
    $TS .venv/bin/python -B $B/parity_fixtures.py --out $B/fixtures-$tag.jsonl --workers 3 > $B/fixtures-$tag.log 2>&1 &
done
wait
echo "fixtures end $(date -u +%FT%TZ)"
export CLASHER_BOT_RUNTIME=$R1
for n in pinned:$R1/native total:$T; do tag=${n%%:*}; dir=${n#*:}
  for i in 0 1 2 3; do
    CLASHER_DELAY_NATIVE_DIR=$dir $TS .venv/bin/python -B $B/parity_roots.py --roots $B/roots --sample 300 --shard $i/4 \
      --out $B/roots-$tag-$i.jsonl > $B/roots-$tag-$i.log 2>&1 &
  done
done
wait
echo "roots end $(date -u +%FT%TZ)"
