#!/usr/bin/env bash
# One mirror+eval cycle (run from 127x05): mirror.sh, then on 03 eval the newest checkpoint of r4 and r5
# vs the six RoyaleGym rungs (40 games each) unless already done. Results: 03:/mpac/sdicks02/jobs/clasher/bot-ext-eval/results
set -uo pipefail
here=$(dirname "$0")
"$here/mirror.sh" >/dev/null
ssh 127x03 'E=/mpac/sdicks02/jobs/clasher/bot-ext-eval; cd $E
for run in rlppo-r4 rlppo-r5; do
  ck=$(ls -d runs/$run/checkpoints/0* 2>/dev/null | sort | tail -1) || true
  [ -n "$ck" ] || continue
  step=$(basename $ck); tag=${run#rlppo-}-ck$step
  [ -e results/$tag-patient.json ] && continue
  ./run_evalset.sh $E/$ck $tag 40 &
done; wait; ls results | grep json | wc -l'
