#!/bin/bash
# R.bots widening gate (08, under bot/exit/cpu_job.sh 7; <= 6 python processes at a time):
#  phase 1: HEADLINE K4L-R-gs-rw-fc-p2 vs R3a,v1 cases 0-5, c56 arm (pins r1-total)   [4 procs]
#           + own-deck M1 smokes vs R3a: LIVE-fast-it5s2 (2 games) and K4L-R-gs-rw-fc (2 games)   [1 + 1]
#  phase 2: same HEADLINE, full arm (pins r1-cards1, widened R.bots)   [4] + side_cut_check x2   [2]
#  phase 3: own-deck M1 smoke vs R3a with the live recipe LIVE-K4L-R-gs-rw-fc-w200-t4-p4 (2 games)   [5] + mirror_probe [1]
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
DEV=$J/r1-cards1-dev; O=${O:-$J/gate4}; mkdir -p $O
cd $J/repo
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1
export CLASHER_BOT_RUNTIME=$DEV CLASHER_DELAY_NATIVE_DIR=$DEV/native
hl() { CLASHER_BOT_RUNTIME_PINS=$2 nice -n 15 $PY -B -m bot.eval.headline --out $O/hl-k4l-$1 --candidate K4L-R-gs-rw-fc-p2 \
         --opponents R3a,v1 --games 6 --workers 1 > $O/hl-k4l-$1.log 2>&1; echo "hl $1 rc $? $(date -u +%FT%TZ)"; }
smoke() { CLASHER_BOT_RUNTIME_PINS=r1-cards1 nice -n 15 $PY -B reports/cards/runtime/tools/noncore_matches.py --player $1 \
            --opponent R3a --deck X1 --own-deck M1 --probe-own --games 2 --out $O/own-$1.jsonl > $O/own-$1.log 2>&1
          echo "smoke $1 rc $? $(date -u +%FT%TZ)"; }
echo "start $(date -u +%FT%TZ)"
hl c56 r1-total & a=$!; smoke LIVE-fast-it5s2 & b=$!; smoke K4L-R-gs-rw-fc & c=$!
wait $a; wait $b; wait $c
T=reports/cards/runtime/tools; TR=$J/timing
CLASHER_BOT_RUNTIME_PINS=r1-cards1 nice -n 15 $PY -B $T/side_cut_check.py $O/side-check-noncore.json $TR/roots-D1.jsonl.gz \
  $TR/roots-D3.jsonl.gz $TR/roots-D4.jsonl.gz $TR/roots-M1.jsonl.gz > $O/side-check-noncore.log 2>&1 & s1=$!
CLASHER_BOT_RUNTIME_PINS=r1-cards1 nice -n 15 $PY -B $T/side_cut_check.py $O/side-check-c56rec.json $J/roots-nt/ \
  > $O/side-check-c56rec.log 2>&1 & s2=$!
hl full r1-cards1
wait $s1; echo "side-check noncore rc $?"; wait $s2; echo "side-check c56rec rc $?"
CLASHER_BOT_RUNTIME_PINS=r1-cards1 nice -n 15 $PY -B $T/mirror_probe.py $O/mirror_probe.json $TR/roots-D1.jsonl.gz \
  $TR/roots-D3.jsonl.gz > $O/mirror_probe.log 2>&1 & m=$!
smoke LIVE-K4L-R-gs-rw-fc-w200-t4-p4
wait $m; echo "mirror rc $?"
echo "end $(date -u +%FT%TZ)"
