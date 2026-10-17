#!/bin/bash
# 05: move READY chunks (and DONE.json of finished runs) from the Mac to night/raw. Loop: bash pull.sh
# Stop: kill the PID in $NIGHT/logs/pull.pid.
# Order per chunk: copy into staging -> verify every sha256 in its manifest -> rename into raw/ (atomic, READY
# included) -> only then delete that sealed chunk dir on the Mac. Restart-safe: a chunk already published in raw/
# but still on the Mac is re-verified and then deleted there; a mismatch keeps the Mac copy and goes to bad/.
# Mac paths touched: only sealed (READY) chunk dirs and DONE.json under ~/clasher-live/nulls/night/out.
set -u
NIGHT=/mpac/sdicks02/scratch/nulls/night
RAW=$NIGHT/raw STAGE=$NIGHT/staging BAD=$NIGHT/bad
mkdir -p "$RAW" "$STAGE" "$BAD" "$NIGHT/logs"
echo $$ > "$NIGHT/logs/pull.pid"
SSH="ssh -o ControlMaster=auto -o ControlPath=/tmp/sdicks02-nightpull-%C -o ControlPersist=900 -o ServerAliveInterval=15"
REMOTE='clasher-live/nulls/night/out'
PY=/mpac/sdicks02/scratch/nulls/venv/bin/python
log() { echo "$(date -u +%FT%TZ) $*" >> "$NIGHT/logs/pull.log"; }
verify() {  # $1 = local chunk dir; exit 0 iff every manifest file matches and READY is present
  "$PY" - "$1" <<'PY'
import hashlib, json, sys
from pathlib import Path
d = Path(sys.argv[1])
m = json.loads((d / 'manifest.json').read_text())
assert (d / 'READY').exists()
for name, v in m['files'].items():
    if hashlib.sha256((d / name).read_bytes()).hexdigest() != v['sha256']:
        sys.exit(1)
PY
}
while true; do
  list=$($SSH macmini-fleet "setopt NULL_GLOB 2>/dev/null; cd ~/$REMOTE 2>/dev/null || { echo __RC=0; exit 0; }; for r in i*/*/chunk-*/READY; do [ -e \"\$r\" ] && echo C \${r%/READY}; done; for d in i*/*/DONE.json; do [ -e \"\$d\" ] && echo D \$d; done; echo __RC=0" 2>>"$NIGHT/logs/pull.err")
  if ! grep -q '^__RC=0$' <<<"$list"; then log "list failed"; sleep 10; continue; fi
  chunks=$(awk '$1=="C"{print $2}' <<<"$list")
  dones=$(awk '$1=="D"{print $2}' <<<"$list")
  if [ -n "$chunks" ]; then
    t0=$(date +%s.%N)
    fetch=$(for c in $chunks; do [ -e "$RAW/$c/READY" ] || echo "$c"; done)
    if [ -n "$fetch" ] && ! printf '%s\n' $fetch | rsync -a -r -e "$SSH" --files-from=- "macmini-fleet:$REMOTE/" "$STAGE/" \
        2>>"$NIGHT/logs/pull.err"; then
      log "rsync failed"; sleep 10; continue
    fi
    ok=() nbad=0
    for c in $chunks; do
      if [ -e "$RAW/$c/READY" ]; then
        verify "$RAW/$c" && ok+=("$c") || { log "published chunk fails verify: $c (Mac copy kept)"; nbad=$((nbad+1)); }
      elif verify "$STAGE/$c"; then
        mkdir -p "$(dirname "$RAW/$c")" && mv "$STAGE/$c" "$RAW/$c" && ok+=("$c")
      else
        nbad=$((nbad+1)); mkdir -p "$(dirname "$BAD/$c")"; rm -rf "$BAD/$c"; mv "$STAGE/$c" "$BAD/$c"
        log "MANIFEST MISMATCH $c (Mac copy kept, staging copy in bad/)"
      fi
    done
    if [ ${#ok[@]} -gt 0 ]; then
      res=$($SSH macmini-fleet "cd ~/$REMOTE && for c in ${ok[*]}; do [ -e \"\$c/READY\" ] && rm -f -- \"\$c\"/* && rmdir -- \"\$c\"; done; echo __RC=0" 2>>"$NIGHT/logs/pull.err")
      grep -q '^__RC=0$' <<<"$res" || log "Mac delete failed (will retry; published copies are verified)"
    fi
    log "chunks: ${#ok[@]} published+deleted, $nbad bad, $(echo "$(date +%s.%N) - $t0" | bc) s"
  fi
  if [ -n "$dones" ]; then
    done_ok=()
    for d in $dones; do
      run=$(dirname "$d")
      mkdir -p "$RAW/$run"
      if rsync -a -e "$SSH" "macmini-fleet:$REMOTE/$d" "$RAW/$d" 2>>"$NIGHT/logs/pull.err"; then done_ok+=("$d"); fi
    done
    if [ ${#done_ok[@]} -gt 0 ]; then
      # DONE.json is written after the run's last chunk is sealed; delete it (and the then-empty run dir) only
      # once no chunk dir of that run remains on the Mac
      $SSH macmini-fleet "setopt NULL_GLOB 2>/dev/null; cd ~/$REMOTE && for d in ${done_ok[*]}; do r=\${d%/DONE.json}; set -- \"\$r\"/chunk-*; [ \$# -eq 0 ] && rm -f -- \"\$d\" && rmdir -- \"\$r\"; done; echo __RC=0" >/dev/null 2>>"$NIGHT/logs/pull.err"
      log "done runs: ${done_ok[*]}"
    fi
  fi
  [ "${ONCE:-0}" = 1 ] && break
  sleep 6
done
