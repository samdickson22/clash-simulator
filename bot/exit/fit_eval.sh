#!/usr/bin/env bash
# GPU-queue item: run one bot.exit.train fit, then (only if it completed) append its on-policy calibration + HEADLINE
# eval to a CPU queue. Neither queue ever holds an item that just waits.
#   [BOT_GPU_MAX_GB=20] bot/exit/fit_eval.sh CPU_QUEUE CAL_START EVAL_WORKERS OPPONENTS -- TRAIN_ARGS...
# TRAIN_ARGS must include --out DIR and --steps N. The eval line is named ev-<DIR minus "train-">, writes
# <dir of DIR>/ce-<same>, and is run by gpu_queue.sh from the repo root.
set -uo pipefail
q=${1:?CPU_QUEUE}; start=${2:?CAL_START}; w=${3:?WORKERS}; opps=${4:?OPPONENTS}; shift 4
[[ ${1:-} == -- ]] && shift
out=$(grep -oE -- '--out [^ ]+' <<<"$*" | awk '{print $2}')
steps=$(grep -oE -- '--steps [0-9]+' <<<"$*" | awk '{print $2}')
[[ -n "$out" && -n "$steps" ]] || { echo "fit_eval: TRAIN_ARGS need --out and --steps"; exit 2; }
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8  # trainer torch threads <= 8 (lead 21:55Z)
ulimit -n 65536  # the loader passes shared-memory fds; many packs exhaust the default 1024 (kmix1 crash 20:23Z)
nice -n 5 env PYTHONDONTWRITEBYTECODE=1 /mpac/sdicks02/repos/clasher-bot-gpu/venv/bin/python -B -m bot.exit.train "$@"
rc=$?
(( rc == 0 )) && [[ -e "$out/complete.json" ]] || { echo "fit_eval: train rc=$rc, no eval queued"; exit "$(( rc ? rc : 1 ))"; }
tag=$(basename "$out"); tag=${tag#train-}
echo "ev-$tag env BOT_EXIT_OPPS=$opps bot/exit/cal_eval.sh $out/step-$(printf %06d "$steps").pt $(dirname "$out")/ce-$tag $start $w 0.5375" >> "$q"
echo "fit_eval: queued ev-$tag in $q"
