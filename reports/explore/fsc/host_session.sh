#!/usr/bin/env bash
# FSC (U3/U4) host session, exploration, NEVER ADOPTABLE. Started only by session.sh (one SSH session per call).
#   launch HOST MANIFEST_SHA256 STOP_AT    preflight (read-only) -> stage -> 8-seed smoke -> live STOP test -> reporting
#   progress HOST                          read-only status; console user on a 12-slot run -> yield to 10 slots
#   stop HOST                              permanent STOP -> wait -> exit records -> STOP proof (ps) -> rsync outputs to 05
# Fail-closed: errexit + pipefail, every step checked, and the EXIT trap prints the true status as the last line (__RC=n).
# Each supervisor instance has its own job dir J/inst/<phase> and STOP file; no STOP file is ever removed. J/STOP is the
# permanent stop: once present nothing is (re)launched. Never pattern-kills; writes only under J (and, on stop, the
# coordinator-authorized 05 mirror directory, which session.sh creates fresh on 05). Prefixes are under /mpac/sdicks02/jobs-fsc
# (on 04, /mpac/sdicks02/jobs/clasher is perception storage). Every supervisor runs under oom_score_adj 1000 (ours die
# first) and RLIMIT_AS 8 GiB per process; its host budget is MemAvailable >= 40 GiB and owned PSS <= 16 GiB.
# Nothing persistent: no cron, timers, units, reboots or service restarts.
set -euo pipefail
shopt -s inherit_errexit nullglob
export LC_ALL=C
trap 'echo "__RC=$?"' EXIT
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" >&2; }
die() { log "FAIL: $2"; exit "$1"; }
cmd=${1:-}; host=${2:-}
J03=/mpac/sdicks02/jobs-fsc/fsc-03-20261013; J04=/mpac/sdicks02/jobs-fsc/fsc-04-20261013
DEADLINE=2026-10-13T07:30:00Z   # latest --stop-at (STOP verified by 05:00Z; K4S condition 7)
case $host in
  127x03) J=$J03; tag=03; cfg=plan-fsc.json;;
  127x04) J=$J04; tag=04; cfg=plan-fsc-04.json;;
  *) die 90 "bad host '$host'";;
esac
[ "$(hostname)" = "$host" ] || die 90 "hostname is not $host"
[ "$(realpath -e "$J")" = "$J" ] || die 90 "$J missing or not canonical"
BASE=/mpac/sdicks02/jobs/clasher/x4s2-20261011           # 03 only: read-only copy source (copy only; no git, chmod, touch, locks)
PY=/mpac/sdicks02/repos/clasher/.venv/bin/python
MIRROR=/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013   # on 127x05; created fresh by session.sh (coordinator-authorized)
SSHOPT='ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ControlPersist=no -o StrictHostKeyChecking=yes -o UpdateHostKeys=no'
E=$J/repo/reports/explore
HC() { python3 -I -B "$E/fsc/hostcheck.py" "$@"; }
ST() { python3 -I -B "$J/bundle/fsc/stage.py" "$@"; }
renice -n 19 -p $$ >/dev/null || die 90 "renice"

