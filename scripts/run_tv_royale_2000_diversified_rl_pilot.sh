#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

while tmux list-sessions -F '#S' 2>/dev/null | rg -Fxq clasher-tv2000-screen; do
  sleep 30
done

promotion_candidate=reports/tv_raw2000_gameplay_screen_promotion_candidate.txt
screen_root=reports/evaluations/tv_raw2000_blend_screen
pilot_root=reports/evaluations/tv_raw2000_diversified_rl_seed1047001
checkpoint_dir=checkpoints/tv_raw2000_diversified_rl_seed1047001
rl_train_pool=datasets/deck_curriculum_v2_seed1040001/train_without_tv_raw2000_human_meta.json
rl_train_pool_manifest=datasets/deck_curriculum_v2_seed1040001/train_without_tv_raw2000_human_meta.manifest.json
rl_promotion_candidate=reports/tv_raw2000_diversified_rl_promotion_candidate.txt
mkdir -p "$pilot_root"
: > "$rl_promotion_candidate"

if [[ ! -s "$promotion_candidate" ]]; then
  print -r -- '{"status":"rl_pilot_skipped","reason":"no_promotion_candidate"}'
  exit 0
fi

IFS= read -r parent < "$promotion_candidate"
if [[ ! -f "$parent" ]]; then
  print -u2 -r -- "promotion candidate does not exist: $parent"
  exit 1
fi

uv run python - "$parent" <<'PY'
import sys
import torch

payload = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
if int(payload.get("format_version", 0)) != 2:
    raise SystemExit("promotion candidate is not a V2 policy")
if int(payload.get("update", -1)) != 40:
    raise SystemExit(f"expected update-40 promotion candidate, got {payload.get('update')}")
PY

for update in 41 42 43 44; do
  stale_checkpoint="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$update").pt"
  if [[ -e "$stale_checkpoint" ]]; then
    print -u2 -r -- "refusing stale bounded-phase checkpoint: $stale_checkpoint"
    exit 1
  fi
done

PYTHONPATH=src:. uv run python scripts/exclude_deck_pool_signatures.py \
  --source datasets/deck_curriculum_v2_seed1040001/train.json \
  --exclude datasets/derived/tv_royale_human_meta_gate_2000/uniform.json \
  --output "$rl_train_pool" \
  --manifest-out "$rl_train_pool_manifest"

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py train -- \
  --decks-path decks.json \
  --sampling-decks-path "$rl_train_pool" \
  --checkpoint-dir "$checkpoint_dir" \
  --resume-from "$parent" \
  --seed 1047001 \
  --updates 44 \
  --num-envs 64 \
  --actor-workers 12 \
  --actor-threads 1 \
  --rollout-steps 64 \
  --decision-interval 8 \
  --max-ticks 6000 \
  --reward-profile defense-v2 \
  --opponent-mode league \
  --league-opponent strategy:balanced \
  --league-opponent strategy:reactive-defense \
  --league-opponent strategy:bridge-pressure \
  --league-opponent strategy:slow-push \
  --league-opponent strategy:spell-control \
  --league-opponent strategy:split-lane \
  --league-opponent checkpoints/generalized_twentyfourth_robust2_kernel999_lr01_seed15033/policy_v2_repair_step_0050.pt \
  --league-opponent checkpoints/katacr_human_u28_repair3_fresh60701_stage2_seed60702/policy_v2_repair_step_0200.pt \
  --league-opponent "$parent" \
  --league-opponent "$parent" \
  --league-opponent checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt \
  --league-opponent checkpoints/human_safety_tvseq_spatialcore_rl_lr1e6_seed1036008/policy_v2_update_000032_alpha025.pt \
  --engine-fast-path on \
  --device mps \
  --actor-device cpu \
  --trainable-prefix critic_encoder. \
  --trainable-prefix value_head. \
  --trainable-prefix action_type_embedding. \
  --trainable-prefix tile_projection. \
  --trainable-prefix memory_tile_film. \
  --trainable-prefix tile_decoder. \
  --trainable-prefix tile_key. \
  --trainable-prefix card_query. \
  --trainable-prefix location_bias. \
  --learning-rate 1e-6 \
  --reset-optimizer \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --clip-ratio 0.2 \
  --value-coef 0.5 \
  --entropy-coef 0.01 \
  --anchor-checkpoint "$parent" \
  --anchor-l2-coef 0.01 \
  --anchor-policy-kl-coef 0.2 \
  --hand-aux-coef 0 \
  --elixir-aux-coef 0 \
  --epochs 2 \
  --sequence-batch-size 2 \
  --target-kl 0.03 \
  --save-every 1 \
  --log-every 1 \
  --no-lr-anneal \
  --quiet-engine \
  2>&1 | tee reports/tv_raw2000_diversified_rl_seed1047001.log

