#!/usr/bin/env bash
# Assemble + gate r1-cards4-dev / live16402d-dev on 127x04 or 127x08.
#   setsid bot/exit/cpu_job.sh 4 bash pipeline.sh JOB SRC REPO NATIVE_SO [gate steps...]
# JOB must be fresh apart from inputs; SRC = build_runtime --export-only tree, REPO = git archive of the same commit.
set -euo pipefail
J=$1 SRC=$2 REPO=$3 NATIVE=$4; shift 4
case $(hostname -s) in 127x04|127x08) ;; *) echo "wrong host"; exit 2;; esac
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
T=$(cd "$(dirname "$0")" && pwd)
exec >>"$J/pipeline.log" 2>&1
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR CLASHER_BOT_RUNTIME CLASHER_BOT_RUNTIME_PINS
date -u +%FT%TZ; echo "pid=$$ src=$SRC repo=$REPO native=$NATIVE"
sha256sum "$NATIVE" "$T"/*.py "$T"/*.sh
if [[ ! -e $J/repo-eval ]]; then
  # Frozen r3-compatible evaluator (e5c11345d + callers at a6a5401c127b) + this release's pin block only.
  rsync -a /mpac/sdicks02/jobs/clasher/cards/r1-cards3-phase1/repo-eval/ "$J/repo-eval/"
  chmod -R u+w "$J/repo-eval"
  sed -n '/^# r1-cards4 = main/,/tournament_crown_from_gamedata=(.Fireball., .Poison., .Tornado.))/p' \
    "$REPO/bot/players/runtime.py" > "$J/pins.py"
  grep -q "PIN_SETS\['live16402d'\]" "$J/pins.py"
  printf '\n' >> "$J/repo-eval/bot/players/runtime.py"; cat "$J/pins.py" >> "$J/repo-eval/bot/players/runtime.py"
fi
if [[ ! -e $J/ASSEMBLY.json ]]; then
  nice -n 15 "$PY" -B "$T/assemble.py" "$J" "$SRC" "$REPO" "$NATIVE"
fi
nice -n 15 "$PY" -B "$T/gates.py" "$J" "$REPO" "$J/repo-eval" "$@"
date -u +%FT%TZ; echo PIPELINE DONE
