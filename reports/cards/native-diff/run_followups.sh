#!/usr/bin/env bash
# Run only after batch/finished.utc, beneath the same 16-CPU lease and nice 15.
set -uo pipefail
job_dir=${1:?job directory}
test -f "$job_dir/batch/finished.utc" || exit 2
cd /mpac/sdicks02/jobs/clasher/cards/root || exit 1
export PYTHONPATH=../out-total:engine-rs:src
export CARDS_GAMEDATA=$PWD/gamedata.json
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python_bin=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
mkdir -p "$job_dir/followups"
pids=()
: > "$job_dir/followups/pids.tsv"
for ((i=0; i<12; i++)); do
    "$python_bin" -B "$job_dir/mixed_games.py" worker \
        --plan "$job_dir/control-plan.json" --worker "$i" --workers 12 \
        --output "$job_dir/controls/games" --config-cache "$job_dir/config-681b5f2c.json" \
        > "$job_dir/followups/control-$i.log" 2>&1 &
    pid=$!
    pids+=("$pid")
    printf 'control\t%s\t%s\n' "$i" "$pid" >> "$job_dir/followups/pids.tsv"
done
for ((i=0; i<4; i++)); do
    "$python_bin" -B "$job_dir/triage_cases.py" \
        --directory "$job_dir/batch/games" --config "$job_dir/config-681b5f2c.json" \
        --worker "$i" --workers 4 --output "$job_dir/triage" \
        > "$job_dir/followups/triage-$i.log" 2>&1 &
    pid=$!
    pids+=("$pid")
    printf 'triage\t%s\t%s\n' "$i" "$pid" >> "$job_dir/followups/pids.tsv"
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid"
    code=$?
    printf '%s\t%s\n' "$pid" "$code" >> "$job_dir/followups/exits.tsv"
    (( code == 0 )) || status=1
done
date -u +%FT%TZ > "$job_dir/followups/finished.utc"
exit "$status"
