#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

offline_root=reports/mechanics_slot_final1000_seed1055901
offline_marker="$offline_root/development_candidate_ready.txt"
candidate=checkpoints/mechanics_slot_probe/final1000_seed1055901/development_candidate.pt
parent=checkpoints/reactive489k_public_v2_distill_gated_seed1055205/endpoint.pt
root="$offline_root/gameplay"
summary="$root/summary.json"
ready_marker="$root/rl_initializer_ready.txt"

if [[ ! -f "$offline_marker" ]] || \
  [[ $(<"$offline_marker") != development_candidate_ready_v1 ]]; then
  print -u2 -- "offline mechanics candidate has not passed its final gate"
  exit 1
fi
if [[ ! -f "$candidate" || ! -f "$parent" ]]; then
  print -u2 -- "candidate or parent checkpoint is missing"
  exit 1
fi
if [[ -e "$root" ]]; then
  print -u2 -- "refusing to overwrite an existing mechanics gameplay gate"
  exit 1
fi
mkdir -p "$root"

for split in validation heldout; do
  if [[ "$split" == validation ]]; then
    decks=datasets/deck_curriculum_v2_seed1040001/validation.json
    seed=1056001
  else
    decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
    seed=1056002
  fi
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$decks" \
    --games 12 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$root/direct_${split}12.metrics.json" \
    --games-json-out "$root/direct_${split}12.games.json" \
    > "$root/direct_${split}12.log" 2>&1
done

run_paired_workload() {
  local name=$1
  local games=$2
  local seed=$3
  shift 3
  for role in parent candidate; do
    local checkpoint
    if [[ "$role" == parent ]]; then
      checkpoint=$parent
    else
      checkpoint=$candidate
    fi
    nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
      --checkpoint "$checkpoint" \
      "$@" \
      --games "$games" \
      --seed "$seed" \
      --device cpu \
      --reward-profile defense-v2 \
      --quiet-engine \
      --json-out "$root/${role}_${name}.metrics.json" \
      --games-json-out "$root/${role}_${name}.games.json" \
      > "$root/${role}_${name}.log" 2>&1
  done
  env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$root/parent_${name}.games.json" \
    --candidate "$root/candidate_${name}.games.json" \
    --output "$root/${name}.compare.json"
}

heldout_decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
run_paired_workload random12 12 1056010 \
  --opponent random \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match
run_paired_workload balanced12 12 1056011 \
  --opponent strategy \
  --opponent-strategy balanced \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match
run_paired_workload reactive12 12 1056012 \
  --opponent strategy \
  --opponent-strategy reactive-defense \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match
run_paired_workload bridge6 6 1056013 \
  --opponent strategy \
  --opponent-strategy bridge-pressure \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match
run_paired_workload slow6 6 1056014 \
  --opponent strategy \
  --opponent-strategy slow-push \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match
run_paired_workload spell6 6 1056015 \
  --opponent strategy \
  --opponent-strategy spell-control \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match
run_paired_workload split6 6 1056016 \
  --opponent strategy \
  --opponent-strategy split-lane \
  --sampling-decks-path "$heldout_decks" \
  --mirror-match

for role in parent candidate; do
  if [[ "$role" == parent ]]; then
    checkpoint=$parent
  else
    checkpoint=$candidate
  fi
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    --opponent strategy \
    --opponent-strategy balanced \
    --sampling-decks-path training_decks/katacr_hog26_only.json \
    --games 12 \
    --mirror-match \
    --seed 1056017 \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$root/${role}_hog12.metrics.json" \
    --games-json-out "$root/${role}_hog12.games.json" \
    --decisions-json-out "$root/${role}_hog12.decisions.json" \
    > "$root/${role}_hog12.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
    --decisions "$root/${role}_hog12.decisions.json" \
    --games "$root/${role}_hog12.games.json" \
    --role primary_building_target \
    --max-zero-use-rate 0.10 \
    --min-window-conversion-rate 0.25 \
    --min-games-per-seat 5 \
    --json-out "$root/${role}_hog12.utilization.json" \
    > "$root/${role}_hog12.utilization.log"
done
env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
  --baseline "$root/parent_hog12.games.json" \
  --candidate "$root/candidate_hog12.games.json" \
  --output "$root/hog12.compare.json"

env PYTHONPATH=src:. uv run python scripts/finalize_mechanics_slot_gameplay_gate.py \
  --root "$root" \
  --candidate-checkpoint "$candidate" \
  --parent-checkpoint "$parent" \
  --validation-decks datasets/deck_curriculum_v2_seed1040001/validation.json \
  --heldout-decks "$heldout_decks" \
  --hog-decks training_decks/katacr_hog26_only.json \
  --output "$summary" \
  2>&1 | tee "$root/finalize.log"

if [[ $(jq -r '.rl_initializer_eligible' "$summary") != true ]]; then
  print -r -- '{"status":"mechanics_gameplay_gate_rejected"}'
  exit 0
fi
ready_marker_tmp="${ready_marker}.tmp.$$"
trap 'rm -f -- "$ready_marker_tmp"' EXIT
print -r -- 'mechanics_rl_initializer_ready_v1' > "$ready_marker_tmp"
mv -- "$ready_marker_tmp" "$ready_marker"
trap - EXIT
print -r -- '{"status":"mechanics_rl_initializer_ready"}'
