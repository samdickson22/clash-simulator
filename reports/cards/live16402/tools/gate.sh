#!/bin/bash
# live16402 gate (run under clasher-bot/bot/exit/cpu_job.sh N, setsid; code = this job dir's repo copy, sync08.sh).
#   gate.sh totality            4 processes: totality probes (recorded-root config / live16402 config) x (plain, scrub)
#   gate.sh matches             <= 8 processes: LIVE K4L (1+4 pool) + 2 fast-tier streams, opponents on non-C56 decks
#   gate.sh nonlive             2 processes: complete-search K4L-R-gs-rw-fc + live belief vs random on non-C56 decks
#   gate.sh eval ARM WORKERS    headline K4L-R-gs-rw-fc vs R3a,v1, cases 0..GAMES-1 (default 200); ARM = l16 (live16402)
#                               | cur (r1-total; GAMES=12 = hash check against the bot lead's K4L-R-gs HEADLINE run)
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/live16402
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
L16=${L16:-$J/runtime/live16402-dev}
[ -d $L16 ] || L16=/mpac/sdicks02/jobs/clasher/cards/runtime/live16402-dev
RT=/mpac/sdicks02/repos/clasher-bot-runtime
arm() {
  case $1 in
    l16) echo "CLASHER_BOT_RUNTIME=$L16 CLASHER_BOT_RUNTIME_PINS=live16402" ;;
    cur) echo "CLASHER_BOT_RUNTIME=$RT/r1 CLASHER_DELAY_NATIVE_DIR=$RT/native-total-r1 CLASHER_BOT_RUNTIME_PINS=r1-total" ;;
  esac
}
T=reports/cards/live16402/tools
PART=${1:?totality|matches|eval}
O=$J/gate; mkdir -p $O
echo "$PART start $(date -u +%FT%TZ) host $(hostname) L16=$L16"
if [ $PART = totality ]; then
  ROOTS=${ROOTS:-/mpac/sdicks02/jobs/clasher/cards/runtime/roots-nt}
  pids=()
  for cfg in root runtime; do for scrub in plain scrub; do
    flags=""; [ $cfg = runtime ] && flags="--runtime-config"; [ $scrub = scrub ] && flags="$flags --scrub"
    env $(arm l16) nice -n 15 $PY -B $T/totality_live.py $flags --roots $ROOTS --out $O/totality-$cfg-$scrub.json \
      > $O/totality-$cfg-$scrub.log 2>&1 & pids+=($!)
  done; done
  for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
elif [ $PART = matches ]; then
  M=reports/cards/runtime/tools/noncore_matches.py          # cards-runtime-scope worker's tool, run unchanged
  LIVE=${LIVE:-LIVE-K4L-R-gs-rw-fc-w200-t4-p4}
  N=${N:-3}
  fast() {  # fast DECKS...
    for d in "$@"; do for o in random R3a; do
      env $(arm l16) nice -n 15 $PY -B $M --player LIVE-fast-it5s2 --opponent $o --deck $d --games $N --out $O/fast.jsonl
    done; done
  }
  fast D1 D2 D3 > $O/fast-a.log 2>&1 & f1=$!
  fast D4 M1 X1 > $O/fast-b.log 2>&1 & f2=$!
  for spec in D1:random D2:random D3:random D4:random M1:random X1:random D1:R3a D2:R3a D3:R3a D4:R3a M1:R3a; do
    d=${spec%%:*}; o=${spec#*:}
    env $(arm l16) nice -n 15 $PY -B $M --player $LIVE --opponent $o --deck $d --games $N --out $O/live.jsonl >> $O/live.log 2>&1
    echo "live $spec rc $? $(date -u +%FT%TZ)"
  done
  wait $f1; echo "fast-a rc $?"; wait $f2; echo "fast-b rc $?"
elif [ $PART = nonlive ]; then   # complete-search K4L (no wall deadline) with the live belief: 2 processes
  M=reports/cards/runtime/tools/noncore_matches.py
  for d in D1 D2 D3 D4 M1; do
    env $(arm l16) nice -n 15 $PY -B $M --player K4L-R-gs-rw-fc --live-belief --opponent random --deck $d --games 2 \
      --out $O/nonlive.jsonl >> $O/nonlive.log 2>&1
    echo "nonlive $d rc $? $(date -u +%FT%TZ)"
  done
elif [ $PART = eval ]; then
  A=${2:?l16|cur}; W=${3:?workers}
  env $(arm $A) nice -n 15 $PY -B -m bot.eval.headline --out $O/hl-$A --candidate K4L-R-gs-rw-fc --opponents R3a,v1 \
    --games ${GAMES:-200} --workers $W > $O/hl-$A.log 2>&1
  echo "eval rc $?"
fi
echo "$PART end $(date -u +%FT%TZ)"
