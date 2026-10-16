#!/usr/bin/env bash
# Always-on overlay (05, no Mac): server up with no driver (between-sessions page/state/stream, Pause writes the PAUSE
# file, deck saved), a driver starts (page/state proxied live), the driver exits (between sessions again), the server
# keeps running; a second server start is a no-op.   tests/overlay_server_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
PY=/mpac/sdicks02/scratch/live-loop/venv/bin/python
T=$(mktemp -d); SP=$((19000 + RANDOM % 400)); DP=$((SP + 500))
export LL_LOOP_DIR=$T/loop LL_PAUSE_FILE=$T/loop/PAUSE LL_DECK_FILE=$T/loop/deck.json
mkdir -p $T/loop/runs
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
st() { curl -s -m 3 http://127.0.0.1:$SP/state; }
jq_() { st | python3 -c "import json,sys; s=json.load(sys.stdin); print($1)"; }
post() { curl -s -m 5 -X POST --data-binary "${2:-}" http://127.0.0.1:$SP/$1; }
PYTHONPATH=/mpac/sdicks02/scratch/live-loop/pydeps $PY -B $LOOP/overlay_server.py --port $SP --driver-port $DP > $T/srv.log 2>&1 &
SPID=$!
for i in $(seq 1 30); do st >/dev/null 2>&1 && break; sleep 1; done
echo "starting next session" > $T/loop/status.txt
check "server up with no driver: driver=false" '[ "$(jq_ "s[\"driver\"]")" = False ]'
check "between-sessions reason from status.txt" '[ "$(jq_ "s[\"reason\"]")" = "starting next session" ]'
check "page served with the banner code" 'curl -s -m 3 http://127.0.0.1:$SP/ | grep -q "BETWEEN SESSIONS"'
check "idle stream serves JPEG frames" 'curl -s -m 3 http://127.0.0.1:$SP/stream -o $T/idle.mjpeg; grep -qa "image/jpeg" $T/idle.mjpeg'
post pause >/dev/null
check "Pause with no driver writes the PAUSE file" '[ -f $T/loop/PAUSE ] && [ "$(jq_ "s[\"paused\"]")" = True ]'
post resume >/dev/null
check "Resume removes it" '[ ! -f $T/loop/PAUSE ]'
post deck "Knight,Archers,Minions,Cannon,Fireball,Giant,MiniPekka,Musketeer" >/dev/null
check "Apply deck with no driver saves deck.json" 'grep -q Cannon $T/loop/deck.json'
check "out-of-scope deck flagged on save" 'post deck "Knight,Archers,Minions,GoblinCage,Fireball,Giant,MiniPekka,Musketeer" | grep -q "OUT OF SCOPE"'
post deck "Knight,Archers,Minions,Cannon,Fireball,Giant,MiniPekka,Musketeer" >/dev/null
check "second server start is a no-op (already running)" '$PY -B $LOOP/overlay_server.py --port $SP --driver-port $DP 2>&1 | grep -q "already running"'
# a driver session (replay) serving its own page on DP
env PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
  CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=4 PYTHONHASHSEED=0 \
  CUDA_VISIBLE_DEVICES= LL_LOCK_FILE=$T/driver.lock \
  timeout 200 nice -n 10 taskset -c 24-31 $BOTPY -B $LOOP/drive.py --out $T/loop/runs/s99 \
    --source replay:/mpac/sdicks02/scratch/live-loop/rec/ladder1-r1 --tap none \
    --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port $DP --seconds 45 \
    > $T/drv.log 2>&1 &
DPID=$!
for i in $(seq 1 60); do [ "$(jq_ "s[\"driver\"]" 2>/dev/null)" = True ] && break; sleep 1; done
check "driver running: state proxied (driver=true, live match field)" '[ "$(jq_ "s[\"driver\"] and \"match\" in s")" = True ]'
check "driver running: the deck shown is the driver's" '[ "$(jq_ "\"Cannon\" in s[\"deck\"]")" = True ]'
check "driver running: live stream relayed" 'curl -s -m 4 http://127.0.0.1:$SP/stream -o $T/live.mjpeg; [ $(stat -c %s $T/live.mjpeg) -gt 20000 ]'
check "Pause proxied to the driver (driver reports paused)" 'post pause | grep -q "paused" && sleep 2 && [ "$(jq_ "s[\"paused\"]")" = True ]'
post resume >/dev/null
wait $DPID
sleep 3
check "driver exited: between sessions again" '[ "$(jq_ "s[\"driver\"]")" = False ]'
check "last session shown" '[ "$(jq_ "s[\"last_session\"].startswith(\"s99\")")" = True ]'
check "server process survived the driver" 'kill -0 $SPID'
kill $SPID; wait $SPID 2>/dev/null
echo "$pass passed, $fail failed  (logs: $T)"
[ "$fail" = 0 ]
