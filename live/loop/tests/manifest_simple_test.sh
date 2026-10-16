#!/usr/bin/env bash
# Start-of-session deployment check (drive.py check_manifest), live path with fake bsgrab (home screen) + fake adb.
#   A no manifest -> manifest_absent, session runs (taps allowed)
#   B matching manifest -> manifest_ok, session runs
#   C a listed file changed -> exit 3 before any tap, status.txt "REFUSED (deployment check): changed ..."
#   D PYTHONHASHSEED=1 -> exit 3 before any tap
#   tests/manifest_simple_test.sh   (run from a full tree copy; env: BOTPY, SHOTS)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
VPY=/mpac/sdicks02/scratch/live-loop/venv/bin/python
SHOTS=${SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
T=$(mktemp -d)
printf '#!/bin/sh\nexec %s %s "$@"\n' $VPY "$HERE/fake_bsgrab.py" > $T/bsgrab; chmod +x $T/bsgrab
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
run() {  # run NAME TREE [env...]
  local d=$T/$1 tree=$2; shift 2; mkdir -p $d
  env PYTHONPATH=$tree:$tree/src:$tree/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
    CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
    CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
    CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=2 CUDA_VISIBLE_DEVICES= \
    LL_ADB=$HERE/fake_adb.sh FAKE_IMAGES=$SHOTS/sol-home-ready.png FAKE_HOLD=1000 PYTHONHASHSEED=0 "$@" \
    LL_LOCK_FILE=$d/driver.lock LL_STATUS_FILE=$d/status.txt FAKE_ADB_LOG=$d/adb.log LL_DECK_FILE=$d/deck.json \
    LL_PAUSE_FILE=$d/PAUSE nice -n 10 $BOTPY -B $tree/live/loop/drive.py --out $d/run --source live --bsgrab $T/bsgrab \
    --tap adb --autonav --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port 0 \
    --seconds 25 > $d/log 2>&1
  echo $? > $d/rc
}
ev() { grep -h "\"ev\": \"$2\"" $T/$1/run/events.jsonl 2>/dev/null; }
# a committed copy of the deployed live/loop + perception files, and its manifest
mkdir -p $T/repo && cp -a $R/live $T/repo/ && (cd $T/repo && git init -q && git add -A live/loop/*.py live/perception/*.py \
  && git -c user.email=t@t -c user.name=t commit -qm deployed)
FILES=$(cd $T/repo && git ls-files 'live/loop/*.py' 'live/perception/*.py' | tr '\n' ' ')
$VPY $LOOP/manifest_build.py --repo $T/repo --commit HEAD --out $T/MANIFEST.json $FILES > $T/build.log
TREE=$T/tree; mkdir -p $TREE && cp -a $R/. $TREE/ 2>/dev/null; find $TREE -name __pycache__ -prune -exec rm -rf {} +
run A $TREE LL_MANIFEST=$T/none.json &
run B $TREE LL_MANIFEST=$T/MANIFEST.json &
wait
cp -a $TREE $T/treeC && echo "# changed" >> $T/treeC/live/loop/towers.py
run C $T/treeC LL_MANIFEST=$T/MANIFEST.json &
run D $TREE LL_MANIFEST=$T/MANIFEST.json PYTHONHASHSEED=1 &
wait
check "build: manifest lists the deployed files" '[ "$($VPY -c "import json;print(len(json.load(open(\"$T/MANIFEST.json\"))[\"files\"]))")" -gt 10 ]'
check "A: no manifest -> manifest_absent, runs (exit 0, taps)" '[ "$(cat $T/A/rc)" = 0 ] && [ -n "$(ev A manifest_absent)" ] && grep -q "input tap" $T/A/adb.log'
check "B: matching manifest -> manifest_ok, runs" '[ "$(cat $T/B/rc)" = 0 ] && [ -n "$(ev B manifest_ok)" ] && grep -q "input tap" $T/B/adb.log'
check "C: changed file -> exit 3, no tap, status names it" '[ "$(cat $T/C/rc)" = 3 ] && ! grep -q "input tap" $T/C/adb.log 2>/dev/null && grep -q "changed live/loop/towers.py" $T/C/status.txt'
check "D: PYTHONHASHSEED=1 -> exit 3, no tap" '[ "$(cat $T/D/rc)" = 3 ] && ! grep -q "input tap" $T/D/adb.log 2>/dev/null && grep -q PYTHONHASHSEED $T/D/status.txt'
echo "$pass passed, $fail failed  (logs: $T)"; [ "$fail" = 0 ]
