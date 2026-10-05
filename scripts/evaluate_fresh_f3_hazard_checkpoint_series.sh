#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_checkpoint_series_seed1069701
checkpoint_dir=checkpoints/fresh_f3_hazard_mixed_league_seed1068701
parent=checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt
decks=datasets/deck_curriculum_v3_seed1056101/validation.json
expanded=reports/fresh_f3_hazard_expanded_safety_seed1069001/decision.json

for required in "$parent" "$decks" "$expanded"; do
  [[ -f "$required" ]] || { print -u2 -- "missing series input: $required"; exit 1; }
done
[[ $(jq -c '.rejection_reasons' "$expanded") == \
  '["direct96_below_52_wins","direct96_losing_seat"]' ]] || {
  print -u2 -- "expanded failure profile changed"
  exit 1
}
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed series"; exit 1; }
mkdir -p "$root"

typeset -a pids
pids=()
flush_jobs() {
  local failed=0
  local pid
  for pid in $pids; do
    wait "$pid" || failed=1
  done
  pids=()
  (( failed == 0 )) || return 1
}

for update in {21..30}; do
  checkpoint=$(printf '%s/policy_v2_update_%06d.pt' "$checkpoint_dir" "$update")
  [[ -f "$checkpoint" ]] || { print -u2 -- "missing series checkpoint: $checkpoint"; exit 1; }
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. \
    OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent policy --opponent-checkpoint "$parent" \
    --sampling-decks-path "$decks" --games 24 --mirror-match --seed 1069701 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/update${update}.metrics.json" \
    --games-json-out "$root/update${update}.games.json" > "$root/update${update}.log" 2>&1 &
  pids+=($!)
  if (( ${#pids[@]} >= 4 )); then
    flush_jobs
  fi
done
flush_jobs
print -r -- 'fresh_f3_hazard_checkpoint_series_complete_v1' > "$root/COMPLETE"
