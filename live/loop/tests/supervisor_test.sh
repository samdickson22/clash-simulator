#!/usr/bin/env bash
# ladder_supervisor.py with a fake driver (tests/fake_driver.py), bash standing in for zsh:
#   1 crash -> relaunch (next sNN) within 5 s     2 staged READY -> boundary file -> driver ends at a battle end -> apply.sh,
#   launch.sh replaced, relaunch with it          3 failed apply -> failed-<ts>, ALERT, relaunch with the old launch.sh
#   4 STOP (empty) -> ends at the boundary, supervisor exits 0, no relaunch     5 STOP 'now' -> TERM at once, exit 0
#   6 3 quick refusals -> ALERT + exit 2         7 adopt a driver started outside, relaunch after it exits
#   tests/supervisor_test.sh   (run from a tree copy; python3 only)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); SUP=$(dirname "$HERE")/ladder_supervisor.py
T=$(mktemp -d); pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
setup() {  # setup DIR -> loop dir with launch.sh (marker A) reading the mode from DIR/mode
  local L=$1; mkdir -p $L/supervisor $L/runs $L/logs; echo battle > $L/mode
  mk_launch $L/supervisor/launch.sh A $L
}
mk_launch() { printf '#!/bin/sh\nFAKE_MODE=$(cat %s/mode) FAKE_MARKER=%s exec python3 %s %s "$1"\n' $3 $2 $HERE/fake_driver.py $3 > $1; }
start() { ( LL_SUP_SHELL=/bin/bash python3 -B $SUP --loop-dir $1 --min-session 20 --first s1 > $1/sup.out 2>&1; echo $? > $1/sup.rc ) > /dev/null 2>&1 & echo $!; }
suprc() { waitfor $1 '[ -s $1/sup.rc ]' 10; cat $1/sup.rc; }
evs() { cat $1/supervisor/supervisor.jsonl 2>/dev/null; }
waitfor() { local i; for i in $(seq ${3:-60}); do eval "$2" && return 0; sleep 1; done; return 1; }   # waitfor DIR COND [s]

# 1 crash recovery
L=$T/c1; setup $L; echo crash > $L/mode; P=$(start $L)
waitfor $L '[ $(evs $L | grep -c "\"launch\"") -ge 3 ]' 30; echo stop-now > $L/SUPERVISOR-STOP; echo now >> $L/SUPERVISOR-STOP
waitfor $L '! kill -0 $P 2>/dev/null' 30
check "1 crash -> relaunch s1 s2 s3 (no give-up: each had a battle)" 'evs $L | grep -q "\"session\": \"s3\"" && ! evs $L | grep -q give_up && [ -d $L/runs/s2 ]'
gap=$(python3 - $L <<'P'
import json,sys,datetime as D
e=[json.loads(l) for l in open(sys.argv[1]+'/supervisor/supervisor.jsonl')]
t=lambda x: D.datetime.strptime(x['ts'],'%Y-%m-%dT%H:%M:%SZ')
ex=[x for x in e if x['ev']=='exit'][0]; la=[x for x in e if x['ev']=='launch' and x['session']=='s2'][0]
print(int((t(la)-t(ex)).total_seconds()))
P
)
check "1 relaunch gap <= 5 s (got $gap)" '[ "$gap" -le 5 ]'

# 2 staged deploy at a boundary
L=$T/c2; setup $L; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 20
mkdir -p $L/supervisor/staged; printf 'echo applied > %s/applied.txt\n' $L > $L/supervisor/staged/apply.sh
mk_launch $L/supervisor/staged/launch.sh B $L; touch $L/supervisor/staged/READY
waitfor $L 'evs $L | grep -q "\"session\": \"s2\""' 40
check "2 deploy: boundary consumed by the driver, apply ran, launch.sh replaced, s2 runs marker B" \
  'ls $L/RESTART-AT-BOUNDARY.used-* >/dev/null 2>&1 && [ -f $L/applied.txt ] && grep -q "FAKE_MARKER=B" $L/supervisor/launch.sh && ls -d $L/supervisor/applied-* >/dev/null && ls $L/supervisor/launch.sh.bak-* >/dev/null && waitfor $L "grep -q \"\\\"marker\\\": \\\"B\\\"\" $L/runs/s2/m01/events.jsonl" 10'

