#!/usr/bin/env bash
# --crop auto (live path, fake bsgrab + fake adb with screencap):
#   A matching adb screencap -> crop_fit event, capture.mode auto in session-config, the session runs (taps)
#   B a different screencap -> exit 3 before any tap, status "REFUSED: auto-crop failed"
#   C window resized mid-session (FAKE_BOUNDS_FILE) -> crop_refit event with the new window, session keeps running
#   tests/autocrop_test.sh   (run from a full tree copy; env: BOTPY, SHOTS)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
VPY=/mpac/sdicks02/scratch/live-loop/venv/bin/python
SHOTS=${SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
T=$(mktemp -d)
printf '#!/bin/sh\nexec %s %s "$@"\n' $VPY "$HERE/fake_bsgrab.py" > $T/bsgrab; chmod +x $T/bsgrab
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
run() {  # run NAME SHOT SECONDS [env...]
  local d=$T/$1 shot=$2 secs=$3; shift 3; mkdir -p $d
  env PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
    CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
    CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
    CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=2 CUDA_VISIBLE_DEVICES= \
    LL_ADB=$HERE/fake_adb_shot.sh FAKE_SHOT=$shot FAKE_IMAGES=$SHOTS/sol-home-ready.png FAKE_HOLD=1000 PYTHONHASHSEED=0 "$@" \
    LL_LOCK_FILE=$d/driver.lock LL_STATUS_FILE=$d/status.txt FAKE_ADB_LOG=$d/adb.log LL_DECK_FILE=$d/deck.json \
    LL_PAUSE_FILE=$d/PAUSE LL_MANIFEST=$d/none.json nice -n 10 $BOTPY -B $R/live/loop/drive.py --out $d/run --source live --bsgrab $T/bsgrab \
    --tap adb --autonav --crop auto --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port 0 \
    --seconds $secs > $d/log 2>&1
  echo $? > $d/rc
}
ev() { grep -h "\"ev\": \"$2\"" $T/$1/run/events.jsonl 2>/dev/null; }
OTHER=$(ls $SHOTS/*.png | grep -v sol-home-ready | head -1)
echo 540,980 > $T/bounds
run A $SHOTS/sol-home-ready.png 25 FAKE_BOUNDS_FILE=$T/bounds &
run B $OTHER 25 &
wait
echo 554,960 > $T/boundsC
( for i in $(seq 120); do ev C crop_fit >/dev/null && break; sleep 1; done; sleep 6; echo 535,926 > $T/boundsC ) &   # resize after the first fit
run C $SHOTS/sol-home-ready.png 60 FAKE_BOUNDS_FILE=$T/boundsC
wait
check "A: crop_fit with a crop, mode auto in session-config, runs (exit 0, taps)" '[ "$(cat $T/A/rc)" = 0 ] && ev A crop_fit | grep -q "\"crop\": \[" && grep -q "\"mode\": \"auto\"" $T/A/run/session-config.json && grep -q "input tap" $T/A/adb.log'
check "B: mismatching screencap -> exit 3, no tap, REFUSED: auto-crop failed" '[ "$(cat $T/B/rc)" = 3 ] && ! grep -q "input tap" $T/B/adb.log 2>/dev/null && grep -q "REFUSED: auto-crop failed" $T/B/status.txt'
check "C: resize mid-session -> crop_refit to the 535x926 window, still exit 0" '[ "$(cat $T/C/rc)" = 0 ] && ev C crop_refit | grep -q "535" && ev C crop_refit | grep -q "\"crop\": \[0.0, 32.0, 503.0, 894.0\]"'
echo "$pass passed, $fail failed  (logs: $T)"; [ "$fail" = 0 ]
