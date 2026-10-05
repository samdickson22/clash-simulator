#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

root=reports/fresh_f3_hazard_anchor_candidates_seed1069801
checkpoint_dir=checkpoints/fresh_f3_hazard_mixed_league_seed1068701
decks=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
hog=training_decks/katacr_hog26_only.json
series=reports/fresh_f3_hazard_checkpoint_series_seed1069701/COMPLETE

for required in "$decks" "$hog" "$series"; do
  [[ -f "$required" ]] || { print -u2 -- "missing anchor-screen input: $required"; exit 1; }
done
[[ ! -e "$root/COMPLETE" ]] || { print -u2 -- "refusing completed anchor screen"; exit 1; }
mkdir -p "$root"

screen_update() {
  local update=$1
  local checkpoint
  checkpoint=$(printf '%s/policy_v2_update_%06d.pt' "$checkpoint_dir" "$update")
  [[ -f "$checkpoint" ]] || return 1
  mkdir -p "$root/update${update}"
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py strategy-benchmark -- \
    --checkpoint "$checkpoint" --sampling-decks-path "$decks" \
    --games-per-opponent 4 --seed 1069801 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/update${update}/strategy.json" \
    --markdown-out "$root/update${update}/strategy.md" \
    > "$root/update${update}/strategy.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent random --sampling-decks-path "$decks" \
    --games 24 --mirror-match --seed 1069802 --decision-interval 8 --max-ticks 6000 \
    --device cpu --reward-profile objective-v1 --quiet-engine \
    --json-out "$root/update${update}/random24.metrics.json" \
    --games-json-out "$root/update${update}/random24.games.json" \
    > "$root/update${update}/random24.log" 2>&1
  nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" --opponent strategy --opponent-strategy balanced \
    --sampling-decks-path "$hog" --games 12 --mirror-match --seed 1069803 \
    --decision-interval 8 --max-ticks 6000 --device cpu --reward-profile objective-v1 \
    --quiet-engine --json-out "$root/update${update}/hog12.metrics.json" \
    --games-json-out "$root/update${update}/hog12.games.json" \
    > "$root/update${update}/hog12.log" 2>&1
}

typeset -a pids
pids=()
for update in 23 24 29 30; do
  screen_update "$update" &
  pids+=($!)
done
failed=0
for pid in $pids; do
  wait "$pid" || failed=1
done
(( failed == 0 )) || exit 1
print -r -- 'fresh_f3_hazard_anchor_candidates_complete_v1' > "$root/COMPLETE"