# 3 failed apply, old state restored (rc 10; same supervisor)
mkdir -p $L/supervisor/staged; echo 'exit 10' > $L/supervisor/staged/apply.sh; mk_launch $L/supervisor/staged/launch.sh C $L; touch $L/supervisor/staged/READY
waitfor $L 'evs $L | grep -q "\"session\": \"s3\""' 40
check "3 failed apply -> failed-<ts>, ALERT, s3 still on launch B" \
  'ls -d $L/supervisor/failed-* >/dev/null && [ -f $L/supervisor/ALERT ] && grep -q "FAKE_MARKER=B" $L/supervisor/launch.sh && waitfor $L "grep -q \"\\\"marker\\\": \\\"B\\\"\" $L/runs/s3/m01/events.jsonl" 10'

# 4 STOP at the boundary (same supervisor)
touch $L/SUPERVISOR-STOP
waitfor $L '! kill -0 $P 2>/dev/null' 40; rc=$(suprc $L)
check "4 STOP -> driver ends at a battle end (restart_at_boundary), supervisor exit 0, no s4" \
  '[ $rc = 0 ] && grep -q restart_at_boundary $L/runs/s3/m01/events.jsonl && [ ! -d $L/runs/s4 ] && evs $L | grep -q "\"stopped\""'

# 5 STOP now
L=$T/c5; setup $L; echo 60 > /dev/null; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 20; sleep 1; echo now > $L/SUPERVISOR-STOP
waitfor $L '! kill -0 $P 2>/dev/null' 15; rc=$(suprc $L)
check "5 STOP now -> driver TERMed (rc 143), supervisor exit 0" '[ $rc = 0 ] && evs $L | grep -q "\"stop_now\"" && evs $L | grep "\"exit\"" | grep -q "\"rc\": 143"'

# 6 refusals -> give up
L=$T/c6; setup $L; echo refuse > $L/mode; P=$(start $L)
waitfor $L '! kill -0 $P 2>/dev/null' 60; rc=$(suprc $L)
check "6 three quick refusals -> ALERT, exit 2, exactly 3 launches" '[ $rc = 2 ] && [ -f $L/supervisor/ALERT ] && [ $(evs $L | grep -c "\"launch\"") = 3 ]'

# 7 adopt a driver started by hand
L=$T/c7; setup $L; echo crash > $L/mode
FAKE_MODE=crash FAKE_CRASH_S=6 python3 $HERE/fake_driver.py $L hand & H=$!
sleep 1; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 30; echo now > $L/SUPERVISOR-STOP; waitfor $L '! kill -0 $P 2>/dev/null' 30
check "7 adopt the hand-started driver (pid $H), launch s1 only after it exits" \
  'evs $L | grep "\"adopt\"" | grep -q "\"pid\": $H" && python3 -c "
