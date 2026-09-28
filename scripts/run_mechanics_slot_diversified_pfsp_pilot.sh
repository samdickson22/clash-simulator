#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

offline_root=${CLASHER_PFSP_OFFLINE_ROOT:-reports/mechanics_slot_final1000_seed1055901}
initializer_root=${CLASHER_PFSP_INITIALIZER_ROOT:-$offline_root/gameplay}
initializer_marker="$initializer_root/rl_initializer_ready.txt"
initializer_marker_value=${CLASHER_PFSP_INITIALIZER_MARKER:-mechanics_rl_initializer_ready_v1}
parent=${CLASHER_PFSP_PARENT:-checkpoints/mechanics_slot_probe/final1000_seed1055901/development_candidate.pt}
tag=${CLASHER_PFSP_TAG:-mechanics_slot_pfsp_seed1056201}
start_update=${CLASHER_PFSP_START_UPDATE:-0}
end_update=${CLASHER_PFSP_END_UPDATE:-4}
train_action_type=${CLASHER_PFSP_TRAIN_ACTION_TYPE:-1}
root="reports/evaluations/$tag"
checkpoint_dir="checkpoints/$tag"
candidate=$(printf '%s/policy_v2_update_%06d.pt' "$checkpoint_dir" "$end_update")
summary="$root/summary.json"
ready_marker="$root/development_candidate_ready.txt"
train_pool=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json
balance_report=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.report.json
exclusion_manifest=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts.manifest.json
pfsp_decks=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.json
pfsp_exclusion_manifest=datasets/deck_curriculum_v3_seed1056101/pfsp_tuning_strict_v2_holdouts.manifest.json
validation_decks=datasets/deck_curriculum_v2_seed1040001/validation.json
heldout_decks=datasets/deck_curriculum_v2_seed1040001/heldout.json
hog_decks=training_decks/katacr_hog26_only.json
win_condition_manifest=datasets/win_condition_utilization_v1/manifest.json
win_condition_root="$root/win_condition_matrix"
split_root=${CLASHER_PFSP_SPLIT_ROOT:-datasets/derived/tv_royale_public_v2_final_split_seed1055801}
rehearsal=datasets/derived/tv_royale_simnative_teacher_spatial_diverse_train_seed1048411.npz

trainable_actor_args=(--trainable-prefix mechanics_slot_choice_query.)
audit_actor_args=(--actor-prefix mechanics_slot_choice_query.)
finalizer_actor_args=(--actor-prefix mechanics_slot_choice_query.)
if [[ "$train_action_type" == 1 ]]; then
  trainable_actor_args=(--trainable-prefix action_type_head. "${trainable_actor_args[@]}")
  audit_actor_args=(--actor-prefix action_type_head. "${audit_actor_args[@]}")
  finalizer_actor_args=(--actor-prefix action_type_head. "${finalizer_actor_args[@]}")
elif [[ "$train_action_type" != 0 ]]; then
  print -u2 -- "CLASHER_PFSP_TRAIN_ACTION_TYPE must be 0 or 1"
  exit 1
fi

if [[ ! -f "$initializer_marker" ]] || \
  [[ $(<"$initializer_marker") != "$initializer_marker_value" ]]; then
  print -u2 -- "mechanics candidate has not passed the gameplay initializer gate"
  exit 1
fi
if [[ -e "$root" || -e "$checkpoint_dir" ]]; then
  print -u2 -- "refusing to overwrite an existing bounded PFSP pilot"
  exit 1
fi
for required in \
  "$parent" \
  "$initializer_root/summary.json" \
  "$train_pool" \
  "$balance_report" \
  "$exclusion_manifest" \
  "$pfsp_decks" \
  "$pfsp_exclusion_manifest" \
  "$validation_decks" \
  "$heldout_decks" \
  "$hog_decks" \
  "$win_condition_manifest" \
  "$rehearsal" \
  checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt
do
  if [[ ! -f "$required" ]]; then
    print -u2 -- "missing PFSP pilot input: $required"
    exit 1
  fi
done
for split in validation archetype_test chronology_test; do
  for suffix in .npz _public_state_v2.npz; do
    required="$split_root/${split}${suffix}"
    if [[ ! -f "$required" ]]; then
      print -u2 -- "missing final human split input: $required"
      exit 1
    fi
  done
done

uv run python - \
  "$parent" \
  "$initializer_root/summary.json" \
  "$train_pool" \
  "$balance_report" \
  "$pfsp_decks" \
  "$pfsp_exclusion_manifest" \
  "$win_condition_manifest" \
  "$validation_decks" \
  "$heldout_decks" \
  "$start_update" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

