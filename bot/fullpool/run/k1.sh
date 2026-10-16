#!/usr/bin/env bash
# One host's K1 shard (K4L rollout-opponent recording, PLAN.md section 2):
#   ROOT=<root> W=15 bot/detach.sh $J/k1-x<host>.log $J/k1-x<host>.receipt.json \
#     bot/exit/cpu_job.sh 16 bot/fullpool/run/k1.sh SHARD CASES
# Cases [SHARD*1000, +CASES) x opponents (fixed stride: per-host CASES may differ, shards stay disjoint) (default R3a, v1, extended RL r5 v10); resumable.
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
SHARD=${1:?SHARD}; CASES=${2:?CASES}; W=${W:-15}; OPPS=${OPPS:-R3a,v1,$STUDENT}
echo "k1 shard $SHARD start $(date -u +%FT%TZ) tree $(cat STAGED-REV) root $ROOT pins $PINS decks $DECKS"
nice -n 15 $PY -B -m bot.search.lopp_record --out "$J/K1-x$SHARD" --candidate K4C-r16 --opponents "$OPPS" \
  --games "$CASES" --start $((SHARD * 1000)) --workers "$W" --base $((TRAIN_BASE + 50000000)) --decks "$DECKS"
echo "k1 shard $SHARD end $(date -u +%FT%TZ) rc $?"
