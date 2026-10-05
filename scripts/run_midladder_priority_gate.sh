#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

challenger_tag=${CHALLENGER_TAG:?CHALLENGER_TAG is required}
screen_root=reports/evaluations/$challenger_tag
candidate_file=$screen_root/development_candidate.txt
priority_root=$screen_root/priority
baseline_root=reports/evaluations/tv_raw1000_spatial_value_rl_u40_safety
parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt

if [[ ! -f "$candidate_file" ]]; then
  print -u2 -r -- "missing direct-screen candidate file: $candidate_file"
  exit 1
fi
candidate=$(<"$candidate_file")
if [[ -z "$candidate" ]]; then
  print -r -- '{"status":"midladder_priority_not_earned"}'
  exit 0
fi
if [[ ! -f "$candidate" ]]; then
  print -u2 -r -- "missing direct-screen candidate checkpoint: $candidate"
  exit 1
fi
mkdir -p "$priority_root"

run_priority() {
  local name=$1
  shift
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$candidate" \
    "$@" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$priority_root/${name}.metrics.json" \
    --games-json-out "$priority_root/${name}.json" \
    > "$priority_root/${name}.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$baseline_root/${name}.json" \
    --candidate "$priority_root/${name}.json" \
    --output "$priority_root/${name}.compare.json"
}

run_priority broad_random \
  --opponent random \
  --games 12 \
  --seed 18501
run_priority safety24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  --games 24 \
  --seed 35101
run_priority human24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  --games 24 \
  --seed 35301

