#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

ready_marker=reports/tv_royale_public_v2_final1000_inputs_ready.txt
visual_audit=reports/tv_royale_public_v2_final1000_visual_audit.json
contact_manifest=reports/tv_royale_public_v2_final1000_contact_sheets/manifest.json
split_root=datasets/derived/tv_royale_public_v2_final_split_seed1055801
gate_root=reports/mechanics_slot_final1000_seed1055901
checkpoint_root=checkpoints/mechanics_slot_probe/final1000_seed1055901
candidate_checkpoint="$checkpoint_root/development_candidate.pt"
candidate_evaluation="$gate_root/materialized_candidate_evaluation.json"
candidate_marker="$gate_root/development_candidate_ready.txt"

uv run python - \
  "$ready_marker" \
  "$visual_audit" \
  "$contact_manifest" \
  "$split_root/split_manifest.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

ready_path, audit_path, contact_path, split_path = map(Path, sys.argv[1:])
if ready_path.read_text(encoding="utf-8").strip() != "pretraining_inputs_ready_v1":
    raise SystemExit("final public-state inputs are not ready")
contact_bytes = contact_path.read_bytes()
contact_sha = hashlib.sha256(contact_bytes).hexdigest()
contact = json.loads(contact_bytes)
audit = json.loads(audit_path.read_text(encoding="utf-8"))
if audit.get("schema") != "tv-royale-public-v2-visual-audit-v1":
    raise SystemExit("unsupported final visual-audit schema")
if audit.get("accepted") is not True:
    raise SystemExit("final contact sheets have not passed visual inspection")
if audit.get("contact_manifest_sha256") != contact_sha:
    raise SystemExit("visual audit does not bind the final contact manifest")
if contact.get("schema") != "tv-royale-public-arena-contact-sheets-v1":
    raise SystemExit("unsupported contact-sheet manifest")
if int(contact.get("completed_games_at_render", 0)) != 1000:
    raise SystemExit("contact sheets were not built from the final 1000 games")
if len(contact.get("arenas", ())) != 20 or len(contact.get("sheets", ())) != 8:
    raise SystemExit("final contact-sheet arena/chronology coverage is incomplete")
expected_sheets = {str(Path(row["output"]).resolve()) for row in contact["sheets"]}
reviewed_sheets = {str(Path(path).resolve()) for path in audit.get("reviewed_sheets", ())}
if reviewed_sheets != expected_sheets:
    raise SystemExit("visual audit did not review every final contact sheet")
for row in contact["sheets"]:
    output = Path(row["output"])
    if hashlib.sha256(output.read_bytes()).hexdigest() != row["output_sha256"]:
        raise SystemExit(f"contact sheet changed after rendering: {output}")
split = json.loads(split_path.read_text(encoding="utf-8"))
if int(split.get("source_replays", 0)) != 1000:
    raise SystemExit("final split does not contain 1000 source replays")
invariants = split.get("invariants") or {}
for name in ("replay_overlap", "deck_signature_overlap", "held_out_archetype_train_overlap"):
    if int(invariants.get(name, -1)) != 0:
        raise SystemExit(f"final split invariant failed: {name}")
required = {"train", "validation", "archetype_test", "chronology_test"}
if set(split.get("splits") or {}) != required:
    raise SystemExit("final split partitions are incomplete")
print(json.dumps({"status": "preflight_passed", "contact_manifest_sha256": contact_sha}))
PY

if [[ -e "$gate_root" || -e "$checkpoint_root" ]]; then
  print -u2 -- "refusing to overwrite an existing final mechanics gate"
  exit 1
fi
mkdir -p "$gate_root" "$checkpoint_root"

simulator_validation=datasets/derived/reactive489k_semantic_behavior_curriculum_validation_seed1055404.npz
simulator_heldout=datasets/derived/reactive489k_semantic_behavior_curriculum_heldout_seed1055405.npz
simulator_checkpoint=checkpoints/reactive489k_seed1051101/raw1000_balanced_epoch5_canonical_lanes.pt
public_checkpoint=checkpoints/reactive489k_public_v2_distill_gated_seed1055205/endpoint.pt

source_seeds=(1055410 1055411 1055412)
finetune_seeds=(1055910 1055911 1055912)
finetuned_probes=()
finetune_reports=()
for index in {1..3}; do
  source_seed=${source_seeds[$index]}
  finetune_seed=${finetune_seeds[$index]}
  source_probe="checkpoints/mechanics_slot_probe/v1_linear_seed${source_seed}.pt"
  output_probe="$checkpoint_root/human_disjoint_from_seed${source_seed}_seed${finetune_seed}.pt"
  env PYTHONPATH=src:. uv run python scripts/finetune_mechanics_slot_probe.py \
    --probe-checkpoint "$source_probe" \
    --validation-corpus "$simulator_validation" \
    --heldout-corpus "$simulator_heldout" \
    --human-corpus "$split_root/train.npz" \
    --human-sidecar "$split_root/train_public_state_v2.npz" \
    --human-validation-corpus "$split_root/validation.npz" \
    --human-validation-sidecar "$split_root/validation_public_state_v2.npz" \
    --simulator-checkpoint "$simulator_checkpoint" \
    --public-checkpoint "$public_checkpoint" \
    --decks-path decks.json \
    --seed "$finetune_seed" \
    --epochs 5 \
    --batch-size 64 \
    --learning-rate 1e-4 \
    --min-human-validation-gain 0.01 \
    --max-simulator-regression 0.01 \
    --output "$output_probe" \
    2>&1 | tee "$gate_root/finetune_seed${source_seed}.log"
  finetuned_probes+=("$output_probe")
  finetune_reports+=("${output_probe:r}.json")
