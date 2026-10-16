#!/usr/bin/env bash
# Live-path test of the driver's control page (05, no Mac): --source live with a fake bsgrab that streams real screenshots,
# a fake adb returning the real dumpsys text and logging taps. Checks: startup (client-version block, session-config),
# pause/resume (+ events, no autonav taps while paused), deck read from the Battle Deck page (out-of-scope flag),
# out-of-scope deck blocks battles (even after Resume), a C56 deck unblocks, deck.json written.
#   tests/control_test.sh   (env: BOTPY, SHOTS)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
SHOTS=${SHOTS:-/mpac/sdicks02/scratch/live-loop/shots}
T=$(mktemp -d); PORT=$((18800 + RANDOM % 500))
export PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
  CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=4 CUDA_VISIBLE_DEVICES= \
  LL_ADB=$HERE/fake_adb.sh FAKE_ADB_LOG=$T/adb.log LL_DECK_FILE=$T/deck.json LL_PAUSE_FILE=$T/PAUSE LL_LOCK_FILE=$T/driver.lock \
  FAKE_IMAGES=$SHOTS/nx2.png:$SHOTS/deckpage.png FAKE_HOLD=120
printf '#!/bin/sh\nexec %s %s "$@"\n' /mpac/sdicks02/scratch/live-loop/venv/bin/python "$HERE/fake_bsgrab.py" > $T/bsgrab
chmod +x $T/bsgrab
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
st() { curl -s -m 3 http://127.0.0.1:$PORT/state; }
jq_() { st | python3 -c "import json,sys; s=json.load(sys.stdin); print($1)"; }
post() { curl -s -m 5 -X POST --data-binary "${2:-}" http://127.0.0.1:$PORT/$1; echo; }
ev() { grep -c "\"ev\": \"$1\"" $T/run/m01/events.jsonl 2>/dev/null || echo 0; }

nice -n 10 taskset -c 24-31 $BOTPY -B $LOOP/drive.py --out $T/run --source live --bsgrab $T/bsgrab --tap adb --autonav \
  --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port $PORT --seconds 150 \
  --matches 2 > $T/drive.log 2>&1 &
DPID=$!
for i in $(seq 1 60); do st >/dev/null 2>&1 && break; sleep 1; done
check "driver started on the live path (no crash)" 'kill -0 $DPID'
check "session-config client version from adb" 'grep -q "\"versionCode\": \"160402020\"" $T/run/m01/session-config.json'
check "page served" 'curl -s -m 3 http://127.0.0.1:$PORT/ | grep -q "Read deck from screen"'
# home frame first: autonav taps Battle (not paused)
for i in $(seq 1 20); do grep -q "input tap 550 1489" $T/adb.log 2>/dev/null && break; sleep 1; done
check "autonav taps Battle on home when running" 'grep -q "input tap 550 1489" $T/adb.log'
post pause >/dev/null; sleep 2; : > $T/adb.log
check "state paused" '[ "$(jq_ "s[\"paused\"]")" = True ]'
check "paused_by_user event" '[ "$(ev paused_by_user)" -ge 1 ]'
sleep 8
check "no taps while paused (home frames)" '[ ! -s $T/adb.log ]'
# wait for the deck page image, then read the deck
for i in $(seq 1 30); do sleep 1; done
post readdeck >/dev/null; sleep 3
check "deck read: 8 cards from the Battle Deck page" '[ "$(jq_ "len([c for c in s[\"read\"][\"cards\"] if c])")" = 8 ]'
check "deck read flags GoblinCage out of scope" '[ "$(jq_ "s[\"read\"][\"out_of_scope\"] == [chr(71)+\"oblinCage\"]")" = True ]'
DECK=$(jq_ "chr(10).join(s['read']['cards'])")
post deck "$DECK" >/dev/null; post resume >/dev/null; sleep 3
check "deck_change event" '[ "$(ev deck_change)" -ge 1 ]'
check "out-of-scope deck keeps the bot paused after Resume" '[ "$(jq_ "s[\"paused_reason\"]")" = deck_out_of_scope ]'
check "page reports the blocking card" '[ "$(jq_ "s[\"deck_out_of_scope\"] == [chr(71)+\"oblinCage\"]")" = True ]'
post deck "Knight,Archers,Minions,Arrows,Fireball,Giant,MiniPekka,Musketeer" >/dev/null; sleep 3
check "C56 deck unblocks (running)" '[ "$(jq_ "s[\"paused\"] or bool(s[\"paused_reason\"])")" = False ]'
check "resumed_by_user event" '[ "$(ev resumed_by_user)" -ge 1 ]'
check "deck.json written" 'grep -q MiniPekka $T/deck.json'
check "bad deck (7 cards) rejected" 'post deck "Knight,Archers,Minions,Arrows,Fireball,Giant,MiniPekka" | grep -q "NOT applied"'
touch $T/PAUSE; sleep 2
check "PAUSE file pauses (/state paused:true, reason file)" '[ "$(jq_ "s[\"paused_reason\"] == \"file\" and s[\"paused\"]")" = True ]'
rm -f $T/PAUSE
kill -TERM $DPID; wait $DPID
check "driver exits cleanly on TERM" '[ -f $T/run/m01/session.json ]'
echo "$pass passed, $fail failed  (logs: $T)"
[ "$fail" = 0 ]
