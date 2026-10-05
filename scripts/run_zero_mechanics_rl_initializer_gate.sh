#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

source_checkpoint=${CLASHER_ZERO_SOURCE_CHECKPOINT:-checkpoints/reactive489k_public_v2_distill_gated_seed1055205/endpoint.pt}
candidate_checkpoint=${CLASHER_ZERO_CANDIDATE_CHECKPOINT:-checkpoints/mechanics_slot_probe/rl_zero_seed1056501/zero_adapter.pt}
equivalence_report=${CLASHER_ZERO_EQUIVALENCE_REPORT:-reports/zero_mechanics_rl_initializer_seed1056501/exact_equivalence.json}
root=${CLASHER_ZERO_INITIALIZER_ROOT:-reports/zero_mechanics_rl_initializer_seed1056501/gameplay}
summary="$root/summary.json"
ready_marker="$root/rl_initializer_ready.txt"
heldout_decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
hog_decks=training_decks/katacr_hog26_only.json

if [[ -e "$root" ]]; then
  print -u2 -- "refusing to overwrite an existing zero-initializer gameplay gate"
  exit 1
fi
for required in \
  "$source_checkpoint" \
  "$candidate_checkpoint" \
  "$equivalence_report" \
  "$heldout_decks" \
  "$hog_decks"
do
  if [[ ! -f "$required" ]]; then
    print -u2 -- "missing zero-initializer input: $required"
    exit 1
  fi
done
mkdir -p "$root"

run_workload() {
  local name=$1
  local games=$2
  local seed=$3
  shift 3
  nice -n 15 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$candidate_checkpoint" \
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
  --opponent random --sampling-decks-path "$heldout_decks" --mirror-match
run_workload balanced12 12 1056011 \
  --opponent strategy --opponent-strategy balanced \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_workload reactive12 12 1056012 \
  --opponent strategy --opponent-strategy reactive-defense \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_workload bridge6 6 1056013 \
  --opponent strategy --opponent-strategy bridge-pressure \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_workload slow6 6 1056014 \
  --opponent strategy --opponent-strategy slow-push \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_workload spell6 6 1056015 \
  --opponent strategy --opponent-strategy spell-control \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_workload split6 6 1056016 \
  --opponent strategy --opponent-strategy split-lane \
  --sampling-decks-path "$heldout_decks" --mirror-match

nice -n 15 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$candidate_checkpoint" \
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
  > "$root/candidate_hog12.log" 2>&1
env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
  --decisions "$root/candidate_hog12.decisions.json" \
  --games "$root/candidate_hog12.games.json" \
  --role primary_building_target \
  --max-zero-use-rate 0.10 \
  --min-window-conversion-rate 0.25 \
  --min-games-per-seat 5 \
  --json-out "$root/candidate_hog12.utilization.json" \
  > "$root/candidate_hog12.utilization.log"

env PYTHONPATH=src:. uv run python scripts/finalize_zero_mechanics_rl_initializer.py \
  --root "$root" \
  --equivalence-report "$equivalence_report" \
  --source-checkpoint "$source_checkpoint" \
  --candidate-checkpoint "$candidate_checkpoint" \
  --heldout-decks "$heldout_decks" \
  --hog-decks "$hog_decks" \
  --output "$summary" \
  2>&1 | tee "$root/finalize.log"

if [[ $(jq -r '.rl_initializer_eligible' "$summary") != true ]]; then
  print -u2 -- "zero-initializer gate did not approve the PFSP parent"
  exit 1
fi
marker_tmp="${ready_marker}.tmp.$$"
trap 'rm -f -- "$marker_tmp"' EXIT
print -r -- 'zero_mechanics_rl_initializer_ready_v1' > "$marker_tmp"
mv -- "$marker_tmp" "$ready_marker"
trap - EXIT
print -r -- '{"status":"zero_mechanics_rl_initializer_ready"}'
