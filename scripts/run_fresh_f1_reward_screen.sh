#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

parent=${CLASHER_REWARD_PARENT:-checkpoints/tv_royale_youtube_causal_seed1067001/oracle_gate_f1_clock1500.pt}
train_decks=${CLASHER_REWARD_TRAIN_DECKS:-datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json}
rehearsal=${CLASHER_REWARD_REHEARSAL:-datasets/derived/fresh_current_client_typed_v1_seed1065401/replay_oracle_mix_152k.npz}
root=${CLASHER_REWARD_ROOT:-reports/fresh_f1_reward_screen_seed1067101}
checkpoint_root=${CLASHER_REWARD_CHECKPOINT_ROOT:-checkpoints/fresh_f1_reward_screen_seed1067101}
seed=${CLASHER_REWARD_SEED:-1067101}
end_update=${CLASHER_REWARD_END_UPDATE:-20}

if [[ -e "$root/train_complete.json" ]]; then
  print -u2 -- "reward screen already completed: $root/train_complete.json"
  exit 1
fi
for required in "$parent" "$train_decks" "$rehearsal"; do
  if [[ ! -f "$required" ]]; then
    print -u2 -- "missing reward-screen input: $required"
    exit 1
  fi
done
mkdir -p "$root" "$checkpoint_root"

env PYTHONPATH=src:. uv run python - "$parent" "$train_decks" "$rehearsal" "$root/preflight.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

import torch

parent, decks, rehearsal, output = map(Path, sys.argv[1:])
checkpoint = torch.load(parent, map_location="cpu", weights_only=False)
config = checkpoint.get("model_config") or {}
required = {
    "num_tokens": 494,
    "card_semantics_version": 3,
    "canonical_lane_globals": True,
    "actor_observation_domain": "causal-frame-v1",
    "memory_kind": "structured",
    "hierarchical_mode_gate_enabled": True,
}
for key, expected in required.items():
    if config.get(key) != expected:
        raise SystemExit(f"parent {key}={config.get(key)!r}, expected {expected!r}")
if int(checkpoint.get("format_version", 0)) != 2:
    raise SystemExit("reward screen requires a format-v2 parent")
if int(checkpoint.get("update", -1)) != 0:
    raise SystemExit("reward screen parent must be the frozen update-0 initializer")
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
payload = {
    "schema": "clasher.fresh_f1_reward_screen_preflight.v1",
    "parent": str(parent.resolve()),
    "parent_sha256": sha(parent),
    "training_decks": str(decks.resolve()),
    "training_decks_sha256": sha(decks),
    "rehearsal_corpus": str(rehearsal.resolve()),
    "rehearsal_corpus_sha256": sha(rehearsal),
    "arms": {
        "legacy": {"reward_shaping_gamma": None, "elixir_leak_penalty_scale": 1.0},
        "gamma": {"reward_shaping_gamma": 0.995, "elixir_leak_penalty_scale": 1.0},
        "gamma_noleak": {"reward_shaping_gamma": 0.995, "elixir_leak_penalty_scale": 0.0},
    },
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, sort_keys=True))
PY

run_arm() {
  local arm=$1
  local shaping_gamma=$2
  local leak_scale=$3
  local checkpoint_dir="$checkpoint_root/$arm"
  local arm_root="$root/$arm"
  local candidate="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$end_update").pt"
  if [[ -e "$candidate" ]]; then
    print -u2 -- "refusing to overwrite existing reward arm: $candidate"
    exit 1
  fi
  mkdir -p "$checkpoint_dir" "$arm_root"

  local gamma_args=()
  if [[ "$shaping_gamma" != legacy ]]; then
    gamma_args+=(--reward-shaping-gamma "$shaping_gamma")
  fi

  env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py train -- \
    --decks-path decks.json \
    --sampling-decks-path "$train_decks" \
    --checkpoint-dir "$checkpoint_dir" \
    --resume-from "$parent" \
    --seed "$seed" \
    --updates "$end_update" \
    --num-envs 64 \
    --actor-workers 12 \
    --actor-threads 1 \
    --rollout-steps 64 \
    --decision-interval 8 \
    --max-ticks 6000 \
    --reward-profile objective-v1 \
    "${gamma_args[@]}" \
    --elixir-leak-penalty-scale "$leak_scale" \
    --opponent-mode league \
    --league-opponent random \
    --league-opponent random \
    --league-opponent random \
    --league-opponent strategy:balanced \
    --league-opponent strategy:reactive-defense \
    --league-opponent strategy:bridge-pressure \
    --league-opponent strategy:slow-push \
    --league-opponent strategy:spell-control \
    --league-opponent strategy:split-lane \
    --league-opponent "$parent" \
    --league-opponent "$parent" \
    --league-opponent "$parent" \
    --engine-fast-path on \
    --device mps \
    --actor-device cpu \
    --learning-rate 1e-5 \
    --reset-optimizer \
    --gamma 0.995 \
    --gae-lambda 0.95 \
    --clip-ratio 0.2 \
    --value-coef 0.5 \
    --entropy-coef 0.01 \
    --anchor-checkpoint "$parent" \
    --anchor-l2-coef 0 \
    --anchor-policy-kl-coef 0.5 \
    --anchor-rehearsal-corpus "$rehearsal" \
    --anchor-rehearsal-sequence-length 8 \
    --anchor-rehearsal-coef 0.2 \
    --anchor-rehearsal-batch-sequences 8 \
    --anchor-rehearsal-loss-component joint \
    --hand-aux-coef 0 \
    --elixir-aux-coef 0 \
    --epochs 2 \
    --sequence-batch-size 2 \
    --target-kl 0.03 \
    --save-every 1 \
    --log-every 1 \
    --no-lr-anneal \
    --quiet-engine \
    2>&1 | tee "$arm_root/train.log"

  if [[ ! -f "$candidate" ]]; then
    print -u2 -- "reward arm did not publish update $end_update: $arm"
    exit 1
  fi
  env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
    --parent "$parent" \
    --checkpoint-dir "$checkpoint_dir" \
    --start-update 1 \
    --end-update "$end_update" \
    --max-approx-kl 0.03 \
    --max-anchor-policy-kl 0.03 \
    --max-clip-fraction 0.25 \
    --output "$arm_root/training_stability.json"
}

run_arm legacy legacy 1.0
run_arm gamma 0.995 1.0
run_arm gamma_noleak 0.995 0.0

env PYTHONPATH=src:. uv run python - "$root" "$checkpoint_root" "$end_update" > "$root/train_complete.json.tmp" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root, checkpoint_root = map(Path, sys.argv[1:3])
update = int(sys.argv[3])
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
payload = {"schema": "clasher.fresh_f1_reward_screen_training.v1", "update": update, "arms": {}}
for arm in ("legacy", "gamma", "gamma_noleak"):
    checkpoint = checkpoint_root / arm / f"policy_v2_update_{update:06d}.pt"
    stability = root / arm / "training_stability.json"
    payload["arms"][arm] = {
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": sha(checkpoint),
        "stability": str(stability.resolve()),
        "stability_sha256": sha(stability),
    }
print(json.dumps(payload, indent=2, sort_keys=True))
PY
mv "$root/train_complete.json.tmp" "$root/train_complete.json"
print -r -- '{"status":"fresh_f1_reward_screen_training_complete"}'
