#!/bin/bash
# Reviewed affected validation only. Must run under cpu_job.sh 4 / nice15.
set -euo pipefail
J=${1:?JOBDIR}; TAG=${2:?FRESH_TAG}
[[ "$TAG" =~ ^semv1-[a-zA-Z0-9-]+$ ]] || exit 2
N=$J/out4; MA=$J/mutA; MB=$J/mutB; O=$J/fid
ES=/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
cd "$J/root"
export CLASHER_ROOT=$J/root PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
P() { local native=$1; shift; PYTHONPATH="$native:$J/root/engine-rs:$J/root/src:$ES" nice -n 15 "$PY" -B "$@"; }
P "$N" "$O/validate_semantic_v1.py" "$O" "$TAG" --identity "$N" "$MA" "$MB"
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
F=$O/probe_dash_semantic_v1.py
start semantic-1 P "$N" "$F" "$O/$TAG-semantic-1.json" zap fireball arrows rocket lightning log barblog snowball
start semantic-2 P "$N" "$F" "$O/$TAG-semantic-2.json" earthquake poison freeze tornado goblin_curse vines void electro_spirit
start semantic-3 P "$N" "$F" "$O/$TAG-semantic-3.json" ice_spirit rage heal clone bowler magic_archer executioner mega_knight
start semantic-4 P "$N" "$F" "$O/$TAG-semantic-4.json" electro_dragon ice_wizard electro_wizard fire_spirits hunter valkyrie princess
wait_all
start mutA P "$MA" "$F" "$O/$TAG-mutA.json" lightning
start mutB P "$MB" "$F" "$O/$TAG-mutB.json" log
start descendants P "$N" "$O/probe_cache_descendants_v1.py" "$O/$TAG-descendants.json"
start fu-paths P "$N" "$O/probe_first_update_paths.py" "$O/$TAG-fu-paths.json"
wait_all
clone_checks() {
    P "$N" "$O/probe_clone_bounds.py" "$O/$TAG-clone-bounds.json" &&
    P "$N" "$O/probe_clone_recovery.py" "$O/$TAG-clone-recovery.json"
}
# The original strict shard's unsupported Executioner name stopped its runner before these phases.
# These unchanged fixtures therefore run once here, with separate parity receipts.
cd "$O"
C10=(Freeze Snowball Vines Rage DarkMagic GoblinCurse Clone Graveyard Heal Mirror)
CA=(GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons)
start clone-checks clone_checks
start scen-b2-root ./run_scen.sh root "$N" "$TAG-scen-b2-root.json" "${C10[@]}"
start scen-b2-stats ./run_scen.sh rootstats "$N" "$TAG-scen-b2-stats.json" "${C10[@]}"
start scen-batchA ./run_scen.sh root "$N" "$TAG-scen-batchA.json" "${CA[@]}"
wait_all
P "$N" "$O/validate_semantic_v1.py" "$O" "$TAG"
