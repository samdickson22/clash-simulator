#!/usr/bin/env bash
# F1 student fit (PLAN.md section 1): ExIt fine-tune of the extended RL r5 v10 on G1 packs + the C56 K4C corpus.
#   ROOT=<root> DEVICE=cpu THREADS=32 NAME=f1a bot/detach.sh $J/fit-f1a.log $J/fit-f1a.receipt.json \
#     bot/exit/cpu_job.sh 4 bot/fullpool/run/fit_f1.sh G1PACK [G1PACK...]
# G1PACKs must be local (rsync the other hosts' packs here first). OLD = C56 corpus (default kc7a x01/x04/x08 under
# OLDDIR); NEW_RATIO, LR, STEPS, BATCH, MICRO, SEED override. DEVICE=cuda once a GPU is handed back (then THREADS=8).
set -uo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
: "${NAME:=f1a}" "${DEVICE:=cpu}" "${THREADS:=32}" "${NEW_RATIO:=1.0}" "${LR:=3e-5}" "${STEPS:=1500}" "${BATCH:=4096}"
: "${MICRO:=1024}" "${SEED:=2026101601}" "${INIT:=$EXT/rl5-v10-fp.pt}"
OLDDIR=${OLDDIR:-$( [ -d /mpac/sdicks02/jobs/clasher/bot-exit-r1/packed-kc7a-x08 ] && echo /mpac/sdicks02/jobs/clasher/bot-exit-r1 || echo /mpac/sdicks02/jobs/clasher/bot-exit-r1-04)}
ASSETS=${ASSETS:-$OLDDIR/inputs/assets.npz}
new=(); for p in "$@"; do new+=(--new "$p"); done
old=(); if [ "${NO_OLD:-0}" != 1 ]; then for x in x01 x04 x08; do old+=(--old "$OLDDIR/packed-kc7a-$x"); done; fi
export OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS
[ "$DEVICE" = cuda ] && export CUDA_VISIBLE_DEVICES=${GPU:-0}
echo "fit $NAME start $(date -u +%FT%TZ) device $DEVICE threads $THREADS init $INIT new $* old ${old[*]} ratio $NEW_RATIO lr $LR steps $STEPS"
nice -n 15 $PY -B -m bot.exit.train --init "$INIT" --assets "$ASSETS" "${new[@]}" "${old[@]}" --new-ratio "$NEW_RATIO" \
  --temperature 0.003 --lr "$LR" --steps "$STEPS" --batch "$BATCH" --microbatch "$MICRO" --seed "$SEED" \
  --device "$DEVICE" --out "$J/fits/$NAME"
echo "fit $NAME end $(date -u +%FT%TZ) rc $?"
