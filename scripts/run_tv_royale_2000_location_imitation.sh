#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

run_root=datasets/derived/tv_royale_raw_cascade_1000_v1
type_split_root=datasets/derived/tv_royale_raw_cascade_2000_split_seed1045801
location_split_root=datasets/derived/tv_royale_raw_cascade_2000_locations_split_seed1045801
type_summary=reports/tv_raw2000_blend_ladder_summary.json
parents_file=reports/tv_raw2000_location_imitation_parents.txt
mapping_file=reports/tv_raw2000_location_imitation_candidate_parents.tsv
candidate_file=reports/tv_raw2000_location_gameplay_candidates.txt
summary_out=reports/tv_raw2000_location_blend_ladder_summary.json
checkpoint_root=checkpoints/tv_raw2000_location_imitation
: > "$candidate_file"

# The collector atomically publishes this combined corpus and the parent
# postprocessor verifies its digest before entering this script.  Do not
# recombine over that evidence artifact: CorpusMetadata carries a creation time
# and seed, so a logically equivalent rewrite would invalidate the integrity
# report.  Spatial fitting consumes the replay-disjoint splits below.
PYTHONPATH=src:. uv run python scripts/split_tv_royale_location_sidecars.py \
  --run-manifest "$run_root/run_manifest.json" \
  --split-manifest "$type_split_root/split_manifest.json" \
  --output-dir "$location_split_root" \
  --seed 1045801 \
  --target-games 2000 \
  --required-label-source tv-royale-raw-cascade-location-visual-strict-v3

set +e
PYTHONPATH=src:. uv run python scripts/verify_tv_royale_location_split.py \
  --manifest "$location_split_root/split_manifest.json" \
  --target-games 2000
location_gate_rc=$?
set -e
if [[ "$location_gate_rc" -eq 3 ]]; then
  print -r -- '{"status":"location_imitation_skipped","reason":"strict_location_data_insufficient"}'
  exit 0
elif [[ "$location_gate_rc" -ne 0 ]]; then
  exit "$location_gate_rc"
fi

PYTHONPATH=src:. uv run python - "$type_summary" "$parents_file" <<'PY'
import json
import sys
from pathlib import Path

import torch

from clasher.rl.model import PolicyConfig

summary = json.loads(Path(sys.argv[1]).read_text())
eligible = []
for row in summary.get("candidates", []):
    checkpoint = Path(str(row.get("checkpoint", "")))
    if not (
        row.get("improves_all_splits") is True
        and row.get("defensive_context_safe") is True
        and row.get("two_seed_repeatable") is True
        and checkpoint.name.startswith("alpha")
    ):
        continue
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    alpha = float(payload["interpolation"]["alpha"])
    hierarchy = PolicyConfig.from_dict(
        payload["model_config"]
    ).deterministic_hierarchy
    eligible.append((hierarchy, alpha, float(row["mean_nll_improvement"]), checkpoint))

selected = []
for hierarchy in ("slot", "play-gate"):
    rows = [row for row in eligible if row[0] == hierarchy]
    if not rows:
        continue
    distance = min(abs(row[1] - 0.0625) for row in rows)
    selected.append(
        max((row for row in rows if abs(row[1] - 0.0625) == distance), key=lambda row: row[2])
    )
if not selected:
    raise SystemExit("no safe type-imitation parent available for location training")
Path(sys.argv[2]).write_text(
    "".join(f"{row[3]}\n" for row in selected), encoding="utf-8"
)
print(json.dumps({"status": "location_parents_selected", "parents": [str(row[3]) for row in selected]}))
PY

