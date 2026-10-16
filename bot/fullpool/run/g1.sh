#!/usr/bin/env bash
# One host's G1 shard (ExIt labels, PLAN.md section 1). Detached, under the per-host CPU cap:
#   ROOT=<root> W=15 bot/detach.sh $J/g1-x<host>.log $J/g1-x<host>.receipt.json \
#     bot/exit/cpu_job.sh 16 bot/fullpool/run/g1.sh SHARD GAMES
# SHARD 0/1/2 -> games [SHARD*1e6, +GAMES) of FP-TRAIN1; resumable (rerun the same command); STOP file: $J/G1/STOP.
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
SHARD=${1:?SHARD}; GAMES=${2:?GAMES}; W=${W:-15}; TEACHER=${TEACHER:-K4C-r16}; POOL=${POOL:-R3a,v1,self}
echo "g1 shard $SHARD start $(date -u +%FT%TZ) tree $(cat STAGED-REV) root $ROOT pins $PINS decks $DECKS teacher $TEACHER"
nice -n 15 $PY -B -m bot.exit.generate --out "$J/G1" --student "$STUDENT" --teacher "$TEACHER" --pool "$POOL" \
  --games "$GAMES" --start $((SHARD * 1000000)) --workers "$W" --base "$TRAIN_BASE" --decks "$DECKS"
echo "g1 shard $SHARD end $(date -u +%FT%TZ) rc $?"
