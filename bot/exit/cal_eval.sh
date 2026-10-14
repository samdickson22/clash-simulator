#!/usr/bin/env bash
# On-policy rate calibration, then HEADLINE eval (vs v1, R3a and reference student D) for one checkpoint.
#   bot/exit/cal_eval.sh CKPT OUTDIR CAL_START WORKERS [TAU0]
set -euo pipefail
ckpt=$1; out=$2; start=$3; w=$4; tau=${5:-0.5375}
D=${BOT_EXIT_D:-/mpac/sdicks02/jobs/clasher/bot-exit-r1/ckpt-it2D/step-001200.pt}
cd "$(dirname "$0")/../.."
bot/exit/run.sh -m bot.exit.calibrate --mode rate --target-plays 37.8 --ckpt "$ckpt" --threshold "$tau" \
    --out "$out/cal" --base 874184153281168 --start "$start" --games 128 --rounds 5 --workers "$w"
bot/exit/run.sh -m bot.eval.headline --out "$out/eval" --candidate "student:$ckpt" \
    --opponents "v1,R3a,student:$D" --games 300 --workers "$w"
