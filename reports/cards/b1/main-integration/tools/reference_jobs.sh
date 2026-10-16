#!/usr/bin/env bash
# On 04/08 only, under cpu_job.sh 4 and nice -n 15. A new immutable run directory
# contains tree/ (engine-cards snapshot), tools/ (this script + review_regressions.py),
# and root/ (engine-rs -> ../tree, src -> ../tree/py/src, gamedata -> ../tree/py/gamedata.json).
# Usage: review_jobs.sh RUN_DIR reference
set -euo pipefail
A=$(realpath "${1:?run directory}")
phase=${2:?phase}
case $(hostname -s) in 127x04|127x08) ;; *) echo '04/08 only' >&2; exit 2;; esac
case "$A" in /mpac/sdicks02/jobs/clasher/cards/b1/review-r1-*) ;; *) exit 2;; esac
case "$phase" in reference) ;; *) exit 2;; esac
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
OLD=/mpac/sdicks02/jobs/clasher/cards/b1/review-r1-20261016-04/tree
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet original-source.sha256 && sha256sum -c --quiet tools.sha256)
sha256sum -c --quiet "$A/native.sha256"
cmp "$OLD/py/gamedata.json" "$A/tree/py/gamedata.json"
mkdir "$A/reference" "$A/root-before" "$A/root-after"
run nice -n 15 "$PY" -B "$A/tools/apply_stats.py" "$A/tree/py/gamedata.json" "$A/stats-spec.json" "$A/reference/gamedata.json"
for entry in "$A/root/"*; do
  name=${entry##*/}
  case "$name" in engine-rs|src|gamedata.json) continue;; esac
  ln -s "$entry" "$A/root-before/$name"
  ln -s "$entry" "$A/root-after/$name"
done
ln -s "$OLD" "$A/root-before/engine-rs"
ln -s "$OLD/py/src" "$A/root-before/src"
ln -s ../tree "$A/root-after/engine-rs"
ln -s ../tree/py/src "$A/root-after/src"
ln -s ../reference/gamedata.json "$A/root-before/gamedata.json"
ln -s ../reference/gamedata.json "$A/root-after/gamedata.json"
CLASHER_ROOT=$A/root-before FIDELITY_EXPECT_SRC=$OLD/py/src/ PYTHONPATH=$OLD/py/src:$ES:/mpac/sdicks02/repos/clasher-bot \
  run nice -n 15 "$PY" -B "$A/tools/reference.py" probe "$A/reference/before.jsonl"
CLASHER_ROOT=$A/root-after FIDELITY_EXPECT_SRC=$A/tree/py/src/ PYTHONPATH=$A/tree/py/src:$ES:/mpac/sdicks02/repos/clasher-bot \
  run nice -n 15 "$PY" -B "$A/tools/reference.py" probe "$A/reference/after.jsonl"
run nice -n 15 "$PY" -B "$A/tools/reference.py" compare "$A/reference/before.jsonl" "$A/reference/after.jsonl" "$A/reference/compare.json"
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet original-source.sha256 && sha256sum -c --quiet tools.sha256)
sha256sum -c --quiet "$A/native.sha256"
printf '%s pid=%s phase=%s\n' "$(date -u +%FT%TZ)" "$$" "$phase" > "$A/$phase.done"