int() { [[ ${1:-} =~ ^[0-9]+$ ]] || die 91 "non-numeric probe output '${1:-}' ($2)"; }
console_users() {
  local helper whoout other
  helper=$(~/.local/bin/fleet-console-users) || die 91 "fleet-console-users failed"; int "$helper" console
  loginctl list-sessions --no-legend >/dev/null || die 91 "loginctl failed"
  whoout=$(who) || die 91 "who failed"
  other=$(printf '%s\n' "$whoout" | awk 'NF && $1 != "sdicks02"' | wc -l); int "$other" who
  echo $(( helper > other ? helper : other ))   # conservative: any other user's login counts
}
# Foreign = sdicks02 python/rsync/clasher processes outside this session's process group (the hub mirror's rsync
# into /mpac/sdicks02/mirrors/ excepted); a process counts only if present in two checked samples 15 s apart.
foreign_sample() {
  local me out
  me=$(ps -o pgid= -p $$) || return 1; me=${me// /}; [[ $me =~ ^[0-9]+$ ]] || return 1
  out=$(ps -u sdicks02 -o pid=,pgid=,args=) || return 1; [ -n "$out" ] || return 1
  printf '%s\n' "$out" | awk -v me="$me" '$2 != me && $0 ~ /python|rsync|clasher_core|supervise|runtime\.sh/ &&
    !($0 ~ /rsync --server/ && $NF ~ /^\/mpac\/sdicks02\/mirrors\//)' | sort
}
preflight() {
  local s1 s2 foreign mem free
  CONSOLE=$(console_users)
  mem=$(awk '/^MemAvailable:/ {print int($2/1048576)}' /proc/meminfo); int "$mem" memavailable
  free=$(df -BG --output=avail /mpac | tail -n 1 | tr -dc 0-9); int "$free" df
  s1=$(foreign_sample) || die 91 "process sample 1 failed"; sleep 15
  s2=$(foreign_sample) || die 91 "process sample 2 failed"
  foreign=$(comm -12 <(printf '%s\n' "$s1") <(printf '%s\n' "$s2"))
  log "preflight console_users=$CONSOLE memavailable_GiB=$mem mpac_free_GiB=$free loadavg=$(cut -d' ' -f1-3 /proc/loadavg)"
  log "other users' CPU%: $(ps -eo user=,pcpu= | awk '$1 != "sdicks02" {s += $2} END {print s+0}')"
  [ -z "$foreign" ] || { printf '%s\n' "$foreign"; die 91 "foreign sdicks02 processes present"; }
  [ "$mem" -ge 64 ] || die 92 "MemAvailable < 64 GiB"
  [ "$free" -ge 20 ] || die 93 "/mpac free < 20 GiB"
  [ -x "$PY" ] || die 94 "no runtime python"
  [ ! -e "$J/STOP" ] || die 95 "permanent STOP present"
}
json() { python3 -I -c 'import json,sys; v=json.load(open(sys.argv[1]))[sys.argv[2]]; assert isinstance(v,int) and not isinstance(v,bool) and v>1; print(v)' "$1" "$2"; }
# start PHASE WORKLIST WORKERS STOP_AT: fresh instance J/inst/PHASE (own job dir and STOP file), detached supervisor.
start() {
  local I=$J/inst/$1 n
  [ ! -e "$J/STOP" ] || die 95 "permanent STOP present"
  mkdir "$I" "$I/repo" "$I/repo/reports" "$I/repo/reports/explore" "$I/repo/reports/explore/x4s2"
  cp "$E/x4s2/runtime.sh" "$I/repo/reports/explore/x4s2/runtime.sh"   # only file the supervisor needs under --job
  cmp "$E/x4s2/runtime.sh" "$I/repo/reports/explore/x4s2/runtime.sh"
  bash "$E/x4s2/detach.sh" "$I/supervisor.log" "$I/receipt.json" nice -n 19 choom -n 1000 -- prlimit --as=8589934592 \
    taskset -c 62 env X4S2_JOB="$J" \
    bash "$E/x4s2/runtime.sh" reports/explore/x4s2/supervise.py --job "$I" --phase "$1" --worklist "$2" \
    --config "$E/fsc/$cfg" --workers "$3" --stop-at "$4" || die 101 "detach $1"
  for ((n = 0; n < 60; n++)); do [ -s "$I/$1/launch.json" ] && break; sleep 1; done
  [ -s "$I/$1/launch.json" ] || { touch "$I/STOP"; die 101 "$1: no launch.json in 60 s (instance STOP touched)"; }
  [ "$(json "$I/receipt.json" pid)" = "$(json "$I/$1/launch.json" supervisor_pid)" ] || die 101 "$1: receipt/launch PID mismatch"
  cat "$I/receipt.json" "$I/$1/launch.json"
}
wait_exit() {  # wait_exit PHASE_DIR SECONDS
  local i; for ((i = 0; i < $2; i += 2)); do [ -s "$1/supervisor-exit.json" ] && return 0; sleep 2; done; return 1
}
in_minutes() { date -u -d "+$1 minutes" +%Y-%m-%dT%H:%M:%SZ; }
current() { local I; I=$(cat "$J/current-instance"); [[ $I == "$J"/inst/rep"$tag"* ]] || die 90 "bad current-instance"; echo "$I"; }

case $cmd in
launch)
  msha=${3:-}; arg=${4:-}
  [[ $msha =~ ^[0-9a-f]{64}$ ]] || die 90 "manifest sha"
  [[ $arg =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$ ]] || die 90 "STOP_AT required (ISO UTC)"
  if [[ $arg > $DEADLINE ]]; then die 90 "STOP_AT after $DEADLINE"; fi
  [ "$(ls -A "$J")" = bundle ] || die 96 "expected fresh $J holding only bundle/"
  ST nolinks "$J"
  preflight
  mkdir "$J/logs" "$J/cache" "$J/inst"
  python3 -I -B "$J/bundle/fsc/hostcheck.py" snapshot "$J/logs/baseline-ps.json"   # baseline for the STOP proof
  if [ "$host" = 127x03 ]; then
    for d in "$BASE" "$BASE/repo" "$BASE/native" "$BASE/inputs"; do
      if [ -L "$d" ] || [ ! -d "$d" ] || [ "$(realpath -e "$d")" != "$d" ]; then die 97 "source $d missing, linked or not canonical"; fi
    done
    need=$(ST need "$BASE" "$J/bundle" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["need_GiB"])'); int "$need" need
    free=$(df -BG --output=avail /mpac | tail -n 1 | tr -dc 0-9); int "$free" df
    log "copy needs ${need} GiB; /mpac free ${free} GiB"
    [ "$free" -ge $(( need + 20 )) ] || die 93 "/mpac free < copy size + 20 GiB"
    ST shadowscan "$BASE/repo" "$J/bundle"
    ST allowlist "$J/bundle" "$J/logs/repo-allowlist.txt"
    printf '%s\n' main02.pt R3a.pt R3a-calibration.json > "$J/logs/inputs-allowlist.txt"
    # Allowlist copies only (the S1 pin's files; the native dir; three inputs). Symlinks are never copied (--no-links).
    nice -n 19 rsync -rt --no-links --files-from="$J/logs/repo-allowlist.txt" "$BASE/repo/" "$J/repo/"
    nice -n 19 rsync -rt --no-links "$BASE/native/" "$J/native/"
    nice -n 19 rsync -rt --no-links --files-from="$J/logs/inputs-allowlist.txt" "$BASE/inputs/" "$J/inputs/"
  else
    bash "$J/bundle/fsc/lan_copy_04.sh"
  fi
  ST install "$J" "$J/bundle" "$host" "$msha"
  log "staged: $(du -sh "$J" | cut -f1)"
  # 8-seed smoke (8 workers; smoke range; excluded from every analysis).
  start "smoke-$tag" "$E/fsc/wl-smoke-$tag.json" 8 "$(in_minutes 30)"
  P=$J/inst/smoke-$tag/smoke-$tag
  wait_exit "$P" 1500 || { touch "$J/inst/smoke-$tag/STOP"; wait_exit "$P" 240 || true; die 99 "smoke: no exit in 25 min"; }
  HC smoke "$P" "$E/fsc/$cfg" "$host" || die 99 "smoke gate"
  # Live STOP test (4 workers; STOP-test range): STOP only once a block has started and workers are live.
  start "stoptest-$tag" "$E/fsc/wl-stoptest-$tag.json" 4 "$(in_minutes 30)"
  I=$J/inst/stoptest-$tag; P=$I/stoptest-$tag; ok=0
  for ((n = 0; n < 90; n++)); do
    if HC prestop "$P" > "$I/pre-stop.json"; then ok=1; break; fi; sleep 2
  done
  [ "$ok" = 1 ] || { touch "$I/STOP"; die 100 "STOP test: no live started block within 180 s"; }
  touch "$I/STOP"; t=$(date +%s.%N); log "STOP test: instance STOP touched at epoch $t"
  wait_exit "$P" 240 || die 100 "STOP test: no supervisor exit in 240 s"
  HC stoptest "$P" "$t" "$I/pre-stop.json" || die 100 "STOP test gate"
  # Reporting run: 12 slots, or 10 with a console user; stop-at = min(now + 7 h 55 min, STOP_AT <= DEADLINE).
  preflight
  workers=12; [ "$CONSOLE" -eq 0 ] || workers=10
  stop_at=$(in_minutes 475); if [[ $arg < $stop_at ]]; then stop_at=$arg; fi
  if [[ ! $stop_at > $(date -u +%Y-%m-%dT%H:%M:%SZ) ]]; then die 101 "stop-at $stop_at already passed"; fi
  printf '%s\n' "$stop_at" > "$J/stop-at"; printf '%s\n' "$E/fsc/wl-$tag.json" > "$J/current-worklist"
  printf '%s\n' "$J/inst/rep$tag" > "$J/current-instance"
  start "rep$tag" "$E/fsc/wl-$tag.json" "$workers" "$stop_at"
  sleep 60
  P=$J/inst/rep$tag/rep$tag
  HC census live "$(json "$P/launch.json" child_pgid)" "$(json "$P/launch.json" supervisor_pid)" \
    || { touch "$J/inst/rep$tag/STOP"; die 101 "reporting run not live after 60 s (instance STOP touched)"; }
  HC guard "$P" || { touch "$J/inst/rep$tag/STOP"; die 101 "memory guards missing on the reporting run (instance STOP touched)"; }
  log "reporting running: rep$tag workers=$workers stop_at=$stop_at started=$(find "$P/blocks" -name '*.started' | wc -l)"
  ;;

progress)
  I=$(current); ph=$(basename "$I"); P=$I/$ph
  if [ -s "$P/progress.json" ]; then cat "$P/progress.json"; fi
  if [ -e "$P/supervisor-exit.json" ]; then HC exitstatus "$P" || die 102 "run ended for an unplanned reason"; exit 0; fi
  HC census live "$(json "$P/launch.json" child_pgid)" "$(json "$P/launch.json" supervisor_pid)" \
    || die 102 "run not live and no exit record"
  console=$(console_users); workers=$(json "$P/launch.json" workers)
  log "phase=$ph workers=$workers console_users=$console proofs=$(find "$P/blocks" -name '*.json' | wc -l)"
  if [ "$console" -gt 0 ] && [ "$workers" -gt 10 ]; then
    # Yield: stop this instance by its own STOP, prove it is gone, relaunch its never-started blocks on 10 slots.
    [ ! -e "$J/STOP" ] || die 95 "permanent STOP present: no yield relaunch"
    log "console user present: yielding to 10 slots"; touch "$I/STOP"
    wait_exit "$P" 240 || die 102 "yield: no supervisor exit in 240 s"
    HC exitstatus "$P" || die 102 "yield: exit record or census not clean"
    python3 -I -c 'import json,sys; assert json.load(open(sys.argv[1]))["reason"]=="owned_STOP"' "$P/supervisor-exit.json"
    n=$(find "$J/inst" -mindepth 1 -maxdepth 1 -name "rep$tag*" | wc -l); new=rep$tag-y$n
    python3 -I -B "$E/x4s2/leftover.py" "$(cat "$J/current-worklist")" "$P" "$J/logs/wl-$new.json"
    printf '%s\n' "$J/logs/wl-$new.json" > "$J/current-worklist"; printf '%s\n' "$J/inst/$new" > "$J/current-instance"
    start "$new" "$J/logs/wl-$new.json" 10 "$(cat "$J/stop-at")"
    sleep 60
    HC census live "$(json "$J/inst/$new/$new/launch.json" child_pgid)" "$(json "$J/inst/$new/$new/launch.json" supervisor_pid)" \
      || { touch "$J/inst/$new/STOP"; die 102 "yield relaunch not live (instance STOP touched)"; }
  fi
  ;;

