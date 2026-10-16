#!/usr/bin/env bash
# On 04/08 only, under cpu_job.sh 4 and nice -n 15. A new immutable run directory
# contains tree/ (engine-cards snapshot), tools/ (this script + review_regressions.py),
# and root/ (engine-rs -> ../tree, src -> ../tree/py/src, gamedata -> ../tree/py/gamedata.json).
# Usage: review_jobs.sh RUN_DIR build|test|affected|gate
set -euo pipefail
A=$(realpath "${1:?run directory}")
phase=${2:?phase}
case $(hostname -s) in 127x04|127x08) ;; *) echo '04/08 only' >&2; exit 2;; esac
case "$A" in /mpac/sdicks02/jobs/clasher/cards/b1/review-r1-*) ;; *) exit 2;; esac
case "$phase" in build|test|affected|gate) ;; *) exit 2;; esac
exec 9>"$A/run.lock"
flock -n 9 || exit 3
[[ ! -e "$A/$phase.done" ]] || { echo 'receipt exists; refusing duplicate' >&2; exit 3; }
case "$phase" in
  test) [[ -f "$A/build.done" ]];;
  affected) [[ -f "$A/build.done" && -f "$A/test.done" ]];;
  gate) [[ -f "$A/build.done" && -f "$A/test.done" && -f "$A/affected.done" && -f "$A/reference.done" ]];;
esac
set -o noclobber
exec >"$A/$phase.log" 2>&1
set +o noclobber
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256)
if [[ "$phase" != build ]]; then sha256sum -c --quiet "$A/native.sha256"; fi
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
case "$phase" in
build)
  export CARGO_HOME=/mpac/sdicks02/tools/cargo RUSTUP_HOME=/mpac/sdicks02/tools/rustup
  export PATH=/mpac/sdicks02/tools/cargo/bin:$PATH CARGO_TARGET_DIR=$A/out/target CARGO_INCREMENTAL=0 PYO3_PYTHON=$PY
  mkdir "$A/out"
  run nice -n 15 cargo +1.97.1 build --offline --manifest-path "$A/tree/Cargo.toml" --release --features extension-module,gil-release -j 4
  cp "$A/out/target/release/libclasher_core.so" "$A/out/clasher_core.abi3.so"
  sha256sum "$A/out/clasher_core.abi3.so" > "$A/native.sha256"
  ;;
test)
  export CLASHER_ROOT=$A/root PYTHONPATH=$A/out:$A/tree:$A/tree/py/src:$ES
  run nice -n 15 "$PY" -B "$A/tools/review_regressions.py" "$A/regressions.json"
  ;;
affected)
  export CLASHER_ROOT=$A/root PYTHONPATH=$A/out:$A/tree:$A/tree/py/src:$ES
  run nice -n 15 "$PY" -B "$A/tools/affected.py" "$A/affected.json"
  ;;
gate)
  # Reuse immutable pinned-arm receipts from the completed B1 final gate.
  # Run only the changed arm; never rewrite the original gate or runtime.
  BASE=/mpac/sdicks02/jobs/clasher/cards/b1/gate
  PIN=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1/clasher_core.abi3.so
  [[ $(sha256sum "$PIN" | cut -d' ' -f1) == 681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b ]]
  cmp "$BASE/compare.json" "$A/original-compare.json"
  (cd "$BASE" && sha256sum -c "$A/pinned-expected.sha256")
  G=$A/gate
  mkdir "$G"
  cp "$BASE/fixtures-pinned.jsonl" "$G/"
  for i in 0 1 2 3; do cp "$BASE/roots-pinned-$i.jsonl" "$G/"; done
  sha256sum "$G"/*pinned*.jsonl > "$A/pinned-receipts.sha256"
  T=/mpac/sdicks02/jobs/clasher/cards/b1/gate-tools
  cd /mpac/sdicks02/repos/clasher-bot
  CLASHER_ROOT=$A/root PYTHONPATH=$A/out:$A/tree:$A/tree/py/src:$ES:/mpac/sdicks02/repos/clasher-bot \
    run nice -n 15 "$PY" -B "$T/parity_fixtures.py" --out "$G/fixtures-total.jsonl" --workers 3 > "$G/fixtures-total.log" 2>&1
  for i in 0 1 2 3; do
    CLASHER_BOT_RUNTIME=$A/root CLASHER_DELAY_NATIVE_DIR=$A/out \
      run nice -n 15 "$PY" -B "$T/parity_roots.py" --roots /mpac/sdicks02/jobs/clasher/cards/b1/roots \
      --sample 300 --shard "$i/4" --out "$G/roots-total-$i.jsonl" > "$G/roots-total-$i.log" 2>&1
  done
  "$PY" -B "$T/compare.py" "$G" > "$G/compare.json"
  "$PY" -B "$A/tools/review_gate_assert.py" "$G/compare.json"
  cat "$G/compare.json"
  ;;
esac
(cd "$A" && sha256sum -c --quiet source.sha256 && sha256sum -c --quiet tools.sha256)
sha256sum -c --quiet "$A/native.sha256"
printf '%s pid=%s phase=%s\n' "$(date -u +%FT%TZ)" "$$" "$phase" > "$A/$phase.done"
