#!/bin/bash
# Read-only safety preflight before any display feed file/config change or feed restart on the Mac. Review before use.
#
#   window_source_preflight.sh FEED_PID [CONFIG_JSON]
#
# Passes (rc 0) only if ALL hold, checked now:
#   1. FEED_PID is a display/display_feed.py whose parent is video_supervisor.py; prints that supervisor's PGID.
#   2. No driver process anywhere in the process table, and none in the supervisor's PGID (regex WS_DRIVER_RE, default
#      '[d]rive[.]py|[m]emloop|[m]em_loop'; bracketed so it never matches this check's own argv).
#   3. Fresh log read (not the gate file alone): the installed display_feed.py's own read-only Driver (it never imports
#      the driver) follows the newest runs/<s>/[mNN/]frames.jsonl tail -> not in_battle, and if those logs moved within
#      BATTLE_HOLD_S the last state is not 'battle'.
#   4. display/capture-gate reads "open".
#   5. With CONFIG_JSON: the INSTALLED feed ignores it (source_plan() -> None without any window query; no 'null' text
#      for its card), so writing it before the restart changes nothing in the running feed.
# Standalone: last stdout line __RC=<n>. Called by the deploy/rollback scripts with WS_NESTED=1 (no __RC line).
set -u
set -o pipefail
rc=1
[ "${WS_NESTED:-0}" = 1 ] || trap 'echo "__RC=$rc"' EXIT
fail() { echo "PREFLIGHT FAIL: $*"; rc=${2:-1}; exit "$rc"; }
LOOP="$HOME/clasher-live/loop"
D="$LOOP/display"
PY="$HOME/clasher-live/venv/bin/python"
RE="${WS_DRIVER_RE:-[d]rive[.]py|[m]emloop|[m]em_loop}"
[ $# -ge 1 ] || fail "usage: $0 FEED_PID [CONFIG_JSON]" 2
FEED_PID="$1"; CONF="${2:-}"
case "$FEED_PID" in ''|*[!0-9]*) fail "bad FEED_PID" 2 ;; esac
[ "$FEED_PID" -gt 1 ] || fail "bad FEED_PID $FEED_PID" 2
echo "preflight $(date -u +%FT%TZ) feed_pid=$FEED_PID"

# 1. exact feed PID + its supervisor
cmd=$(ps -p "$FEED_PID" -o command= 2>/dev/null) || fail "no process $FEED_PID" 3
case "$cmd" in *display/display_feed.py*) ;; *) fail "PID $FEED_PID is not display_feed.py: ${cmd:0:120}" 3 ;; esac
SUP=$(ps -p "$FEED_PID" -o ppid= 2>/dev/null | tr -d ' ') || fail "ppid of $FEED_PID unreadable" 3
case "$SUP" in ''|*[!0-9]*) fail "bad parent pid '$SUP'" 3 ;; esac
scmd=$(ps -p "$SUP" -o command= 2>/dev/null) || fail "no parent $SUP" 3
case "$scmd" in *video_supervisor.py*) ;; *) fail "parent $SUP is not video_supervisor.py: ${scmd:0:120}" 3 ;; esac
PGID=$(ps -p "$SUP" -o pgid= 2>/dev/null | tr -d ' ') || fail "pgid of $SUP unreadable" 3
case "$PGID" in ''|*[!0-9]*) fail "bad pgid '$PGID'" 3 ;; esac
echo "feed $FEED_PID supervisor $SUP pgid $PGID"

# 2. no driver process (anywhere; and listed separately for the supervisor's group)
TABLE=$(ps -axo pid=,pgid=,command=) || fail "ps failed" 4
# sanity: the snapshot parses and holds the feed and its supervisor (an empty/garbled table must not pass)
echo "$TABLE" | awk -v p="$FEED_PID" -v s="$SUP" '$1 == p {a=1} $1 == s {b=1} END {exit !(a && b)}' \
  || fail "process table snapshot lacks feed $FEED_PID / supervisor $SUP" 4
DRV=$(echo "$TABLE" | awk -v re="$RE" '{c=$0; sub(/^ *[0-9]+ +[0-9]+ /, "", c); if (c ~ re) print}') || fail "table scan failed" 4
GRP=$(echo "$TABLE" | awk -v g="$PGID" -v re="$RE" '$2 == g {c=$0; sub(/^ *[0-9]+ +[0-9]+ /, "", c); if (c ~ re) print}') \
  || fail "group scan failed" 4
[ -z "$GRP" ] || fail "driver process in supervisor PGID $PGID: $(echo "$GRP" | cut -c1-160 | head -3)" 5
[ -z "$DRV" ] || fail "driver process running: $(echo "$DRV" | cut -c1-160 | head -3)" 5
echo "no driver process (re '$RE'); pgid $PGID members: $(echo "$TABLE" | awk -v g="$PGID" '$2 == g {print $1}' | tr '\n' ' ')"

# 3. fresh driver-log battle check with the installed feed's read-only Driver
TMPF=$(mktemp -t ws-preflight) || fail "mktemp failed" 4
"$PY" -I - "$D/display_feed.py" > "$TMPF" 2>&1 <<'PYEOF'
import importlib.util, sys, time
spec = importlib.util.spec_from_file_location('df_preflight', sys.argv[1])
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)
d = df.Driver()
d.follow(d.find())
d.poll()
age = time.time() - d.logs_t() if d.logs_t() else -1
state = (d.frame or {}).get('state')
recent_battle = state == 'battle' and 0 <= age < df.BATTLE_HOLD_S
print(f'LOGS dir={d.match_dir} state={state} logs_age_s={age:.1f} active={d.active()} in_battle={d.in_battle()}')
sys.exit(3 if (d.in_battle() or recent_battle) else 0)
PYEOF
prc=$?
grep '^LOGS ' "$TMPF" || tail -3 "$TMPF"
rm -f "$TMPF"
[ "$prc" = 0 ] || fail "driver logs show a battle (or the check failed rc $prc)" 6

# 4. gate file
g=$(tr -d ' \n' < "$D/capture-gate" 2>/dev/null || echo missing)
[ "$g" = open ] || fail "capture-gate is '$g'" 7

# 5. the running (installed) feed must ignore the new config
if [ -n "$CONF" ]; then
  "$PY" -I - "$D/display_feed.py" "$CONF" <<'PYEOF' || fail "installed feed would react to $CONF" 8
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('df_preflight', sys.argv[1])
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)
df.SOURCE_FILE = Path(sys.argv[2])
def no_query(*a, **k):
    raise SystemExit('source_plan made a window query')
df.list_windows = no_query
assert df.source_plan() is None, 'source_plan picked a plan'
assert 'null' not in json.dumps(json.loads(Path(sys.argv[2]).read_text())).lower(), "'null' text would switch the card"
print('CONFIG ignored by the installed feed')
PYEOF
fi
echo "PREFLIGHT OK $(date -u +%FT%TZ)"
rc=0
