#!/usr/bin/env bash
# TIERS Mac session launcher (runs on 127x05). Uses the same nonce-anchored remote-status `mac()` and macfs.py
# primitives as stage_phase_b.sh (Sol pre-run r6). Commands:
#   ship                 : copy session_wrapper.py to $S/helpers/session-r1/ (exclusive write; SHA-verified)
#   preflight            : read-only: staged bundle tiers-pins == approved SHA, absent build/output/console paths,
#                          wrapper SHA, no other measure_tiers/session_wrapper process, lock file present
#   launch GO_REF        : nice -n 10 python -B session_wrapper.py S SHA (daemonizes on the Mac); then confirms the
#                          session-pre.json appeared and the daemon PID is alive. GO_REF (coordinator message/commit)
#                          is recorded; it is required.
#   status               : read-only: console log tail, pre/post receipts presence, process liveness
# No measurement logic lives here; the session itself is the frozen measure_tiers.py via the wrapper.
set -euo pipefail
shopt -s inherit_errexit
HERE=$(cd "$(dirname "$0")" && pwd)
S=/Users/sam/Desktop/code/clasher-mac-e4-tiers-20261011
PY=/Users/sam/Desktop/code/clasher/.venv/bin/python
SHA=273ef19647c6fa2ee869793541b2000fc5a6947183b0d26977224c781ceb599d   # coordinator-approved (dbe683e0)
OUT=$HERE/receipts/phase-b-session-20261012
MAC=(timeout 90 ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 macmini-fleet)   # every remote call bounded
mkdir -p "$OUT"
exec 9> "$OUT/.session.lock"
flock -n 9 || { echo "another run_session.sh holds the lock" >&2; exit 1; }
log() { printf '%s %s\n' "$(date -u +%FT%TZ)" "$*" | tee -a "$OUT/session-launcher.log" >&2; }
die() { log "FAIL $*"; exit 1; }
mac() {
  local out rc nonce tail
  nonce=$(od -An -tx8 -N8 /dev/urandom | tr -d ' \n'); [[ $nonce =~ ^[0-9a-f]{16}$ ]] || die "nonce"
  out=$("${MAC[@]}" "setopt pipefail; { $1 ; }; printf '\n__RC_${nonce}=%s\n' \$?") || die "ssh transport failed: ${1:0:100}"
  tail=${out##*$'\n'}; [[ $out == *$'\n'* ]] || tail=$out
  [[ $tail =~ ^__RC_${nonce}=([0-9]+)$ ]] || die "no/invalid final status line: ${1:0:100}"
  rc=${BASH_REMATCH[1]}
  out=${out%$'\n'"$tail"}; [[ $out == "$tail" ]] && out=""
  [[ $rc == 0 ]] || die "remote rc=$rc: ${1:0:100}"
  printf '%s' "$out"
}
MACFS_B64=$(base64 -w0 "$HERE/macfs.py")
MACFS="/usr/bin/python3 -I -c \"import base64;exec(base64.b64decode('$MACFS_B64'))\" '$S'"
macfs() { mac "$MACFS $*"; }
state() { local st; st=$(macfs state "$1"); printf '%s' "$st"; }
need() { local st; st=$(state "$1"); [[ $st == "$2" ]] || die "$1 is '$st', expected $2"; }
WRAPPER_SHA=$(sha256sum "$HERE/session_wrapper.py" | cut -d' ' -f1)

cmd_ship() {
  local st got
  st=$(state helpers/session-r1); if [[ $st == absent ]]; then macfs mkdir helpers/session-r1; fi
  need helpers/session-r1 dir
  st=$(state helpers/session-r1/session_wrapper.py)
  if [[ $st == absent ]]; then macfs write helpers/session-r1/session_wrapper.py < "$HERE/session_wrapper.py"; fi
  got=$(mac "shasum -a 256 '$S/helpers/session-r1/session_wrapper.py'"); got=${got%% *}
  [[ $got == "$WRAPPER_SHA" ]] || die "wrapper SHA on Mac $got != $WRAPPER_SHA"
  log "ship OK wrapper $WRAPPER_SHA"
}

cmd_preflight() {
  local pins got p st procs
  need staged-a5/bundle-a5 dir; need session.lock file; need runtime-a5 dir
  pins=$(mac "shasum -a 256 '$S/staged-a5/bundle-a5/tiers-pins.json'"); pins=${pins%% *}
  [[ $pins == "$SHA" ]] || die "staged tiers-pins $pins != approved $SHA"
  got=$(mac "shasum -a 256 '$S/helpers/session-r1/session_wrapper.py'"); got=${got%% *}
  [[ $got == "$WRAPPER_SHA" ]] || die "wrapper SHA $got"
  for p in build-a5 session-a5-r1 session-a5-r1.console.log session-a5-r1.pre.json session-a5-r1.post.json; do
    st=$(state "$p"); [[ $st == absent ]] || die "$p exists"
  done
  procs=$(mac "ps -Ao pid,command | grep -E 'measure_tiers.py|session_wrapper.py|build_tiers.sh' | grep -v grep || true")
  [[ -z $procs ]] || die "session-like processes already running: $procs"
  log "preflight OK tiers-pins $pins wrapper $WRAPPER_SHA"
}

cmd_launch() {
  local go=${1:?GO reference required} pid st i
  cmd_preflight
  log "launch GO=$go"
  mac "cd '$S' && nice -n 10 '$PY' -B '$S/helpers/session-r1/session_wrapper.py' '$S' $SHA" > "$OUT/launch-stdout.txt" \
    || die "launch call failed; THE REMOTE SESSION MAY ALREADY BE RUNNING (check status; do not relaunch)"
  local deadline=$(( $(date +%s) + 60 )); st=absent
  while (( $(date +%s) < deadline )); do
    st=$(state session-a5-r1.pre.json); [[ $st == file ]] && break; sleep 2
  done
  [[ $st == file ]] || die "session-pre.json did not appear within 60 s wall clock; THE REMOTE SESSION MAY ALREADY BE RUNNING (check status; do not relaunch)"
  mac "cat '$S/session-a5-r1.pre.json'" > "$OUT/session-a5-r1.pre.json"
  pid=$(python3 -c "import json;print(json.load(open('$OUT/session-a5-r1.pre.json'))['pid'])")
  [[ $pid =~ ^[0-9]+$ ]] || die "pid"
  mac "kill -0 $pid" || die "wrapper not alive"
  printf '%s\n' "$go" > "$OUT/GO-reference.txt"
  log "launch OK wrapper pid $pid"
}

cmd_status() {
  local s
  s=$(mac "cd '$S' && date -u +%FT%TZ && ls -l session-a5-r1.pre.json session-a5-r1.post.json 2>/dev/null; tail -5 session-a5-r1.console.log 2>/dev/null; ps -Ao pid,etime,pcpu,command | grep -E 'measure_tiers.py|session_wrapper.py|build_tiers.sh|caffeinate -i -w' | grep -v grep | cut -c1-160 || true")
  printf '%s\n' "$s"
}

case ${1:-} in
  ship) cmd_ship ;; preflight) cmd_preflight ;; launch) shift; cmd_launch "$@" ;; status) cmd_status ;;
  *) echo "usage: run_session.sh ship|preflight|launch GO_REF|status" >&2; exit 2 ;;
esac
