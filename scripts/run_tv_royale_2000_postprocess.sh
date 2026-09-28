#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

postprocess_success=reports/tv_raw2000_postprocess_success.txt
: > "$postprocess_success"

while tmux list-sessions -F '#S' 2>/dev/null | rg -Fxq clasher-tv2000; do
  sleep 30
done

run_root=datasets/derived/tv_royale_raw_cascade_1000_v1
split_root=datasets/derived/tv_royale_raw_cascade_2000_split_seed1045801
meta_root=datasets/derived/tv_royale_human_meta_gate_2000
combined="$run_root/tv_royale_raw_cascade_2000.npz"
manifest="$run_root/run_manifest.json"

uv run python - "$manifest" "$combined" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
combined_path = Path(sys.argv[2])
payload = json.loads(manifest_path.read_text())
if payload.get("completed_games") != 2000:
    raise SystemExit(
        f"raw cascade incomplete: {payload.get('completed_games')}/2000 games"
    )
if not combined_path.is_file():
    raise SystemExit(f"missing combined corpus: {combined_path}")
print(json.dumps({"status": "verified", "completed_games": 2000}))
PY

PYTHONPATH=src:. uv run python scripts/verify_tv_royale_run_integrity.py \
  --run-manifest "$manifest" \
  --scratch-root datasets/external/tv_royale_raw_stream_1000_v1 \
  --target-games 2000 \
  --required-location-label-source tv-royale-raw-cascade-location-visual-strict-v3 \
  --output reports/tv_royale_raw_cascade_2000_integrity.json

PYTHONPATH=src:. uv run python scripts/build_tv_royale_human_meta_gate.py \
  --run-manifest "$manifest" \
  --output-dir "$meta_root" \
  --decks-path decks.json \
  --target-games 2000 \
  --min-replays 2

PYTHONPATH=src:. uv run python scripts/verify_tv_royale_human_meta_gate.py \
  --manifest "$meta_root/manifest.json" \
  --target-games 2000

PYTHONPATH=src:. uv run python scripts/split_tv_royale_raw_cascade.py \
  --run-manifest "$manifest" \
  --output-dir "$split_root" \
  --decks-path decks.json \
  --seed 1045801 \
  --target-games 2000 \
  --reserve-manifest "$meta_root/manifest.json"

uv run python - "$split_root/split_manifest.json" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text())
invariants = manifest.get("invariants", {})
required = {
    "incomplete_visible_hand_rows": 0,
    "visible_hand_filter": "four-known-visible-slots-v1",
    "previous_action_chain": "previous-retained-expert-action-v1",
    "replay_overlap": 0,
    "deck_signature_overlap": 0,
    "held_out_archetype_train_overlap": 0,
}
mismatches = {
    key: {"expected": expected, "actual": invariants.get(key)}
    for key, expected in required.items()
    if invariants.get(key) != expected
}
if int(manifest.get("schema_version", 0)) < 2 or mismatches:
    raise SystemExit(
        f"unsafe TV Royale split manifest: schema={manifest.get('schema_version')}, "
        f"mismatches={mismatches}"
    )
print(json.dumps({"status": "complete_hand_split_verified", **required}))
PY

PYTHONPATH=src:. uv run python scripts/verify_tv_royale_type_split.py \
  --manifest "$split_root/split_manifest.json" \
  --target-games 2000

parent=checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
for seed in 1045901 1045902; do
  checkpoint_root="checkpoints/tv_raw2000_headonly_seed${seed}"
  PYTHONPATH=src:. uv run python run_clasher.py imitation -- fit \
    --corpus "$split_root/train.npz" \
    --initial-checkpoint "$parent" \
    --output-checkpoint "$checkpoint_root/epoch20.pt" \
    --control-checkpoint "$checkpoint_root/control.pt" \
    --manifest-out "reports/tv_raw2000_headonly_seed${seed}_epoch20_manifest.json" \
    --seed "$seed" \
    --split-seed 1045900 \
    --epochs 20 \
    --batch-size 32 \
    --learning-rate 2.5e-4 \
    --device mps \
    --sequence-length 8 \
    --trim-entity-padding \
    --imitation-objective type-head-v1 \
    --location-loss-coef 0 \
    --trainable-prefix action_type_head
