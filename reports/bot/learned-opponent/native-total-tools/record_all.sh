#!/bin/bash
# 12 games (x4s indices 0..11: all deck pairings mix), 12 cores, pinned r1 runtime
set -uo pipefail
cd /mpac/sdicks02/repos/clasher-bot
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
B=/mpac/sdicks02/jobs/clasher/bot-native-total
pids=()
for i in $(seq 0 11); do
  nice -n 10 .venv/bin/python -B $B/record_roots.py --out $B/roots --index $i > $B/roots-log-$i.txt 2>&1 &
  pids+=($!)
done
for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
date -u +%FT%TZ
