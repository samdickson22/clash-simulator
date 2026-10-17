#!/bin/bash
# cards/levels gates (run on 04/08 under bot/exit/cpu_job.sh, launched with bot/detach.sh). J = job dir with
# repo/ (this branch) and repo-before/ (git archive of origin/main 7065dc345).
#   gates.sh 1a ROOTNAME PINS    K4L HEADLINE parity: CAND (K4L-R-gs-rw-fc-p2) vs R3a,v1, cases 0..5, before/after
#   gates.sh 1b                  full-pool K4L-R-gs-mk1a1 vs R3a,v1 on LIVE-AB1 cases 0..G-1 (5), before/after
#   gates.sh 3                   no-crash: K4L-R-gs-mk1a1 vs R3a on LIVE-AB1 cases 0..G-1 (4), --levels max
# Expected: identical command_sha256 per (candidate, opponent, case) before vs after (1a, 1b); 0 errors (3).
set -uo pipefail
LJ=${LJ:-/mpac/sdicks02/jobs/clasher/cards/levels}
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
O=$LJ/gates; mkdir -p $O
gate=${1:?gate}
echo "start $gate $(date -u +%FT%TZ) host $(hostname)"
pids=()
case $gate in
  1a)
    rootname=${2:?root}; pins=${3:?pins}; ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/$rootname
    export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
      CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0
    for when in before after; do
      repo=$LJ/repo; [ $when = before ] && repo=$LJ/repo-before
      ( cd $repo && CLASHER_BOT_RUNTIME=$ROOT CLASHER_DELAY_NATIVE_DIR=$ROOT/native CLASHER_BOT_RUNTIME_PINS=$pins \
          nice -n 15 $PY -B -m bot.eval.headline --out $O/1a-$pins-$when --candidate ${CAND:-K4L-R-gs-rw-fc-p2} \
          --opponents R3a,v1 --games ${G:-6} --workers ${W:-1} > $O/1a-$pins-$when.log 2>&1 ) & pids+=($!)
    done ;;
  1b)
    for when in before after; do
      repo=$LJ/repo; [ $when = before ] && repo=$LJ/repo-before
      ( export ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/live16402c PINS=live16402c
        cd $repo && source bot/fullpool/run/env.sh
        nice -n 15 $PY -B -m bot.eval.headline --out $O/1b-$when --candidate K4L-R-gs-mk1a1 --opponents R3a,v1 \
          --games ${G:-5} --workers ${W:-2} --bank LIVE-AB1 > $O/1b-$when.log 2>&1 ) & pids+=($!)
    done ;;
  3)
    ( export ROOT=/mpac/sdicks02/repos/clasher-bot-runtime/live16402c PINS=live16402c
      cd $LJ/repo && source bot/fullpool/run/env.sh
      export CLASHER_LEVELS_CACHE=$LJ/level-configs BOT_PLAYLOG=1
      nice -n 15 $PY -B -m bot.eval.headline --out $O/3-max --candidate ${CAND3:-K4L-R-gs-mk1a1} --opponents R3a \
        --games ${G:-4} --workers ${W:-2} --bank LIVE-AB1 --levels max > $O/3-max.log 2>&1 ) & pids+=($!) ;;
esac
for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
echo "end $gate $(date -u +%FT%TZ)"
