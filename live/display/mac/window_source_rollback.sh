#!/bin/bash
# Roll back one window_source_deploy.sh run on the Mac. Review before use.
#
#   window_source_rollback.sh STAMP FEED_PID
#
# STAMP names display/window-deploy-<STAMP>/ (receipt.txt + backup/). Order:
#   lock -> strict receipt parse (exactly one before_/after_ line each) -> every backup hash-checked vs the receipt
#   (config too, when it was present) -> current files saved to window-deploy-<STAMP>/rollback-<NOW>/ (hash-checked)
#   -> restore temps beside the targets (hash-checked) -> preflight BEFORE any live change -> renames (verified)
#   -> preflight incl. "the restored feed ignores the live config" -> SIGTERM the exact feed PID -> respawn
#   -> config last: restore the old one, or (absent before) move the deployed one into rollback-<NOW>/ (nothing deleted).
# A failure after the first rename and before the signal puts the saved current files back (EXIT trap).
# Last stdout line: __RC=<n>.
set -u
set -o pipefail
rc=1; LOCKED=0; MUTATED=0; SIGNALED=0; FEED_PID=""
LOOP="$HOME/clasher-live/loop"
D="$LOOP/display"
LOCK="$D/.window-source.lock"
NOW="$(date -u +%Y%m%dT%H%M%SZ)-$$"

