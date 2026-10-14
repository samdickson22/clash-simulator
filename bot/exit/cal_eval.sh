#!/usr/bin/env bash
# On-policy rate calibration, then HEADLINE eval (vs v1, R3a, reference student D, optional BOT_EXIT_OPP) for one checkpoint.
# BOT_EXIT_OPPS replaces the whole opponent list (e.g. "v1,R3a,student:IT5S2" to skip D).
#   bot/exit/cal_eval.sh CKPT OUTDIR CAL_START WORKERS [TAU0]
set -euo pipefail
ckpt=$1; out=$2; start=$3; w=$4; tau=${5:-0.5375}
D=${BOT_EXIT_D:-/mpac/sdicks02/jobs/clasher/bot-exit-r1/ckpt-it2D/step-001200.pt}
cd "$(dirname "$0")/../.."
# per-host worker ceiling (e.g. 24 on 08 while RL actors run there); edit the file to change it
maxw=$(cat /mpac/sdicks02/jobs/clasher/bot-cpu-claims/max-eval-workers 2>/dev/null || true); [[ "$maxw" =~ ^[0-9]+$ ]] && (( w > maxw )) && w=$maxw
bot/exit/cpu_room.sh "$w" 105
# hold the room for the whole job (cpu_feeder.sh honours leases), including the gaps between calibration rounds
lease=/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-$$
echo "$w $(ps -o pgid= -p $$ | tr -d ' ')" > "$lease"; trap 'rm -f "$lease"' EXIT
bot/exit/run.sh -m bot.exit.calibrate --mode rate --target-plays 37.8 --ckpt "$ckpt" --threshold "$tau" \
    --out "$out/cal" --base 874184153281168 --start "$start" --games 128 --rounds 5 --workers "$w"
bot/exit/run.sh -m bot.eval.headline --out "$out/eval" --candidate "student:$ckpt" \
    --opponents "${BOT_EXIT_OPPS:-v1,R3a,student:$D${BOT_EXIT_OPP:+,$BOT_EXIT_OPP}}" --games 300 --workers "$w"
