#!/bin/bash
# Final-code no-crash re-run (lopp_fast content-hash cache + r1-cards1 fc_side_cut): LIVE K4L recipe, one game per deck.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
until grep -q '^end' $J/gate-k4lfp.log 2>/dev/null; do sleep 20; done
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export CLASHER_BOT_RUNTIME=$J/r1-cards1-dev CLASHER_BOT_RUNTIME_PINS=r1-cards1
O=$J/noncore-final; mkdir -p $O
for spec in D1:random D2:random D3:random D4:random M1:random D1:R3a; do
  d=${spec%%:*}; o=${spec#*:}
  nice -n 15 $PY -B reports/cards/runtime/tools/noncore_matches.py --player LIVE-K4L-R-gs-rw-fc-w200-t4-p4 --opponent $o \
    --deck $d --games 1 --seed 20261016300 --out $O/live.jsonl >> $O/live.log 2>&1
  echo "live $spec rc $? $(date -u +%FT%TZ)"
done
echo "end $(date -u +%FT%TZ)"
