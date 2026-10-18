#!/bin/bash
# Deploy the display window source (stream-source.json kind "window") + gated dispgrab on the Mac. Review before use.
#
#   window_source_deploy.sh STAGE_DIR FEED_PID [--no-config]
#   window_source_deploy.sh --restart-only FEED_PID
#
# STAGE_DIR: display_feed.py, dispgrab.swift, stream-source.json + SHA256SUMS listing exactly those three (shasum -a 256).
# Single operator, one run at a time (mkdir lock display/.window-source.lock). Everything is first snapshotted into a
# new private dir display/window-deploy-<STAMP>/ (mode 700: stage/, backup/, receipt.txt) and checked there; the stage
# is never read again. Order:
#   lock -> snapshot + manifest check -> validate (py_compile; the NEW feed parses the config as a valid window source)
#   -> preflight -> swiftc from the snapshot -> backups (hash-checked) + install temps beside the targets (hash-checked)
#   -> preflight -> renames (each hash-verified) -> preflight -> SIGTERM the exact feed PID -> wait for the respawn.
# preflight = window_source_preflight.sh (same dir): exact feed PID under video_supervisor.py, no driver process
# (global + supervisor PGID), no battle in a fresh driver-log read, gate open, the running feed ignores the config.
# Any failure after the first live rename and before the signal restores the backups (EXIT trap). The feed is never
# signalled by group or pattern. Never starts or stops an emulator. Last stdout line: __RC=<n> (ssh status untrusted).
set -u
set -o pipefail
rc=1; LOCKED=0; MUTATED=0; SIGNALED=0; PRIV=""; NOCONF=0; SRC_BEFORE=""; FEED_PID=""
LOOP="$HOME/clasher-live/loop"
D="$LOOP/display"
PY="$HOME/clasher-live/venv/bin/python"
LOCK="$D/.window-source.lock"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"

