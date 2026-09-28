#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

if (( $# != 2 )); then
  print -u2 -r -- "usage: $0 CHECKPOINT OUTPUT_ROOT"
  exit 2
fi

checkpoint=$1
output_root=$2
parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
mkdir -p "$output_root"

if [[ ! -f "$checkpoint" ]]; then
  print -u2 -r -- "candidate checkpoint does not exist: $checkpoint"
  exit 1
fi

for split in validation heldout; do
  if [[ "$split" == validation ]]; then
    seed=1046601
    decks=datasets/deck_curriculum_v2_seed1040001/validation.json
  else
    seed=1046602
    decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
  fi
  nice -n 5 env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$decks" \
    --games 48 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --json-out "$output_root/${split}48.metrics.json" \
    --games-json-out "$output_root/${split}48.json" \
    > "$output_root/${split}48.log" 2>&1
done

uv run python - "$output_root" "$checkpoint" "$parent" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
rows = [
    json.loads((root / f"{split}48.metrics.json").read_text())["metrics"]
    for split in ("validation", "heldout")
]
payload = {
    "schema_version": 1,
    "checkpoint": str(Path(sys.argv[2]).resolve()),
    "parent": str(Path(sys.argv[3]).resolve()),
    "games": sum(int(row["games"]) for row in rows),
    "wins": sum(int(row["wins"]) for row in rows),
    "losses": sum(int(row["losses"]) for row in rows),
    "draws": sum(int(row["draws"]) for row in rows),
    "crown_difference": sum(
        row["crown_diff_per_game"] * row["games"] for row in rows
    ),
}
payload["earns_priority_screen"] = payload["wins"] > payload["losses"]
(root / "expanded_summary.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n"
)
print(json.dumps({"status": "expanded_probe_complete", **payload}, sort_keys=True))
PY
