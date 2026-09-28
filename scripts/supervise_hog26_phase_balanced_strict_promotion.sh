#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
corpus_reports=${CORPUS_REPORTS:-reports/hog26_phase_balanced_terminal_cf_v3_seed1175001}
corpus_root=${CORPUS_ROOT:-datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001}
ranker_reports=${RANKER_REPORTS:-reports/hog26_phase_balanced_structured_rankers_v2}
ranker_root=${RANKER_ROOT:-checkpoints/hog26_phase_balanced_structured_rankers_v2}
gameplay="$ranker_reports/gameplay"
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}

mkdir -p "$ranker_reports"

reject() {
  local stage=$1
  printf '%s\n' "$stage" > "$ranker_reports/STRICT_PROMOTION_REJECTED"
}

while [[ ! -e "$corpus_reports/SUPERVISOR_COMPLETE" ]]; do
  if [[ -e "$corpus_reports/local_recovery.exit" ]]; then
    exit_code=$(tr -d '[:space:]' < "$corpus_reports/local_recovery.exit")
    if [[ -n "$exit_code" && "$exit_code" != 0 ]]; then
      printf '%s\n' rankers_preempted_by_corpus_failure \
        > "$ranker_reports/OFFLINE_REJECTED"
      reject rejected_at_corpus
      exit 0
    fi
  fi
  sleep 30
done

if [[ ! -e "$corpus_reports/WEIGHTED_FIRST100_COMPLETE" \
  || -e "$corpus_reports/WEIGHTED_FIRST100_REJECTED" ]]; then
  reject rejected_at_weighted_first100_audit
  exit 0
fi
if ! "$python_bin" - "$corpus_reports/weighted_first100_audit.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if (
    payload.get("schema") != "clasher.weighted_first100_production_audit.v1"
    or payload.get("passed") is not True
    or payload.get("games") != 100
    or payload.get("game_ids") != [0, 99]
    or len(payload.get("observed_archetype_games", {})) != 8
    or float(payload.get("total_variation", 1.0))
    > float(payload.get("maximum_total_variation", 0.0))
):
    raise SystemExit("weighted first100 production audit is invalid")
PY
then
  reject rejected_at_weighted_first100_audit
  exit 0
fi
if ! "$python_bin" - \
  "$corpus_reports/weighted_exact200_sampling_audit.json" \
  "$corpus_reports/weighted_exact200_label_verification.json" <<'PY'
import json
import sys
from pathlib import Path

sampling = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
labels = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
if (
    sampling.get("schema") != "clasher.weighted_exact200_production_audit.v1"
    or sampling.get("passed") is not True
    or sampling.get("games") != 200
    or sampling.get("game_ids") != [0, 199]
    or len(sampling.get("observed_archetype_games", {})) != 8
    or float(sampling.get("total_variation", 1.0))
    > float(sampling.get("maximum_total_variation", 0.0))
    or labels.get("games") != 200
    or labels.get("states", 0) < 1
    or labels.get("tick_coverage", {}).get("maximum") != 5632
):
    raise SystemExit("weighted exact200 production audits are invalid")
PY
then
  reject rejected_at_weighted_exact200_audit
  exit 0
fi
if ! "$python_bin" - \
  "$corpus_reports/weighted_exact400_sampling_audit.json" \
  "$corpus_reports/weighted_exact400_label_verification.json" <<'PY'
import json
import sys
from pathlib import Path

sampling = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
labels = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
if (
    sampling.get("schema") != "clasher.weighted_exact400_production_audit.v1"
    or sampling.get("passed") is not True
    or sampling.get("games") != 400
    or sampling.get("game_ids") != [0, 399]
    or len(sampling.get("observed_archetype_games", {})) != 8
    or float(sampling.get("total_variation", 1.0))
    > float(sampling.get("maximum_total_variation", 0.0))
    or labels.get("games") != 400
    or labels.get("states", 0) < 1
    or labels.get("tick_coverage", {}).get("maximum") != 5632
):
    raise SystemExit("weighted exact400 production audits are invalid")
PY
then
  reject rejected_at_weighted_exact400_audit
  exit 0
fi
if ! env PYTHONPATH=src:. "$python_bin" \
  scripts/audit_weighted_counterfactual_sampling.py \
    --shards "$corpus_root/uniform/train/shards" \
    --opponent-pool datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json \
    --games 500 \
    --maximum-total-variation 0.075 \
    --schema clasher.weighted_exact500_production_audit.v1 \
    --output "$corpus_reports/weighted_exact500_sampling_audit.json"; then
  reject rejected_at_weighted_exact500_audit
  exit 0