candidate="$checkpoint_dir/policy_v2_update_000044.pt"
if [[ ! -f "$candidate" ]]; then
  print -u2 -r -- "RL pilot did not publish update 44: $candidate"
  exit 1
fi

PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" \
  --checkpoint-dir "$checkpoint_dir" \
  --start-update 41 \
  --end-update 44 \
  --max-approx-kl 0.03 \
  --max-anchor-policy-kl 0.01 \
  --max-clip-fraction 0.20 \
  --output "$pilot_root/training_stability.json"

PYTHONPATH=src:. uv run python scripts/audit_rl_state_dict_changes.py \
  --before "$parent" \
  --after "$candidate" \
  --value-prefix critic_encoder. \
  --value-prefix value_head. \
  --actor-prefix action_type_embedding. \
  --actor-prefix tile_projection. \
  --actor-prefix memory_tile_film. \
  --actor-prefix tile_decoder. \
  --actor-prefix tile_key. \
  --actor-prefix card_query. \
  --actor-prefix location_bias. \
  --output "$pilot_root/state_dict_audit.json"

for split in validation heldout; do
  if [[ "$split" == validation ]]; then
    seed=1047101
    decks=datasets/deck_curriculum_v2_seed1040001/validation.json
  else
    seed=1047102
    decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
  fi
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$decks" \
    --games 24 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$pilot_root/${split}24.metrics.json" \
    --games-json-out "$pilot_root/${split}24.json" \
    > "$pilot_root/${split}24.log" 2>&1
done

