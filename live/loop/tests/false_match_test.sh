#!/usr/bin/env bash
# False-match test (05, live path, no Mac): a fake bsgrab streams real screenshots — home, a battle frame (HUD) for a few
# seconds, home again. Case A (running, battle 4 s): one false_match event, dir m01-false-* with false_match.json and no
# session.json, m01 reopened, no m02. Case B (page-paused, battle 1 s): no match_start at all (paused start needs 1.5 s).
#   tests/false_match_test.sh   (env: BOTPY, SHOTS, BATTLE)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
SHOTS=${SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
BATTLE=${BATTLE:-/mpac/sdicks02/scratch/live-loop/runs/s5m01/video/000600.jpg}
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
run_case() {   # $1 = dir, $2 = FAKE_HOLD (frames per image at 10 fps), $3 = extra driver args, $4 = touch PAUSE first (1/0)
  local T=$1
  mkdir -p $T
  printf '#!/bin/sh\nexec %s %s "$@"\n' /mpac/sdicks02/scratch/live-loop/venv/bin/python "$HERE/fake_bsgrab.py" > $T/bsgrab
  chmod +x $T/bsgrab
  [ "$4" = 1 ] && touch $T/PAUSE
  env PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
    CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
    CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
    CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=4 CUDA_VISIBLE_DEVICES= \
    LL_ADB=$HERE/fake_adb.sh FAKE_ADB_LOG=$T/adb.log LL_DECK_FILE=$T/deck.json LL_PAUSE_FILE=$T/PAUSE LL_LOCK_FILE=$T/driver.lock \
    FAKE_IMAGES=$SHOTS/nx2.png:$BATTLE:$SHOTS/nx2.png:$SHOTS/nx2.png:$SHOTS/nx2.png:$SHOTS/nx2.png FAKE_HOLD=$2 \
    timeout 200 nice -n 10 taskset -c 24-31 $BOTPY -B $LOOP/drive.py --out $T/run --source live --bsgrab $T/bsgrab \
      --tap adb --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port 0 $3 \
      > $T/drive.log 2>&1
}
A=$(mktemp -d); B=$(mktemp -d)
run_case $A 40 "--seconds 45 --matches 2" 0 &
run_case $B 10 "--seconds 30 --matches 2" 1 &
wait
ev() { cat $1/run/m01*/events.jsonl 2>/dev/null | grep -c "\"ev\": \"$2\""; }
check "A: match_start seen" '[ "$(ev $A match_start)" -ge 1 ]'
check "A: false_match logged" '[ "$(ev $A false_match)" -ge 1 ]'
check "A: no match_end for the false battle" '[ "$(ev $A match_end)" = 0 ]'
check "A: m01-false-* dir with false_match.json, no session.json" 'd=$(ls -d $A/run/m01-false-* | head -1); [ -f $d/false_match.json ] && [ ! -f $d/session.json ]'
check "A: m01 reopened (fresh dir with events)" '[ -f $A/run/m01/events.jsonl ] && grep -q "after\": \"false_match" $A/run/m01/events.jsonl'
check "A: no m02 (false match did not count)" '[ ! -d $A/run/m02 ]'
check "A: false battle lasted < 30 s" 'grep -h false_match $A/run/m01-false-*/events.jsonl | python3 -c "import json,sys; print(json.loads(sys.stdin.readline())[\"seconds\"] < 30)" | grep -q True'
check "B: paused + 1 s HUD -> no match_start" '[ "$(ev $B match_start)" = 0 ]'
check "B: paused -> no taps" '[ ! -s $B/adb.log ]'
echo "$pass passed, $fail failed  (logs: $A $B)"
[ "$fail" = 0 ]
