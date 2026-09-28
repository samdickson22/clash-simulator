#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

policy=checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
output_root=datasets/derived/hog26_clean8_terminal_cf_seed1099001

for required in "$policy" "$learner_decks" "$opponent_decks"; do
  [[ -f "$required" ]] || { print -u2 -- "missing counterfactual input: $required"; exit 1; }
done
[[ ! -e "$output_root/COMPLETE" ]] || { print -u2 -- "refusing completed corpus"; exit 1; }

collect_one() {
  local split=$1 seed=$2 game=$3
  local padded root
  padded=$(printf '%03d' "$game")
  root="$output_root/$split/shards/shard_$padded"
  [[ ! -e "$root.npz" && ! -e "$root.json" ]] || return 0
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/collect_terminal_counterfactual_corpus.py \
    --policy "$policy" --decks-path decks.json \
    --learner-sampling-decks-path "$learner_decks" \
    --opponent-sampling-decks-path "$opponent_decks" \
    --games 1 --game-offset "$game" --seed "$seed" --states-per-game 3 \
    --minimum-tick 256 --query-stride 64 --decision-interval 8 --max-ticks 6000 \
    --max-candidates 10 --locations-per-slot 2 --spatially-diverse-locations \
    --device cpu --torch-threads 1 --output "$root.npz" --report "$root.json" \
    > "$root.log" 2>&1
}

collect_split() {
  local split=$1 seed=$2 games=$3
  local batch_start game stop pid
  local -a pids
  mkdir -p "$output_root/$split/shards"
  for (( batch_start = 0; batch_start < games; batch_start += 12 )); do
    stop=$(( batch_start + 12 ))
    (( stop > games )) && stop=$games
    pids=()
    for (( game = batch_start; game < stop; game++ )); do
      collect_one "$split" "$seed" "$game" &
      pids+=($!)
    done
    for pid in $pids; do
      wait "$pid"
    done
  done
  env PYTHONPATH=src:. uv run python scripts/combine_terminal_counterfactual_corpora.py \
    --input-root "$output_root/$split/shards" --output "$output_root/$split.npz" \
    --report "$output_root/$split.json" > "$output_root/$split.combine.log" 2>&1
}

collect_split train 1099001 72
collect_split validation 1101001 36

env OUTPUT_ROOT="$output_root" uv run python - <<'PY'
import json
import os
from collections import Counter
from pathlib import Path

root = Path(os.environ["OUTPUT_ROOT"])
requirements = {
    "train": (500, 50),
    "validation": (250, 25),
}
summary = {}
for split, (minimum_pairs, minimum_games) in requirements.items():
    payload = json.loads((root / f"{split}.json").read_text())
    decisive = [row for row in payload["states"] if row["decisive_improvement"]]
    high_margin_pairs = []
    for row in payload["states"]:
        base_action = int(row["base"]["action"])
        base = next(
            candidate
            for candidate in row["candidates"]
            if int(candidate["action"]) == base_action
        )
        for candidate in row["candidates"]:
            candidate_action = int(candidate["action"])
            if candidate_action == base_action:
                continue
            if (candidate_action < 2304) == (base_action < 2304):
                continue
            outcome_gap = float(candidate["terminal_score"]) - float(
                base["terminal_score"]
            )
            crown_gap = int(candidate["crown_difference"]) - int(
                base["crown_difference"]
            )
            damage_gap = float(candidate["tower_damage_difference"]) - float(
                base["tower_damage_difference"]
            )
            if (
                outcome_gap != 0.0
                or abs(crown_gap) >= 1
                or (crown_gap == 0 and abs(damage_gap) >= 1500.0)
            ):
                high_margin_pairs.append((int(row["game"]), outcome_gap, crown_gap, damage_gap))
    games = Counter(row[0] for row in high_margin_pairs)
    summary[split] = {
        "states": int(payload["array_shapes"]["base_actions"][0]),
        "decisive_improvements": len(decisive),
        "high_margin_placement_wait_pairs": len(high_margin_pairs),
        "games_with_high_margin_pairs": len(games),
    }
    if len(high_margin_pairs) < minimum_pairs or len(games) < minimum_games:
        raise SystemExit(
            f"{split} high-margin yield below gate: {summary[split]} "
            f"requires pairs>={minimum_pairs}, games>={minimum_games}"
        )
(root / "yield_gate.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, sort_keys=True))
PY

for split in train validation; do
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 \
    uv run python scripts/hydrate_terminal_counterfactual_trajectories.py \
    --corpus-report "$output_root/$split.json" --decks-path decks.json \
    --output "$output_root/${split}_trajectories.npz" \
    --report "$output_root/${split}_trajectories.json" \
    --device cpu --torch-threads 1 --decision-interval 8 --max-ticks 6000 \
    > "$output_root/${split}_trajectories.log" 2>&1
done

print -r -- 'hog26_clean8_terminal_cf_seed1099001_complete_v1' \
  > "$output_root/COMPLETE"
