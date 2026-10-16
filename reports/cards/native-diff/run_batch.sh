#!/usr/bin/env bash
# Called beneath setsid, nice -n 15 and BOT LEAD's cpu_job.sh N.
set -uo pipefail
job_dir=${1:?job directory}
plan=${2:?plan}
workers=${3:-16}
label=${4:-batch}
cd /mpac/sdicks02/jobs/clasher/cards/root || exit 1
export PYTHONPATH=../out-total:engine-rs:src
export CARDS_GAMEDATA=$PWD/gamedata.json
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python_bin=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
mkdir -p "$job_dir/$label"
pids=()
: > "$job_dir/$label/pids.tsv"
for ((i=0; i<workers; i++)); do
    "$python_bin" -B "$job_dir/mixed_games.py" worker --plan "$plan" \
        --worker "$i" --workers "$workers" --output "$job_dir/$label/games" \
        --config-cache "$job_dir/config-681b5f2c.json" \
        > "$job_dir/$label/worker-$i.log" 2>&1 &
    pid=$!
    pids+=("$pid")
    printf '%s\t%s\n' "$i" "$pid" >> "$job_dir/$label/pids.tsv"
done
status=0
for pid in "${pids[@]}"; do
    wait "$pid"
    code=$?
    printf '%s\t%s\n' "$pid" "$code" >> "$job_dir/$label/exits.tsv"
    (( code == 0 )) || status=1
done
date -u +%FT%TZ > "$job_dir/$label/finished.utc"
exit "$status"