import torch
from scripts.finalize_win_condition_utilization_matrix import (
    verify_win_condition_manifest,
)

parent, initializer_path, train_pool, balance_path, pfsp_pool, pfsp_manifest_path = map(
    Path, sys.argv[1:7]
)
win_condition_manifest, validation_pool, heldout_pool = map(Path, sys.argv[7:10])
start_update = int(sys.argv[10])
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
initializer = json.loads(initializer_path.read_text())
if initializer.get("rl_initializer_eligible") is not True:
    raise SystemExit("initializer summary is not eligible")
if Path(initializer.get("candidate_checkpoint", "")).resolve() != parent.resolve():
    raise SystemExit("initializer summary identifies another parent")
if initializer.get("candidate_checkpoint_sha256") != sha(parent):
    raise SystemExit("approved initializer checkpoint changed")
checkpoint = torch.load(parent, map_location="cpu", weights_only=False)
if int(checkpoint.get("format_version", 0)) != 2 or int(checkpoint.get("update", -1)) != start_update:
    raise SystemExit("bounded PFSP pilot parent update does not match its declared interval")
config = checkpoint.get("model_config") or {}
if config.get("mechanics_slot_choice_adapter_enabled") is not True:
    raise SystemExit("bounded PFSP pilot requires the mechanics slot adapter")
balance = json.loads(balance_path.read_text())
if Path(balance.get("output", "")).resolve() != train_pool.resolve():
    raise SystemExit("card-balance report identifies another training pool")
if balance.get("output_sha256") != sha(train_pool):
    raise SystemExit("card-balanced training pool changed")
pfsp_manifest = json.loads(pfsp_manifest_path.read_text())
if Path(pfsp_manifest.get("output", "")).resolve() != pfsp_pool.resolve():
    raise SystemExit("PFSP tuning manifest identifies another pool")
if pfsp_manifest.get("output_sha256") != sha(pfsp_pool):
    raise SystemExit("PFSP tuning pool changed")
if int(pfsp_manifest.get("retained_exclusion_overlap", -1)) != 0:
    raise SystemExit("PFSP tuning pool overlaps a frozen evaluation pool")
verify_win_condition_manifest(
    manifest_path=win_condition_manifest,
    validation_pool=validation_pool,
    heldout_pool=heldout_pool,
)
print(json.dumps({"status": "pfsp_pilot_preflight_passed"}))
PY

mkdir -p "$root" "$checkpoint_dir"

env PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
  --checkpoint "$parent" \
  --decks-path decks.json \
  --sampling-decks-path "$pfsp_decks" \
  --games-per-opponent 6 \
  --seed 1056201 \
  --device cpu \
  --reward-profile defense-v2 \
  --json-out "$root/parent_strategy.json" \
  --markdown-out "$root/parent_strategy.md" \
  --quiet-engine \
  > "$root/parent_strategy.log" 2>&1

env PYTHONUNBUFFERED=1 PYTHONPATH=src:. uv run python run_clasher.py train -- \
  --decks-path decks.json \
  --sampling-decks-path "$train_pool" \
  --checkpoint-dir "$checkpoint_dir" \
  --resume-from "$parent" \
  --seed 1056201 \
  --updates "$end_update" \
  --num-envs 64 \
  --actor-workers 12 \
  --actor-threads 1 \
  --rollout-steps 64 \
  --decision-interval 8 \
  --max-ticks 6000 \
  --reward-profile defense-v2 \
  --opponent-mode league \
  --league-opponent random \
  --league-opponent "$parent" \
  --league-opponent "$parent" \
  --league-opponent checkpoints/tv_raw1000_spatial_value_rl_seed1044801/policy_v2_update_000040.pt \
  --pfsp-report "$root/parent_strategy.json" \
  --pfsp-strategy-workers 8 \
  --engine-fast-path on \
  --device mps \
  --actor-device cpu \
  "${trainable_actor_args[@]}" \
  --trainable-prefix critic_encoder. \
  --trainable-prefix value_head. \
  --learning-rate 1e-5 \
  --reset-optimizer \
  --gamma 0.995 \
  --gae-lambda 0.95 \
  --clip-ratio 0.2 \
  --value-coef 0.5 \
  --entropy-coef 0.01 \
  --anchor-checkpoint "$parent" \
  --anchor-l2-coef 0 \
  --anchor-policy-kl-coef 0.2 \
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
  2>&1 | tee "$root/train.log"

if [[ ! -f "$candidate" ]]; then
  print -u2 -- "bounded PFSP pilot did not publish update $end_update"
  exit 1
fi

