#!/usr/bin/env bash
# F1 student fit (PLAN.md section 1): ExIt fine-tune of the extended RL r5 v10 on G1 packs + the C56 K4C corpus.
#   After a fresh GPU allocation and source/data review, use a unique NAME/log/receipt:
#   ROOT=<root> DEVICE=cuda THREADS=8 LOADERS=2 NAME=<fresh-name> bot/detach.sh <fresh-log> <fresh-receipt> \
#     bot/exit/cpu_job.sh 10 bot/fullpool/run/fit_f1.sh G1PACK [G1PACK...]
# G1PACKs must be local (rsync the other hosts' packs here first). OLD = C56 corpus (default kc7a x01/x04/x08 under
# OLDDIR). NEW_RATIO is a batch fraction: .5 = 1:1, .6666666666666666 = 2:1 new:old.
# No allocation is implied by this script. DEVICE=cuda requires an explicit GPU handback.
set -euo pipefail
# env.sh otherwise selects the CPU venv, whose CUDA build is incompatible with fleet drivers.
if [[ "${DEVICE:-cpu}" = cuda ]]; then
  : "${PY:=/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python}"
fi
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
: "${NAME:?unique fresh NAME required}" "${DEVICE:=cpu}" "${THREADS:=8}" "${LOADERS:=2}" "${NEW_RATIO:=0.5}" "${LR:=3e-5}" "${STEPS:=1500}" "${BATCH:=4096}"
: "${MICRO:=1024}" "${SEED:=2026101601}" "${INIT:=$EXT/rl5-v10-fp.pt}"
[[ "$THREADS" =~ ^[1-9][0-9]*$ && "$LOADERS" =~ ^[0-9]+$ ]] || { echo 'invalid threads/loaders' >&2; exit 1; }
fullpool_require_cpu_budget "$((THREADS + LOADERS))"
[[ ! -e "$J/fits/$NAME" ]] || { echo 'fresh output directory required' >&2; exit 1; }
OLDDIR=${OLDDIR:-$( [ -d /mpac/sdicks02/jobs/clasher/bot-exit-r1/packed-kc7a-x08 ] && echo /mpac/sdicks02/jobs/clasher/bot-exit-r1 || echo /mpac/sdicks02/jobs/clasher/bot-exit-r1-04)}
ASSETS=${ASSETS:-$OLDDIR/inputs/assets.npz}
new=(); for p in "$@"; do new+=(--new "$p"); done
old=(); if [ "${NO_OLD:-0}" != 1 ]; then for x in x01 x04 x08; do old+=(--old "$OLDDIR/packed-kc7a-$x"); done; fi
export OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS
[ "$DEVICE" = cuda ] && export CUDA_VISIBLE_DEVICES=${GPU:-0}
echo "fit $NAME start $(date -u +%FT%TZ) device $DEVICE threads $THREADS loaders $LOADERS init $INIT new $* old ${old[*]} fraction $NEW_RATIO lr $LR steps $STEPS"
exec nice -n 15 "$PY" -B -m bot.exit.train --init "$INIT" --assets "$ASSETS" "${new[@]}" "${old[@]}" --new-ratio "$NEW_RATIO" \
  --temperature 0.003 --lr "$LR" --steps "$STEPS" --batch "$BATCH" --microbatch "$MICRO" --seed "$SEED" \
  --loader-workers "$LOADERS" --device "$DEVICE" --out "$J/fits/$NAME"
