#!/bin/bash
# HEADLINE K4L command-hash gate (08, under bot/exit/cpu_job.sh 16): CAND (default K4L-R-gs-rw-fc-p2) vs OPPS (R3a,v1), cases 0..G-1,
# four arms on the dev root, PYTHONHASHSEED=0:
#   c56-before / full-before = repo-before (lopp_fast.py at HEAD, r1-cards1 without fc_side_cut: the 01:45Z state)
#   c56-after  / full-after  = repo (lopp_fast content-hash pool cache + base_cut; r1-cards1 with fc_side_cut)
#   c56 = pins r1-total, full = pins r1-cards1. Expected: identical command_sha256 per case across all four.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
DEV=$J/r1-cards1-dev; O=$J/gate; mkdir -p $O
G=${G:-6}
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
echo "start $(date -u +%FT%TZ)"
pids=()
for arm in c56-before c56-after full-before full-after; do
  scope=${arm%%-*}; when=${arm#*-}
  repo=$J/repo; [ $when = before ] && repo=$J/repo-before
  pins=r1-total; [ $scope = full ] && pins=r1-cards1
  ( cd $repo && CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=$pins \
      nice -n 15 $PY -B -m bot.eval.headline --out $O/hl-${TAG:-k4l}-$arm --candidate ${CAND:-K4L-R-gs-rw-fc-p2} --opponents ${OPPS:-R3a,v1} \
      --games $G --workers 1 > $O/hl-${TAG:-k4l}-$arm.log 2>&1 ) & pids+=($!)
done
for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
echo "end $(date -u +%FT%TZ)"
