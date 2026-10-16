#!/bin/bash
# B1+B2 merged-tree native==Python suites on 127x08 (run under cpu_job.sh 8; <= 8 processes). usage: run_b1b2.sh JOBDIR
J=$1; R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1; ES=$R1/reports/strategy_council_20260928/engine-speed
PY="nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B"; O=$J/fid
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1
C10="Freeze Snowball Vines Rage DarkMagic GoblinCurse Clone Graveyard Heal Mirror"
CA="GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons"
CB1="RoyalRecruits ThreeMusketeers GiantSkeleton SkeletonBalloon Hunter MiniSparkys RoyalGiant BattleHealer GoblinGiant GiantBuffer"
T5="3.5,14.5 14.5,12.5 9.5,10.5 3.5,17.5,1 13.5,20.5,1"; T3="3.5,14.5 14.5,12.5 3.5,17.5,1"
cd $O
./run_scen.sh root ../out m-scen-b2-root.json $C10 > m-scen-b2-root.log 2>&1 &
./run_scen.sh rootstats ../out m-scen-b2-stats.json $C10 > m-scen-b2-stats.log 2>&1 &
./run_scen.sh root ../out m-scen-batchA.json $CA > m-scen-batchA.log 2>&1 &
(cd $J/fid-b1 && bash run_scen.sh root ../out m-scen-b1.json $CB1 $CA > $O/m-scen-b1.log 2>&1) &
(cd $J/root && CLASHER_ROOT=$J/root PYTHONPATH=$J/out:$J/root/engine-rs:$J/root/src:$ES $PY $O/probe_first_update_paths.py $O/m-fu-paths.json > $O/m-fu-paths.log 2>&1
 CLASHER_ROOT=$J/root PYTHONPATH=$J/out:$J/root/engine-rs:$J/root/src:$ES $PY $O/probe_clone_bounds.py $O/m-clone-bounds.json > $O/m-clone-bounds.log 2>&1) &
(CLASHER_ROOT=$J/root PYTHONPATH=$J/out:$J/tree:$J/tree/py/src:$ES $PY $J/fid-b1/review_regressions.py $O/m-b1-regressions.json > $O/m-b1-regressions.log 2>&1) &
(cd $J/fid-b1 && bash run_taps.sh root ../out $O/m-taps-rr.json RoyalRecruits 3.5,14.5 14.5,14.5 8.5,10.5 9.5,12.5 0.5,8.5 17.5,3.5 9.0,6.5 12.5,4.5 16.5,12.5 3.5,17.5,1 14.5,17.5,1 9.5,21.5,1 2.5,28.5,1 15.5,23.5,1 9.5,25.5,1 > $O/m-taps-rr.log 2>&1
 bash run_taps.sh root ../out $O/m-taps-3m.json ThreeMusketeers $T5 > $O/m-taps-3m.log 2>&1
 bash run_taps.sh root ../out $O/m-taps-hu.json Hunter $T5 > $O/m-taps-hu.log 2>&1) &
(cd $J/fid-b1 && bash run_taps.sh root ../out $O/m-taps-gg.json GoblinGiant $T5 > $O/m-taps-gg.log 2>&1
 for en in Minions Fireball Zap Arrows Log BabyDragon MinionHorde; do ENEMY=$en bash run_taps.sh root ../out $O/m-taps-gg-$en.json GoblinGiant $T3 > $O/m-taps-gg-$en.log 2>&1; done) &
wait
date -u > $O/m.done
