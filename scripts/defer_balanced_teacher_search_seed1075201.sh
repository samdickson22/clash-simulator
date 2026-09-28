#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

training_endpoint=checkpoints/hog26_strategy_majority_seed1075001/policy_v2_update_000146.pt
output=reports/hog26_balanced_teacher_search_seed1075201/search.json

while [[ ! -f "$training_endpoint" ]]; do
  sleep 30
done
before=$(stat -f%z "$training_endpoint")
sleep 5
after=$(stat -f%z "$training_endpoint")
[[ "$before" == "$after" ]] || { print -u2 -- "training endpoint was not stable"; exit 1; }
[[ ! -e "$output" ]] || { print -u2 -- "refusing existing teacher search"; exit 1; }

mkdir -p "${output:h}"
nice -n 10 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. OMP_NUM_THREADS=1 \
  uv run python scripts/search_balanced_strategy_teacher.py \
  --decks-path decks.json \
  --learner-decks-path training_decks/katacr_hog26_only.json \
  --search-decks-path datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json \
  --validation-decks-path datasets/deck_curriculum_v3_seed1056101/validation.json \
  --candidates 32 --finalists 6 --search-games-per-matchup 2 \
  --validation-games-per-matchup 4 --workers 6 --seed 1075201 \
  --json-out "$output" > "${output:h}/search.log" 2>&1
print -r -- 'hog26_balanced_teacher_search_seed1075201_complete_v1' > "${output:h}/COMPLETE"
