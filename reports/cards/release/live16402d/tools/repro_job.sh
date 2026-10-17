#!/usr/bin/env bash
# setsid bot/exit/cpu_job.sh 2 nice -n15 bash repro_job.sh JOBDIR   (127x04/08 only)
set -euo pipefail
J=${1:?fresh job dir holding repro_mixed.py + public_root.py}
case $(hostname -s) in 127x04|127x08) ;; *) exit 2;; esac
[[ ! -e $J/out ]]
exec >"$J/repro.log" 2>&1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMBA_DISABLE_JIT=1 NUMPY_MADVISE_HUGEPAGE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
export CLASHER_BOT_RUNTIME=${RUNTIME:-/mpac/sdicks02/jobs/clasher/cards/runtime/live16402c-dev}
export CLASHER_BOT_RUNTIME_PINS=${PINS:-live16402c}
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
date -u +%FT%TZ; sha256sum "$J"/repro_mixed.py "$J"/public_root.py
cd "${EVAL:-/mpac/sdicks02/jobs/clasher/cards/r1-cards3-phase1/repo-eval}"
rc=0; nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B "$J/repro_mixed.py" "$PWD" "$J/public_root.py" "$J/out" || rc=$?
date -u +%FT%TZ; echo "rc=$rc" > "$J/repro.done"
