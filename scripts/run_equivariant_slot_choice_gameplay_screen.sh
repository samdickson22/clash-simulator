#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

candidate=${CLASHER_EQUIVARIANT_CANDIDATE:-checkpoints/equivariant_slot_choice/accepted6m_distilled_top1_seed1056804/distilled_epoch5.pt}
root=${CLASHER_EQUIVARIANT_SCREEN_ROOT:-reports/equivariant_slot_choice_distilled_top1_seed1056804/gameplay}
parent_root=reports/accepted6m_zero_mechanics_rl_initializer_seed1056701/gameplay
heldout_decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
hog_decks=training_decks/katacr_hog26_only.json

if [[ ! -f "$candidate" || ! -d "$parent_root" ]]; then
  print -u2 -- "missing candidate checkpoint or accepted-parent evidence"
  exit 1
fi
if [[ -e "$root" ]]; then
  print -u2 -- "refusing to overwrite existing equivariant gameplay screen"
  exit 1
fi
mkdir -p "$root"

run_workload() {
  local name=$1
  local games=$2
  local seed=$3
  shift 3
  nice -n 10 env \
    OMP_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=src:. \
    uv run python run_clasher.py eval -- \
      --checkpoint "$candidate" \
      "$@" \
      --games "$games" \
      --seed "$seed" \
      --device cpu \
      --reward-profile defense-v2 \
      --quiet-engine \
      --json-out "$root/candidate_${name}.metrics.json" \
      --games-json-out "$root/candidate_${name}.games.json" \
      > "$root/candidate_${name}.log" 2>&1
}

run_workload random12 12 1056010 \
  --opponent random --sampling-decks-path "$heldout_decks" --mirror-match &
pid_random=$!
run_workload balanced12 12 1056011 \
  --opponent strategy --opponent-strategy balanced \
  --sampling-decks-path "$heldout_decks" --mirror-match &
pid_balanced=$!
run_workload reactive12 12 1056012 \
  --opponent strategy --opponent-strategy reactive-defense \
  --sampling-decks-path "$heldout_decks" --mirror-match &
pid_reactive=$!
run_workload bridge6 6 1056013 \
  --opponent strategy --opponent-strategy bridge-pressure \
  --sampling-decks-path "$heldout_decks" --mirror-match &
pid_bridge=$!
wait "$pid_random" "$pid_balanced" "$pid_reactive" "$pid_bridge"

run_workload slow6 6 1056014 \
  --opponent strategy --opponent-strategy slow-push \
  --sampling-decks-path "$heldout_decks" --mirror-match &
pid_slow=$!
run_workload spell6 6 1056015 \
  --opponent strategy --opponent-strategy spell-control \
  --sampling-decks-path "$heldout_decks" --mirror-match &
pid_spell=$!
run_workload split6 6 1056016 \
  --opponent strategy --opponent-strategy split-lane \
  --sampling-decks-path "$heldout_decks" --mirror-match &
pid_split=$!

nice -n 10 env \
  OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONPATH=src:. \
  uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    --opponent strategy \
    --opponent-strategy balanced \
    --sampling-decks-path "$hog_decks" \
    --games 12 \
    --mirror-match \
    --seed 1056017 \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$root/candidate_hog12.metrics.json" \
    --games-json-out "$root/candidate_hog12.games.json" \
    --decisions-json-out "$root/candidate_hog12.decisions.json" \
    > "$root/candidate_hog12.log" 2>&1 &
pid_hog=$!
wait "$pid_slow" "$pid_spell" "$pid_split" "$pid_hog"

env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
  --decisions "$root/candidate_hog12.decisions.json" \
  --games "$root/candidate_hog12.games.json" \
  --role primary_building_target \
  --max-zero-use-rate 0.10 \
  --min-window-conversion-rate 0.25 \
  --min-games-per-seat 5 \
  --json-out "$root/candidate_hog12.utilization.json" \
  > "$root/candidate_hog12.utilization.log"

for name in random12 balanced12 reactive12 bridge6 slow6 spell6 split6 hog12; do
  env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$parent_root/candidate_${name}.games.json" \
    --candidate "$root/candidate_${name}.games.json" \
    --output "$root/${name}.compare.json"
done

jq -n \
  --slurpfile random "$root/candidate_random12.metrics.json" \
  --slurpfile balanced "$root/candidate_balanced12.metrics.json" \
  --slurpfile reactive "$root/candidate_reactive12.metrics.json" \
  --slurpfile bridge "$root/candidate_bridge6.metrics.json" \
  --slurpfile slow "$root/candidate_slow6.metrics.json" \
  --slurpfile spell "$root/candidate_spell6.metrics.json" \
  --slurpfile split "$root/candidate_split6.metrics.json" \
  --slurpfile hog "$root/candidate_hog12.metrics.json" \
  '{
    schema: "equivariant-slot-gameplay-screen-v1",
    workloads: {
      random12: $random[0].metrics,
      balanced12: $balanced[0].metrics,
      reactive12: $reactive[0].metrics,
      bridge6: $bridge[0].metrics,
      slow6: $slow[0].metrics,
      spell6: $spell[0].metrics,
      split6: $split[0].metrics,
      hog12: $hog[0].metrics
    }
  }' > "$root/summary.json"
print -r -- '{"status":"equivariant_gameplay_screen_complete"}'
