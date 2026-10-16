#!/usr/bin/env bash
# KF1 K4L refit (PLAN.md section 2), CPU. Arm a: fine-tune from poolfp.npz (vocab order kept); arm b: fresh vocab.
#   After source/data/capacity review, use unique NAME/log/receipt:
#   ROOT=<root> ARM=a NAME=<fresh-name> bot/detach.sh <fresh-log> <fresh-receipt> bot/exit/cpu_job.sh 10 \
#     bot/fullpool/run/fit_kf1.sh REC_DIR[,REC_DIR...]
# REC dirs: local K1-x* dirs. OLD_REC must name the separately reviewed legacy C56 recording dirs.
set -euo pipefail
cd "$(dirname "$0")/../../.."; source bot/fullpool/run/env.sh
REC=${1:?REC dirs, comma-separated}; ARM=${ARM:-a}; OPPS=${OPPS:-R3a,v1,$STUDENT}
: "${OLD_REC:?reviewed legacy C56 recording dirs required, comma-separated}"
REC="$REC,$OLD_REC"
: "${NAME:?unique fresh NAME required}" "${THREADS:=8}" "${PROCS:=8}"
[[ "$ARM" = a || "$ARM" = b ]] || { echo 'ARM must be a or b' >&2; exit 1; }
[[ "$THREADS" =~ ^[1-9][0-9]*$ && "$PROCS" =~ ^[1-9][0-9]*$ ]] || { echo 'invalid threads/procs' >&2; exit 1; }
# Extraction workers exit before threaded training starts; reserve the larger phase.
demand=$((PROCS + 1)); (( THREADS > demand )) && demand=$THREADS
fullpool_require_cpu_budget "$demand"
[[ ! -e "$J/lopp-k1/$NAME.npz" && ! -e "$J/lopp-k1/$NAME.json" ]] || { echo 'fresh output name required' >&2; exit 1; }
init=(); [ "$ARM" = a ] && init=(--init "$LOPP/poolfp.npz")
echo "kf1 $ARM start $(date -u +%FT%TZ) rec $REC opponents $OPPS"
exec nice -n 15 "$PY" -B -m bot.search.lopp_train --rec "$REC" --out "$J/lopp-k1" --name "$NAME" --opponents "$OPPS" \
  --epochs ${EPOCHS:-8} --hidden 256 --layers 2 --threads "$THREADS" --procs "$PROCS" "${init[@]}"
