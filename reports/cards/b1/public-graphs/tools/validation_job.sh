#!/usr/bin/env bash
# Candidate validation; independent review required before execution.
set -euo pipefail
J=${1:?fresh run directory}
phase=${2:?phase}
case "$phase" in real-r1|real-live|mixed|headline-baseline|headline-candidate) ;; *) exit 2;; esac
[[ $(hostname -s) == 127x08 ]]
[[ $J == /mpac/sdicks02/jobs/clasher/cards/b1/public-graphs-20261016-02 ]]
exec 9>"$J/run.lock"
flock -n 9
[[ ! -e $J/$phase.done && ! -e $J/$phase.pid ]]
set -o noclobber
exec >"$J/$phase.log" 2>&1
set +o noclobber
(cd "$J" && sha256sum -c inputs.sha256)
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 NUMBA_DISABLE_JIT=1 PYTHONOPTIMIZE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset CLASHER_ROOT CLASHER_EVAL_RUNTIME_ROOT CLASHER_DELAY_NATIVE_DIR BOT_FULLPOOL_POLICIES
case "$phase" in
  headline-baseline)
    export CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 CLASHER_BOT_RUNTIME_PINS=r1-total
    export CLASHER_DELAY_NATIVE_DIR=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1;;
  real-r1|headline-candidate)
    export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards3-dev CLASHER_BOT_RUNTIME_PINS=r1-cards3;;
  *) export CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/cards/runtime/live16402c-dev CLASHER_BOT_RUNTIME_PINS=live16402c;;
esac
export CLASHER_LEVELS_CACHE="$J/levels-$phase"
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
printf '%s pid=%s phase=%s\n' "$(date -u +%FT%TZ)" "$$" "$phase"
printf '%s\n' "$$" > "$J/$phase.pid"
cd /mpac/sdicks02/jobs/clasher/cards/r1-cards3-phase1/repo-eval
setsid nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B "$J/validate.py" "$phase" "$J" &
child=$!
printf '%s\n' "$child" > "$J/$phase.child.pgid"
rc=0; wait "$child" || rc=$?
drain
[[ $rc == 0 ]]
(cd "$J" && sha256sum -c inputs.sha256)
printf '%s pid=%s phase=%s\n' "$(date -u +%FT%TZ)" "$$" "$phase" > "$J/$phase.done"