uv run python - "$priority_root" "$candidate" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
checkpoint = sys.argv[2]
workloads = {
    name: json.loads((root / f"{name}.compare.json").read_text())
    for name in ("broad_random", "safety24", "human24")
}
payload = {
    "schema_version": 1,
    "checkpoint": checkpoint,
    "games": sum(int(row["games"]) for row in workloads.values()),
    "improvements": sum(int(row["improvement_count"]) for row in workloads.values()),
    "regressions": sum(int(row["regression_count"]) for row in workloads.values()),
    "unchanged": sum(int(row["unchanged_count"]) for row in workloads.values()),
    "crown_difference_change": sum(
        float(row["crown_difference_change"]) for row in workloads.values()
    ),
    "passes_strict_no_regression": all(
        bool(row["passes_strict_no_regression"]) for row in workloads.values()
    ),
    "workloads": workloads,
}
(root / "priority_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
(root / "priority_candidate.txt").write_text(
    checkpoint + "\n" if payload["passes_strict_no_regression"] else "",
    encoding="utf-8",
)
print(json.dumps({"status": "midladder_priority_complete", **payload}, sort_keys=True))
PY

priority_candidate=$(<"$priority_root/priority_candidate.txt")
if [[ -z "$priority_candidate" ]]; then
  print -r -- '{"status":"midladder_challenger_rejected","stage":"priority"}'
  exit 0
fi

full_root=$screen_root/full168
mkdir -p "$full_root"
run_full() {
  local name=$1
  shift
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$candidate" \
    "$@" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$full_root/${name}.metrics.json" \
    --games-json-out "$full_root/${name}.json" \
    > "$full_root/${name}.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$baseline_root/${name}.json" \
    --candidate "$full_root/${name}.json" \
    --output "$full_root/${name}.compare.json"
}

run_full hog_random \
  --opponent random \
  --sampling-decks-path training_decks/katacr_hog26_only.json \
  --games 12 \
  --seed 18601
run_full direct24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000032_alpha025.pt \
  --games 24 \
  --seed 35201
run_full source36501 \
  --opponent random \
  --games 12 \
  --seed 36501
run_full unseen42501 \
  --opponent random \
  --games 24 \
  --seed 42501
run_full balanced \
  --opponent strategy \
  --opponent-strategy balanced \
  --games 6 \
  --seed 18701
run_full reactive \
  --opponent strategy \
  --opponent-strategy reactive-defense \
  --games 6 \
  --seed 18801
run_full bridge \
  --opponent strategy \
  --opponent-strategy bridge-pressure \
  --games 6 \
  --seed 18901
run_full slow \
  --opponent strategy \
  --opponent-strategy slow-push \
  --games 6 \
  --seed 18951
run_full spell \
  --opponent strategy \
  --opponent-strategy spell-control \
  --games 6 \
  --seed 19001
run_full split \
  --opponent strategy \
  --opponent-strategy split-lane \
  --games 6 \
  --seed 19051

uv run python - "$priority_root" "$full_root" "$candidate" <<'PY'
import json
import sys
from pathlib import Path

priority_root = Path(sys.argv[1])
full_root = Path(sys.argv[2])
checkpoint = sys.argv[3]
priority_names = ("broad_random", "safety24", "human24")
remaining_names = (
    "hog_random", "direct24", "source36501", "unseen42501", "balanced",
    "reactive", "bridge", "slow", "spell", "split",
)
workloads = {
    **{
        name: json.loads((priority_root / f"{name}.compare.json").read_text())
        for name in priority_names
    },
    **{
        name: json.loads((full_root / f"{name}.compare.json").read_text())
        for name in remaining_names
    },
}
payload = {
    "schema_version": 1,
    "checkpoint": checkpoint,
    "games": sum(int(row["games"]) for row in workloads.values()),
    "improvements": sum(int(row["improvement_count"]) for row in workloads.values()),
    "regressions": sum(int(row["regression_count"]) for row in workloads.values()),
    "unchanged": sum(int(row["unchanged_count"]) for row in workloads.values()),
    "crown_difference_change": sum(
        float(row["crown_difference_change"]) for row in workloads.values()
    ),
    "passes_strict_no_regression": all(
        bool(row["passes_strict_no_regression"]) for row in workloads.values()
    ),
    "workloads": workloads,
}
(full_root / "full168_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
(full_root / "full168_candidate.txt").write_text(
    checkpoint + "\n" if payload["passes_strict_no_regression"] else "",
    encoding="utf-8",
)
print(json.dumps({"status": "midladder_full168_complete", **payload}, sort_keys=True))
PY

full_candidate=$(<"$full_root/full168_candidate.txt")
if [[ -z "$full_candidate" ]]; then
  print -r -- '{"status":"midladder_challenger_rejected","stage":"full168"}'
  exit 0
fi

meta_root=datasets/derived/tv_royale_human_meta_gate_2000
human_root=$screen_root/human_meta
mkdir -p "$human_root"
for view in uniform frequency_weighted; do
  if [[ "$view" == uniform ]]; then
    seed=1046701
  else
    seed=1046702
  fi
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$candidate" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$meta_root/${view}.json" \
    --games 64 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$human_root/${view}64.metrics.json" \
    --games-json-out "$human_root/${view}64.json" \
    > "$human_root/${view}64.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/summarize_deck_generalization.py \
    --games-json "$human_root/${view}64.json" \
    --deck-pool "$meta_root/${view}.json" \
    --output "$human_root/${view}64.by_deck.json"
done

uv run python - "$human_root" "$candidate" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
checkpoint = sys.argv[2]
views = {
    view: json.loads((root / f"{view}64.metrics.json").read_text())["metrics"]
    for view in ("uniform", "frequency_weighted")
}
wins = sum(int(row["wins"]) for row in views.values())
losses = sum(int(row["losses"]) for row in views.values())
payload = {
    "schema_version": 1,
    "checkpoint": checkpoint,
    "evaluation_only": True,
    "training_action_labels_used": False,
    "games": sum(int(row["games"]) for row in views.values()),
    "wins": wins,
    "losses": losses,
    "draws": sum(int(row["draws"]) for row in views.values()),
    "crown_difference": sum(
        float(row["crown_diff_per_game"]) * int(row["games"])
        for row in views.values()
    ),
    "passes_human_meta_gate": (
        wins > losses
        and all(int(row["wins"]) >= int(row["losses"]) for row in views.values())
    ),
    "views": views,
}
(root / "summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
(root.parent / "promotion_candidate.txt").write_text(
    checkpoint + "\n" if payload["passes_human_meta_gate"] else "",
    encoding="utf-8",
)
print(json.dumps({"status": "midladder_human_meta_complete", **payload}, sort_keys=True))
PY
