#!/bin/bash
# Roll back one feed_only_deploy.sh run on the Mac: display_feed.py only. Review before use.
#
#   feed_only_rollback.sh STAMP FEED_PID
#
# STAMP names display/feed-deploy-<STAMP>/ (receipt.txt + backup/display_feed.py). Order:
#   lock -> strict receipt parse -> backup hash-checked vs the receipt -> current feed saved to
#   feed-deploy-<STAMP>/rollback-<NOW>/ (hash-checked) -> restore temp beside the target (hash-checked) -> preflight
#   -> rename (verified) -> preflight -> exact PID re-verified + gate open -> SIGTERM that PID -> respawn.
# dispgrab, stream-source.json, capture-gate, supervisor and MediaMTX are never touched (the crop config has its own
# data backup: display/stream-source.before-black-fix-20261018.json). A failure after the rename and before the signal
# puts the saved current feed back (EXIT trap). Last stdout line: __RC=<n>.
set -u
set -o pipefail
rc=1; LOCKED=0; MUTATED=0; SIGNALED=0; FEED_PID=""; SAVE=""
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
on_exit() {
  if [ "$rc" != 0 ] && [ "$MUTATED" = 1 ] && [ "$SIGNALED" = 0 ]; then
    local want
    say "rollback failed before the signal: putting the deployed feed back from $SAVE"
    if want=$(sha "$SAVE/display_feed.py") && cp -p "$SAVE/display_feed.py" "$D/.display_feed.py.rec-$NOW" \
       && mv -f "$D/.display_feed.py.rec-$NOW" "$D/display_feed.py" && [ "$(sha "$D/display_feed.py")" = "$want" ]; then
      say "RECOVERED: deployed feed back; feed not signalled"
    else
      say "RECOVERY INCOMPLETE: inspect $SAVE"
    fi
  fi
  rm -f "$D/.display_feed.py.rb-$NOW" "$D/.display_feed.py.rec-$NOW" 2>/dev/null
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
preflight() { WS_NESTED=1 bash "$HERE/window_source_preflight.sh" "$FEED_PID" || die "preflight failed (see above)" 11; }
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
PRIV="$D/feed-deploy-$STAMP"
SAVE="$PRIV/rollback-$NOW"
say "feed-only rollback start stamp=$STAMP feed_pid=$FEED_PID"
mkdir "$LOCK" 2>/dev/null || die "lock $LOCK exists: another deploy/rollback is running (or stale: inspect, then rmdir)" 3
LOCKED=1
[ -f "$PRIV/receipt.txt" ] || die "no receipt $PRIV/receipt.txt" 3

B_FEED=$(field before_display_feed.py) && is_sha "$B_FEED" || die "receipt before_display_feed.py malformed" 3
A_FEED=$(field after_display_feed.py) && is_sha "$A_FEED" || die "receipt after_display_feed.py malformed" 3
[ "$(sha "$PRIV/backup/display_feed.py")" = "$B_FEED" ] || die "backup display_feed.py does not match the receipt" 3
C_FEED=$(sha "$D/display_feed.py") || die "live display_feed.py unreadable" 3
[ "$C_FEED" = "$A_FEED" ] || say "note: live display_feed.py $C_FEED is not the deployed $A_FEED (changed since; saved anyway)"

# ---- save the current feed, prepare the restore temp (hash-checked) -- nothing live changed yet
mkdir -m 700 "$SAVE" || die "cannot create $SAVE" 4
cp -p "$D/display_feed.py" "$SAVE/display_feed.py" && [ "$(sha "$SAVE/display_feed.py")" = "$C_FEED" ] || die "save failed" 4
cp -p "$PRIV/backup/display_feed.py" "$D/.display_feed.py.rb-$NOW" && [ "$(sha "$D/.display_feed.py.rb-$NOW")" = "$B_FEED" ] \
  || die "restore temp failed" 4

preflight
[ "$(sha "$D/display_feed.py")" = "$C_FEED" ] || die "live feed changed since the save" 4
MUTATED=1
mv -f "$D/.display_feed.py.rb-$NOW" "$D/display_feed.py" || die "rename failed" 22
[ "$(sha "$D/display_feed.py")" = "$B_FEED" ] || die "live feed hash after restore is not $B_FEED" 22
say "restored display_feed.py $B_FEED (deployed copy in $SAVE)"
preflight
SUP=$(feed_ok "$FEED_PID") || die "PID $FEED_PID is not a display_feed.py under video_supervisor.py" 12
[ "$(tr -d ' \n' < "$D/capture-gate" 2>/dev/null)" = open ] || die "capture-gate not open right before TERM" 12
SIGNALED=1
say "TERM feed $FEED_PID (supervisor $SUP)"
kill -TERM "$FEED_PID" || die "kill -TERM $FEED_PID failed (restored file stays; feed not restarted)" 13
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
echo "rollback $NOW old_feed $FEED_PID new_feed $NEW feed $B_FEED $(date -u +%FT%TZ)" >> "$PRIV/receipt.txt" \
  || die "receipt append failed" 21
rc=0