stop)
  touch "$J/STOP"; for I in "$J"/inst/*/; do touch "$I/STOP"; done; log "permanent and instance STOP files touched"
  I=$(current); P=$I/$(basename "$I")
  wait_exit "$P" 240 || die 103 "no supervisor-exit.json in 240 s (STOP files stay)"
  for I in "$J"/inst/*/; do
    I=${I%/}; P=$I/$(basename "$I")
    HC census empty "$(json "$I/receipt.json" pgid)" "$(json "$I/receipt.json" pid)" || die 103 "census $I"
    HC exitstatus "$P" || die 103 "exit record $P"
  done
  proof=0; HC proof "$J" || proof=$?   # mirror the outputs even if the proof fails, then report the failure
  ST nolinks "$J"
  nice -n 19 rsync -rt --no-links -e "$SSHOPT" --rsync-path='nice -n 19 rsync' \
    --exclude=/repo/ --exclude=/native/ --exclude=/inputs/ --exclude=/cache/ --exclude=/bundle/ \
    "$J/" "127x05:$MIRROR/$host/"
  log "outputs mirrored to 127x05:$MIRROR/$host"
  [ "$proof" = 0 ] || die 104 "STOP proof failed (see JSON above); STOP files stay"
  ;;
*) die 90 "unknown command '$cmd'";;
esac
