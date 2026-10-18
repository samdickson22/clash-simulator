#!/bin/bash
# Swap ONLY display/display_feed.py on the Mac and restart the feed by exact PID. Review before use.
#
#   feed_only_deploy.sh STAGE_DIR FEED_PID
#
# STAGE_DIR: display_feed.py + SHA256SUMS listing exactly that one file (shasum -a 256). dispgrab (binary), the
# supervisor, MediaMTX, stream-source.json and capture-gate are never written (their hashes go to the receipt only).
# Single operator (mkdir lock display/.window-source.lock, shared with window_source_deploy/rollback). Order:
#   lock -> private snapshot display/feed-deploy-<STAMP>/ (700: stage/, backup/, receipt.txt) + manifest check
#   -> py_compile + import of the snapshot -> preflight -> backup (hash-checked) + temp beside the target (hash-checked)
#   -> preflight -> rename (verified) -> preflight -> exact PID re-verified + gate open -> SIGTERM that PID -> respawn.
# preflight = window_source_preflight.sh in this script's dir (exact feed PID under video_supervisor.py, no
# [d]rive.py / memloop process, no battle in a fresh log read, gate open). Any failure after the rename and before the
# signal restores the backup (EXIT trap). Never signals by group or pattern. Last stdout line: __RC=<n>.
set -u
set -o pipefail
rc=1; LOCKED=0; MUTATED=0; SIGNALED=0; PRIV=""; FEED_PID=""
LOOP="$HOME/clasher-live/loop"
D="$LOOP/display"
PY="$HOME/clasher-live/venv/bin/python"
LOCK="$D/.window-source.lock"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"

say() { echo "$(date -u +%FT%TZ) $*"; }
die() { say "ERROR: $*"; rc=${2:-1}; exit "$rc"; }
sha() {
  local h
  h=$(shasum -a 256 "$1" 2>/dev/null | awk '{print $1}') || return 1
  case "$h" in *[!0-9a-f]*|'') return 1 ;; esac
  [ ${#h} = 64 ] || return 1
  echo "$h"
}
rec() { echo "$*" >> "$PRIV/receipt.txt" || die "receipt write failed" 21; }
on_exit() {
  if [ "$rc" != 0 ] && [ "$MUTATED" = 1 ] && [ "$SIGNALED" = 0 ]; then
    local want
    say "restoring display_feed.py from $PRIV/backup"
    if want=$(sha "$PRIV/backup/display_feed.py") && cp -p "$PRIV/backup/display_feed.py" "$D/.display_feed.py.rec-$STAMP" \
       && mv -f "$D/.display_feed.py.rec-$STAMP" "$D/display_feed.py" && [ "$(sha "$D/display_feed.py")" = "$want" ]; then
      say "RECOVERED: pre-deploy display_feed.py back; feed not signalled"
    else
      say "RECOVERY INCOMPLETE: inspect $PRIV"
    fi
  fi
  rm -f "$D/.display_feed.py.new-$STAMP" "$D/.display_feed.py.rec-$STAMP" 2>/dev/null
  if [ "$LOCKED" = 1 ]; then rmdir "$LOCK" 2>/dev/null || echo "WARNING: could not remove $LOCK"; fi
  echo "__RC=$rc"
}
trap on_exit EXIT
trap 'die "interrupted" 30' INT TERM HUP
HERE=$(cd "$(dirname "$0")" && pwd) || die "no script dir" 2

feed_ok() {   # $1 pid: a display_feed.py whose parent is video_supervisor.py -> prints the supervisor pid
  local cmd ppid pcmd
  cmd=$(ps -p "$1" -o command= 2>/dev/null) || return 1
  case "$cmd" in *display/display_feed.py*) ;; *) return 1 ;; esac
  ppid=$(ps -p "$1" -o ppid= 2>/dev/null | tr -d ' ') || return 1
  pcmd=$(ps -p "$ppid" -o command= 2>/dev/null) || return 1
  case "$pcmd" in *video_supervisor.py*) echo "$ppid"; return 0 ;; esac
  return 1
}
preflight() { WS_NESTED=1 bash "$HERE/window_source_preflight.sh" "$FEED_PID" || die "preflight failed (see above)" 11; }

[ $# -eq 2 ] || die "usage: $0 STAGE_DIR FEED_PID" 2
STAGE="$1"; FEED_PID="$2"
case "$FEED_PID" in ''|*[!0-9]*) die "bad FEED_PID" 2 ;; esac
[ "$FEED_PID" -gt 1 ] || die "bad FEED_PID $FEED_PID" 2
[ -f "$HERE/window_source_preflight.sh" ] || die "window_source_preflight.sh not next to this script" 2
say "feed-only deploy start stamp=$STAMP feed_pid=$FEED_PID"
mkdir "$LOCK" 2>/dev/null || die "lock $LOCK exists: another deploy/rollback is running (or stale: inspect, then rmdir)" 3
LOCKED=1