done

for seed in 1045901 1045902; do
  checkpoint_root="checkpoints/tv_raw2000_headonly_seed${seed}"
  for blend in 000390625:0.00390625 00078125:0.0078125 0015625:0.015625 003125:0.03125 00625:0.0625 0125:0.125 025:0.25 0375:0.375 050:0.50 0625:0.625 075:0.75; do
    label=${blend%%:*}
    alpha=${blend#*:}
    PYTHONPATH=src:. uv run python scripts/interpolate_policy_checkpoints.py \
      --parent "$parent" \
      --candidate "$checkpoint_root/epoch20.pt" \
      --alpha "$alpha" \
      --output "$checkpoint_root/alpha${label}_slot.pt"
    PYTHONPATH=src:. uv run python scripts/set_policy_deterministic_hierarchy.py \
      --source "$checkpoint_root/alpha${label}_slot.pt" \
      --hierarchy play-gate \
      --output "$checkpoint_root/alpha${label}_playgate.pt"
  done
done

for corpus_name in validation archetype_test chronology_test; do
  for model_name in control seed1045901 seed1045902; do
    case "$model_name" in
      control)
        checkpoint="$parent"
        ;;
      seed1045901)
        checkpoint=checkpoints/tv_raw2000_headonly_seed1045901/epoch20.pt
        ;;
      seed1045902)
        checkpoint=checkpoints/tv_raw2000_headonly_seed1045902/epoch20.pt
        ;;
    esac
    PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
      --corpus "$split_root/${corpus_name}.npz" \
      --checkpoint "$checkpoint" \
      --device mps \
      --json-out "reports/tv_raw2000_${corpus_name}_${model_name}_recurrent.json"
  done
done

for corpus_name in validation archetype_test chronology_test; do
  checkpoints=(--checkpoint "$parent")
  for seed in 1045901 1045902; do
    checkpoint_root="checkpoints/tv_raw2000_headonly_seed${seed}"
    checkpoints+=(--checkpoint "$checkpoint_root/epoch20.pt")
    for label in 000390625 00078125 0015625 003125 00625 0125 025 0375 050 0625 075; do
      checkpoints+=(--checkpoint "$checkpoint_root/alpha${label}_slot.pt")
      checkpoints+=(--checkpoint "$checkpoint_root/alpha${label}_playgate.pt")
    done
  done
  PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$split_root/${corpus_name}.npz" \
    "${checkpoints[@]}" \
    --device mps \
    --json-out "reports/tv_raw2000_${corpus_name}_blend_ladder_recurrent.json"
  PYTHONPATH=src:. uv run python scripts/evaluate_card_frequency_generalization.py \
    --corpus "$split_root/${corpus_name}.npz" \
    --frequency-reference-corpus "$split_root/train.npz" \
    "${checkpoints[@]}" \
    --device mps \
    --json-out "reports/tv_raw2000_${corpus_name}_blend_ladder_card_frequency.json"
  PYTHONPATH=src:. uv run python scripts/evaluate_defensive_context_generalization.py \
    --corpus "$split_root/${corpus_name}.npz" \
    "${checkpoints[@]}" \
    --device mps \
    --json-out "reports/tv_raw2000_${corpus_name}_blend_ladder_defensive_context.json"
done

uv run python - <<'PY'
import json
from pathlib import Path

split_names = ("validation", "archetype_test", "chronology_test")
by_split = {
    split: json.loads(
        Path(f"reports/tv_raw2000_{split}_blend_ladder_recurrent.json").read_text()
    )["results"]
    for split in split_names
}
by_frequency = {
    split: json.loads(
        Path(
            f"reports/tv_raw2000_{split}_blend_ladder_card_frequency.json"
        ).read_text()
    )["results"]
    for split in split_names
}
by_defense = {
    split: json.loads(
        Path(
            f"reports/tv_raw2000_{split}_blend_ladder_defensive_context.json"
        ).read_text()
    )["results"]
    for split in split_names
}
defensive_contexts = ("tower_zone", "own_half_pressure")