mkdir -p "$checkpoint_root"
: > "$mapping_file"
while IFS= read -r parent; do
  [[ -n "$parent" ]] || continue
  slug="${parent:h:t}_${parent:t:r}"
  printf '%s\t%s\t0\t0\n' "$parent" "$parent" >> "$mapping_file"
  for location_epochs in 5 20; do
    for location_seed in 1046001 1046002; do
      output_root="$checkpoint_root/${slug}_epoch${location_epochs}_seed${location_seed}"
      endpoint="$output_root/endpoint.pt"
      mkdir -p "$output_root"
      PYTHONPATH=src:. uv run python run_clasher.py imitation -- fit \
        --corpus "$location_split_root/train.npz" \
        --initial-checkpoint "$parent" \
        --output-checkpoint "$endpoint" \
        --control-checkpoint "$output_root/control.pt" \
        --manifest-out "reports/tv_raw2000_location_${slug}_epoch${location_epochs}_seed${location_seed}_manifest.json" \
        --seed "$location_seed" \
        --split-seed 1046000 \
        --epochs "$location_epochs" \
        --batch-size 32 \
        --learning-rate 1e-4 \
        --device mps \
        --sequence-length 1 \
        --trim-entity-padding \
        --left-right-augmentation \
        --placement-actions-only \
        --imitation-objective spatial-v1 \
        --type-loss-coef 0 \
        --location-loss-coef 1 \
        --trainable-prefix tile_projection. \
        --trainable-prefix memory_tile_film. \
        --trainable-prefix tile_decoder. \
        --trainable-prefix tile_key. \
        --trainable-prefix card_query. \
        --trainable-prefix location_bias.
      uv run python - "$parent" "$endpoint" "reports/tv_raw2000_location_${slug}_epoch${location_epochs}_seed${location_seed}_state_dict_audit.json" <<'PY'
import json
import sys
from pathlib import Path

import torch

allowed = (
    "tile_projection.",
    "memory_tile_film.",
    "tile_decoder.",
    "tile_key.",
    "card_query.",
    "location_bias.",
)
before = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
after = torch.load(sys.argv[2], map_location="cpu", weights_only=False)
before_state = before["model_state_dict"]
after_state = after["model_state_dict"]
if before_state.keys() != after_state.keys():
    raise SystemExit("location imitation changed the model state schema")
changed = [
    name
    for name in before_state
    if not torch.equal(before_state[name], after_state[name])
]
unauthorized = [name for name in changed if not name.startswith(allowed)]
payload = {
    "schema_version": 1,
    "parent": str(Path(sys.argv[1]).resolve()),
    "endpoint": str(Path(sys.argv[2]).resolve()),
    "allowed_prefixes": list(allowed),
    "changed_parameters": changed,
    "changed_parameter_count": len(changed),
    "unauthorized_changes": unauthorized,
    "passes": bool(changed) and not unauthorized,
}
Path(sys.argv[3]).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
if not payload["passes"]:
    raise SystemExit("location imitation state-dict audit failed")
print(json.dumps({"status": "location_state_dict_audit_complete", **payload}))
PY
      for blend in 0015625:0.015625 003125:0.03125 00625:0.0625 0125:0.125 025:0.25; do
        label=${blend%%:*}
        alpha=${blend#*:}
        candidate="$output_root/alpha${label}.pt"
        PYTHONPATH=src:. uv run python scripts/interpolate_policy_checkpoints.py \
          --parent "$parent" \
          --candidate "$endpoint" \
          --alpha "$alpha" \
          --output "$candidate"
        printf '%s\t%s\t%s\t%s\n' \
          "$candidate" "$parent" "$location_epochs" "$location_seed" \
          >> "$mapping_file"
      done
    done
  done
done < "$parents_file"

for split in validation archetype_test chronology_test; do
  checkpoints=()
  while IFS=$'\t' read -r checkpoint parent training_epochs training_seed; do
    checkpoints+=(--checkpoint "$checkpoint")
  done < "$mapping_file"
  PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$location_split_root/${split}.npz" \
    "${checkpoints[@]}" \
    --device mps \
    --json-out "reports/tv_raw2000_locations_${split}_blend_ladder.json"
done

PYTHONPATH=src:. uv run python scripts/select_tv_royale_location_candidates.py \
  --mapping-file "$mapping_file" \
  --validation-report reports/tv_raw2000_locations_validation_blend_ladder.json \
  --archetype-report reports/tv_raw2000_locations_archetype_test_blend_ladder.json \
  --chronology-report reports/tv_raw2000_locations_chronology_test_blend_ladder.json \
  --summary-out "$summary_out" \
  --candidate-out "$candidate_file"