uv run python - "$pilot_root" "$candidate" "$parent" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = [
    json.loads((root / f"{split}24.metrics.json").read_text())["metrics"]
    for split in ("validation", "heldout")
]
wins = sum(int(row["wins"]) for row in rows)
losses = sum(int(row["losses"]) for row in rows)
payload = {
    "schema_version": 1,
    "checkpoint": sys.argv[2],
    "parent": sys.argv[3],
    "games": sum(int(row["games"]) for row in rows),
    "wins": wins,
    "losses": losses,
    "draws": sum(int(row["draws"]) for row in rows),
    "crown_difference": sum(
        row["crown_diff_per_game"] * row["games"] for row in rows
    ),
    "earns_priority_screen": wins > losses,
}
(root / "direct_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "rl_direct_screen_complete", **payload}))
PY

if ! uv run python - "$pilot_root/direct_summary.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
raise SystemExit(0 if payload["earns_priority_screen"] else 1)
PY
then
  print -r -- '{"status":"rl_pilot_rejected","stage":"direct"}'
  exit 0
fi

run_priority() {
  local name=$1
  shift
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    "$@" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$pilot_root/${name}.metrics.json" \
    --games-json-out "$pilot_root/${name}.json" \
    > "$pilot_root/${name}.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$screen_root/priority/${name}.json" \
    --candidate "$pilot_root/${name}.json" \
    --output "$pilot_root/${name}.compare.json"
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

uv run python - "$pilot_root" "$candidate" "$parent" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = {
    name: json.loads((root / f"{name}.compare.json").read_text())
    for name in ("broad_random", "safety24", "human24")
}
payload = {
    "schema_version": 1,
    "checkpoint": sys.argv[2],
    "parent": sys.argv[3],
    "games": sum(row["games"] for row in rows.values()),
    "improvements": sum(row["improvement_count"] for row in rows.values()),
    "regressions": sum(row["regression_count"] for row in rows.values()),
    "crown_difference_change": sum(
        row["crown_difference_change"] for row in rows.values()
    ),
    "passes_strict_no_regression": all(
        row["passes_strict_no_regression"] for row in rows.values()
    ),
    "workloads": rows,
}
(root / "priority_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "rl_priority_screen_complete", **payload}))
PY

if ! uv run python - "$pilot_root/priority_summary.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
raise SystemExit(0 if payload["passes_strict_no_regression"] else 1)
PY
then
  print -r -- '{"status":"rl_pilot_rejected","stage":"priority"}'
  exit 0
fi

run_full() {
  local name=$1
  shift
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    "$@" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$pilot_root/${name}.metrics.json" \
    --games-json-out "$pilot_root/${name}.json" \
    > "$pilot_root/${name}.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$screen_root/full168/${name}.json" \
    --candidate "$pilot_root/${name}.json" \
    --output "$pilot_root/${name}.compare.json"
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

uv run python - "$pilot_root" "$candidate" "$parent" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
names = (
    "broad_random",
    "safety24",
    "human24",
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
rows = {
    name: json.loads((root / f"{name}.compare.json").read_text())
    for name in names
}
payload = {
    "schema_version": 1,
    "checkpoint": sys.argv[2],
    "parent": sys.argv[3],
    "games": sum(row["games"] for row in rows.values()),
    "improvements": sum(row["improvement_count"] for row in rows.values()),
    "regressions": sum(row["regression_count"] for row in rows.values()),
    "unchanged": sum(row["unchanged_count"] for row in rows.values()),
    "crown_difference_change": sum(
        row["crown_difference_change"] for row in rows.values()
    ),
    "passes_strict_no_regression": all(
        row["passes_strict_no_regression"] for row in rows.values()
    ),
    "workloads": rows,
}
(root / "full168_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "rl_full168_screen_complete", **payload}))
PY

if ! uv run python - "$pilot_root/full168_summary.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
raise SystemExit(0 if payload["passes_strict_no_regression"] else 1)
PY
then
  print -r -- '{"status":"rl_pilot_rejected","stage":"full168"}'
  exit 0
fi

meta_root=datasets/derived/tv_royale_human_meta_gate_2000
for view in uniform frequency_weighted; do
  if [[ "$view" == uniform ]]; then
    seed=1047201
  else
    seed=1047202
  fi
  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$meta_root/${view}.json" \
    --games 64 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$pilot_root/human_meta_${view}64.metrics.json" \
    --games-json-out "$pilot_root/human_meta_${view}64.json" \
    > "$pilot_root/human_meta_${view}64.log" 2>&1
  PYTHONPATH=src:. uv run python scripts/summarize_deck_generalization.py \
    --games-json "$pilot_root/human_meta_${view}64.json" \
    --deck-pool "$meta_root/${view}.json" \
    --output "$pilot_root/human_meta_${view}64.by_deck.json"
done

PYTHONPATH=src:. uv run python scripts/finalize_tv_royale_rl_pilot.py \
  --pilot-root "$pilot_root" \
  --candidate "$candidate" \
  --parent "$parent" \
  --deck-exclusion-manifest "$rl_train_pool_manifest" \
  --promotion-candidate "$rl_promotion_candidate" \
  --summary-out "$pilot_root/human_meta_summary.json"

if [[ -s "$rl_promotion_candidate" ]]; then
  print -r -- '{"status":"rl_pilot_promotion_candidate_ready"}'
else
  print -r -- '{"status":"rl_pilot_rejected","stage":"human_meta"}'
fi
