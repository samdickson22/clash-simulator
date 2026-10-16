#!/bin/bash
# 03 chain (<= 8 busy processes at a time): after noncore.sh -> HEADLINE gate -> saved-root timing probe.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
until grep -q '^end' $J/noncore.log; do sleep 20; done
echo "headline $(date -u +%FT%TZ)"
POLW=3 K4LW=1 RL5=$J/rl5-policy-00010.pt bash $J/repo/reports/cards/runtime/tools/gate.sh headline > $J/gate-headline.log 2>&1
echo "headline rc $? $(date -u +%FT%TZ)"
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CLASHER_BOT_RUNTIME=$J/r1-cards1-dev CLASHER_BOT_RUNTIME_PINS=r1-cards1
mkdir -p $J/timing
for d in X1 D1 D3 D4; do
  nice -n 15 $PY -B reports/cards/runtime/tools/noncore_matches.py --player LIVE-K4L-R-gs-rw-fc-w200-t4-p4 --opponent random \
    --deck $d --games 1 --seed 20261016100 --save-roots $J/timing/roots-$d.jsonl.gz --out $J/timing/games.jsonl >> $J/timing/games.log 2>&1
done
nice -n 15 $PY -B reports/cards/runtime/tools/time_roots.py $J/timing/roots-*.jsonl.gz > $J/timing/time_roots.txt 2>&1
echo "end $(date -u +%FT%TZ)"
