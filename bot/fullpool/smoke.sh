#!/usr/bin/env bash
# Full-pool smoke under pin r1-cards1 (run from a repo tree on 03/04/08 under bot/exit/cpu_job.sh, setsid):
#   bot/exit/cpu_job.sh 14 bot/fullpool/smoke.sh OUT [ARMS]
# Env: DEV = runtime root; PINS = pin set (default r1-cards1; e.g. live16402); EXT = dir with rl5-v10-fp.pt (+ the original policy-00010.pt);
#      LOPP = model dir with pool.npz and poolfp.npz; W = headline workers (default 12); N = games per arm (40).
# Arms (default all, in this order):
#   stu   extended RL r5 v10 student vs R3a, bank FP-DEV (both decks full-pool), N games
#   k4l   K4L-R-gs with the extended K4L net vs R3a, bank FPO-DEV (our deck C56: R.bots stays C56), N games
#   c56s  C56 end-to-end parity: original vs extended student vs R3a on HEADLINE x4s cases 0..19 (command hashes)
#   c56k  same for K4L-R-gs mpool vs mpoolfp, cases 0..5
#   gen   bot.exit.generate, extended student + K4S-b64 teacher, decks fullpool:<FP-TRAIN1 seed>:own=c56, 2 games
# Optional (need R.bots widened to the full pool, i.e. search seats holding non-C56 cards):
#   k4lf  K4L-R-gs-mpoolfp vs R3a on FP-DEV (both decks full-pool), N games
#   genf  as gen with both decks full-pool (teacher holds non-C56 cards), 2 games
# Every arm is resumable (headline/generate skip finished keys). Summary: python -m bot.fullpool.smoke_summary OUT.
set -uo pipefail
OUT=${1:?OUT}; ARMS=${2:-stu k4l c56s c56k gen}
repo=$(cd "$(dirname "$0")/../.." && pwd); cd "$repo"
DEV=${DEV:-/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards1-dev}
EXT=${EXT:-/mpac/sdicks02/jobs/clasher/bot-fullpool/ext}
LOPP=${LOPP:-/mpac/sdicks02/jobs/clasher/bot-fullpool/lopp-fp}
W=${W:-12}; N=${N:-40}
PY=${PY:-/mpac/sdicks02/repos/clasher-bot/.venv/bin/python}
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 \
  CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 NUMPY_MADVISE_HUGEPAGE=0 \
  CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=${PINS:-r1-cards1} \
  CLASHER_LOPP_MODELS=$LOPP
STU0="student:$EXT/policy-00010.pt@0.5375"; STU1="student:$EXT/rl5-v10-fp.pt@0.5375"
mkdir -p "$OUT"
hl() { nice -n 15 $PY -B -m bot.eval.headline "$@"; }
for arm in $ARMS; do
  echo "$arm start $(date -u +%FT%TZ)"
  case $arm in
    stu)  hl --out "$OUT/stu" --candidate "$STU1" --opponents R3a --games $N --workers $W --bank FP-DEV ;;
    k4l)  hl --out "$OUT/k4l" --candidate K4L-R-gs-mpoolfp --opponents R3a --games $N --workers $W --bank FPO-DEV ;;
    c56s) hl --out "$OUT/c56s" --candidate "$STU0,$STU1" --opponents R3a --games 20 --workers $W ;;
    c56k) hl --out "$OUT/c56k" --candidate K4L-R-gs-mpool,K4L-R-gs-mpoolfp --opponents R3a --games 6 --workers $W ;;
    gen)  nice -n 15 $PY -B -m bot.exit.generate --out "$OUT/gen" --student "$STU1" --pool R3a --games 2 --workers 2 \
            --base 2613058991490864 --decks fullpool:11433651:freq=b53b02a1fde4,own=c56 ;;
    k4lf) hl --out "$OUT/k4lf" --candidate K4L-R-gs-mpoolfp --opponents R3a --games $N --workers $W --bank FP-DEV ;;
    genf) nice -n 15 $PY -B -m bot.exit.generate --out "$OUT/genf" --student "$STU1" --pool R3a --games 2 --workers 2 \
            --base 2613058991490864 --start 1000 --decks fullpool:11433651:freq=b53b02a1fde4 ;;
  esac
  echo "$arm end $(date -u +%FT%TZ) rc $?"
done
