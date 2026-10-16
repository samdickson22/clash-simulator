#!/bin/bash
# 03 timing batches (<= 6 busy processes): paired X1 c56/full, then non-C56 decks (full, roots saved), then the
# side-cut value check. Output: $J/timing/.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
T=reports/cards/runtime/tools
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
DEV=$J/r1-cards1-dev; O=$J/timing; mkdir -p $O
c56="CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=r1-total"
full="CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=r1-cards1"
N=${N:-60}
run() { tag=$1; arm=$2; deck=$3; shift 3
  env ${!arm} nice -n 15 $PY -B $T/decision_timing.py --deck $deck --decisions $N --out $O/$tag.jsonl "$@" > $O/$tag.log 2>&1; }
echo "b1 $(date -u +%FT%TZ)"
run X1-c56 c56 X1 & run X1-full full X1 & wait
echo "b2 $(date -u +%FT%TZ)"
run D3-full full D3 --save-roots $O/roots-D3.jsonl.gz & run D4-full full D4 --save-roots $O/roots-D4.jsonl.gz & wait
echo "b3 $(date -u +%FT%TZ)"
run D1-full full D1 --save-roots $O/roots-D1.jsonl.gz & run M1-full full M1 --save-roots $O/roots-M1.jsonl.gz & wait
echo "check $(date -u +%FT%TZ)"
env $full nice -n 15 $PY -B $T/side_cut_check.py $O/side-check-noncore.json $O/roots-D1.jsonl.gz $O/roots-D3.jsonl.gz \
  $O/roots-D4.jsonl.gz $O/roots-M1.jsonl.gz > $O/side-check-noncore.log 2>&1 &
env $full nice -n 15 $PY -B $T/side_cut_check.py $O/side-check-c56rec.json /mpac/sdicks02/jobs/clasher/bot-native-total/roots/ \
  > $O/side-check-c56rec.log 2>&1 &
wait
echo "end $(date -u +%FT%TZ)"
