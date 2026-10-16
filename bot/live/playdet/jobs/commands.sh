#!/usr/bin/env bash
# Print plain invocations for the LIVE LEAD's cpu_job.sh lease; do not run jobs.
set -euo pipefail
out=${1:?usage: commands.sh OUTPUT_ROOT [SHARDS=16]}
shards=${2:-16}
[[ "$shards" =~ ^[1-9][0-9]*$ ]] || exit 2
for source in t1-train t1-validation sim; do
    for ((shard=0; shard<shards; shard++)); do
        printf 'PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 nice -n 19 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -m bot.live.playdet.build --source %q --shard %q --threads 1 --out %q\n' "$source" "$shard/$shards" "$out/$source"
    done
done
