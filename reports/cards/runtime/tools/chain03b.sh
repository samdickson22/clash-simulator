#!/bin/bash
# 03 (<= 6 busy processes): roots parity (3 arms, full arm now with fc_side_cut) -> side-cut value checks ->
# HEADLINE policy gate (students it5s2 + RL r5 v10 vs v1,R3a, cases 0-29, c56 vs full).
set -uo pipefail
J=/mpac/sdicks02/jobs/clasher/cards/runtime
cd $J/repo
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
T=reports/cards/runtime/tools
mkdir -p $J/gate2
ROOTS=/mpac/sdicks02/jobs/clasher/bot-native-total/roots O=$J/gate2 bash $T/gate.sh roots
echo "roots rc $? $(date -u +%FT%TZ)"
export PYTHONHASHSEED=0 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 CLASHER_BOT_RUNTIME=$J/r1-cards1-dev CLASHER_DELAY_NATIVE_DIR=$J/r1-cards1-dev/native CLASHER_BOT_RUNTIME_PINS=r1-cards1
O=$J/timing
nice -n 15 $PY -B $T/side_cut_check.py $O/side-check-noncore.json $O/roots-D1.jsonl.gz $O/roots-D3.jsonl.gz \
  $O/roots-D4.jsonl.gz $O/roots-M1.jsonl.gz > $O/side-check-noncore.log 2>&1 &
nice -n 15 $PY -B $T/side_cut_check.py $O/side-check-c56rec.json /mpac/sdicks02/jobs/clasher/bot-native-total/roots/ \
  > $O/side-check-c56rec.log 2>&1 &
wait
echo "checks $(date -u +%FT%TZ)"
O=$J/gate2 POLW=3 RL5=$J/rl5-policy-00010.pt bash $T/gate.sh headline-pol
echo "end $(date -u +%FT%TZ)"
