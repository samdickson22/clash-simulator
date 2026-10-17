#!/bin/bash
# Batch C1 native==Python verification on 04: run under cpu_job.sh 6.  Output: $J/verify/
J=/mpac/sdicks02/jobs/clasher/cards/c1; V=$J/verify; mkdir -p $V
CARDS='Bowler Assassin ZapMachine ElectroWizard IceWizard InfernoDragon MegaKnight Fisherman AxeMan ElectroDragon BossBandit Ronin'
run() { (export NAT=$J/out ROOT=$J/$1; source $J/ctools/env.sh; cd $ROOT; shift; nice -n 15 $PY -B "$@"); }
run root $J/tools/probe_native_scen.py $V/scen-root.json $CARDS > $V/scen-root.log 2>&1 &
run rootstats $J/tools/probe_native_scen.py $V/scen-rootstats.json $CARDS > $V/scen-rootstats.log 2>&1 &
run root $J/ctools/probe_c1_cases.py $V/cases.json > $V/cases.log 2>&1 &
run root $J/tools/probe_first_update_paths.py $V/paths.json > $V/paths.log 2>&1 &
run root $J/tools/probe_native_scen.py $V/batchA-cases.json --cases > $V/batchA-cases.log 2>&1 &
run root $J/ctools/replay_games.py $J/nd-plan.json $V/nd.json 22 245 274 323 16 86 336 460 189 415 548 > $V/nd.log 2>&1 &
wait
date -u > $V/done
