#!/usr/bin/env bash
# Keep Numba caches writable outside read-only runtime roots; preserve caller overrides.
export NUMBA_CACHE_DIR=${NUMBA_CACHE_DIR:-/mpac/sdicks02/cache/numba}
set -uo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2
export PYTHONHASHSEED=0 NUMPY_MADVISE_HUGEPAGE=0 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="$job:/mpac/sdicks02/repos/clasher-bot-deckopt2"
cd /mpac/sdicks02/repos/clasher-bot-deckopt2
while [[ ! -f "$job/STOP-REFRESH" ]]; do
  for host in 127x01 127x03 127x04; do
    for stage in screen new-cards/screen final-validation/validation; do
      if [[ -f "$job/$stage/bank.json" ]]; then
        mkdir -p "$job/$stage/rows"
        rsync -a --ignore-missing-args "$host:$job/$stage/rows/" "$job/$stage/rows/" 2>/dev/null || true
      fi
    done
  done
  /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -c "import runpy;runpy.run_path('$job/refresh.py',run_name='__main__')" || break
  rsync -a "$job/REPORT.md" "$job/status.json" "$job/PROGRESS.md" 127x01:"$job/" || true
  sleep 60
done
