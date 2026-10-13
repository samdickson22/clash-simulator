#!/usr/bin/env bash
# FSC (U3/U4) host session, exploration, NEVER ADOPTABLE. One SSH session per call; prints __RC=<n> last.
#   launch HOST [STOP_AT]  preflight (read-only) -> stage -> 8-seed smoke -> live STOP test -> detached reporting run
#   progress HOST          read-only status; if a console user appeared on a 12-slot run: yield to 10 slots
#   stop HOST              touch STOP -> wait for supervisor exit -> census by PID -> rsync outputs to 05
# Never pattern-kills; never writes outside J (and the 05 mirror on stop). Reads the X4S2 job on 03 only to copy it.
set -uo pipefail
cmd=${1:?cmd}; host=${2:?host}; arg=${3:-}
J03=/mpac/sdicks02/jobs/clasher/fsc-03-20261013; J04=/mpac/sdicks02/jobs/clasher/fsc-04-20261013
case $host in
  127x03) J=$J03; tag=03; cfg=plan-fsc.json;;
  127x04) J=$J04; tag=04; cfg=plan-fsc-04.json;;
  *) echo "__RC=90"; exit 90;;
esac
BASE=/mpac/sdicks02/jobs/clasher/x4s2-20261011           # 03 only, read-only copy source (X4S2's finished job)
PY=/mpac/sdicks02/repos/clasher/.venv/bin/python
MIRROR=/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013   # on 127x05
E=$J/repo/reports/explore
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { log "FAIL: $2"; echo "__RC=$1"; exit "$1"; }
[ "$(hostname)" = "$host" ] || die 90 "hostname $(hostname) != $host"
renice -n 19 -p $$ >/dev/null

foreign_now() {
  ps -u sdicks02 -o pid=,pgid=,args= | awk -v me="$(ps -o pgid= -p $$ | tr -d ' ')" \
    '$2 != me && $0 ~ /python|rsync|clasher_core|supervise|runtime\.sh/ && !($0 ~ /rsync --server/ && $NF ~ /^\/mpac\/sdicks02\/mirrors\//)' | sort
}
preflight() {
  local console mem free foreign
  console=$(~/.local/bin/fleet-console-users); mem=$(awk '/MemAvailable/ {print int($2/1048576)}' /proc/meminfo)
  free=$(df -BG --output=avail /mpac | tail -1 | tr -dc 0-9)
  # Foreign = any sdicks02 python/rsync/clasher process outside this session's process group that is present in
  # two samples 15 s apart (transient status probes pass). The hub mirror's rsync into /mpac/sdicks02/mirrors/ is allowed.
  foreign=$(comm -12 <(foreign_now) <(sleep 15; foreign_now))
  log "preflight console_users=$console memavailable_GiB=$mem mpac_free_GiB=$free loadavg=$(cut -d' ' -f1-3 /proc/loadavg)"
  log "other users' CPU%: $(ps -eo user=,pcpu= | awk '$1 != "sdicks02" {s += $2} END {print s+0}')"
  [ -z "$foreign" ] || { printf '%s\n' "$foreign"; die 91 "foreign sdicks02 processes present"; }
  [ "$mem" -ge 24 ] || die 92 "MemAvailable < 24 GiB"
  [ "$free" -ge 20 ] || die 93 "/mpac free < 20 GiB"
  [ -x "$PY" ] || die 94 "no runtime python"
  [ ! -e "$J/STOP" ] || die 95 "STOP present"
  CONSOLE=$console
}

# run_sup PHASE WORKLIST WORKERS STOP_AT: detached (setsid) supervisor; prints the PID/PGID receipt.
run_sup() {
  bash "$E/x4s2/detach.sh" "$J/logs/$1.log" "$J/logs/$1.receipt.json" nice -n 19 taskset -c 62 env X4S2_JOB="$J" \
    bash "$E/x4s2/runtime.sh" reports/explore/x4s2/supervise.py --job "$J" --phase "$1" --worklist "$2" \
    --config "$E/fsc/$cfg" --workers "$3" --stop-at "$4"
}
# wait_exit PHASE SECONDS: wait for supervisor-exit.json (the supervisor's own bounded stop is <= ~110 s).
wait_exit() {
  local i; for ((i = 0; i < $2; i += 2)); do [ -s "$J/$1/supervisor-exit.json" ] && return 0; sleep 2; done; return 1
}
in_hours() { date -u -d "+$1" +%Y-%m-%dT%H:%M:%SZ; }

