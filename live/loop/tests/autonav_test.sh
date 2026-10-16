#!/usr/bin/env bash
# Autonav between battles on the live path (05, no Mac): fake bsgrab streams real guest screens 8 s each, fake adb logs
# taps. Expect taps ONLY on result OK (its own row). Reward presenters remain unknown for deferred manual handling;
# searching-with-Cancel, this Collection fixture, the picker and a synthetic smooth Buy target emit no taps.
# Other Collection / Pass variants already match road; this test does not establish purchase-screen safety.
# tests/autonav_test.sh  (env: BOTPY, SHOTS)
set -u
export LL_MANIFEST_SKIP=1     # the deployment manifest guard has its own test (manifest_test.sh)
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
SHOTS=${SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
RUNS=${RUNS:-/mpac/sdicks02/scratch/live-loop/runs}
T=$(mktemp -d)
# Temporary fixture only: reproduce the review's Buy button over the former reward tap point.
nice -n 19 /mpac/sdicks02/scratch/live-loop/venv/bin/python -B - "$T/buy.png" <<'PY'
import sys
import cv2
import numpy as np
cv2.setNumThreads(1)
f = np.full((1920, 1080, 3), 245, np.uint8)
cv2.putText(f, 'Google Play', (240, 500), cv2.FONT_HERSHEY_SIMPLEX, 1.7, (30, 30, 30), 3)
cv2.putText(f, 'Confirm purchase', (220, 900), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (30, 30, 30), 2)
cv2.rectangle(f, (200, 1430), (880, 1570), (90, 155, 35), -1)
cv2.putText(f, 'BUY', (450, 1520), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
assert cv2.imwrite(sys.argv[1], f)
PY
IMGS=$SHOTS/sol-s23-second-home.png:$SHOTS/sol-s23-chest-1.png:$SHOTS/sol-s22-selected.png:$SHOTS/sol-mini-choice-ready.png:$SHOTS/sol-s23-next-open.png:$T/buy.png:$RUNS/s22/m02/video/000040.jpg
export PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
  CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENCV_FOR_THREADS_NUM=1 CUDA_VISIBLE_DEVICES= \
  LL_ADB=$HERE/fake_adb.sh FAKE_ADB_LOG=$T/adb.log LL_DECK_FILE=$T/deck.json LL_PAUSE_FILE=$T/PAUSE LL_LOCK_FILE=$T/driver.lock \
  FAKE_IMAGES=$IMGS FAKE_HOLD=80
printf '#!/bin/sh\nexec %s %s "$@"\n' /mpac/sdicks02/scratch/live-loop/venv/bin/python "$HERE/fake_bsgrab.py" > $T/bsgrab
chmod +x $T/bsgrab
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
nice -n 19 $BOTPY -B $LOOP/drive.py --out $T/run --source live --bsgrab $T/bsgrab --tap adb --autonav \
  --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port 0 --seconds 90 \
  > $T/drive.log 2>&1
EV=$(ls $T/run/m01/events.jsonl $T/run/events.jsonl 2>/dev/null | head -1)   # no battle: the session dir itself
taps() { grep -o 'input tap [0-9]* [0-9]*' $T/adb.log 2>/dev/null | sort | uniq -c; }
echo "taps:"; taps
check "driver ran (events written)" '[ -s $EV ]'
check "reward presenters / synthetic Buy target never receive the former background tap" '! grep -q "input tap 540 1500" $T/adb.log'
check "result variant: OK tapped on its own row (705, y 1700..1880)" 'grep -Eq "input tap 705 1(7|8)[0-9][0-9]" $T/adb.log'
check "no other taps (reward / Buy / Cancel / this Collection / picker / Battle / road OK)" \
  '[ -z "$(grep -o "input tap [0-9]* [0-9]*" $T/adb.log | grep -Ev "input tap 705 1(7|8)[0-9][0-9]")" ]'
check "nav_tap events only for result, never reward" \
  '[ -z "$(grep "\"ev\": \"nav_tap\"" $EV | grep -v "\"screen\": \"result\"")" ]'
check "the driver did not crash" '! grep -q Traceback $T/drive.log'
echo "$pass passed, $fail failed  (logs: $T)"; [ "$fail" = 0 ]
