#!/usr/bin/env bash
# Stall guard (05): replay of s14-m04 (Sam's Cannon deck; the live bot sat at full elixir) with the search tier forced to WAIT
# (LL_TEST_STALL=1). Expect stall_alert within ~STALL_S of full elixir, then plays from the fast tier
# (source fast-disabled) and stall_cleared.   tests/stall_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE"); R=$(cd "$LOOP/../.." && pwd)
BOTPY=${BOTPY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
REC=${REC:-/mpac/sdicks02/scratch/live-loop/rec/s14m04}   # the live bot sat at full elixir here
T=$(mktemp -d)
echo '["Valkyrie", "Archers", "Minions", "Cannon", "Fireball", "Giant", "MiniPekka", "Musketeer"]' > $T/deck.json
env PYTHONPATH=$R:$R/src:$R/live/perception:/mpac/sdicks02/scratch/live-loop/pydeps \
  CLASHER_BOT_RUNTIME=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1 \
  CLASHER_LIVE_FAST=student:/mpac/sdicks02/scratch/live-loop/rl5/policy-00010.pt@0.5375 \
  CLASHER_LOPP_MODELS=/mpac/sdicks02/jobs/clasher/live-macbench/lopp-models OMP_NUM_THREADS=8 PYTHONHASHSEED=0 \
  CUDA_VISIBLE_DEVICES= LL_DECK_FILE=$T/deck.json LL_PAUSE_FILE=$T/PAUSE LL_LOCK_FILE=$T/driver.lock \
  LL_TEST_STALL=1 LL_STALL_S=6 \
  timeout 1500 nice -n 10 taskset -c 24-31 $BOTPY -B $LOOP/drive.py --out $T/run --source replay:$REC --no-realtime \
    --tap none --export /mpac/sdicks02/jobs/clasher/live-perc-r3-20261015/export-interim-r5e3 --overlay-port 0 \
    --seconds 1500 > $T/log 2>&1
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
check "stall_alert logged" 'grep -q "\"ev\": \"stall_alert\"" $T/run/events.jsonl'
check "alert within 6-8 s of the last play / match start" 'grep -m1 stall_alert $T/run/events.jsonl | python3 -c "import json,sys; s=json.loads(sys.stdin.read())[\"seconds\"]; sys.exit(not 6 <= s <= 8)"'
check "fast tier plays after the alert (source fast-disabled)" 'grep "\"submitted\": true" $T/run/decisions.jsonl | grep -q "fast-disabled"'
check "stall_cleared after a play" 'grep -q "\"ev\": \"stall_cleared\"" $T/run/events.jsonl'
check "no search-tier play (the forced WAIT held)" '! grep "\"submitted\": true" $T/run/decisions.jsonl | grep -q "\"source\": \"search\""'
check "no step errors" '! grep -q "\"err\": \"" $T/run/frames.jsonl'
echo "stalls: $(grep -c stall_alert $T/run/events.jsonl), plays: $(grep -c '"submitted": true' $T/run/decisions.jsonl)"
echo "$pass passed, $fail failed  (logs: $T)"
[ "$fail" = 0 ]