env PYTHONPATH=src:. uv run python scripts/verify_rl_training_stability.py \
  --parent "$parent" \
  --checkpoint-dir "$checkpoint_dir" \
  --start-update "$((start_update + 1))" \
  --end-update "$end_update" \
  --max-approx-kl 0.03 \
  --max-anchor-policy-kl 0.01 \
  --max-clip-fraction 0.20 \
  --output "$root/training_stability.json"

env PYTHONPATH=src:. uv run python scripts/audit_rl_state_dict_changes.py \
  --before "$parent" \
  --after "$candidate" \
  "${audit_actor_args[@]}" \
  --value-prefix critic_encoder. \
  --value-prefix value_head. \
  --output "$root/state_dict_audit.json"

env PYTHONPATH=src:. uv run python run_clasher.py strategy-benchmark -- \
  --checkpoint "$candidate" \
  --decks-path decks.json \
  --sampling-decks-path "$pfsp_decks" \
  --games-per-opponent 6 \
  --seed 1056201 \
  --device cpu \
  --reward-profile defense-v2 \
  --json-out "$root/candidate_strategy.json" \
  --markdown-out "$root/candidate_strategy.md" \
  --quiet-engine \
  > "$root/candidate_strategy.log" 2>&1

for split in validation heldout; do
  if [[ "$split" == validation ]]; then
    decks=$validation_decks
    seed=1056301
  else
    decks=$heldout_decks
    seed=1056302
  fi
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    --opponent policy \
    --opponent-checkpoint "$parent" \
    --sampling-decks-path "$decks" \
    --games 12 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$root/direct_${split}12.metrics.json" \
    --games-json-out "$root/direct_${split}12.games.json" \
    > "$root/direct_${split}12.log" 2>&1
done

run_candidate_workload() {
  local name=$1
  local games=$2
  local seed=$3
  shift 3
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$candidate" \
    "$@" \
    --games "$games" \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$root/candidate_${name}.metrics.json" \
    --games-json-out "$root/candidate_${name}.games.json" \
    > "$root/candidate_${name}.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$initializer_root/candidate_${name}.games.json" \
    --candidate "$root/candidate_${name}.games.json" \
    --output "$root/${name}.compare.json"
}

run_candidate_workload random12 12 1056010 \
  --opponent random --sampling-decks-path "$heldout_decks" --mirror-match
run_candidate_workload balanced12 12 1056011 \
  --opponent strategy --opponent-strategy balanced \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_candidate_workload reactive12 12 1056012 \
  --opponent strategy --opponent-strategy reactive-defense \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_candidate_workload bridge6 6 1056013 \
  --opponent strategy --opponent-strategy bridge-pressure \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_candidate_workload slow6 6 1056014 \
  --opponent strategy --opponent-strategy slow-push \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_candidate_workload spell6 6 1056015 \
  --opponent strategy --opponent-strategy spell-control \
  --sampling-decks-path "$heldout_decks" --mirror-match
run_candidate_workload split6 6 1056016 \
  --opponent strategy --opponent-strategy split-lane \
  --sampling-decks-path "$heldout_decks" --mirror-match

env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
  --checkpoint "$candidate" \
  --opponent strategy \
  --opponent-strategy balanced \
  --sampling-decks-path "$hog_decks" \
  --games 12 \
  --mirror-match \
  --seed 1056017 \
  --device cpu \
  --reward-profile defense-v2 \
  --quiet-engine \
  --json-out "$root/candidate_hog12.metrics.json" \
  --games-json-out "$root/candidate_hog12.games.json" \
  --decisions-json-out "$root/candidate_hog12.decisions.json" \
  > "$root/candidate_hog12.log" 2>&1
env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
  --baseline "$initializer_root/candidate_hog12.games.json" \
  --candidate "$root/candidate_hog12.games.json" \
  --output "$root/hog12.compare.json"
env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
  --decisions "$root/candidate_hog12.decisions.json" \
  --games "$root/candidate_hog12.games.json" \
  --role primary_building_target \
  --max-zero-use-rate 0.10 \
  --min-window-conversion-rate 0.25 \
  --min-games-per-seat 5 \
  --json-out "$root/candidate_hog12.utilization.json" \
  > "$root/candidate_hog12.utilization.log"

