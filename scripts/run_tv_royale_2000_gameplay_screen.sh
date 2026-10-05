#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

while tmux list-sessions -F '#S' 2>/dev/null | rg -Fxq clasher-tv2000-post; do
  sleep 30
done

summary=reports/tv_raw2000_blend_ladder_summary.json
screen_root=reports/evaluations/tv_raw2000_blend_screen
candidate_list=reports/tv_raw2000_gameplay_screen_candidates.txt
development_selected_path=reports/tv_raw2000_gameplay_screen_development_selected.txt
promotion_candidate_path=reports/tv_raw2000_gameplay_screen_promotion_candidate.txt
parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
mkdir -p "$screen_root"
: > "$promotion_candidate_path"

if ! grep -Fqx -- 'postprocess_complete_v1' reports/tv_raw2000_postprocess_success.txt; then
  print -u2 -r -- 'TV Royale postprocess did not publish its success handoff'
  exit 1
fi

PYTHONPATH=src:. uv run python scripts/select_tv_royale_gameplay_candidates.py \
  --summary "$summary" \
  --output "$candidate_list" \
  --safe-alpha 0.0625 \
  --middle-alpha 0.50

if [[ -s reports/tv_raw2000_location_gameplay_candidates.txt ]]; then
  while IFS= read -r checkpoint; do
    [[ -n "$checkpoint" ]] || continue
    if ! grep -Fqx -- "$checkpoint" "$candidate_list"; then
      print -r -- "$checkpoint" >> "$candidate_list"
    fi
  done < reports/tv_raw2000_location_gameplay_candidates.txt
fi

development_status_root="$screen_root/development_status_$$"
max_development_jobs=4
mkdir -p "$development_status_root"

run_development_checkpoint() {
  local checkpoint=$1
  local checkpoint_root=${checkpoint:h:t}
  local checkpoint_name=${checkpoint:t:r}
  local slug="${checkpoint_root}_${checkpoint_name}"
  local output_root="$screen_root/$slug"
  mkdir -p "$output_root"
  nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path datasets/deck_curriculum_v2_seed1040001/validation.json \
    --games 12 \
    --mirror-match \
    --seed 1046501 \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$output_root/validation12.metrics.json" \
    --games-json-out "$output_root/validation12.json" \
    > "$output_root/validation12.log" 2>&1
  nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path datasets/deck_curriculum_v2_seed1040001/heldout.json \
    --games 12 \
    --mirror-match \
    --seed 1046502 \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$output_root/heldout12.metrics.json" \
    --games-json-out "$output_root/heldout12.json" \
    > "$output_root/heldout12.log" 2>&1
  print -r -- complete > "$development_status_root/$slug.ok"
}

development_batch_count=0
while IFS= read -r checkpoint; do
  run_development_checkpoint "$checkpoint" &
  (( development_batch_count += 1 ))
  if (( development_batch_count == max_development_jobs )); then
    wait || true
    development_batch_count=0
  fi
done < "$candidate_list"
wait || true

while IFS= read -r checkpoint; do
  checkpoint_root=${checkpoint:h:t}
  checkpoint_name=${checkpoint:t:r}
  slug="${checkpoint_root}_${checkpoint_name}"
  if [[ ! -f "$development_status_root/$slug.ok" ]]; then
    print -u2 -r -- "development screen worker failed: $checkpoint"
    exit 1
  fi
done < "$candidate_list"

PYTHONPATH=src:. uv run python scripts/select_tv_royale_development_candidate.py \
  --screen-root "$screen_root" \
  --candidate-list "$candidate_list" \
  --selected-out "$development_selected_path" \
  --opponent-checkpoint "$parent" \
  --validation-decks datasets/deck_curriculum_v2_seed1040001/validation.json \
  --heldout-decks datasets/deck_curriculum_v2_seed1040001/heldout.json \
  --safe-alpha 0.0625

if [[ ! -s "$development_selected_path" ]]; then
  print -r -- '{"status":"gameplay_screen_complete","expanded":false}'
  exit 0
fi

