#!/usr/bin/env bash
# Low-disk handling (05, no Mac). Thresholds via env so 05's large free space counts as "low":
#  A) pause threshold above free space, live path on home frames: low_disk event, paused reason low_disk, NO taps
#  B) same thresholds, replay of a real battle: the battle in progress is still played (decisions made)
#  C) stop floor above free space: the driver refuses to start
#   tests/low_disk_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
SHOTS=${SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
export PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
  CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=4 CUDA_VISIBLE_DEVICES= \
  LL_ADB=$HERE/fake_adb.sh
EXP=/mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
A=$(mktemp -d); B=$(mktemp -d); C=$(mktemp -d)
printf '#!/bin/sh\nexec %s %s "$@"\n' /mpac/sdicks02/scratch/live-loop/venv/bin/python "$HERE/fake_bsgrab.py" > $A/bsgrab; chmod +x $A/bsgrab
( export LL_DISK_PAUSE_GB=1000000 LL_DISK_RESUME_GB=2000000 LL_DISK_STOP_GB=0 LL_DECK_FILE=$A/deck.json \
    LL_PAUSE_FILE=$A/PAUSE LL_LOCK_FILE=$A/driver.lock FAKE_ADB_LOG=$A/adb.log FAKE_IMAGES=$SHOTS/nx2.png FAKE_HOLD=1000
  timeout 120 nice -n 10 taskset -c 24-31 $BOTPY -B $LOOP/drive.py --out $A/run --source live --bsgrab $A/bsgrab --tap adb \
    --autonav --export $EXP --overlay-port 0 --seconds 25 > $A/log 2>&1 ) &
( export LL_DISK_PAUSE_GB=1000000 LL_DISK_RESUME_GB=2000000 LL_DISK_STOP_GB=0 LL_DECK_FILE=$B/deck.json \
    LL_PAUSE_FILE=$B/PAUSE LL_LOCK_FILE=$B/driver.lock
  timeout 300 nice -n 10 taskset -c 32-39 $BOTPY -B $LOOP/drive.py --out $B/run \
    --source replay:/mpac/sdicks02/scratch/live-loop/rec/ladder1-r1 --no-realtime --tap none --export $EXP \
    --overlay-port 0 --seconds 120 > $B/log 2>&1 ) &
wait
check "A: low_disk event" 'grep -q "\"ev\": \"low_disk\"" $A/run/events.jsonl'
check "A: paused with reason low_disk" 'grep -q "\"reason\": \"low_disk\"" $A/run/events.jsonl'
check "A: no taps while low on disk (home frames)" '[ ! -s $A/adb.log ]'
check "A: no stop event" '! grep -q "\"ev\": \"stop\"" $A/run/events.jsonl'
check "B: battle in progress still played (decisions)" '[ "$(grep -c submitted $B/run/decisions.jsonl)" -gt 10 ]'
check "B: not paused during the battle" '! grep -q "\"reason\": \"low_disk\", \"state\": \"battle\"" $B/run/events.jsonl'
LL_DISK_STOP_GB=1000000 LL_DECK_FILE=$C/deck.json LL_PAUSE_FILE=$C/PAUSE LL_LOCK_FILE=$C/driver.lock \
  timeout 60 $BOTPY -B $LOOP/drive.py --out $C/run --source replay:/mpac/sdicks02/scratch/live-loop/rec/ladder1-r1 \
  --tap none --export $EXP --overlay-port 0 --seconds 10 > $C/log 2>&1; crc=$?
check "C: below the stop floor the driver refuses to start" '[ $crc -ne 0 ] && grep -q "stop floor" $C/log'
echo "$pass passed, $fail failed  (logs: $A $B $C)"
[ "$fail" = 0 ]
