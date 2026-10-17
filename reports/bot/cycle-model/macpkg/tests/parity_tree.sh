#!/usr/bin/env bash
# run parity_tree.py for the 6 (tree, mode) arms sequentially on this host (08); env as bot/cyclemodel parity runs
set -euo pipefail
J=/mpac/sdicks02/jobs/clasher/bot-cycle; T=$J/pkg-trees; OUT=$J/pkgparity.jsonl
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
  CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3 \
  CLASHER_DELAY_NATIVE_DIR=/mpac/sdicks02/repos/clasher-bot-runtime/live16402b-r3/native \
  CLASHER_BOT_RUNTIME_PINS=live16402b-r3 CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/bot-fullpool/lopp-fp \
  BOT_FULLPOOL_POLICIES="v1=/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/main02-fp.pt,R3a=/mpac/sdicks02/jobs/clasher/bot-fullpool/ext/R3a-fp.pt"
export NUMBA_CACHE_DIR=/mpac/sdicks02/cache/numba-cycle
unset BOT_CYCLE_MODEL BOT_BELIEF_PRIOR BOT_CYCLE_PREAL
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python; N=K4L-R-gs-mk1a1-res,K4L-R-gs-rw-fc-t2-mk1a1-res
echo "start $(date -u +%FT%TZ)"
cd /tmp
for arm in base-W:off cyc-W:off cyc-W:soft base-P:off cyc-P:off cyc-P:soft; do
  t=${arm%%:*}; m=${arm##*:}
  nice -n 15 $PY -B $J/parity_tree.py $OUT --tree $T/$t --label $t --mode $m --names $N --cases 0-9 --procs ${PROCS:-20}
  echo "$arm done $(date -u +%T)"
done
echo "end $(date -u +%FT%TZ)"