say() { echo "$(date -u +%FT%TZ) $*"; }
die() { say "ERROR: $*"; rc=${2:-1}; exit "$rc"; }
sha() {   # sha256 of a file on stdout; non-zero (no output) on any failure
  local h
  h=$(shasum -a 256 "$1" 2>/dev/null | awk '{print $1}') || return 1
  case "$h" in *[!0-9a-f]*|'') return 1 ;; esac
  [ ${#h} = 64 ] || return 1
  echo "$h"
}
rec() { echo "$*" >> "$PRIV/receipt.txt" || die "receipt write failed" 21; }
put() {   # put TMP DEST WANT_SHA: TMP sits beside DEST and was hash-checked; rename, then verify DEST
  mv -f "$1" "$2" || die "rename $1 -> $2 failed" 22
  [ "$(sha "$2")" = "$3" ] || die "$2 hash after install is not $3" 22
}
restore_one() {   # restore_one BACKUP DEST TMP: best effort, never exits (runs in the EXIT trap)
  local want
  want=$(sha "$1") || { echo "  RESTORE FAILED $2 (backup unreadable)"; return 1; }
  cp -p "$1" "$3" && mv -f "$3" "$2" && [ "$(sha "$2")" = "$want" ] && echo "  restored $2" && return 0
  echo "  RESTORE FAILED $2"; return 1
}
recover() {
  local ok=0
  say "recovering pre-deploy files from $PRIV/backup"
  restore_one "$PRIV/backup/display_feed.py" "$D/display_feed.py" "$D/.display_feed.py.rec-$STAMP" || ok=1
  restore_one "$PRIV/backup/dispgrab" "$D/bin/dispgrab" "$D/bin/.dispgrab.rec-$STAMP" || ok=1
  if [ "$NOCONF" = 0 ]; then
    if [ "$SRC_BEFORE" = present ]; then
      restore_one "$PRIV/backup/stream-source.json" "$LOOP/stream-source.json" "$LOOP/.stream-source.json.rec-$STAMP" || ok=1
    elif [ -f "$LOOP/stream-source.json" ]; then
      mv -f "$LOOP/stream-source.json" "$PRIV/aborted-stream-source.json" && echo "  moved the new config aside" || ok=1
    fi
  fi
  if [ "$ok" = 0 ]; then say "RECOVERED: pre-deploy files back; feed not signalled"; else say "RECOVERY INCOMPLETE: inspect $PRIV"; fi
}
on_exit() {
  if [ "$rc" != 0 ] && [ "$MUTATED" = 1 ] && [ "$SIGNALED" = 0 ]; then recover; fi
  rm -f "$D/.display_feed.py.new-$STAMP" "$D/bin/.dispgrab.new-$STAMP" "$LOOP/.stream-source.json.new-$STAMP" 2>/dev/null
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
preflight() { WS_NESTED=1 bash "$HERE/window_source_preflight.sh" "$FEED_PID" "$@" || die "preflight failed (see above)" 11; }

# ---- arguments
RESTART_ONLY=0
if [ "${1:-}" = --restart-only ]; then
  [ $# -eq 2 ] || die "usage: $0 --restart-only FEED_PID" 2
  RESTART_ONLY=1; FEED_PID="$2"
else
  { [ $# -ge 2 ] && [ $# -le 3 ]; } || die "usage: $0 STAGE_DIR FEED_PID [--no-config]" 2
  STAGE="$1"; FEED_PID="$2"
  if [ $# -eq 3 ]; then
    if [ "$3" = --no-config ]; then NOCONF=1; else die "unknown option $3" 2; fi
  fi
fi
case "$FEED_PID" in ''|*[!0-9]*) die "bad FEED_PID" 2 ;; esac
[ "$FEED_PID" -gt 1 ] || die "bad FEED_PID $FEED_PID" 2
[ -f "$HERE/window_source_preflight.sh" ] || die "window_source_preflight.sh not next to this script" 2
say "start stamp=$STAMP feed_pid=$FEED_PID restart_only=$RESTART_ONLY no_config=$NOCONF"
mkdir "$LOCK" 2>/dev/null || die "lock $LOCK exists: another deploy/rollback is running (or stale: inspect, then rmdir)" 3
LOCKED=1

if [ "$RESTART_ONLY" = 0 ]; then
  # ---- private snapshot of the stage; the manifest must list exactly the three files
  PRIV="$D/window-deploy-$STAMP"
  { mkdir -m 700 "$PRIV" && mkdir "$PRIV/stage" "$PRIV/backup"; } || die "cannot create private dir $PRIV" 4
  : > "$PRIV/receipt.txt" || die "receipt create failed" 21
  rec "stamp $STAMP"
  [ -f "$STAGE/SHA256SUMS" ] || die "no $STAGE/SHA256SUMS" 4
  cp "$STAGE/SHA256SUMS" "$PRIV/stage/SHA256SUMS" || die "manifest copy failed" 4
  NAMES=$(awk '{print $2}' "$PRIV/stage/SHA256SUMS" | sort | tr '\n' ' ') || die "manifest read failed" 4
  [ "$NAMES" = "dispgrab.swift display_feed.py stream-source.json " ] \
    || die "manifest must list exactly display_feed.py dispgrab.swift stream-source.json (has: $NAMES)" 4
  NL=$(wc -l < "$PRIV/stage/SHA256SUMS" | tr -d ' ') || die "manifest read failed" 4
  [ "$NL" = 3 ] || die "manifest must have exactly 3 lines" 4
  for f in display_feed.py dispgrab.swift stream-source.json; do
    want=$(awk -v f="$f" '$2 == f {print $1}' "$PRIV/stage/SHA256SUMS") || die "manifest read failed" 4
    case "$want" in *[!0-9a-f]*|'') die "manifest sha for $f malformed" 4 ;; esac
    [ ${#want} = 64 ] || die "manifest sha for $f malformed" 4
    cp "$STAGE/$f" "$PRIV/stage/$f" || die "snapshot of $f failed" 4
    [ "$(sha "$PRIV/stage/$f")" = "$want" ] || die "snapshot $f does not match the manifest" 4
    rec "stage_$f $want"
  done
  S="$PRIV/stage"
  NEW_FEED=$(sha "$S/display_feed.py") || die "sha failed" 20
  NEW_CONF=$(sha "$S/stream-source.json") || die "sha failed" 20
  # ---- validate the snapshot (nothing live touched yet)
  "$PY" -I -m py_compile "$S/display_feed.py" || die "display_feed.py does not compile" 5
  "$PY" -I - "$S/display_feed.py" "$S/stream-source.json" <<'PYEOF' || die "stream-source.json is not a valid window source for the new feed" 5
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('df_new', sys.argv[1])
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)
df.SOURCE_FILE = Path(sys.argv[2])
s = df.window_source()
if not s or s.get('error'):
    print('window_source:', (s or {}).get('error', 'not a window source'))
    sys.exit(1)
print('config ok: owner', repr(s['owner']), 'crop', s['crop'], 'insets', s['insets'], 'anchor', s['anchor'], 'size', s['size'])
PYEOF
  preflight "$S/stream-source.json"
  say "compiling dispgrab from the snapshot"
  swiftc -parse-as-library -O "$S/dispgrab.swift" -o "$PRIV/dispgrab" || die "swiftc failed (nothing installed)" 6
  NEW_GRAB=$(sha "$PRIV/dispgrab") || die "sha failed" 20
  rec "compiled_dispgrab $NEW_GRAB"
  # ---- backups (hash-checked against the live files) + install temps beside the targets (hash-checked)
  for pair in "display_feed.py:$D/display_feed.py" "dispgrab:$D/bin/dispgrab"; do
    n=${pair%%:*}; live=${pair#*:}
    [ -f "$live" ] || die "live $live missing" 7
    h=$(sha "$live") || die "sha of $live failed" 20
    cp -p "$live" "$PRIV/backup/$n" || die "backup of $live failed" 7
    [ "$(sha "$PRIV/backup/$n")" = "$h" ] || die "backup of $live does not match (changed while copying?)" 7
    rec "before_$n $h"
  done
  if [ -f "$LOOP/stream-source.json" ]; then
    SRC_BEFORE=present
    h=$(sha "$LOOP/stream-source.json") || die "sha of the live config failed" 20
    cp -p "$LOOP/stream-source.json" "$PRIV/backup/stream-source.json" || die "config backup failed" 7
    [ "$(sha "$PRIV/backup/stream-source.json")" = "$h" ] || die "config backup does not match" 7
    rec "before_stream-source.json $h"
  elif [ -e "$LOOP/stream-source.json" ] || [ -L "$LOOP/stream-source.json" ]; then
    die "$LOOP/stream-source.json exists but is not a regular file" 7
  else
    SRC_BEFORE=absent
    rec "before_stream-source.json absent"
  fi
  rec "no_config $NOCONF"
  { cp "$S/display_feed.py" "$D/.display_feed.py.new-$STAMP" && chmod 755 "$D/.display_feed.py.new-$STAMP"; } || die "feed temp failed" 8
  [ "$(sha "$D/.display_feed.py.new-$STAMP")" = "$NEW_FEED" ] || die "feed temp hash mismatch" 8
  { cp "$PRIV/dispgrab" "$D/bin/.dispgrab.new-$STAMP" && chmod 755 "$D/bin/.dispgrab.new-$STAMP"; } || die "dispgrab temp failed" 8
  [ "$(sha "$D/bin/.dispgrab.new-$STAMP")" = "$NEW_GRAB" ] || die "dispgrab temp hash mismatch" 8
  if [ "$NOCONF" = 0 ]; then
    cp "$S/stream-source.json" "$LOOP/.stream-source.json.new-$STAMP" || die "config temp failed" 8
    [ "$(sha "$LOOP/.stream-source.json.new-$STAMP")" = "$NEW_CONF" ] || die "config temp hash mismatch" 8
  fi
  # ---- last check, then the renames (from here until the signal any failure restores the backups)
  preflight "$S/stream-source.json"
  MUTATED=1
  put "$D/bin/.dispgrab.new-$STAMP" "$D/bin/dispgrab" "$NEW_GRAB"
  put "$D/.display_feed.py.new-$STAMP" "$D/display_feed.py" "$NEW_FEED"
  if [ "$NOCONF" = 0 ]; then put "$LOOP/.stream-source.json.new-$STAMP" "$LOOP/stream-source.json" "$NEW_CONF"; fi
  rec "after_display_feed.py $NEW_FEED"
  rec "after_dispgrab $NEW_GRAB"
  if [ "$NOCONF" = 0 ]; then rec "after_stream-source.json $NEW_CONF"; else rec "after_stream-source.json unchanged"; fi
  say "installed; receipt $PRIV/receipt.txt:"
  cat "$PRIV/receipt.txt" || die "receipt read failed" 21
fi

# ---- restart the feed: preflight, exact PID re-verified, then SIGTERM that PID only
preflight
SUP=$(feed_ok "$FEED_PID") || die "PID $FEED_PID is not a display_feed.py under video_supervisor.py" 12
[ "$(tr -d ' \n' < "$D/capture-gate" 2>/dev/null)" = open ] || die "capture-gate not open right before TERM" 12
SIGNALED=1
say "TERM feed $FEED_PID (supervisor $SUP)"
kill -TERM "$FEED_PID" || die "kill -TERM $FEED_PID failed" 13
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
if [ -n "$PRIV" ]; then rec "restart old $FEED_PID new $NEW $(date -u +%FT%TZ)"; fi
rc=0
