#!/usr/bin/env bash
# KF1 K4L refit (PLAN.md section 2), CPU. Arm a: fine-tune from poolfp.npz (vocab order kept); arm b: fresh vocab.
#   ROOT=<root> ARM=a bot/detach.sh $J/kf1a.log $J/kf1a.receipt.json bot/exit/cpu_job.sh 16 \
#     bot/fullpool/run/fit_kf1.sh REC_DIR[,REC_DIR...]
# REC dirs: local K1-x* dirs (rsync the other hosts' rec-*.jsonl.gz here first), optionally the old C56 recordings.
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
REC=${1:?REC dirs, comma-separated}; ARM=${ARM:-a}; OPPS=${OPPS:-R3a,v1,$STUDENT}
init=(); [ "$ARM" = a ] && init=(--init "$LOPP/poolfp.npz")
echo "kf1 $ARM start $(date -u +%FT%TZ) rec $REC opponents $OPPS"
nice -n 15 $PY -B -m bot.search.lopp_train --rec "$REC" --out "$J/lopp-k1" --name "k1$ARM" --opponents "$OPPS" \
  --epochs ${EPOCHS:-8} --hidden 256 --layers 2 --threads ${THREADS:-16} --procs ${PROCS:-8} "${init[@]}"
echo "kf1 $ARM end $(date -u +%FT%TZ) rc $?"
