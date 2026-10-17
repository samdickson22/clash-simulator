#!/bin/bash
# archived default-off parity: ARMS="tree:mode ..." RUNS="..." NAME; one process per (run, arm), at most P at a time; 05, nice 19
set -u
J=/mpac/sdicks02/jobs/clasher/bot-cycle; NAME=${NAME:-K4L-R-gs-rw-fc-t2-mk1a1-res}; P=${P:-3}
run_one(){ local run=$1 tree=$2 mode=$3
  ( export TREE=$J/pkg-trees/$tree; source /mpac/sdicks02/jobs/clasher/live-multibody-20261015/guardfix/cycpkg-env.sh
    export NUMBA_CACHE_DIR=/mpac/sdicks02/cache/numba-cycle OMP_NUM_THREADS=1
    unset BOT_CYCLE_MODEL BOT_CYCLE_PREAL
    if [ $mode = soft ]; then export BOT_CYCLE_MODEL=soft BOT_CYCLE_PREAL=$TREE/reports/bot/cycle-model/preal-v1.json; fi
    cd /tmp && timeout 5400 nice -n 19 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B $J/archived_parity.py $run $NAME $J/archpar/$run-$tree-$mode.json > $J/archpar/$run-$tree-$mode.log 2>&1
    echo "$run $tree $mode rc=$? $(date -u +%T)" >> $J/archpar/rc.txt )
}
echo "start $(date -u +%FT%TZ) name $NAME"
for run in ${RUNS:-s72-m04}; do for arm in ${ARMS:-base-W:off}; do
  while [ $(jobs -rp | wc -l) -ge $P ]; do sleep 5; done
  run_one $run ${arm%%:*} ${arm##*:} &
done; done; wait
echo "end $(date -u +%FT%TZ)"
