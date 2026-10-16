#!/bin/bash
# Reviewed fresh build/affected checks only; cpu_job.sh 4 / nice15.
set -euo pipefail
J=${1:?JOBDIR}; TAG=${2:?TAG}
trap 'code=$?; printf "%s\n" "$code" > "$J/run.exit"' EXIT
PY=/mpac/sdicks02/repos/clasher-bot/.venv/bin/python
export CARGO_HOME=/mpac/sdicks02/tools/cargo RUSTUP_HOME=/mpac/sdicks02/tools/rustup
export PATH=/mpac/sdicks02/tools/cargo/bin:$PATH
export PYO3_PYTHON=$PY CARGO_INCREMENTAL=0 CARGO_BUILD_JOBS=4
export PYTHONOPTIMIZE=0 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 RAYON_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
unset BASH_ENV ENV PYTHONHOME PYTHONINSPECT PYTHONSTARTUP RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
O=$J/fid
"$PY" -B "$O/validate_rage_fix_v1.py" prepare "$J" "$TAG"
for spec in out4:tree mutA:treeA mutB:treeB; do
    arm=${spec%%:*}; source_tree=${spec#*:}
    if nice -n 15 cargo +1.97.1 build --offline --manifest-path "$J/$source_tree/Cargo.toml" \
        --target-dir "$J/target" --release --features extension-module,gil-release -j 4 > "$J/build-$arm.log" 2>&1; then
        printf '0\n' > "$J/build-$arm.exit"
    else
        code=$?; printf '%s\n' "$code" > "$J/build-$arm.exit"; exit "$code"
    fi
    cp "$J/target/release/libclasher_core.so" "$J/$arm/clasher_core.abi3.so"
done
"$PY" -B "$O/validate_rage_fix_v1.py" identity "$J" "$TAG"
read -r B2_RAGE_BUILD_SHA256 rage_build_filename < <(sha256sum "$J/build.json")
export B2_RAGE_BUILD_SHA256
ES=/mpac/sdicks02/repos/clasher-bot-runtime/r1/reports/strategy_council_20260928/engine-speed
cd "$J/root"
P() {
    local arm=$1 label=$2; shift 2
    CLASHER_ROOT=$J/root PYTHONPATH="$J/$arm:$J/tree:$J/root/src:$ES" \
        nice -n 15 "$PY" -B "$O/validate_rage_fix_v1.py" exec "$J" "$TAG" "$arm" "$label" "$@"
}
pids=(); labels=()
start() {
    local label=$1; shift
    "$@" > "$O/$TAG-$label.log" 2>&1 &
    pids+=("$!"); labels+=("$label")
    printf '%s %s\n' "$!" "$label" >> "$J/children.pids"
}
wait_all() {
    local failed=0 code i
    for i in "${!pids[@]}"; do
        if wait "${pids[$i]}"; then code=0; else code=$?; failed=1; fi
        printf '%s\n' "$code" > "$O/$TAG-${labels[$i]}.exit"
    done
    pids=(); labels=(); return "$failed"
}
F=$O/probe_dash_semantic_v1.py
start baseline-1 P out4 baseline-1 "$F" "$O/$TAG-baseline-1.json" rage lightning
start baseline-2 P out4 baseline-2 "$F" "$O/$TAG-baseline-2.json" poison log
start baseline-3 P out4 baseline-3 "$F" "$O/$TAG-baseline-3.json" vines void
start baseline-4 P out4 baseline-4 "$F" "$O/$TAG-baseline-4.json" goblin_curse barblog
wait_all
start mutA P mutA mutA "$F" "$O/$TAG-mutA.json" lightning
start mutB P mutB mutB "$F" "$O/$TAG-mutB.json" log
start descendants P out4 descendants "$O/probe_cache_descendants_v1.py" "$O/$TAG-descendants.json"
start fu-paths P out4 fu-paths "$O/probe_first_update_paths.py" "$O/$TAG-fu-paths.json"
wait_all
clone_checks() {
    P out4 clone-bounds "$O/probe_clone_bounds.py" "$O/$TAG-clone-bounds.json" &&
    P out4 clone-recovery "$O/probe_clone_recovery.py" "$O/$TAG-clone-recovery.json" &&
    P out4 rage-impact "$O/probe_rage_impact_v1.py" "$O/$TAG-rage-impact.json" &&
    P out4 rage-mirror "$O/probe_rage_impact_v1.py" "$O/$TAG-rage-mirror.json" --mirror
}
cd "$O"
C10=(Freeze Snowball Vines Rage DarkMagic GoblinCurse Clone Graveyard Heal Mirror)
CA=(GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons)
scenario_case() {
    local root=$1 label=$2; shift 2
    CLASHER_ROOT=$J/$root PYTHONPATH="$J/out4:$J/tree:$J/root/src:$ES" \
        nice -n 15 "$PY" -B "$O/validate_rage_fix_v1.py" exec "$J" "$TAG" out4 "$label" \
        "$O/probe_native_scen.py" "$O/$TAG-$label.json" "$@"
}
start clone-checks clone_checks
# Same unchanged scenario probe and explicit data arms, with actual import receipts.
start scen-b2-root scenario_case root scen-b2-root "${C10[@]}"
start scen-b2-stats scenario_case rootstats scen-b2-stats "${C10[@]}"
start scen-batchA scenario_case root scen-batchA "${CA[@]}"
wait_all
"$PY" -B "$O/validate_rage_fix_v1.py" validate "$J" "$TAG"
