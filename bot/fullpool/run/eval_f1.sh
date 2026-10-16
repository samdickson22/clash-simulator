#!/usr/bin/env bash
# F1 screen (PLAN.md section 1 gates): candidates vs opponents on a named bank, one host's case slice.
#   ROOT=<root> PINS=live16402b-r3 W=60 bot/detach.sh LOG RECEIPT bot/exit/cpu_job.sh 61 \
#     bot/fullpool/run/eval_f1.sh OUT BANK START GAMES
# Defaults: CANDS = f1a2, f1b2 (step 1200, own calibration) and the extended RL r5 v10 baseline; OPPS = R3a,v1, the
# extended v1/R3a via BOT_FULLPOOL_POLICIES (env.sh). BANK: FP-DEV (both decks full-pool) or C56-REG (x4s decks).
# Cases are identical across candidates and opponents (bot/fullpool/banks.py), so results pair by (opponent, index).
set -euo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
OUT=${1:?OUT}; BANK=${2:?BANK}; START=${3:?START}; GAMES=${4:?GAMES}; W=${W:-60}
CANDS=${CANDS:-student:$J/fits/f1a2/step-001200.pt,student:$J/fits/f1b2/step-001200.pt,$STUDENT}
OPPS=${OPPS:-R3a,v1}
echo "eval_f1 start $(date -u +%FT%TZ) tree $(cat STAGED-REV 2>/dev/null) root $ROOT pins $PINS bank $BANK cases [$START,+$GAMES) cands $CANDS opps $OPPS"
exec nice -n 15 "$PY" -B -m bot.eval.headline --out "$OUT" --candidate "$CANDS" --opponents "$OPPS" \
  --games "$GAMES" --start "$START" --workers "$W" --bank "$BANK"
