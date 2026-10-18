#!/bin/bash
# Fault test for display_feed's stale-capture watchdog on the Mac: SIGSTOP the exact capture child, expect the feed to
# replace it. Read-only except the STOP/CONT of that one PID. Review before use.
#
#   capture_fault_test.sh FEED_PID CAPTURE_PID FEED_SHA256 [WAIT_S=45, 35..120]
#
# Checks first (all must hold): FEED_PID is display/display_feed.py under video_supervisor.py; the installed
# display_feed.py hashes to FEED_SHA256 (the watchdog build); CAPTURE_PID is "<display>/bin/dispgrab stream ...", a
# child of FEED_PID, the dispgrab pid in display/pipeline.json, and the ONLY dispgrab stream/grid process; no vision
# driver ('[d]rive[.]py'); capture-gate reads open. Then SIGSTOP CAPTURE_PID only. A stopped dispgrab writes no stats
# line, so the feed sees "no dispgrab stats line" STATS_LATE_S (15 s) after the last one (<= 15 s after the STOP),
# TERMs it (pending while stopped), KILLs it 2 s later (reap wait <= 2 s), and starts one replacement after the
# guarded checks (pgrep x2, ps, dispgrab info <= 3 s): estimated worst ~22 s after the STOP; WAIT_S (default 45) is the
# test deadline, not a proven bound. PASS = CAPTURE_PID gone, exactly one dispgrab capture, a child of FEED_PID,
# recorded in pipeline.json, and within 25 s after it appears a FRESH state.json (t within 3 s) with video.running true,
# kind 'display', capture_pid = the replacement, capture_age_s < 2 (its first stats line comes after 10 s), and
# stale_restarts above its pre-test value (the watchdog replaced it, not a process exit).
# EXIT trap: if CAPTURE_PID still exists with the same command and is stopped, SIGCONT it. Never signals by pattern,
# group, or any other PID. Last stdout line: __RC=<n>.
set -u
set -o pipefail
rc=1; STOPPED=0; CAP=""; CAPCMD=""
LOOP="$HOME/clasher-live/loop"
D="$LOOP/display"
PYI="$HOME/clasher-live/venv/bin/python"
say() { echo "$(date -u +%FT%TZ) $*"; }
die() { say "ERROR: $*"; rc=${2:-1}; exit "$rc"; }
on_exit() {
  if [ "$STOPPED" = 1 ] && [ -n "$CAP" ]; then
    local c st
    c=$(ps -p "$CAP" -o command= 2>/dev/null)
    st=$(ps -p "$CAP" -o stat= 2>/dev/null | tr -d ' ')
    if [ -n "$c" ] && [ "$c" = "$CAPCMD" ]; then
      case "$st" in T*) say "old capture $CAP still stopped: SIGCONT"; kill -CONT "$CAP" || say "SIGCONT $CAP failed" ;; esac
    fi
  fi
  echo "__RC=$rc"
}
trap on_exit EXIT
trap 'die "interrupted" 30' INT TERM HUP

caps() { ps -axo pid=,ppid=,command= | awk '{c=$0; sub(/^ *[0-9]+ +[0-9]+ /, "", c); if (c ~ /[d]ispgrab (stream|grid) /) print $1" "$2}'; }
pjson() { "$PYI" -I -c 'import json,sys; v=json.load(open(sys.argv[1])).get("dispgrab"); print(v if isinstance(v,int) else "")' "$D/pipeline.json" 2>/dev/null; }
video() { "$PYI" -I -c 'import json,sys; v=json.load(open(sys.argv[1]))["video"]; print(json.dumps({k: v.get(k) for k in ("kind","running","starts","capture_age_s","capture_pid","stale_restarts","last_stale","window_probe","error")}))' "$D/state.json" 2>/dev/null; }
restarts() { "$PYI" -I -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["video"]["stale_restarts"]))' "$D/state.json" 2>/dev/null; }
age_ok() {   # $1 replacement pid, $2 stale_restarts before the STOP
  "$PYI" -I -c 'import json,sys,time
st = json.load(open(sys.argv[1])); v = st["video"]; a = v.get("capture_age_s")
ok = (abs(time.time() - float(st["t"])) < 3 and v.get("running") is True and v.get("kind") == "display"
      and v.get("capture_pid") == int(sys.argv[2]) and isinstance(a, (int, float)) and 0 <= a < 2
      and int(v.get("stale_restarts") or 0) > int(sys.argv[3]))
sys.exit(0 if ok else 1)' "$D/state.json" "$1" "$2" 2>/dev/null
}

