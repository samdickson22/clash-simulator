#!/bin/bash
# Non-C56 opponent decks through the live K4L recipe and the fast tier, full scope (r1-cards1-dev), <= 7 processes:
# one LIVE-K4L-...-p4 process (1 + 4 pool workers) at a time, and the fast tier (2 processes) beside it.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export CLASHER_BOT_RUNTIME=$J/r1-cards1-dev CLASHER_BOT_RUNTIME_PINS=r1-cards1
O=$J/noncore; mkdir -p $O
T=reports/cards/runtime/tools/noncore_matches.py
LIVE=${LIVE:-LIVE-K4L-R-gs-rw-fc-w200-t4-p4}
echo "start $(date -u +%FT%TZ)"
(
  for d in D1 D2 D3 D4 M1 X1; do for o in random R3a; do
    nice -n 15 $PY -B $T --player LIVE-fast-it5s2 --opponent $o --deck $d --games 2 --out $O/fast.jsonl
  done; done
) > $O/fast.log 2>&1 &
fp=$!
for spec in D1:random D2:random D3:random D4:random M1:random X1:random D1:R3a D2:R3a; do
  d=${spec%%:*}; o=${spec#*:}; n=2; [ $o = R3a ] && n=1
  nice -n 15 $PY -B $T --player $LIVE --opponent $o --deck $d --games $n --out $O/live.jsonl >> $O/live.log 2>&1
  echo "live $spec rc $? $(date -u +%FT%TZ)"
done
wait $fp; echo "fast rc $?"
echo "end $(date -u +%FT%TZ)"
