#!/bin/bash
J=/mpac/sdicks02/jobs/clasher/cards/c1; V=$J/verify; G=($(cat $J/nd-sample.txt))
export NAT=$J/out ROOT=$J/root; source $J/ctools/env.sh; cd $ROOT
for w in 0 1 2 3 4 5; do
  sel=(); for ((k=w; k<${#G[@]}; k+=6)); do sel+=(${G[k]}); done
  nice -n 15 $PY -B $J/ctools/replay_games.py $J/nd-plan.json $V/nd-sample-$w.json ${sel[@]} > $V/nd-sample-$w.log 2>&1 &
done
wait; date -u > $V/nd-sample.done
