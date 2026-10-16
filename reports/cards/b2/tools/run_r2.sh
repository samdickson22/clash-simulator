#!/bin/bash
# Next reviewed harness version. DO NOT replace the queued 08 r2 runner in place.
# Run under cpu_job.sh 4. Usage: run_r2.sh JOBDIR NATIVE MUTANT_A MUTANT_B FRESH_TAG
set -euo pipefail
J=${1:?JOBDIR}; N=${2:?NATIVE}; MA=${3:?MUTANT_A}; MB=${4:?MUTANT_B}; TAG=${5:?FRESH_TAG}
[[ "$TAG" =~ ^[a-zA-Z0-9_-]+$ && "$TAG" != r2 ]] || exit 2
R1=/mpac/sdicks02/repos/clasher-bot-runtime/r1
ES=$R1/reports/strategy_council_20260928/engine-speed
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
O=$J/fid
cd "$J/root"
export CLASHER_ROOT=$J/root PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
P() { local native=$1; shift; PYTHONPATH="$native:$J/root/engine-rs:$J/root/src:$ES" nice -n 15 "$PY" -B "$@"; }
# Exclusive identity file makes retries with the same tag fail before creating/overwriting evidence.
P "$N" "$O/validate_r2.py" "$O" "$TAG" --identity "$N" "$MA" "$MB"
pids=(); labels=()
start() {
    local label=$1; shift
    "$@" > "$O/$TAG-$label.log" 2>&1 &
    pids+=("$!"); labels+=("$label")
    printf '%s %s\n' "$!" "$label" >> "$O/$TAG.pids"
}
wait_all() {
    local failed=0 code i
    for i in "${!pids[@]}"; do
        if wait "${pids[$i]}"; then code=0; else code=$?; failed=1; fi
        printf '%s\n' "$code" > "$O/$TAG-${labels[$i]}.exit"
    done
    pids=(); labels=()
    return "$failed"
}
F=$O/probe_dash_full.py
start full-1 P "$N" "$F" "$O/$TAG-full-1.json" zap fireball arrows rocket lightning log barblog snowball
start full-2 P "$N" "$F" "$O/$TAG-full-2.json" earthquake poison freeze tornado goblin_curse vines void electro_spirit
start full-3 P "$N" "$F" "$O/$TAG-full-3.json" ice_spirit rage heal clone bowler magic_archer executioner mega_knight
start full-4 P "$N" "$F" "$O/$TAG-full-4.json" electro_dragon ice_wizard electro_wizard fire_spirits hunter valkyrie princess
wait_all
# Four more workers only after the four full-snapshot shards have exited.
start mutA P "$MA" "$F" "$O/$TAG-mutA.json" lightning
start mutB P "$MB" "$F" "$O/$TAG-mutB.json" log
start fu-paths P "$N" "$O/probe_first_update_paths.py" "$O/$TAG-fu-paths.json"
clone_checks() {
    P "$N" "$O/probe_clone_bounds.py" "$O/$TAG-clone-bounds.json" &&
    P "$N" "$O/probe_clone_recovery.py" "$O/$TAG-clone-recovery.json"
}
start clone-checks clone_checks
wait_all
# Three scenario workers, still under the same outer four-process lease.
cd "$O"
C10=(Freeze Snowball Vines Rage DarkMagic GoblinCurse Clone Graveyard Heal Mirror)
CA=(GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons)
start scen-b2-root ./run_scen.sh root "$N" "$TAG-scen-b2-root.json" "${C10[@]}"
start scen-b2-stats ./run_scen.sh rootstats "$N" "$TAG-scen-b2-stats.json" "${C10[@]}"
start scen-batchA ./run_scen.sh root "$N" "$TAG-scen-batchA.json" "${CA[@]}"
wait_all
# JSON validation rejects swallowed probe exceptions, false action acceptance and unrelated mutant failures.
P "$N" "$O/validate_r2.py" "$O" "$TAG"
