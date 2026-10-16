#!/usr/bin/env bash
# Value-net v0 fit (bot/fullpool/value_net.py; plan step 2) on local G1 + C56 packs, on this host's GPU:
#   ROOT=<root> NAME=<fresh-name> bot/detach.sh <log> <receipt> bot/exit/cpu_job.sh 10 bot/fullpool/run/fit_vn.sh PACK...
# Defaults: init = extended rl5 v10 trunk, assets = the C56 corpus assets, 6000 steps x 4096 rows, d30 checkpoint selection.
set -euo pipefail
: "${PY:=/mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python}"
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
: "${NAME:?unique fresh NAME required}" "${THREADS:=4}" "${LOADERS:=6}" "${STEPS:=6000}" "${LR:=1e-4}" "${BATCH:=4096}"
: "${MICRO:=1024}" "${SEED:=2026101701}" "${INIT:=$EXT/rl5-v10-fp.pt}" "${MAIN_HEAD:=d30}" "${EVAL_EVERY:=500}" "${EVAL_ROWS:=60000}"
fullpool_require_cpu_budget "$((THREADS + LOADERS))"
[[ ! -e "$J/vnet/$NAME" ]] || { echo 'fresh output directory required' >&2; exit 1; }
OLDDIR=${OLDDIR:-$( [ -d /mpac/sdicks02/jobs/clasher/bot-exit-r1/packed-kc7a-x08 ] && echo /mpac/sdicks02/jobs/clasher/bot-exit-r1 || echo /mpac/sdicks02/jobs/clasher/bot-exit-r1-04)}
ASSETS=${ASSETS:-$OLDDIR/inputs/assets.npz}
packs=(); for p in "$@"; do packs+=(--pack "$p"); done
export OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS CUDA_VISIBLE_DEVICES=${GPU:-0} BOT_GPU_MAX_GB=${BOT_GPU_MAX_GB:-40}
echo "vnet $NAME start $(date -u +%FT%TZ) tree $(cat STAGED-REV 2>/dev/null) init $INIT packs $* steps $STEPS lr $LR head $MAIN_HEAD"
exec nice -n 15 "$PY" -B -m bot.fullpool.value_net --init "$INIT" --assets "$ASSETS" "${packs[@]}" --steps "$STEPS" --lr "$LR" \
  --batch "$BATCH" --microbatch "$MICRO" --seed "$SEED" --loader-workers "$LOADERS" --main-head "$MAIN_HEAD" \
  --eval-every "$EVAL_EVERY" --eval-rows "$EVAL_ROWS" --out "$J/vnet/$NAME"
