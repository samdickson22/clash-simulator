#!/usr/bin/env bash
# Leaf-value data (bot/fullpool/leaf_value.py): the bundle's serial search twin on full-pool decks vs a strong-heavy pool,
# dumping every searched root's native public view (bot.value.gen). Detached, under the per-host CPU cap:
#   ROOT=<root> PINS=<pins> W=30 bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh 31 bot/fullpool/run/leafgen.sh START GAMES
# Bank LEAF1 1388654536695216 = int.from_bytes(os.urandom(6),'big')<<4 (drawn on 127x03 2026-10-16T23:41Z; generate.check_bank).
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
START=${1:?START}; GAMES=${2:?GAMES}; W=${W:-30}
: "${CAND:=K4L-R-gs-rw-mk1a1}" "${POOL:=K4C-r16,LIVE-K4CW-r16,K4C-r16,R3a,v1}" "${LEAF_BASE:=1388654536695216}"
export BOT_BELIEF_PRIOR=$DECKS
echo "leafgen start $(date -u +%FT%TZ) tree $(cat STAGED-REV) root $ROOT pins $PINS cand $CAND pool $POOL decks $DECKS"
nice -n 15 $PY -B -m bot.value.gen --out "$J/leafgen1" --candidate "$CAND" --pool "$POOL" --games "$GAMES" --start "$START" \
  --workers "$W" --base "$LEAF_BASE" --decks "$DECKS"
echo "leafgen end $(date -u +%FT%TZ) rc $?"
