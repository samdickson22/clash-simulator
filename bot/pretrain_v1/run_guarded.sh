#!/bin/bash
# Run one pretrain-v1 job (BC / eval) on a shared fleet host under a host guard, never displacing RL work.
#   run_guarded.sh LOG -- python -m bot.pretrain_v1.train_bc ...
# Guard (every 20 s): MemAvailable < 29 GiB or 1-min load > 90 -> SIGTERM the job's process group (it is resumable
# from its per-epoch checkpoints); the RL guard on 04/08 preempts at 24 GiB, so this stops first. nice 10, own
# process group, GPU visible only when GPU=0 is set. Writes LOG and LOG.guard.
set -u
LOG=$1; shift; [ "$1" = "--" ] && shift
MIN_KB=$((29*1024*1024)); MAX_LOAD=90
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=${OMP_NUM_THREADS:-4} NUMPY_MADVISE_HUGEPAGE=0
export CUDA_VISIBLE_DEVICES=${GPU:-}
setsid nice -n 10 "$@" > "$LOG" 2>&1 &
PID=$!
echo "$(date -u +%FT%TZ) start pid $PID: $*" >> "$LOG.guard"
while kill -0 $PID 2>/dev/null; do
  sleep 20
  avail=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  load=$(awk '{print int($1)}' /proc/loadavg)
  if [ "$avail" -lt "$MIN_KB" ] || [ "$load" -gt "$MAX_LOAD" ]; then
    echo "$(date -u +%FT%TZ) guard stop: MemAvailable ${avail} kB load ${load}" >> "$LOG.guard"
    kill -TERM -- -$PID 2>/dev/null; sleep 10; kill -KILL -- -$PID 2>/dev/null
    exit 75
  fi
done
wait $PID; rc=$?
echo "$(date -u +%FT%TZ) exit $rc" >> "$LOG.guard"
exit $rc
