#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

trainer_session=${TRAINER_SESSION:-clasher-midladder-clean}
challenger_tag=${CHALLENGER_TAG:-midladder_clean_history4_league_seed1048701}
end_update=${CHALLENGER_END_UPDATE:-104}
train_log=reports/${challenger_tag}.log

while tmux list-sessions -F '#S' 2>/dev/null | rg -qx "$trainer_session"; do
  if [[ -f "$train_log" ]] && rg -q 'update=[0-9]+ .* kl_stop=1(?: |$)' "$train_log"; then
    print -u2 -r -- "clean challenger hit KL early stop; terminating $trainer_session"
    tmux kill-session -t "$trainer_session"
    exit 1
  fi
  sleep 30
done

parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
checkpoint_dir=checkpoints/$challenger_tag
report_root=reports/evaluations/$challenger_tag
mkdir -p "$report_root"

endpoint="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$end_update").pt"
if [[ ! -f "$endpoint" ]]; then
  print -u2 -r -- "clean challenger exited without endpoint: $endpoint"
  exit 1
fi

PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" \
  --checkpoint-dir "$checkpoint_dir" \
  --start-update 41 \
  --end-update "$end_update" \
  --max-approx-kl 0.03 \
  --max-anchor-policy-kl 0.03 \
  --max-clip-fraction 0.20 \
  --output "$report_root/training_stability.json"

PYTHONPATH=src:. uv run python scripts/audit_rl_state_dict_changes.py \
  --before "$parent" \
  --after "$endpoint" \
  --actor-prefix actor_encoder. \
  --actor-prefix memory. \
  --actor-prefix public_history_ \
  --actor-prefix action_type_embedding. \
  --actor-prefix action_type_head. \
  --actor-prefix tile_projection. \
  --actor-prefix memory_tile_film. \
  --actor-prefix tile_decoder. \
  --actor-prefix tile_key. \
  --actor-prefix card_query. \
  --actor-prefix location_bias. \
  --allow-added-prefix public_history_ \
  --value-prefix critic_encoder. \
  --value-prefix value_head. \
  --output "$report_root/state_dict_audit.json"

for update in 56 72 88 104; do
  candidate="$checkpoint_dir/policy_v2_update_$(printf '%06d' "$update").pt"
  candidate_root="$report_root/u${update}_direct24"
  mkdir -p "$candidate_root"
  for split in validation heldout; do
    if [[ "$split" == validation ]]; then
      pool=datasets/deck_curriculum_v2_seed1040001/validation.json
      seed=1048711
    else
      pool=datasets/deck_curriculum_v2_seed1040001/heldout.json
      seed=1048712
    fi
    uv run python scripts/run_clasher.py eval -- \
      --checkpoint "$candidate" \
      --opponent policy \
      --opponent-checkpoint "$parent" \
      --sampling-decks-path "$pool" \
      --games 12 \
      --mirror-match \
      --seed "$seed" \
      --device mps \
      --reward-profile defense-v2 \
      --quiet-engine \
      --json-out "$candidate_root/${split}.metrics.json" \
      --games-json-out "$candidate_root/${split}.games.json"
  done
done

uv run python - "$checkpoint_dir" "$report_root" <<'PY'
import json
import sys
from pathlib import Path

checkpoint_dir = Path(sys.argv[1])
root = Path(sys.argv[2])
rows = []
for update in (56, 72, 88, 104):
    metrics = [
        json.loads((root / f"u{update}_direct24/{split}.metrics.json").read_text())["metrics"]
        for split in ("validation", "heldout")
    ]
    rows.append(
        {
            "update": update,
            "checkpoint": str(checkpoint_dir / f"policy_v2_update_{update:06d}.pt"),
            "games": sum(int(row["games"]) for row in metrics),
            "wins": sum(int(row["wins"]) for row in metrics),
            "losses": sum(int(row["losses"]) for row in metrics),
            "draws": sum(int(row["draws"]) for row in metrics),
            "crown_difference": sum(
                float(row["crown_diff_per_game"]) * int(row["games"])
                for row in metrics
            ),
        }
    )

best = max(rows, key=lambda row: (row["wins"] - row["losses"], row["crown_difference"], -row["update"]))
payload = {
    "schema_version": 1,
    "parent": "checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt",
    "rows": rows,
    "best": best,
    "earns_priority_screen": best["wins"] > best["losses"],
}
(root / "direct_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
candidate_out = root / "development_candidate.txt"
candidate_out.write_text(
    best["checkpoint"] + "\n" if payload["earns_priority_screen"] else "",
    encoding="utf-8",
)
print(json.dumps(payload, sort_keys=True))
PY

env CHALLENGER_TAG="$challenger_tag" zsh scripts/run_midladder_priority_gate.sh
