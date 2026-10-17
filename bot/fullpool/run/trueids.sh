#!/usr/bin/env bash
# True-ids class smoke (bot/fullpool/trueids_smoke.py) on ROOT/PINS with the bundle env:
#   ROOT=<root> PINS=<pins> bot/exit/cpu_job.sh 13 bot/fullpool/run/trueids.sh NAME CARD[,CARD...] [GAMES=4]
# -> $J/trueids/NAME.jsonl (reference line, one row per game, summary line).
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
NAME=${1:?NAME}; CARDS=${2:?CARDS}; GAMES=${3:-4}
export BOT_BELIEF_PRIOR=fullpool:11433651:freq=b53b02a1fde4
mkdir -p "$J/trueids"
echo "trueids $NAME start $(date -u +%FT%TZ) tree $(cat STAGED-REV) root $ROOT pins $PINS cards $CARDS"
nice -n 15 $PY -B -m bot.fullpool.trueids_smoke "$J/trueids/$NAME.jsonl" --cards "$CARDS" --games "$GAMES" --procs 12
echo "trueids $NAME end $(date -u +%FT%TZ) rc $?"