def rare_accuracy(row):
    bins = row["card_frequency_bins"]
    names = ("unseen", "one_to_9", "ten_to_99")
    samples = sum(bins[name]["samples"] for name in names)
    if not samples:
        return None
    return sum(
        bins[name]["action_type_accuracy"] * bins[name]["samples"]
        for name in names
    ) / samples


control = {
    split: by_split[split][0]["action_type_nll"] for split in split_names
}
control_rare = {
    split: rare_accuracy(by_frequency[split][0]) for split in split_names
}
control_defense = {
    split: {
        context: by_defense[split][0]["contexts"][context]["action_type_nll"]
        for context in defensive_contexts
    }
    for split in split_names
}
rows = []
for result in by_split[split_names[0]][1:]:
    checkpoint = result["checkpoint"]
    split_results = {
        split: next(
            row for row in by_split[split] if row["checkpoint"] == checkpoint
        )
        for split in split_names
    }
    nll = {
        split: split_results[split]["action_type_nll"] for split in split_names
    }
    frequency_results = {
        split: next(
            row for row in by_frequency[split] if row["checkpoint"] == checkpoint
        )
        for split in split_names
    }
    rare = {split: rare_accuracy(frequency_results[split]) for split in split_names}
    defense_results = {
        split: next(
            row for row in by_defense[split] if row["checkpoint"] == checkpoint
        )
        for split in split_names
    }
    defense_nll = {
        split: {
            context: defense_results[split]["contexts"][context]["action_type_nll"]
            for context in defensive_contexts
        }
        for split in split_names
    }
    defensive_context_safe = all(
        defense_nll[split][context] is not None
        and control_defense[split][context] is not None
        and defense_nll[split][context] <= control_defense[split][context]
        for split in split_names
        for context in defensive_contexts
    )
    rows.append(
        {
            "checkpoint": checkpoint,
            "action_type_nll": nll,
            "nll_improvement": {
                split: control[split] - nll[split] for split in split_names
            },
            "improves_all_splits": all(nll[split] < control[split] for split in split_names),
            "defensive_context_action_type_nll": defense_nll,
            "defensive_context_nll_improvement": {
                split: {
                    context: (
                        None
                        if defense_nll[split][context] is None
                        or control_defense[split][context] is None
                        else control_defense[split][context]
                        - defense_nll[split][context]
                    )
                    for context in defensive_contexts
                }
                for split in split_names
            },
            "defensive_context_safe": defensive_context_safe,
            "mean_nll_improvement": sum(
                control[split] - nll[split] for split in split_names
            )
            / len(split_names),
            "rare_card_action_type_accuracy": rare,
            "rare_card_accuracy_change": {
                split: (
                    None
                    if rare[split] is None or control_rare[split] is None
                    else rare[split] - control_rare[split]
                )
                for split in split_names
            },
        }
    )
payload = {
    "schema_version": 1,
    "control_action_type_nll": control,
    "control_rare_card_action_type_accuracy": control_rare,
    "control_defensive_context_action_type_nll": control_defense,
    "candidates": sorted(
        rows, key=lambda row: row["mean_nll_improvement"], reverse=True
    ),
}
output = Path("reports/tv_raw2000_blend_ladder_summary.json")
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps({"status": "blend_ladder_complete", "summary": str(output)}))
PY

PYTHONPATH=src:. uv run python scripts/annotate_tv_royale_type_repeatability.py \
  --summary reports/tv_raw2000_blend_ladder_summary.json \
  --output reports/tv_raw2000_blend_ladder_summary.json \
  --expected-seed 1045901 \
  --expected-seed 1045902

zsh scripts/run_tv_royale_2000_location_imitation.sh

print -r -- 'postprocess_complete_v1' > "$postprocess_success"
print -r -- '{"status":"postprocess_complete","games":2000}'
