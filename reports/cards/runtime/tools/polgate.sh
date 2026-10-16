#!/bin/bash
# polgate.sh ARM OUTDIR [GAMES=10] [WORKERS=6]: HEADLINE policy command-hash gate, one arm (c56 = pins r1-total,
# full = pins r1-cards1) on the dev root: students it5s2 + RL r5 v10 (@0.5375) vs v1,R3a, cases 0..GAMES-1.
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
ARM=$1; O=$2; G=${3:-10}; W=${4:-6}
RL5=${RL5:-/mpac/sdicks02/jobs/clasher/bot-rl-r5/snapshots/policy-00010.pt}
DEV=$J/r1-cards1-dev; pins=r1-total; [ $ARM = full ] && pins=r1-cards1
cd $J/repo
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
echo "start $ARM $(date -u +%FT%TZ)"
CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=$pins nice -n 15 \
  /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B -m bot.eval.headline --out $O/hl-pol-$ARM \
  --candidate "student:/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt@0.5375,student:$RL5@0.5375" \
  --opponents v1,R3a --games $G --workers $W
echo "end $ARM rc $? $(date -u +%FT%TZ)"