IFS= read -r selected < "$development_selected_path"
expanded_root="$screen_root/expanded"
mkdir -p "$expanded_root"
for split in validation heldout; do
  if [[ "$split" == validation ]]; then
    seed=1046601
    decks=datasets/deck_curriculum_v2_seed1040001/validation.json
  else
    seed=1046602
    decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
  fi
  nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$selected" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$decks" \
    --games 48 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$expanded_root/${split}48.metrics.json" \
    --games-json-out "$expanded_root/${split}48.json" \
    > "$expanded_root/${split}48.log" 2>&1
done

uv run python - "$expanded_root" "$selected" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
checkpoint = sys.argv[2]
metrics = [
    json.loads((root / f"{split}48.metrics.json").read_text())["metrics"]
    for split in ("validation", "heldout")
]
payload = {
    "schema_version": 1,
    "checkpoint": checkpoint,
    "wins": sum(int(row["wins"]) for row in metrics),
    "losses": sum(int(row["losses"]) for row in metrics),
    "draws": sum(int(row["draws"]) for row in metrics),
    "crown_difference": sum(
        row["crown_diff_per_game"] * row["games"] for row in metrics
    ),
}
(root / "expanded_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "expanded_gameplay_screen_complete", **payload}))
PY

if ! uv run python - "$expanded_root/expanded_summary.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
raise SystemExit(0 if payload["wins"] > payload["losses"] else 1)
PY
then
  print -r -- '{"status":"gameplay_screen_complete","expanded":true,"priority":false}'
  exit 0
fi

priority_root="$screen_root/priority"
mkdir -p "$priority_root"
nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$selected" \
  --opponent random \
  --games 12 \
  --seed 18501 \
  --device cpu \
  --reward-profile defense-v2 \
  --json-out "$priority_root/broad_random.metrics.json" \
  --games-json-out "$priority_root/broad_random.json" \
  > "$priority_root/broad_random.log" 2>&1
nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$selected" \
  --opponent policy \
  --opponent-checkpoint checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  --games 24 \
  --seed 35101 \
  --device cpu \
  --reward-profile defense-v2 \
  --json-out "$priority_root/safety24.metrics.json" \
  --games-json-out "$priority_root/safety24.json" \
  > "$priority_root/safety24.log" 2>&1
nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
  --checkpoint "$selected" \
  --opponent policy \
  --opponent-checkpoint checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  --games 24 \
  --seed 35301 \
  --device cpu \
  --reward-profile defense-v2 \
  --json-out "$priority_root/human24.metrics.json" \
  --games-json-out "$priority_root/human24.json" \
  > "$priority_root/human24.log" 2>&1

for workload in broad_random safety24 human24; do
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "reports/evaluations/tv_raw1000_spatial_value_rl_u40_safety/${workload}.json" \
    --candidate "$priority_root/${workload}.json" \
    --output "$priority_root/${workload}.compare.json"
done

uv run python - "$priority_root" "$selected" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
checkpoint = sys.argv[2]
comparisons = {
    name: json.loads((root / f"{name}.compare.json").read_text())
    for name in ("broad_random", "safety24", "human24")
}
payload = {
    "schema_version": 1,
    "checkpoint": checkpoint,
    "games": sum(row["games"] for row in comparisons.values()),
    "improvements": sum(row["improvement_count"] for row in comparisons.values()),
    "regressions": sum(row["regression_count"] for row in comparisons.values()),
    "crown_difference_change": sum(
        row["crown_difference_change"] for row in comparisons.values()
    ),
    "passes_strict_no_regression": all(
        row["passes_strict_no_regression"] for row in comparisons.values()
    ),
    "workloads": comparisons,
}
(root / "priority_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "priority_screen_complete", **payload}))
PY

if ! uv run python - "$priority_root/priority_summary.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
raise SystemExit(0 if payload["passes_strict_no_regression"] else 1)
PY
then
  print -r -- '{"status":"gameplay_screen_complete","expanded":true,"priority":true,"full168":false}'
  exit 0
fi

full_root="$screen_root/full168"
mkdir -p "$full_root"

run_full_workload() {
  local name=$1
  shift
  nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$selected" \
    "$@" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$full_root/${name}.metrics.json" \
    --games-json-out "$full_root/${name}.json" \
    > "$full_root/${name}.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "reports/evaluations/tv_raw1000_spatial_value_rl_u40_safety/${name}.json" \
    --candidate "$full_root/${name}.json" \
    --output "$full_root/${name}.compare.json"
}

run_full_workload hog_random \
  --opponent random \
  --sampling-decks-path training_decks/katacr_hog26_only.json \
  --games 12 \
  --seed 18601
run_full_workload direct24 \
  --opponent policy \
  --opponent-checkpoint checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000032_alpha025.pt \
  --games 24 \
  --seed 35201
run_full_workload source36501 \
  --opponent random \
  --games 12 \
  --seed 36501
run_full_workload unseen42501 \
  --opponent random \
  --games 24 \
  --seed 42501
run_full_workload balanced \
  --opponent strategy \
  --opponent-strategy balanced \
  --games 6 \
  --seed 18701
run_full_workload reactive \
  --opponent strategy \
  --opponent-strategy reactive-defense \
  --games 6 \
  --seed 18801
run_full_workload bridge \
  --opponent strategy \
  --opponent-strategy bridge-pressure \
  --games 6 \
  --seed 18901
run_full_workload slow \
  --opponent strategy \
  --opponent-strategy slow-push \
  --games 6 \
  --seed 18951
run_full_workload spell \
  --opponent strategy \
  --opponent-strategy spell-control \
  --games 6 \
  --seed 19001
run_full_workload split \
  --opponent strategy \
  --opponent-strategy split-lane \
  --games 6 \
  --seed 19051

uv run python - "$priority_root" "$full_root" "$selected" <<'PY'
import json
import sys
from pathlib import Path

priority_root = Path(sys.argv[1])
full_root = Path(sys.argv[2])
checkpoint = sys.argv[3]
priority_names = ("broad_random", "safety24", "human24")
remaining_names = (
    "hog_random",
    "direct24",
    "source36501",
    "unseen42501",
    "balanced",
    "reactive",
    "bridge",
    "slow",
    "spell",
    "split",
)
comparisons = {
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
    "games": sum(row["games"] for row in comparisons.values()),
    "improvements": sum(row["improvement_count"] for row in comparisons.values()),
    "regressions": sum(row["regression_count"] for row in comparisons.values()),
    "unchanged": sum(row["unchanged_count"] for row in comparisons.values()),
    "crown_difference_change": sum(
        row["crown_difference_change"] for row in comparisons.values()
    ),
    "passes_strict_no_regression": all(
        row["passes_strict_no_regression"] for row in comparisons.values()
    ),
    "workloads": comparisons,
}
(full_root / "full168_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "full168_screen_complete", **payload}))
PY

if ! uv run python - "$full_root/full168_summary.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
raise SystemExit(0 if payload["passes_strict_no_regression"] else 1)
PY
then
  print -r -- '{"status":"gameplay_screen_complete","expanded":true,"priority":true,"full168":true,"human_meta":false}'
  exit 0
fi

meta_root=datasets/derived/tv_royale_human_meta_gate_2000
human_meta_root="$screen_root/human_meta"
mkdir -p "$human_meta_root"
for view in uniform frequency_weighted; do
  if [[ "$view" == uniform ]]; then
    seed=1046701
  else
    seed=1046702
  fi
  nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python scripts/run_clasher.py eval -- \
    --checkpoint "$selected" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$meta_root/${view}.json" \
    --games 64 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$human_meta_root/${view}64.metrics.json" \
    --games-json-out "$human_meta_root/${view}64.json" \
    > "$human_meta_root/${view}64.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/summarize_deck_generalization.py \
    --games-json "$human_meta_root/${view}64.json" \
    --deck-pool "$meta_root/${view}.json" \
    --output "$human_meta_root/${view}64.by_deck.json"
done

uv run python - "$human_meta_root" "$selected" <<'PY'
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
        row["crown_diff_per_game"] * row["games"] for row in views.values()
    ),
    "passes_human_meta_gate": (
        wins > losses
        and all(int(row["wins"]) >= int(row["losses"]) for row in views.values())
    ),
    "views": views,
}
(root / "summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "human_meta_gate_complete", **payload}))
PY

PYTHONPATH=src:. uv run python scripts/finalize_tv_royale_gameplay_screen.py \
  --screen-root "$screen_root" \
  --development-selected "$development_selected_path" \
  --promotion-candidate "$promotion_candidate_path" \
  --summary-out "$screen_root/final_promotion_summary.json"
