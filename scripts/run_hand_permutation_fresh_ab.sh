#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

structural_session=${CLASHER_STRUCTURAL_EVAL_SESSION:-clasher-structural-epoch2-eval}
structural_summary=${CLASHER_STRUCTURAL_SUMMARY:-reports/human_safety_structural_fresh_seed1011001_epoch2/gameplay/summary.json}
root=reports/human_safety_handperm_fresh_seed1011001
checkpoint_dir=checkpoints/human_safety_handperm_fresh_seed1011001
checkpoint="$checkpoint_dir/epoch1.pt"

while tmux list-sessions -F '#S' 2>/dev/null | rg -Fxq "$structural_session"; do
  sleep 15
done

if [[ ! -f "$structural_summary" ]]; then
  print -u2 -- "structural continuation did not publish its gameplay summary"
  exit 1
fi

if uv run python - "$structural_summary" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1]))
rows = list(summary["workloads"].values())
games = sum(int(row["games"]) for row in rows)
wins = sum(int(row["wins"]) for row in rows)
weighted_noop = sum(
    float(row["candidate_noop_when_playable"]) * int(row["games"])
    for row in rows
) / games
viable = wins >= 20 and weighted_noop < 0.90
print(
    json.dumps(
        {
            "structural_games": games,
            "structural_wins": wins,
            "structural_weighted_playable_noop": weighted_noop,
            "structural_offline_continuation_viable": viable,
        },
        sort_keys=True,
    )
)
raise SystemExit(0 if viable else 1)
PY
then
  print -r -- '{"status":"hand_permutation_arm_skipped","reason":"structural_continuation_viable"}'
  exit 0
fi

if [[ -e "$root" || -e "$checkpoint_dir" ]]; then
  print -u2 -- "refusing to overwrite existing hand-permutation experiment"
  exit 1
fi
mkdir -p "$root" "$checkpoint_dir"

env \
  PYTHONUNBUFFERED=1 \
  PYTHONPATH=src:. \
  PYTORCH_ENABLE_MPS_FALLBACK=1 \
  uv run python scripts/run_clasher.py imitation -- fit \
    --corpus datasets/human_safety_balanced_v1.npz \
    --output-checkpoint "$checkpoint" \
    --control-checkpoint "$checkpoint_dir/random_control.pt" \
    --manifest-out "$root/manifest.json" \
    --seed 1011001 \
    --split-seed 1011001 \
    --epochs 1 \
    --batch-size 32 \
    --learning-rate 0.00025 \
    --validation-fraction 0.2 \
    --device mps \
    --d-model 192 \
    --num-heads 6 \
    --actor-layers 5 \
    --critic-layers 3 \
    --memory-size 384 \
    --encoder-kind attention \
    --decoder-kind attention \
    --memory-kind lstm \
    --card-input-mode hybrid \
    --card-semantics-version 1 \
    --sequence-length 32 \
    --left-right-augmentation \
    --hand-permutation-augmentation \
    --imitation-objective spatial-v1 \
    2>&1 | tee "$root/train.log"

env PYTHONPATH=src:. PYTORCH_ENABLE_MPS_FALLBACK=1 \
  uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus datasets/tv_royale_human_chronological_arena28_v1.npz \
    --checkpoint checkpoints/human_safety_legacy_fresh_seed1011001/epoch1.pt \
    --checkpoint checkpoints/human_safety_structural_fresh_seed1011001/epoch1.pt \
    --checkpoint "$checkpoint" \
    --device mps \
    --json-out "$root/chronology_arena28.json" \
    > "$root/chronology_arena28.log" 2>&1

env \
  CLASHER_EQUIVARIANT_CANDIDATE="$checkpoint" \
  CLASHER_EQUIVARIANT_SCREEN_ROOT="$root/gameplay" \
  scripts/run_equivariant_slot_choice_gameplay_screen.sh \
  > "$root/gameplay_screen.log" 2>&1

env PYTHONPATH=src:. \
  uv run python scripts/audit_policy_hand_slot_robustness.py \
    --checkpoint "$checkpoint" \
    --sampling-decks-path training_decks/katacr_hog26_only.json \
    --designated-card HogRider \
    --opponent-strategy balanced \
    --games 12 \
    --seed 1056902 \
    --reward-profile defense-v2 \
    --json-out "$root/hand_slot_robustness_hog12.json" \
    > "$root/hand_slot_robustness_hog12.log" 2>&1

print -r -- '{"status":"hand_permutation_fresh_ab_complete"}'
