#!/bin/bash
# Card-scope switch gate (run under bot/exit/cpu_job.sh N, setsid). Arms, all PYTHONHASHSEED=0:
#   live = r1 root + native-total-r1, pins r1-total  (today's live runtime; roots only)
#   c56  = r1-cards1-dev root, pins r1-total          (dev root, C56 scope)
#   full = r1-cards1-dev root, pins r1-cards1          (dev root, full scope)
# gate.sh roots     : roots parity, 3 arms x 2 shards (6 processes; ROOTS=dir of recorded roots)
# gate.sh headline  : HEADLINE command hashes, c56 vs full: students it5s2 + RL r5 v10 vs v1,R3a (30 cases each),
#                     then K4L-R-gs-rw-fc-p2 vs R3a,v1 (6 cases each); 2*POLW, then 2*3*K4LW processes
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
DEV=$J/r1-cards1-dev
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
arm() {  # arm NAME -> env assignments
  case $1 in
    live) echo "CLASHER_BOT_RUNTIME=/mpac/sdicks02/repos/clasher-bot-runtime/r1 CLASHER_DELAY_NATIVE_DIR=/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1 CLASHER_BOT_RUNTIME_PINS=r1-total" ;;
    c56) echo "CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=r1-total" ;;
    full) echo "CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native CLASHER_BOT_RUNTIME_PINS=r1-cards1" ;;
  esac
}
O=${O:-$J/gate}; mkdir -p $O
RL5=${RL5:-/mpac/sdicks02/jobs/clasher/bot-rl-r5/snapshots/policy-00010.pt}   # RL r5 v10, sha256 e188e2ae…
STU="student:/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt@0.5375,student:$RL5@0.5375"
POLW=${POLW:-4}; K4LW=${K4LW:-2}   # headline workers per arm (03: POLW=3 K4LW=1 keeps <= 8 busy processes)
PART=${1:?roots|headline}
ROOTS=${ROOTS:-$J/roots-nt}
if [ $PART = roots ]; then   # 3 arms x 2 shards = 6 processes
  echo "roots start $(date -u +%FT%TZ)"
  pids=()
  for a in live c56 full; do for i in 0 1; do
    env $(arm $a) nice -n 15 $PY -B reports/cards/runtime/tools/parity_scope_roots.py --roots $ROOTS --sample 300 \
      --shard $i/2 --out $O/roots-$a-$i.jsonl > $O/roots-$a-$i.log 2>&1 & pids+=($!)
  done; done
  for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
  echo "roots end $(date -u +%FT%TZ)"
  exit
fi
# headline: policies (2 arms x POLW workers), then (PART=headline only) K4L-R-gs-rw-fc-p2 (2 arms x K4LW x 3 procs)
echo "headline-pol start $(date -u +%FT%TZ)"
pids=()
for a in c56 full; do
  env $(arm $a) nice -n 15 $PY -B -m bot.eval.headline --out $O/hl-pol-$a --candidate "$STU" --opponents v1,R3a \
    --games 30 --workers $POLW > $O/hl-pol-$a.log 2>&1 & pids+=($!)
done
for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
[ $PART = headline-pol ] && exit
echo "headline-k4l start $(date -u +%FT%TZ)"
pids=()
for a in c56 full; do
  env $(arm $a) nice -n 15 $PY -B -m bot.eval.headline --out $O/hl-k4l-$a --candidate K4L-R-gs-rw-fc-p2 --opponents R3a,v1 \
    --games 6 --workers $K4LW > $O/hl-k4l-$a.log 2>&1 & pids+=($!)
done
for p in "${pids[@]}"; do wait $p; echo "pid $p rc $?"; done
echo "end $(date -u +%FT%TZ)"
