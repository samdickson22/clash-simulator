#!/usr/bin/env bash
# Launch one detached, leased, niced shard job on THIS host (run via ssh on 127x03/04/08).
#   run_host.sh OUT TAG A:B WORKERS [extra gen_shards.py args...]
# Uses /mpac/sdicks02/jobs/clasher/yolo-synth-20261016/{venv,code,bank}; log -> logs/TAG-A-B.log; prints the PID.
set -euo pipefail
W=/mpac/sdicks02/jobs/clasher/yolo-synth-20261016
out=$1; tag=$2; shards=$3; workers=$4; shift 4
mkdir -p "$out" "$W/logs"
log="$W/logs/$tag-${shards/:/-}.log"
cd "$W"
setsid nohup nice -n 19 env NUMPY_MADVISE_HUGEPAGE=0 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 \
  /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh $((workers+1)) \
  "$W/venv/bin/python" "$W/code/gen_shards.py" --bank "$W/bank" --out "$out" --tag "$tag" --shards "$shards" \
  --workers "$workers" "$@" > "$log" 2>&1 < /dev/null &
echo "$(hostname) PID $! log $log"