mkdir -p "$win_condition_root"
run_win_condition_utilization() {
  local role=$1
  local checkpoint=$2
  local tag=$3
  local card=$4
  local deck_pool=$5
  local seed=$6
  env PYTHONPATH=src:. uv run python run_clasher.py eval -- \
    --checkpoint "$checkpoint" \
    --opponent strategy \
    --opponent-strategy balanced \
    --sampling-decks-path "$deck_pool" \
    --games 2 \
    --mirror-match \
    --seed "$seed" \
    --device cpu \
    --reward-profile defense-v2 \
    --quiet-engine \
    --json-out "$win_condition_root/${role}_${tag}2.metrics.json" \
    --games-json-out "$win_condition_root/${role}_${tag}2.games.json" \
    --decisions-json-out "$win_condition_root/${role}_${tag}2.decisions.json" \
    > "$win_condition_root/${role}_${tag}2.log" 2>&1
  env PYTHONPATH=src:. uv run python scripts/evaluate_win_condition_utilization.py \
    --decisions "$win_condition_root/${role}_${tag}2.decisions.json" \
    --games "$win_condition_root/${role}_${tag}2.games.json" \
    --card "$card" \
    --max-zero-use-rate 0 \
    --min-window-conversion-rate 0.25 \
    --min-games-per-seat 1 \
    --json-out "$win_condition_root/${role}_${tag}2.utilization.json" \
    > "$win_condition_root/${role}_${tag}2.utilization.log"
}

while IFS=$'\t' read -r index archetype card deck_pool; do
  tag=${archetype//-/_}
  seed=$((1056401 + index))
  run_win_condition_utilization parent "$parent" "$tag" "$card" "$deck_pool" "$seed"
  run_win_condition_utilization candidate "$candidate" "$tag" "$card" "$deck_pool" "$seed"
  env PYTHONPATH=src:. uv run python scripts/compare_policy_game_records.py \
    --baseline "$win_condition_root/parent_${tag}2.games.json" \
    --candidate "$win_condition_root/candidate_${tag}2.games.json" \
    --output "$win_condition_root/${tag}2.compare.json"
done < <(
  uv run python - "$win_condition_manifest" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for index, entry in enumerate(manifest["entries"]):
    print(
        index,
        entry["archetype"],
        entry["designated_card"],
        Path(entry["deck_pool"]).resolve(),
        sep="\t",
    )
PY
)

for split in validation archetype chronology; do
  case "$split" in
    validation) source_name=validation ;;
    archetype) source_name=archetype_test ;;
    chronology) source_name=chronology_test ;;
  esac
  env PYTHONPATH=src:. uv run python scripts/evaluate_recurrent_corpus.py \
    --corpus "$split_root/${source_name}.npz" \
    --public-observation-sidecar "$split_root/${source_name}_public_state_v2.npz" \
    --checkpoint "$parent" \
    --checkpoint "$candidate" \
    --decks-path decks.json \
    --device cpu \
    --json-out "$root/human_${split}.json" \
    > "$root/human_${split}.log"
done

env PYTHONPATH=src:. uv run python scripts/finalize_mechanics_slot_pfsp_pilot.py \
  --root "$root" \
  --initializer-root "$initializer_root" \
  --parent "$parent" \
  --candidate "$candidate" \
  --train-pool "$train_pool" \
  --balance-report "$balance_report" \
  --exclusion-manifest "$exclusion_manifest" \
  --pfsp-sampling-decks "$pfsp_decks" \
  --pfsp-exclusion-manifest "$pfsp_exclusion_manifest" \
  --validation-decks "$validation_decks" \
  --heldout-decks "$heldout_decks" \
  --hog-decks "$hog_decks" \
  --win-condition-root "$win_condition_root" \
  --win-condition-manifest "$win_condition_manifest" \
  --start-update "$start_update" \
  --end-update "$end_update" \
  "${finalizer_actor_args[@]}" \
  --human-validation-corpus "$split_root/validation.npz" \
  --human-validation-sidecar "$split_root/validation_public_state_v2.npz" \
  --human-archetype-corpus "$split_root/archetype_test.npz" \
  --human-archetype-sidecar "$split_root/archetype_test_public_state_v2.npz" \
  --human-chronology-corpus "$split_root/chronology_test.npz" \
  --human-chronology-sidecar "$split_root/chronology_test_public_state_v2.npz" \
  --output "$summary" \
  2>&1 | tee "$root/finalize.log"

if [[ $(jq -r '.development_candidate_eligible' "$summary") != true ]]; then
  print -r -- '{"status":"bounded_pfsp_pilot_rejected"}'
  exit 0
fi
marker_tmp="${ready_marker}.tmp.$$"
trap 'rm -f -- "$marker_tmp"' EXIT
print -r -- 'mechanics_pfsp_development_candidate_ready_v1' > "$marker_tmp"
mv -- "$marker_tmp" "$ready_marker"
trap - EXIT
print -r -- '{"status":"bounded_pfsp_development_candidate_ready"}'
