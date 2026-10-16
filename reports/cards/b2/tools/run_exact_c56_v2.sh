#!/bin/bash
# Fresh exact-source C56 run, normal cpu_job.sh 4 / nice15. No old gate restart.
set -euo pipefail
J=${1:?JOBDIR}
trap 'code=$?; printf "%s\n" "$code" > "$J/run.exit"' EXIT
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
ES=$R1/reports/strategy_council_20260928/engine-speed
BOT=/mpac/sdicks02/repos/clasher-bot
PIN=$J/pinned-native
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export PYTHONOPTIMIZE=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset BASH_ENV ENV PYTHONHOME PYTHONINSPECT PYTHONSTARTUP
cd "$BOT"
"$PY" -B "$J/tools/exact_c56_receipts_v2.py" identity "$J"
pids=(); labels=()
start() {
    local label=$1; shift
    "$@" > "$J/gate/$label.log" 2>&1 &
    pids+=("$!"); labels+=("$label")
    printf '%s %s\n' "$!" "$label" >> "$J/children.pids"
}
wait_all() {
    local failed=0 code i
    for i in "${!pids[@]}"; do
        if wait "${pids[$i]}"; then code=0; else code=$?; failed=1; fi
        printf '%s\n' "$code" > "$J/gate/${labels[$i]}.exit"
    done
    pids=(); labels=()
    return "$failed"
}
arm() {
    local name=$1; shift
    local root=$R1 native=$PIN
    if [[ "$name" == total ]]; then root=$J/rt; native=$J/total-native; fi
    CLASHER_ROOT=$root CLASHER_EVAL_RUNTIME_ROOT=$root CLASHER_BOT_RUNTIME=$root \
    CLASHER_DELAY_NATIVE_DIR=$native CLASHER_BOT_RUNTIME_PINS=r1-total \
    PYTHONPATH="$native:$root/engine-rs:$root/src:$ES:$BOT" nice -n 15 "$PY" -B "$@"
}
# Two fixture pools of two workers = four active simulation workers.
start fixtures-pinned arm pinned "$J/tools/observe_c56_fixtures_v2.py" "$J/canonical/parity_fixtures.py" "$J/gate/audit-pinned" --out "$J/gate/fixtures-pinned.jsonl" --workers 2
start fixtures-total arm total "$J/tools/observe_c56_fixtures_v2.py" "$J/canonical/parity_fixtures.py" "$J/gate/audit-total" --out "$J/gate/fixtures-total.jsonl" --workers 2
wait_all
for name in pinned total; do
    for shard in 0 1; do
        start roots-$name-$shard arm "$name" "$J/canonical/parity_roots.py" --roots "$J/roots" --sample 300 --shard "$shard/2" --out "$J/gate/roots-$name-$shard.jsonl"
    done
done
wait_all
"$PY" -B "$J/canonical/compare.py" "$J/gate" > "$J/gate/compare.json"
"$PY" -B "$J/tools/exact_c56_receipts_v2.py" validate "$J"