case $cmd in
launch)
  [ -d "$J/bundle" ] && [ ! -e "$J/repo" ] || die 96 "expected fresh $J with only bundle/"
  preflight
  mkdir -p "$J/logs" "$J/cache"
  if [ "$host" = 127x03 ]; then
    for d in repo native inputs; do [ -d "$BASE/$d" ] || die 97 "missing $BASE/$d"; done
    rsync -a --exclude=/reports/explore/x4s/ --exclude=/reports/explore/x4s2/ --exclude=/reports/explore/k4s-confirm/ \
      --exclude=/reports/explore/t1/ --exclude='t1-*' --exclude='k4s-*' --exclude=__pycache__ --exclude='*.pyc' \
      "$BASE/repo/" "$J/repo/" || die 97 "repo copy"
    cp -a "$BASE/native" "$J/native" && mkdir "$J/inputs" && \
      cp -a "$BASE/inputs/main02.pt" "$BASE/inputs/R3a.pt" "$BASE/inputs/R3a-calibration.json" "$J/inputs/" || die 97 "copy"
  else
    bash "$J/bundle/fsc/lan_copy_04.sh" || die 97 "LAN copy from 03"
  fi
  python3 -I "$J/bundle/fsc/stage.py" install "$J" "$J/bundle" "$host" || die 98 "staging verification"
  log "staged: $(du -sh "$J" | cut -f1)"
  # 8-seed smoke (8 workers), then the live STOP test (4 workers); both excluded from every analysis.
  run_sup "smoke-$tag" "$E/fsc/wl-smoke-$tag.json" 8 "$(in_hours '30 minutes')" || die 99 "smoke launch"
  wait_exit "smoke-$tag" 1500 || { touch "$J/STOP"; wait_exit "smoke-$tag" 240; die 99 "smoke did not exit in 25 min (STOP left in place)"; }
  python3 -I "$E/fsc/hostcheck.py" smoke "$J/smoke-$tag" "$E/fsc/$cfg" "$host" || die 99 "smoke gate"
  run_sup "stoptest-$tag" "$E/fsc/wl-stoptest-$tag.json" 4 "$(in_hours '30 minutes')" || die 100 "stoptest launch"
  for ((i = 0; i < 180; i += 2)); do compgen -G "$J/stoptest-$tag/blocks/*.started" >/dev/null && break; sleep 2; done
  sleep 20; touch "$J/STOP"; log "STOP touched for the STOP test"
  wait_exit "stoptest-$tag" 240 || die 100 "STOP test: no supervisor exit in 240 s (STOP left in place)"
  python3 -I "$E/fsc/hostcheck.py" stoptest "$J/stoptest-$tag" || die 100 "STOP test gate (STOP left in place)"
  rm -f "$J/STOP"
  # Reporting run: 12 slots, or 10 with a console user; stop-at = min(now + 8 h - 5 min, optional STOP_AT).
  preflight
  workers=12; [ "$CONSOLE" -gt 0 ] && workers=10
  stop_at=$(in_hours '475 minutes'); [ -n "$arg" ] && [[ "$arg" < "$stop_at" ]] && stop_at=$arg
  echo "rep$tag" > "$J/current-phase"; echo "$E/fsc/wl-$tag.json" > "$J/current-worklist"; echo "$stop_at" > "$J/stop-at"
  run_sup "rep$tag" "$E/fsc/wl-$tag.json" "$workers" "$stop_at" || die 101 "reporting launch"
  for ((i = 0; i < 60; i++)); do [ -s "$J/rep$tag/launch.json" ] && break; sleep 1; done
  cat "$J/rep$tag/launch.json" || die 101 "no launch.json"
  sleep 60
  python3 -I "$E/fsc/hostcheck.py" census "$(python3 -c "import json;print(json.load(open('$J/rep$tag/launch.json'))['child_pgid'])")" \
    >/dev/null && die 101 "reporting group empty after 60 s"
  log "reporting running: phase rep$tag workers=$workers stop_at=$stop_at started_blocks=$(ls "$J/rep$tag/blocks" 2>/dev/null | wc -l)"
  echo "__RC=0" ;;

progress)
  ph=$(cat "$J/current-phase"); p=$J/$ph
  [ -s "$p/progress.json" ] && cat "$p/progress.json"
  [ -s "$p/supervisor-exit.json" ] && { cat "$p/supervisor-exit.json"; echo "__RC=0"; exit 0; }
  console=$(~/.local/bin/fleet-console-users); workers=$(python3 -c "import json;print(json.load(open('$p/launch.json'))['workers'])")
  log "phase=$ph workers=$workers console_users=$console proofs=$(ls "$p/blocks" | grep -c '\.json$')"
  if [ "$console" -gt 0 ] && [ "$workers" -gt 10 ]; then
    # Yield: stop this phase, keep its never-started blocks in order, relaunch them on 10 slots (same stop-at).
    log "console user present: yielding to 10 slots"; touch "$J/STOP"
    wait_exit "$ph" 240 || die 102 "yield: no supervisor exit (STOP left in place)"
    rm -f "$J/STOP"; n=$(ls -d "$J"/rep$tag* | wc -l); new="rep$tag-y$n"
    python3 -I "$E/x4s2/leftover.py" "$(cat "$J/current-worklist")" "$p" "$J/logs/wl-$new.json" || die 102 "leftover"
    echo "$new" > "$J/current-phase"; echo "$J/logs/wl-$new.json" > "$J/current-worklist"
    run_sup "$new" "$J/logs/wl-$new.json" 10 "$(cat "$J/stop-at")" || die 102 "yield relaunch"
  fi
  echo "__RC=0" ;;

stop)
  touch "$J/STOP"; log "STOP touched"; ph=$(cat "$J/current-phase")
  wait_exit "$ph" 240 || log "no supervisor-exit.json after 240 s"
  rc=0
  for r in "$J"/logs/*.receipt.json; do
    pid=$(python3 -c "import json;print(json.load(open('$r'))['pid'])")
    d=$J/$(basename "$r" .receipt.json); pg=0
    [ -s "$d/launch.json" ] && pg=$(python3 -c "import json;print(json.load(open('$d/launch.json'))['child_pgid'])")
    python3 -I "$E/fsc/hostcheck.py" census "$pg" "$pid" || rc=103
  done
  [ "$rc" = 0 ] || die 103 "processes remain (by PID census above)"
  cat "$J/$ph/supervisor-exit.json"
  rsync -a --rsync-path="mkdir -p $MIRROR/$host && nice -n 19 rsync" \
    --exclude=/repo/ --exclude=/native/ --exclude=/inputs/ --exclude=/cache/ --exclude=/bundle/ \
    "$J/" "127x05:$MIRROR/$host/" || die 104 "rsync to 05"
  log "outputs mirrored to 127x05:$MIRROR/$host"
  echo "__RC=0" ;;
*) die 90 "unknown command $cmd" ;;
esac
