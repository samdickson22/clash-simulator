#!/usr/bin/env bash
# On 04/08 only, under cpu_job.sh 4 and nice -n 15. A new immutable run directory
# contains tree/ (engine-cards snapshot), tools/ (this script + review_regressions.py),
# and root/ (engine-rs -> ../tree, src -> ../tree/py/src, gamedata -> ../tree/py/gamedata.json).
# Usage: review_jobs.sh RUN_DIR supplemental
set -euo pipefail
A=$(realpath "${1:?run directory}")
phase=${2:?phase}
case $(hostname -s) in 127x04|127x08) ;; *) echo '04/08 only' >&2; exit 2;; esac
case "$A" in /mpac/sdicks02/jobs/clasher/cards/b1/review-r1-*) ;; *) exit 2;; esac
case "$phase" in supplemental) ;; *) exit 2;; esac
exec 9>"$A/run.lock"
flock -n 9 || exit 3
[[ ! -e "$A/$phase.done" ]] || { echo 'receipt exists; refusing duplicate' >&2; exit 3; }
[[ -f "$A/build.done" && -f "$A/test.done" && -f "$A/affected.done" ]]
set -o noclobber
exec >"$A/$phase.log" 2>&1
set +o noclobber
child=
group_alive() {
  ps -eo pgid=,stat= | awk -v g="$child" '$1==g && $2 !~ /^Z/ {alive=1} END {exit !alive}'
}
reap_group() {
  [[ -n "$child" ]] || return 0
  kill -TERM -- "-$child" 2>/dev/null || true
  for ((attempt=0; attempt<50; attempt++)); do
    group_alive || break
    sleep 0.1
  done
  if group_alive; then kill -KILL -- "-$child" 2>/dev/null || true; fi
  # Keep the run lock and CPU lease until every non-zombie group member is gone.
  while group_alive; do sleep 0.1; done
  wait "$child" 2>/dev/null || true
  child=
}
trap reap_group EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
run() {
  setsid "$@" &
  child=$!
  local status=0
  wait "$child" || status=$?
  reap_group
  return "$status"
}
export PYTHONOPTIMIZE=0 NUMBA_DISABLE_JIT=1
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
ES=$R1/reports/strategy_council_20260928/engine-speed
printf '%s pid=%s phase=%s\n' "$(date -u +%FT%TZ)" "$$" "$phase"
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256)
sha256sum -c --quiet "$A/native.sha256"
(cd "$A/supplemental" && sha256sum -c --quiet tools.sha256)
export CLASHER_ROOT=$A/root PYTHONPATH=$A/out:$A/tree:$A/tree/py/src:$ES
run nice -n 15 "$PY" -B "$A/supplemental/supplemental.py" "$A/supplemental/result.json"
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256)
sha256sum -c --quiet "$A/native.sha256"
(cd "$A/supplemental" && sha256sum -c --quiet tools.sha256)
printf '%s pid=%s phase=%s\n' "$(date -u +%FT%TZ)" "$$" "$phase" > "$A/$phase.done"