import json,sys; e=[json.loads(l)[\"ev\"] for l in open(\"$L/supervisor/supervisor.jsonl\")]; sys.exit(0 if e.index(\"adopted_exit\") < e.index(\"launch\") else 1)"'

# 8 uncertain apply (rc 7) -> uncertain-<ts>, ALERT, supervisor exit 3, no relaunch
L=$T/c8; setup $L; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 20
mkdir -p $L/supervisor/staged; echo 'exit 7' > $L/supervisor/staged/apply.sh; touch $L/supervisor/staged/READY
waitfor $L '! kill -0 $P 2>/dev/null' 40; rc=$(suprc $L)
check "8 uncertain apply -> ALERT, exit 3, no s2" '[ "$rc" = 3 ] && ls -d $L/supervisor/uncertain-* >/dev/null && [ -f $L/supervisor/ALERT ] && [ ! -d $L/runs/s2 ]'

# 9 crash with a staged deploy -> relaunch WITHOUT applying; applied only after the next boundary exit
L=$T/c9; setup $L; echo crash > $L/mode; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 20
mkdir -p $L/supervisor/staged; printf 'echo applied > %s/applied.txt\n' $L > $L/supervisor/staged/apply.sh; touch $L/supervisor/staged/READY
waitfor $L 'evs $L | grep -q deploy_waits' 30; echo battle > $L/mode
waitfor $L 'evs $L | grep -q deploy_applied' 60; echo now > $L/SUPERVISOR-STOP; waitfor $L '! kill -0 $P 2>/dev/null' 30
check "9 crash -> deploy_waits (no apply on a crash exit), then applied after a boundary exit" \
  'python3 -c "
import json,sys; e=[json.loads(l)[\"ev\"] for l in open(\"$L/supervisor/supervisor.jsonl\")]; sys.exit(0 if e.index(\"deploy_waits\") < e.index(\"deploy_applied\") else 1)" && [ -f $L/applied.txt ] && ls $L/RESTART-AT-BOUNDARY.used-* >/dev/null 2>&1'

# 9b an old receipt (.taken-<pid> from an earlier request) never proves a crash exit
L=$T/c9b; setup $L; echo crash > $L/mode; echo "token deadbeef old" > $L/RESTART-AT-BOUNDARY.taken-1; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 20
mkdir -p $L/supervisor/staged; printf 'echo applied > %s/applied.txt\n' $L > $L/supervisor/staged/apply.sh; touch $L/supervisor/staged/READY
waitfor $L 'evs $L | grep -q deploy_waits' 30; echo now > $L/SUPERVISOR-STOP; waitfor $L '! kill -0 $P 2>/dev/null' 30
check "9b stale receipt with another token: deploy_waits, not applied" '[ ! -f $L/applied.txt ] && [ -f $L/RESTART-AT-BOUNDARY.taken-1 ]'

# 10 adopted driver whose lock file names no valid PID: STOP now never signals, falls back to a boundary request
L=$T/c10; setup $L
( exec 9>>$L/driver.lock; flock -n 9; : > $L/driver.lock; echo "junk" > $L/driver.lock; sleep 8 ) & H=$!
sleep 1; P=$(start $L); waitfor $L 'evs $L | grep -q "\"adopt\""' 15; echo now > $L/SUPERVISOR-STOP
waitfor $L '! kill -0 $P 2>/dev/null' 30
check "10 unknown holder: stop_now_refused (no kill), holder untouched until it exits" \
  'evs $L | grep -q stop_now_refused && ! evs $L | grep -q "\"stop_now\""'

# 11 stale boundary file at start (no STOP/READY) is cleared before adopting a hand-started driver
L=$T/c11; setup $L; echo stale > $L/RESTART-AT-BOUNDARY
FAKE_MODE=battle FAKE_BATTLE_S=2 python3 $HERE/fake_driver.py $L hand & H=$!
sleep 1; P=$(start $L); sleep 6
check "11 stale boundary cleared at start; the adopted driver keeps playing" '[ ! -f $L/RESTART-AT-BOUNDARY ] && ls $L/RESTART-AT-BOUNDARY.stale-* >/dev/null && kill -0 $H'
echo now > $L/SUPERVISOR-STOP; waitfor $L '! kill -0 $P 2>/dev/null' 30; kill $H 2>/dev/null

# 11b STOP now with an adopted driver that has a valid PID: never signalled, ends at its battle boundary instead
L=$T/c11b; setup $L
FAKE_MODE=battle FAKE_BATTLE_S=3 python3 $HERE/fake_driver.py $L hand & H=$!
sleep 1; P=$(start $L); waitfor $L 'evs $L | grep -q "\"adopt\""' 15; echo now > $L/SUPERVISOR-STOP
waitfor $L '! kill -0 $P 2>/dev/null' 30; wait $H; hrc=$?
check "11b adopted + STOP now -> stop_now_refused, boundary request, driver exits 0 at its battle end (not TERM)" \
  'evs $L | grep -q stop_now_refused && [ $hrc = 0 ] && ls $L/RESTART-AT-BOUNDARY.used-* >/dev/null 2>&1'

# 12 --first naming an existing session is not reused
L=$T/c12; setup $L; mkdir -p $L/runs/s1/m01; echo '{"ev": "match_start"}' > $L/runs/s1/m01/events.jsonl; echo refuse > $L/mode
P=$(start $L); waitfor $L '! kill -0 $P 2>/dev/null' 60; rc=$(suprc $L)
check "12 existing s1 not reused (first_name_taken), refusals still give up (exit 2)" 'evs $L | grep -q first_name_taken && [ "$rc" = 2 ] && ! evs $L | grep "\"launch\"" | grep -q "\"s1\""'

# 13 SIGTERM to the supervisor during an apply: the apply completes, then the supervisor exits 0 without launching
L=$T/c13; setup $L; P=$(start $L)
waitfor $L 'evs $L | grep -q "\"launch\""' 20
mkdir -p $L/supervisor/staged; printf 'sleep 4; echo applied > %s/applied.txt\n' $L > $L/supervisor/staged/apply.sh; touch $L/supervisor/staged/READY
waitfor $L 'pgrep -f "^/bin/bash $L/supervisor/staged/apply.sh" >/dev/null || ls $L/supervisor/applied-* >/dev/null 2>&1' 60
SP=$(cat $L/supervisor/supervisor.lock | awk '{print $2}'); kill -TERM $SP
waitfor $L '! kill -0 $P 2>/dev/null' 30; rc=$(suprc $L)
check "13 TERM during apply -> applied, supervisor_term_deferred, exit 0, no relaunch after" \
  '[ "$rc" = 0 ] && [ -f $L/applied.txt ] && evs $L | grep -q supervisor_term_deferred && evs $L | grep -q "TERM after apply" && [ $(evs $L | grep -c "\"launch\"") = 1 ]'

# 14 adopted holder that writes its PID late: the supervisor learns it (adopt_pid_learned)
L=$T/c14; setup $L
( exec 9>>$L/driver.lock; flock -n 9; : > $L/driver.lock; sleep 3; echo "pid $BASHPID late" > $L/driver.lock; sleep 4 ) & H=$!
sleep 1; P=$(start $L); waitfor $L 'evs $L | grep -q adopt_pid_learned' 15
echo now > $L/SUPERVISOR-STOP; waitfor $L '! kill -0 $P 2>/dev/null' 30
check "14 PID-less adoption learns the holder PID once written" 'evs $L | grep -q adopt_pid_learned'

# 15 adopted A hands the lock straight to B (B was blocked on flock): handoff seen, B adopted, nothing signalled
L=$T/c15; setup $L
( exec 9>>$L/driver.lock; flock 9; : > $L/driver.lock; echo "pid $BASHPID A" > $L/driver.lock; sleep 4 ) & A=$!
sleep 0.5
( exec 9>>$L/driver.lock; flock 9; : > $L/driver.lock; echo "pid $BASHPID B" > $L/driver.lock; sleep 5 ) & B=$!
P=$(start $L); waitfor $L '[ $(evs $L | grep -c "\"adopt\"") -ge 2 ]' 20
echo now > $L/SUPERVISOR-STOP; waitfor $L '! kill -0 $P 2>/dev/null' 30
check "15 A->B lock handoff: both adopted in turn (pids $A, $B), no stop_now signal" \
  'evs $L | grep "\"adopt\"" | grep -q "\"pid\": $A" && evs $L | grep "\"adopt\"" | grep -q "\"pid\": $B" && ! evs $L | grep -q "\"stop_now\""'
echo "$pass passed, $fail failed  (logs: $T)"; [ "$fail" = 0 ]