[ $# -ge 3 ] && [ $# -le 4 ] || die "usage: $0 FEED_PID CAPTURE_PID FEED_SHA256 [WAIT_S]" 2
FEED_PID="$1"; CAP="$2"; WANT="$3"; WAIT_S="${4:-45}"
for v in "$FEED_PID" "$CAP" "$WAIT_S"; do case "$v" in ''|*[!0-9]*) die "bad numeric argument '$v'" 2 ;; esac; done
[ "$FEED_PID" -gt 1 ] && [ "$CAP" -gt 1 ] && [ "$WAIT_S" -ge 35 ] && [ "$WAIT_S" -le 120 ] || die "argument out of range (WAIT_S 35..120)" 2
case "$WANT" in *[!0-9a-f]*|'') die "bad FEED_SHA256" 2 ;; esac; [ ${#WANT} = 64 ] || die "bad FEED_SHA256" 2
say "capture fault test feed=$FEED_PID capture=$CAP wait=${WAIT_S}s"

fcmd=$(ps -p "$FEED_PID" -o command= 2>/dev/null) || die "no process $FEED_PID" 3
case "$fcmd" in *display/display_feed.py*) ;; *) die "PID $FEED_PID is not display_feed.py" 3 ;; esac
SUP=$(ps -p "$FEED_PID" -o ppid= | tr -d ' ')
case "$(ps -p "$SUP" -o command= 2>/dev/null)" in *video_supervisor.py*) ;; *) die "feed parent $SUP is not video_supervisor.py" 3 ;; esac
[ "$(shasum -a 256 "$D/display_feed.py" | awk '{print $1}')" = "$WANT" ] || die "installed display_feed.py is not $WANT" 3
CAPCMD=$(ps -p "$CAP" -o command= 2>/dev/null) || die "no process $CAP" 4
case "$CAPCMD" in "$D/bin/dispgrab stream "*) ;; *) die "PID $CAP is not $D/bin/dispgrab stream: ${CAPCMD:0:120}" 4 ;; esac
[ "$(ps -p "$CAP" -o ppid= | tr -d ' ')" = "$FEED_PID" ] || die "capture $CAP is not a child of feed $FEED_PID" 4
[ "$(pjson)" = "$CAP" ] || die "pipeline.json dispgrab is not $CAP" 4
C=$(caps); [ "$C" = "$CAP $FEED_PID" ] || die "capture clients are not exactly $CAP: $(echo "$C" | tr '\n' ';')" 4
D_RE=$(ps -axo command= | awk '/[d]rive[.]py/' | head -3)
[ -z "$D_RE" ] || die "vision driver running: ${D_RE:0:160}" 5
[ "$(tr -d ' \n' < "$D/capture-gate" 2>/dev/null)" = open ] || die "capture-gate not open" 5
R0=$(restarts) || die "state.json unreadable (stale_restarts): is the watchdog build running?" 5
case "$R0" in ''|*[!0-9]*) die "bad stale_restarts '$R0'" 5 ;; esac
say "before: stale_restarts=$R0 $(video)"

# last identity re-check, then STOP that PID only
[ "$(ps -p "$CAP" -o command= 2>/dev/null)" = "$CAPCMD" ] || die "capture $CAP changed before STOP" 4
STOPPED=1
T0=$(date +%s)
kill -STOP "$CAP" || die "kill -STOP $CAP failed" 6
say "SIGSTOP $CAP"
NEWCAP=""
while [ $(( $(date +%s) - T0 )) -le "$WAIT_S" ]; do
  sleep 1
  C=$(caps)
  if ! kill -0 "$CAP" 2>/dev/null && [ "$(echo "$C" | grep -c '[0-9]')" = 1 ]; then
    set -- $C
    if [ "$2" = "$FEED_PID" ] && [ "$(pjson)" = "$1" ]; then NEWCAP="$1"; break; fi
  fi
  [ $(( ($(date +%s) - T0) % 5 )) = 0 ] && say "t+$(( $(date +%s) - T0 ))s clients=[$(echo "$C" | tr '\n' ';')] $(video)"
done
[ -n "$NEWCAP" ] || die "no single replacement capture within ${WAIT_S}s (clients: $(caps | tr '\n' ';'))" 7
STOPPED=0
say "replaced: $CAP -> $NEWCAP after $(( $(date +%s) - T0 ))s; $(grep -E 'capture stale|capture recovery' "$D/feed.log" 2>/dev/null | tail -2 | tr '\n' ' ')"
T1=$(date +%s)
until age_ok "$NEWCAP" "$R0"; do
  [ $(( $(date +%s) - T1 )) -le 25 ] || die "replacement $NEWCAP: no fresh healthy watchdog state within 25 s: $(video)" 8
  sleep 1
done
C=$(caps); [ "$C" = "$NEWCAP $FEED_PID" ] || die "capture clients after recovery: $(echo "$C" | tr '\n' ';')" 8
say "PASS: $(video)"
rc=0