fi
if ! env PYTHONPATH=src:. "$python_bin" \
  scripts/audit_weighted_counterfactual_sampling.py \
    --shards "$corpus_root/uniform/validation/shards" \
    --opponent-pool datasets/deck_curriculum_v3_seed1056101/validation.json \
    --games 150 \
    --maximum-total-variation 0.125 \
    --schema clasher.weighted_exact150_validation_audit.v1 \
    --output "$corpus_reports/weighted_exact150_validation_sampling_audit.json"; then
  reject rejected_at_weighted_exact150_validation_audit
  exit 0
fi
if ! "$python_bin" - \
  reports/hog26_heldout_gameplay_sampling_canary_seed1164811.json <<'PY'
import hashlib
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if (
    payload.get("schema")
    != "clasher.hog26_heldout_gameplay_sampling_canary.v1"
    or payload.get("passed") is not True
    or payload.get("promotion_authorized") is not False
):
    raise SystemExit("held-out gameplay sampling canary is invalid")
for entry in (payload["learner_pool"], payload["sampling_source"]):
    path = Path(entry["path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise SystemExit(f"held-out gameplay authority changed: {path}")
required_archetypes = {"graveyard", "lava-hound", "royal-hogs", "x-bow"}
for name, games, seats, minimum_unique in (
    ("screen", 8, {"0": 4, "1": 4}, 7),
    ("quarantine", 16, {"0": 8, "1": 8}, 16),
):
    row = payload[name]
    pool = Path(row["pool_path"])
    if (
        hashlib.sha256(pool.read_bytes()).hexdigest() != row["pool_sha256"]
        or int(row["games"]) != games
        or row["candidate_seats"] != seats
        or set(row["archetype_games"]) != required_archetypes
        or min(int(value) for value in row["archetype_games"].values()) < 1
        or int(row["unique_opponent_decks"]) < minimum_unique
    ):
        raise SystemExit(f"held-out {name} sampling canary is invalid")
if any(int(value) != 0 for value in payload["exact_deck_overlap"].values()):
    raise SystemExit("held-out gameplay pools overlap another frozen split")
PY
then
  reject rejected_at_heldout_gameplay_sampling_canary
  exit 0
fi

if [[ -e "$ranker_reports/DECK_MEMBERSHIP_REJECTED" ]]; then
  reject rejected_at_deck_membership
  exit 0
fi
if [[ ! -e "$ranker_reports/DECK_MEMBERSHIP_COMPLETE" ]]; then
  if ! env PYTHONPATH=src:. "$python_bin" \
    scripts/audit_counterfactual_deck_membership.py \
      --report "$corpus_root/uniform/train.json" \
      --learner-pool training_decks/katacr_hog26_only.json \
      --opponent-pool datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json \
      --forbidden-opponent-pool datasets/deck_curriculum_v3_seed1056101/validation.json \
      --expected-games 500 \
      --output "$ranker_reports/train_deck_membership.json" \
      > "$ranker_reports/train_deck_membership.log" 2>&1; then
    printf '%s\n' rejected_at_train_deck_membership \
      > "$ranker_reports/DECK_MEMBERSHIP_REJECTED"
    reject rejected_at_deck_membership
    exit 0
  fi
  if ! env PYTHONPATH=src:. "$python_bin" \
    scripts/audit_counterfactual_deck_membership.py \
      --report "$corpus_root/uniform/validation.json" \
      --learner-pool training_decks/katacr_hog26_only.json \
      --opponent-pool datasets/deck_curriculum_v3_seed1056101/validation.json \
      --forbidden-opponent-pool datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json \
      --expected-games 150 \
      --output "$ranker_reports/validation_deck_membership.json" \
      > "$ranker_reports/validation_deck_membership.log" 2>&1; then
    printf '%s\n' rejected_at_validation_deck_membership \
      > "$ranker_reports/DECK_MEMBERSHIP_REJECTED"
    reject rejected_at_deck_membership
    exit 0
  fi
  printf '%s\n' hog26_counterfactual_deck_membership_complete_v1 \
    > "$ranker_reports/DECK_MEMBERSHIP_COMPLETE"
fi

if [[ -e "$ranker_reports/OFFLINE_REJECTED" ]]; then
  reject rejected_at_offline_gate
  exit 0
fi
if [[ ! -e "$ranker_reports/OFFLINE_COMPLETE" ]]; then
  if ! bash scripts/run_hog26_phase_balanced_structured_ranker_seeds.sh \
    >> "$ranker_reports/watcher.log" 2>&1; then
    printf '%s\n' hog26_phase_balanced_ranker_fit_or_gate_rejected_v1 \
      > "$ranker_reports/OFFLINE_REJECTED"
    reject rejected_at_offline_gate
    exit 0
  fi
  printf '%s\n' hog26_phase_balanced_ranker_offline_complete_v1 \
    > "$ranker_reports/OFFLINE_COMPLETE"
fi

selected_seed=$($python_bin - "$ranker_reports/offline_gate.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("passed") is not True:
    raise SystemExit("offline gate did not pass")
print(int(payload["selected_seed"]))
PY
)

if [[ -e "$ranker_reports/PHASE_CARD_REJECTED" ]]; then
  reject rejected_at_phase_card_gate
  exit 0
fi
if [[ ! -e "$ranker_reports/PHASE_CARD_COMPLETE" ]]; then
  if ! env PYTHONPATH=src:. "$python_bin" \
    scripts/audit_structured_ranker_phase_card.py \
      --checkpoint "$ranker_root/seed_${selected_seed}.pt" \
      --fit-report "$ranker_reports/seed_${selected_seed}.json" \
      --validation-corpus "$corpus_root/validation.npz" \
      --policy "$policy" \
      --decks-path decks.json \
      --required-card HogRider \
      --minimum-phase-roots 15 \
      --minimum-phase-optimal-rate 0.35 \
      --minimum-phase-improvement-recall 0.35 \
      --minimum-required-card-roots 10 \
      --minimum-required-card-recall 0.35 \
      --output "$ranker_reports/selected_phase_card_gate.json" \
      > "$ranker_reports/selected_phase_card_gate.log" 2>&1; then
    printf '%s\n' rejected_at_selected_phase_card_gate \
      > "$ranker_reports/PHASE_CARD_REJECTED"
    reject rejected_at_phase_card_gate
    exit 0
  fi
  printf '%s\n' hog26_selected_phase_card_gate_complete_v1 \
    > "$ranker_reports/PHASE_CARD_COMPLETE"
fi

if [[ -e "$gameplay/REJECTED" ]]; then
  reject rejected_at_gameplay_gate
  exit 0
fi
if [[ ! -e "$gameplay/COMPLETE" ]]; then
  if ! bash scripts/run_hog26_phase_balanced_structured_gameplay_gate.sh \
    >> "$ranker_reports/gameplay_watcher.log" 2>&1; then
    reject rejected_at_gameplay_runner
    exit 0
  fi
fi
if [[ ! -e "$gameplay/COMPLETE" ]]; then
  reject rejected_at_gameplay_gate
  exit 0
fi

if [[ -e "$gameplay/CARD_UTILIZATION_REJECTED" ]]; then
  reject rejected_at_card_utilization_gate
  exit 0
fi
if [[ ! -e "$gameplay/CARD_UTILIZATION_COMPLETE" ]]; then
  strategies=(
    bridge-pressure
    slow-push
    balanced
    reactive-defense
    spell-control
    split-lane
  )
  screen_inputs=()
  quarantine_inputs=()
  for strategy in "${strategies[@]}"; do
    screen_inputs+=(--input "$gameplay/screen/$strategy.json")
    quarantine_inputs+=(--input "$gameplay/quarantine/$strategy.json")
  done
  if ! env PYTHONPATH=src:. "$python_bin" \
    scripts/audit_action_value_card_utilization.py \
      "${screen_inputs[@]}" \
      --required-card HogRider \
      --minimum-game-usage-rate 0.75 \
      --minimum-strategy-game-usage-rate 0.50 \
      --minimum-plays-per-game 1.0 \
      --minimum-selected-overrides 4 \
      --minimum-override-tiles 2 \
      --maximum-override-tile-share 0.75 \
      --output "$gameplay/screen_card_utilization.json" \
      > "$gameplay/screen_card_utilization.log" 2>&1; then
    printf '%s\n' rejected_at_screen_card_utilization \
      > "$gameplay/CARD_UTILIZATION_REJECTED"
    reject rejected_at_card_utilization_gate
    exit 0
  fi
  if ! env PYTHONPATH=src:. "$python_bin" \
    scripts/audit_action_value_card_utilization.py \
      "${quarantine_inputs[@]}" \
      --required-card HogRider \
      --minimum-game-usage-rate 0.75 \
      --minimum-strategy-game-usage-rate 0.50 \
      --minimum-plays-per-game 1.0 \
      --minimum-selected-overrides 8 \
      --minimum-override-tiles 2 \
      --maximum-override-tile-share 0.75 \
      --output "$gameplay/quarantine_card_utilization.json" \
      > "$gameplay/quarantine_card_utilization.log" 2>&1; then
    printf '%s\n' rejected_at_quarantine_card_utilization \
      > "$gameplay/CARD_UTILIZATION_REJECTED"
    reject rejected_at_card_utilization_gate
    exit 0
  fi
  printf '%s\n' hog26_card_utilization_complete_v1 \
    > "$gameplay/CARD_UTILIZATION_COMPLETE"
fi

printf '%s\n' hog26_phase_balanced_strict_promotion_gates_complete_v1 \
  > "$ranker_reports/STRICT_PROMOTION_GATES_COMPLETE"
