#!/usr/bin/env bash
# Reviewed entrypoint; invoke with setsid cpu_job.sh 4 nice -n15 bash ... RUN.
set -euo pipefail
J=${1:?fresh run directory}
[[ $(hostname -s) == 127x08 ]]
[[ $J == /mpac/sdicks02/jobs/clasher/cards/b1/public-graphs-20261016-01 ]]
exec 9>"$J/run.lock"
flock -n 9
[[ ! -e $J/capture.done && ! -e $J/capture ]]
set -o noclobber
exec >"$J/capture.log" 2>&1
set +o noclobber
(cd "$J" && sha256sum -c inputs.sha256)
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMBA_DISABLE_JIT=1 PYTHONOPTIMIZE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/live16402c-dev CLASHER_BOT_RUNTIME_PINS=live16402c
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR
child=
alive() { ps -eo pgid=,stat= | awk -v g="$child" '$1==g && $2 !~ /^Z/ {a=1} END {exit !a}'; }
drain() {
  [[ -n $child ]] || return 0
  kill -TERM -- "-$child" 2>/dev/null || true
  for ((n=0;n<50;n++)); do alive || break; sleep .1; done
  if alive; then kill -KILL -- "-$child" 2>/dev/null || true; fi
  while alive; do sleep .1; done
  wait "$child" 2>/dev/null || true
  child=
}
trap drain EXIT
trap 'exit 143' TERM HUP
trap 'exit 130' INT
printf '%s pid=%s phase=capture\n' "$(date -u +%FT%TZ)" "$$"
printf '%s\n' "$$" > "$J/wrapper.pid"
cd /mpac/sdicks02/jobs/clasher/cards/r1-cards3-phase1/repo-eval
setsid nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B "$J/capture_mixed.py" "$PWD" "$J/capture" &
child=$!
printf '%s\n' "$child" > "$J/child.pgid"
rc=0; wait "$child" || rc=$?
drain
[[ $rc == 0 ]]
(cd "$J" && sha256sum -c inputs.sha256)
printf '%s pid=%s phase=capture\n' "$(date -u +%FT%TZ)" "$$" > "$J/capture.done"
