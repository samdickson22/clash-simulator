#!/usr/bin/env bash
# Live full-pool switch gate: paired A/B on bank LIVE-AB1 (e16 vs Battle Log decks), one host's case slice.
#   ROOT=<r3 root> PINS=live16402b-r3 W=<w> bot/detach.sh LOG RECEIPT bot/exit/cpu_job.sh <w+1> \
#     bot/fullpool/run/ab_live.sh OUT START GAMES
# Arm A = current live: C56 K4L-R-gs (pool net, live C56-catalog belief) seeing the live-perception alias of the
# opponent's off-vocab cards (aliased:, bot/fullpool/alias.py). Arm B = full-pool K4L-R-gs with the extended K4L net
# k1a1, the open-world belief and true ids. Opponents: extended R3a and v1. LOPP must hold pool.npz and k1a1.npz.
set -euo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
OUT=${1:?OUT}; START=${2:?START}; GAMES=${3:?GAMES}; W=${W:-40}
CANDS=${CANDS:-aliased:K4L-R-gs-mpool,K4L-R-gs-mk1a1}; OPPS=${OPPS:-R3a,v1}
echo "ab_live start $(date -u +%FT%TZ) tree $(cat STAGED-REV 2>/dev/null) root $ROOT pins $PINS cases [$START,+$GAMES) cands $CANDS opps $OPPS"
exec nice -n 15 "$PY" -B -m bot.eval.headline --out "$OUT" --candidate "$CANDS" --opponents "$OPPS" \
  --games "$GAMES" --start "$START" --workers "$W" --bank LIVE-AB1