# ---- private snapshot; the manifest must list exactly display_feed.py
PRIV="$D/feed-deploy-$STAMP"
{ mkdir -m 700 "$PRIV" && mkdir "$PRIV/stage" "$PRIV/backup"; } || die "cannot create private dir $PRIV" 4
: > "$PRIV/receipt.txt" || die "receipt create failed" 21
rec "stamp $STAMP"
[ -f "$STAGE/SHA256SUMS" ] || die "no $STAGE/SHA256SUMS" 4
cp "$STAGE/SHA256SUMS" "$PRIV/stage/SHA256SUMS" || die "manifest copy failed" 4
NL=$(wc -l < "$PRIV/stage/SHA256SUMS" | tr -d ' ') || die "manifest read failed" 4
[ "$NL" = 1 ] || die "manifest must have exactly 1 line" 4
NAME=$(awk '{print $2}' "$PRIV/stage/SHA256SUMS") || die "manifest read failed" 4
[ "$NAME" = display_feed.py ] || die "manifest must list display_feed.py (has: $NAME)" 4
NEW_FEED=$(awk '{print $1}' "$PRIV/stage/SHA256SUMS") || die "manifest read failed" 4
case "$NEW_FEED" in *[!0-9a-f]*|'') die "manifest sha malformed" 4 ;; esac
[ ${#NEW_FEED} = 64 ] || die "manifest sha malformed" 4
cp "$STAGE/display_feed.py" "$PRIV/stage/display_feed.py" || die "snapshot failed" 4
[ "$(sha "$PRIV/stage/display_feed.py")" = "$NEW_FEED" ] || die "snapshot does not match the manifest" 4
rec "stage_display_feed.py $NEW_FEED"

# ---- validate the snapshot (nothing live touched yet): compiles and imports (module level only; main() not run)
"$PY" -I -m py_compile "$PRIV/stage/display_feed.py" || die "display_feed.py does not compile" 5
"$PY" -I - "$PRIV/stage/display_feed.py" <<'PYEOF' || die "display_feed.py does not import" 5
import importlib.util, sys
spec = importlib.util.spec_from_file_location('df_new', sys.argv[1])
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)
assert callable(df.main) and callable(df.driver_running) and df.VISION_TTL_S > 0
print('import ok')
PYEOF

# ---- untouched files: receipt only
for f in "$D/bin/dispgrab" "$LOOP/stream-source.json"; do
  if [ -f "$f" ]; then rec "untouched $(basename "$f") $(sha "$f" || echo unreadable)"; else rec "untouched $(basename "$f") absent"; fi
done
preflight

# ---- backup (hash-checked) + temp beside the target (hash-checked)
[ -f "$D/display_feed.py" ] || die "live $D/display_feed.py missing" 7
B_FEED=$(sha "$D/display_feed.py") || die "sha of the live feed failed" 20
cp -p "$D/display_feed.py" "$PRIV/backup/display_feed.py" || die "backup failed" 7
[ "$(sha "$PRIV/backup/display_feed.py")" = "$B_FEED" ] || die "backup does not match (changed while copying?)" 7
rec "before_display_feed.py $B_FEED"
[ "$B_FEED" != "$NEW_FEED" ] || die "live feed already is $NEW_FEED: nothing to deploy" 7
{ cp "$PRIV/stage/display_feed.py" "$D/.display_feed.py.new-$STAMP" && chmod 755 "$D/.display_feed.py.new-$STAMP"; } \
  || die "feed temp failed" 8
[ "$(sha "$D/.display_feed.py.new-$STAMP")" = "$NEW_FEED" ] || die "feed temp hash mismatch" 8

# ---- last check, then the rename (until the signal, any failure restores the backup)
preflight
[ "$(sha "$D/display_feed.py")" = "$B_FEED" ] || die "live feed changed since the backup" 7
MUTATED=1
mv -f "$D/.display_feed.py.new-$STAMP" "$D/display_feed.py" || die "rename failed" 22
[ "$(sha "$D/display_feed.py")" = "$NEW_FEED" ] || die "live feed hash after install is not $NEW_FEED" 22
rec "after_display_feed.py $NEW_FEED"
say "installed; receipt $PRIV/receipt.txt:"
cat "$PRIV/receipt.txt" || die "receipt read failed" 21

# ---- restart: preflight, exact PID re-verified, gate open, then SIGTERM that PID only
preflight
SUP=$(feed_ok "$FEED_PID") || die "PID $FEED_PID is not a display_feed.py under video_supervisor.py" 12
[ "$(tr -d ' \n' < "$D/capture-gate" 2>/dev/null)" = open ] || die "capture-gate not open right before TERM" 12
SIGNALED=1
say "TERM feed $FEED_PID (supervisor $SUP)"
kill -TERM "$FEED_PID" || die "kill -TERM $FEED_PID failed (new file installed; feed not restarted)" 13
for _ in $(seq 1 100); do kill -0 "$FEED_PID" 2>/dev/null || break; sleep 0.1; done
if kill -0 "$FEED_PID" 2>/dev/null; then
  die "feed $FEED_PID still alive 10 s after TERM (it defers exit during a battle; investigate, do not resend)" 13
fi
NEW=""
for _ in $(seq 1 60); do
  NEW=$(ps -axo pid=,ppid=,command= | awk -v s="$SUP" -v o="$FEED_PID" '$2 == s && $1 != o && /display\/display_feed\.py/ {print $1}' | tail -1)
  [ -n "$NEW" ] && break
  sleep 0.5
done
[ -n "$NEW" ] || die "supervisor $SUP did not respawn a feed within 30 s" 14
say "new feed pid $NEW: $(ps -p "$NEW" -o lstart=,command= | cut -c1-200)"
rec "restart old $FEED_PID new $NEW $(date -u +%FT%TZ)"
rc=0
