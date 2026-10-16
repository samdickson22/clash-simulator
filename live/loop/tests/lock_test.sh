#!/usr/bin/env bash
# Single-instance lock (05, no Mac): driver A runs; driver B with the same lock file must exit at once with a clear
# message and create no run dir; after A exits, driver C starts.   tests/lock_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
T=$(mktemp -d)
export PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
  CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=4 CUDA_VISIBLE_DEVICES= \
  LL_DECK_FILE=$T/deck.json LL_PAUSE_FILE=$T/PAUSE LL_LOCK_FILE=$T/driver.lock
run() { timeout 120 nice -n 10 taskset -c 24-31 $BOTPY -B $LOOP/drive.py --out $T/$1 --source replay:/mpac/sdicks02/scratch/live-loop/rec/ladder1-r1 \
  --tap none --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port 0 --seconds $2; }
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
run A 25 > $T/A.log 2>&1 &
APID=$!
sleep 4
t0=$(date +%s); run B 25 > $T/B.log 2>&1; brc=$?; t1=$(date +%s)
check "second driver refused (non-zero exit)" '[ $brc -ne 0 ]'
check "refusal is immediate (< 5 s)" '[ $((t1 - t0)) -lt 5 ]'
check "refusal names the holder (pid + run of A)" 'grep -qE "another driver holds .*pid [0-9]+ out $T/A " $T/B.log'
check "no run dir for the refused driver" '[ ! -e $T/B ]'
check "first driver still running" 'kill -0 $APID'
wait $APID
run C 8 > $T/C.log 2>&1; crc=$?
check "after A exits, a new driver starts (lock released)" '[ -d $T/C ] && grep -q "\"ev\": \"loaded\"" $T/C/events.jsonl'
# stale lock after a crash: kill -9 the driver (flock is released by the kernel), a new driver must start
run D 60 > $T/D.log 2>&1 &
DPID=$!
sleep 15
DRV=$(sed -n 's/^pid \([0-9]*\) .*/\1/p' $T/driver.lock)        # the python driver itself (not the timeout wrapper)
kill -9 $DRV; wait $DPID 2>/dev/null
sleep 1
run E 8 > $T/E.log 2>&1
check "after kill -9 (stale lock file), a new driver starts" '[ -d $T/E ] && grep -q "\"ev\": \"loaded\"" $T/E/events.jsonl'
echo "$pass passed, $fail failed  (logs: $T)"
[ "$fail" = 0 ]