say() { echo "$(date -u +%FT%TZ) $*"; }
die() { say "ERROR: $*"; rc=${2:-1}; exit "$rc"; }
sha() {
  local h
  h=$(shasum -a 256 "$1" 2>/dev/null | awk '{print $1}') || return 1
  case "$h" in *[!0-9a-f]*|'') return 1 ;; esac
  [ ${#h} = 64 ] || return 1
  echo "$h"
}
put() {   # put TMP DEST WANT_SHA
  mv -f "$1" "$2" || die "rename $1 -> $2 failed" 22
  [ "$(sha "$2")" = "$3" ] || die "$2 hash after restore is not $3" 22
}
restore_one() {   # best effort, never exits (EXIT trap)
  local want
  want=$(sha "$1") || { echo "  RESTORE FAILED $2 (saved copy unreadable)"; return 1; }
  cp -p "$1" "$3" && mv -f "$3" "$2" && [ "$(sha "$2")" = "$want" ] && echo "  put back $2" && return 0
  echo "  RESTORE FAILED $2"; return 1
}
on_exit() {
  if [ "$rc" != 0 ] && [ "$MUTATED" = 1 ] && [ "$SIGNALED" = 0 ]; then
    local ok=0
    say "rollback failed before the signal: putting the deployed files back from $SAVE"
    restore_one "$SAVE/display_feed.py" "$D/display_feed.py" "$D/.display_feed.py.rec-$NOW" || ok=1
    restore_one "$SAVE/dispgrab" "$D/bin/dispgrab" "$D/bin/.dispgrab.rec-$NOW" || ok=1
    if [ "$ok" = 0 ]; then say "RECOVERED: deployed state back; feed not signalled"; else say "RECOVERY INCOMPLETE: inspect $SAVE"; fi
  fi
  rm -f "$D/.display_feed.py.rb-$NOW" "$D/bin/.dispgrab.rb-$NOW" "$LOOP/.stream-source.json.rb-$NOW" 2>/dev/null
  if [ "$LOCKED" = 1 ]; then rmdir "$LOCK" 2>/dev/null || echo "WARNING: could not remove $LOCK"; fi
  echo "__RC=$rc"
}
trap on_exit EXIT
trap 'die "interrupted" 30' INT TERM HUP
HERE=$(cd "$(dirname "$0")" && pwd) || die "no script dir" 2

feed_ok() {
  local cmd ppid pcmd
  cmd=$(ps -p "$1" -o command= 2>/dev/null) || return 1
  case "$cmd" in *display/display_feed.py*) ;; *) return 1 ;; esac
  ppid=$(ps -p "$1" -o ppid= 2>/dev/null | tr -d ' ') || return 1
  pcmd=$(ps -p "$ppid" -o command= 2>/dev/null) || return 1
  case "$pcmd" in *video_supervisor.py*) echo "$ppid"; return 0 ;; esac
  return 1
}
preflight() { WS_NESTED=1 bash "$HERE/window_source_preflight.sh" "$FEED_PID" "$@" || die "preflight failed (see above)" 11; }
field() {   # field KEY: the value of the single "KEY value" receipt line, or die
  local n v
  n=$(awk -v k="$1" '$1 == k' "$PRIV/receipt.txt" | wc -l | tr -d ' ') || die "receipt read failed" 3
  [ "$n" = 1 ] || die "receipt has $n '$1' lines (need exactly 1)" 3
  v=$(awk -v k="$1" '$1 == k {print $2}' "$PRIV/receipt.txt") || die "receipt read failed" 3
  [ -n "$v" ] || die "receipt '$1' empty" 3
  echo "$v"
}
is_sha() { case "$1" in *[!0-9a-f]*|'') return 1 ;; esac; [ ${#1} = 64 ]; }

[ $# -eq 2 ] || die "usage: $0 STAMP FEED_PID" 2
STAMP="$1"; FEED_PID="$2"
case "$STAMP" in */*|.*|'') die "bad STAMP" 2 ;; esac
case "$FEED_PID" in ''|*[!0-9]*) die "bad FEED_PID" 2 ;; esac
[ "$FEED_PID" -gt 1 ] || die "bad FEED_PID $FEED_PID" 2
[ -f "$HERE/window_source_preflight.sh" ] || die "window_source_preflight.sh not next to this script" 2
PRIV="$D/window-deploy-$STAMP"
SAVE="$PRIV/rollback-$NOW"
say "rollback start stamp=$STAMP feed_pid=$FEED_PID"
mkdir "$LOCK" 2>/dev/null || die "lock $LOCK exists: another deploy/rollback is running (or stale: inspect, then rmdir)" 3
LOCKED=1
[ -f "$PRIV/receipt.txt" ] || die "no receipt $PRIV/receipt.txt" 3

# ---- strict receipt + backups
B_FEED=$(field before_display_feed.py) && is_sha "$B_FEED" || die "receipt before_display_feed.py malformed" 3
B_GRAB=$(field before_dispgrab) && is_sha "$B_GRAB" || die "receipt before_dispgrab malformed" 3
B_CONF=$(field before_stream-source.json) || die "receipt before_stream-source.json missing" 3
{ [ "$B_CONF" = absent ] || is_sha "$B_CONF"; } || die "receipt before_stream-source.json malformed: $B_CONF" 3
A_FEED=$(field after_display_feed.py) && is_sha "$A_FEED" || die "receipt after_display_feed.py malformed" 3
A_GRAB=$(field after_dispgrab) && is_sha "$A_GRAB" || die "receipt after_dispgrab malformed" 3
NOCONF=$(field no_config) || die "receipt no_config missing" 3
case "$NOCONF" in 0|1) ;; *) die "receipt no_config malformed" 3 ;; esac
[ "$(sha "$PRIV/backup/display_feed.py")" = "$B_FEED" ] || die "backup display_feed.py does not match the receipt" 3
[ "$(sha "$PRIV/backup/dispgrab")" = "$B_GRAB" ] || die "backup dispgrab does not match the receipt" 3
if [ "$B_CONF" != absent ]; then
  [ "$(sha "$PRIV/backup/stream-source.json")" = "$B_CONF" ] || die "backup stream-source.json does not match the receipt" 3
fi
C_FEED=$(sha "$D/display_feed.py") || die "live display_feed.py unreadable" 3
C_GRAB=$(sha "$D/bin/dispgrab") || die "live dispgrab unreadable" 3
[ "$C_FEED" = "$A_FEED" ] || say "note: live display_feed.py $C_FEED is not the deployed $A_FEED (changed since; saved anyway)"
[ "$C_GRAB" = "$A_GRAB" ] || say "note: live dispgrab $C_GRAB is not the deployed $A_GRAB (changed since; saved anyway)"

# ---- save the current files, prepare restore temps (all hash-checked) -- nothing live changed yet
mkdir -m 700 "$SAVE" || die "cannot create $SAVE" 4
cp -p "$D/display_feed.py" "$SAVE/display_feed.py" && [ "$(sha "$SAVE/display_feed.py")" = "$C_FEED" ] || die "save of display_feed.py failed" 4
cp -p "$D/bin/dispgrab" "$SAVE/dispgrab" && [ "$(sha "$SAVE/dispgrab")" = "$C_GRAB" ] || die "save of dispgrab failed" 4
cp -p "$PRIV/backup/display_feed.py" "$D/.display_feed.py.rb-$NOW" && [ "$(sha "$D/.display_feed.py.rb-$NOW")" = "$B_FEED" ] \
  || die "feed restore temp failed" 4
cp -p "$PRIV/backup/dispgrab" "$D/bin/.dispgrab.rb-$NOW" && [ "$(sha "$D/bin/.dispgrab.rb-$NOW")" = "$B_GRAB" ] \
  || die "dispgrab restore temp failed" 4
if [ "$NOCONF" = 0 ] && [ "$B_CONF" != absent ]; then
  cp -p "$PRIV/backup/stream-source.json" "$LOOP/.stream-source.json.rb-$NOW" \
    && [ "$(sha "$LOOP/.stream-source.json.rb-$NOW")" = "$B_CONF" ] || die "config restore temp failed" 4
fi

preflight                                # before any live file/config change
MUTATED=1
put "$D/bin/.dispgrab.rb-$NOW" "$D/bin/dispgrab" "$B_GRAB"
put "$D/.display_feed.py.rb-$NOW" "$D/display_feed.py" "$B_FEED"
say "restored display_feed.py $B_FEED, dispgrab $B_GRAB (deployed copies in $SAVE)"
# the running (deployed) feed keeps the window config until replaced; the restored feed must ignore it
if [ -f "$LOOP/stream-source.json" ]; then preflight "$LOOP/stream-source.json"; else preflight; fi
SUP=$(feed_ok "$FEED_PID") || die "PID $FEED_PID is not a display_feed.py under video_supervisor.py" 12
[ "$(tr -d ' \n' < "$D/capture-gate" 2>/dev/null)" = open ] || die "capture-gate not open right before TERM" 12
SIGNALED=1
say "TERM feed $FEED_PID (supervisor $SUP)"
kill -TERM "$FEED_PID" || die "kill -TERM $FEED_PID failed (restored files stay; feed not restarted)" 13
for _ in $(seq 1 100); do kill -0 "$FEED_PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$FEED_PID" 2>/dev/null; then
  die "feed $FEED_PID still alive 10 s after TERM (it defers exit during a battle; it exits after it; do not resend)" 13
fi
NEW=""
for _ in $(seq 1 60); do
  NEW=$(ps -axo pid=,ppid=,command= | awk -v s="$SUP" -v o="$FEED_PID" '$2 == s && $1 != o && /display\/display_feed\.py/ {print $1}' | tail -1)
  [ -n "$NEW" ] && break
  sleep 0.5
done
[ -n "$NEW" ] || die "supervisor $SUP did not respawn a feed within 30 s" 14
say "new feed pid $NEW"

# ---- config last (the restored feed ignores a kind:window file, checked above)
if [ "$NOCONF" = 1 ]; then
  say "deploy did not write the config; left as is"
elif [ "$B_CONF" != absent ]; then
  put "$LOOP/.stream-source.json.rb-$NOW" "$LOOP/stream-source.json" "$B_CONF"
  say "restored stream-source.json $B_CONF"
elif [ -f "$LOOP/stream-source.json" ]; then
  mv "$LOOP/stream-source.json" "$SAVE/stream-source.json" || die "config move-aside failed" 15
  say "moved the deployed stream-source.json to $SAVE/ (none before the deploy)"
fi
{ echo "rollback $NOW old_feed $FEED_PID new_feed $NEW feed $B_FEED dispgrab $B_GRAB config $B_CONF $(date -u +%FT%TZ)"; } \
  >> "$PRIV/receipt.txt" || die "receipt append failed" 21
rc=0
