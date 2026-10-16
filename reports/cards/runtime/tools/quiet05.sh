#!/bin/bash
# Quiet timing on 127x05 (lead: taskset 4 cores, nice, <= ~10 min, skip if load > 40). One run at a time.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
CORES=${CORES:-120-123}
DEV=$J/r1-cards1-dev; O=$J/quiet05; mkdir -p $O
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export CLASHER_LIVE_FAST=student:$J/students/it5s2-step001200.pt@0.5375   # 05 has no clasher-bot-runtime/students (sha-pinned copy)
export CLASHER_LOPP_MODELS=$J/lopp-models   # copy of 08 bot-lopp-models/pool.npz (sha256 1e4bb6a0…)
load=$(cut -d' ' -f1 /proc/loadavg); echo "load $load $(date -u +%FT%TZ)"
awk -v l=$load 'BEGIN{exit !(l > 40)}' && { echo "load > 40: skipped"; exit 0; }
for spec in X1:c56:before X1:c56:after X1:full:before X1:full:after D3:full:before D3:full:after; do
  IFS=: read deck scope when <<< "$spec"
  repo=/mpac/sdicks02/repos/clasher-cards; [ $when = before ] && repo=$J/repo-before
  pins=r1-total; [ $scope = full ] && pins=r1-cards1
  ( cd $repo && CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=$pins \
      taskset -c $CORES nice -n 10 $PY -B reports/cards/runtime/tools/decision_timing.py --deck $deck --decisions 60 \
      --out $O/$deck-$scope-$when.jsonl > $O/$deck-$scope-$when.log 2>&1 )
  echo "$spec rc $? $(date -u +%FT%TZ) load $(cut -d' ' -f1 /proc/loadavg)"
done