done

zero_sweep="$gate_root/zero_shot_validation_sweep.json"
env PYTHONPATH=src:. uv run python scripts/sweep_mechanics_slot_blend.py \
  --probe-checkpoint checkpoints/mechanics_slot_probe/v1_linear_seed1055410.pt \
  --probe-checkpoint checkpoints/mechanics_slot_probe/v1_linear_seed1055411.pt \
  --probe-checkpoint checkpoints/mechanics_slot_probe/v1_linear_seed1055412.pt \
  --validation-corpus "$simulator_validation" \
  --heldout-corpus "$simulator_heldout" \
  --human-corpus "$split_root/validation.npz" \
  --human-sidecar "$split_root/validation_public_state_v2.npz" \
  --simulator-checkpoint "$simulator_checkpoint" \
  --public-checkpoint "$public_checkpoint" \
  --decks-path decks.json \
  --alpha-step 0.005 \
  --max-simulator-disagreement 0.01 \
  --min-human-accuracy-gain 0.01 \
  --output "$zero_sweep" \
  2>&1 | tee "$gate_root/zero_shot_validation_sweep.log"

finetuned_sweep="$gate_root/human_finetuned_validation_sweep.json"
env PYTHONPATH=src:. uv run python scripts/sweep_mechanics_slot_blend.py \
  --probe-checkpoint "${finetuned_probes[1]}" \
  --probe-checkpoint "${finetuned_probes[2]}" \
  --probe-checkpoint "${finetuned_probes[3]}" \
  --validation-corpus "$simulator_validation" \
  --heldout-corpus "$simulator_heldout" \
  --human-corpus "$split_root/validation.npz" \
  --human-sidecar "$split_root/validation_public_state_v2.npz" \
  --simulator-checkpoint "$simulator_checkpoint" \
  --public-checkpoint "$public_checkpoint" \
  --decks-path decks.json \
  --alpha-step 0.005 \
  --max-simulator-disagreement 0.01 \
  --min-human-accuracy-gain 0.01 \
  --output "$finetuned_sweep" \
  2>&1 | tee "$gate_root/human_finetuned_validation_sweep.log"

decision="$gate_root/selection.json"
env PYTHONPATH=src:. uv run python scripts/select_mechanics_slot_candidate.py \
  --zero-shot-sweep "$zero_sweep" \
  --finetuned-sweep "$finetuned_sweep" \
  --finetune-report "${finetune_reports[1]}" \
  --finetune-report "${finetune_reports[2]}" \
  --finetune-report "${finetune_reports[3]}" \
  --output "$decision" \
  2>&1 | tee "$gate_root/selection.log"

if [[ $(jq -r '.status' "$decision") != candidate_selected ]]; then
  print -r -- '{"status":"rejected","reason":"no_cross_seed_safe_candidate"}'
  exit 0
fi

selected_probe=$(jq -r '.selected.median_seed.probe' "$decision")
alpha=$(jq -r '.selected.alpha' "$decision")
base_scale=$(jq -r '.selected.base_scale' "$decision")
query_scale=$(jq -r '.selected.query_scale' "$decision")
env PYTHONPATH=src:. uv run python scripts/add_mechanics_slot_choice_adapter.py \
  --input "$public_checkpoint" \
  --output "$candidate_checkpoint" \
  --decks-path decks.json \
  --query-checkpoint "$selected_probe" \
  --base-scale "$base_scale" \
  --query-scale "$query_scale"

env PYTHONPATH=src:. uv run python scripts/evaluate_mechanics_slot_policy_candidate.py \
  --parent-checkpoint "$public_checkpoint" \
  --candidate-checkpoint "$candidate_checkpoint" \
  --probe-checkpoint "$selected_probe" \
  --alpha "$alpha" \
  --simulator-validation-corpus "$simulator_validation" \
  --simulator-heldout-corpus "$simulator_heldout" \
  --human-validation-corpus "$split_root/validation.npz" \
  --human-validation-sidecar "$split_root/validation_public_state_v2.npz" \
  --human-archetype-corpus "$split_root/archetype_test.npz" \
  --human-archetype-sidecar "$split_root/archetype_test_public_state_v2.npz" \
  --human-chronology-corpus "$split_root/chronology_test.npz" \
  --human-chronology-sidecar "$split_root/chronology_test_public_state_v2.npz" \
  --decks-path decks.json \
  --output "$candidate_evaluation" \
  2>&1 | tee "$gate_root/materialized_candidate_evaluation.log"

candidate_marker_tmp="${candidate_marker}.tmp.$$"
trap 'rm -f -- "$candidate_marker_tmp"' EXIT
print -r -- 'development_candidate_ready_v1' > "$candidate_marker_tmp"
mv -- "$candidate_marker_tmp" "$candidate_marker"
trap - EXIT
print -r -- '{"status":"development_candidate_ready_for_gameplay_gates"}'
