#!/usr/bin/env bash
# Hourly mirror of this host's full-pool filler outputs to a peer host (BOT LEAD 10-17, after the 127x03 loss): a dead
# host loses about one interval of output. One loop per host, detached:
#   bot/detach.sh $J/mirror/mirror.log $J/mirror/mirror.receipt.json bot/exit/mirror_out.sh PEER [INTERVAL_S=3600]
# Pairing (enforced): 127x01 -> 127x04, 127x04 -> 127x08, 127x08 -> 127x01.
# Copies, with plain `rsync -a` (delta transfer into a temp file + rename on the peer; never --delete, never --inplace),
# the source dirs below into PEER:/mpac/sdicks02/jobs/clasher/bot-mirror/<this host>/<path relative to $J> and nowhere
# else: the peer's mirror root must already exist and must not be a symlink, and the per-source dir must not be a
# symlink (checked every pass). Missing source dirs are skipped; one failed dir does not stop the others; passes start
# INTERVAL apart (start to start); $J/mirror/STOP is checked between dirs and every 60 s of sleep.
# Reviewed by Sol (gpt-6.1-sol high) 2026-10-17 before first run (flags, glob base, pairing, confinement, timeouts, STOP).
set -uo pipefail
PEER=${1:?PEER host, e.g. 127x04}; INTERVAL=${2:-3600}
[[ "$INTERVAL" =~ ^[1-9][0-9]*$ ]] || { echo "bad interval $INTERVAL" >&2; exit 1; }
J=/mpac/sdicks02/jobs/clasher/bot-fullpool
DEST_ROOT=/mpac/sdicks02/jobs/clasher/bot-mirror
SRC=$(hostname -s) || exit 1
case "$SRC:$PEER" in
    127x01:127x04|127x04:127x08|127x08:127x01) ;;
    *) echo "pairing $SRC -> $PEER not allowed" >&2; exit 1 ;;
esac
DEST=$DEST_ROOT/$SRC
mkdir -p "$J/mirror" || exit 1
cd "$J" || exit 1
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o ServerAliveCountMax=3)
# outputs of the filler content and fits (relative to $J): MC / sibling / leaf data, K1 recordings, fit outputs, filler state
DIRS=(mcgen1 sibgen1 leafgen3 leafvalue vnet trueids filler)
log() { echo "$(date -u +%FT%TZ) $*"; }
stopped() { [[ -e "$J/mirror/STOP" ]]; }
nap() { local until=$(( $1 )); while (( $(date +%s) < until )) && ! stopped; do sleep 60; done; }
log "mirror start src $SRC peer $PEER dest $DEST interval $INTERVAL"
while ! stopped; do
    t0=$(date +%s); n=0; f=0
    if ! timeout 90 "${SSH[@]}" "$PEER" \
            "test -d '$DEST_ROOT' && test ! -L '$DEST_ROOT' && test ! -L '$DEST' && mkdir -p '$DEST' && test ! -L '$DEST'"; then
        log "peer $PEER unreachable or mirror root missing/unsafe; retry next pass"
        nap "t0 + INTERVAL"; continue
    fi
    shopt -s nullglob
    for d in "${DIRS[@]}" K1-x*; do
        stopped && break
        [[ -d "$J/$d" && ! -L "$J/$d" ]] || continue
        nice -n 19 rsync -a --timeout=300 -e "${SSH[*]}" "$J/$d/" "$PEER:$DEST/$d/" 2>>"$J/mirror/rsync-errors.log"
        rc=$?
        if (( rc == 0 )); then n=$((n+1)); else f=$((f+1)); log "rsync $d failed (rc $rc)"; fi
    done
    shopt -u nullglob
    log "pass done: $n dirs ok, $f failed, $(( $(date +%s) - t0 )) s"
    nap "t0 + INTERVAL"
done
log "STOP present; mirror exits"
