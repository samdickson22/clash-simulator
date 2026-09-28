#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

output_root=${OUTPUT_ROOT:-datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001}
contract=${CONTRACT:-reports/hog26_phase_balanced_terminal_cf_contract_v1.json}
python_bin=${PYTHON_BIN:-python}
train_screen=${TRAIN_SCREEN:-reports/hog26_overtime_screen_train_weighted_v2_seed1175001/manifest.json}
validation_screen=${VALIDATION_SCREEN:-reports/hog26_overtime_screen_validation_weighted_v2_seed1181001/manifest.json}

[[ -f "$contract" ]] || {
  echo "missing frozen phase-balanced contract: $contract" >&2
  exit 1
}
[[ ! -e "$output_root/PHASE_BALANCED_COMPLETE" ]] || {
  echo "refusing completed phase-balanced corpus: $output_root" >&2
  exit 1
}
for screen in "$train_screen" "$validation_screen"; do
  [[ -f "$screen" ]] || {
    echo "missing frozen overtime screen: $screen" >&2
    exit 1
  }
done

"$python_bin" - "$contract" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if contract.get("schema") != "clasher.hog26_phase_balanced_terminal_cf_contract.v1":
    raise SystemExit("unexpected phase-balanced collection contract")
authorities = [
    contract["policy"],
    *contract["deck_authority"].values(),
    contract["collection"]["schedule_source"],
    contract["required_state_contract"]["snapshot_source"],
    *contract["pipeline_sources"].values(),
]
for authority in authorities:
    if not isinstance(authority, dict) or "path" not in authority:
        continue
    path = Path(authority["path"])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != authority["sha256"]:
        raise SystemExit(f"phase-balanced source authority changed: {path}")
launch = contract["launch_condition"]
weighted = Path(launch["weighted_sampling_canary_path"])
if hashlib.sha256(weighted.read_bytes()).hexdigest() != launch[
    "weighted_sampling_canary_sha256"
]:
    raise SystemExit("weighted sampling canary authority changed")
PY

if [[ ! -e "$output_root/uniform/COMPLETE" ]]; then
  env \
    WORKERS="${WORKERS:-64}" \
    TRAIN_GAMES=500 \
    VALIDATION_GAMES=150 \
    STATES_PER_GAME=16 \
    QUERY_STRIDE=16 \
    QUERY_SCHEDULE=phase-balanced \
    INCLUDE_STRUCTURED_STATE=1 \
    INCLUDE_ACTION_TIME_RECURRENT_STATE=1 \
    MINIMUM_TRAIN_ROOTS=3500 \
    MINIMUM_VALIDATION_ROOTS=950 \
    TRAIN_SEED=1175001 \
    VALIDATION_SEED=1181001 \
    OUTPUT_ROOT="$output_root/uniform" \
    PYTHON_BIN="$python_bin" \
    scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh
else
  env PYTHONPATH=src:. "$python_bin" - \
    "$output_root/uniform" "$contract" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

from scripts.verify_hog26_structured_terminal_cf_corpus import verify_split

root = Path(sys.argv[1])
contract = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
for split, games, opponent_key in (
    ("train", 500, "train_opponents"),
    ("validation", 150, "validation_opponents"),
):
    verify_split(
        root,
        split,
        games,
        expected_contract="public-actor-v2-action-time-recurrence",
        expected_game_ids=set(range(games)),
    )
    report = json.loads((root / f"{split}.json").read_text(encoding="utf-8"))
    expected = {
        "policy": contract["policy"]["sha256"],
        "decks": contract["deck_authority"]["runtime_decks"]["sha256"],
        "outcome": None,
        "sampling_decks": None,
        "learner_sampling_decks": contract["deck_authority"]["learner"]["sha256"],
        "opponent_sampling_decks": contract["deck_authority"][opponent_key]["sha256"],
    }
    if report.get("input_sha256") != expected:
        raise SystemExit(f"resumed uniform {split} input authority changed")
manifest = root / "manifest.json"
if not manifest.is_file() or not (root / "train.npz").is_file() or not (
    root / "validation.npz"
).is_file():
    raise SystemExit("resumed uniform corpus is incomplete")
print(
    json.dumps(
        {
            "uniform_manifest_sha256": hashlib.sha256(
                manifest.read_bytes()
            ).hexdigest(),
            "status": "verified-resume",
        },
        sort_keys=True,
    )
)
PY
fi

env \
  WORKERS="${WORKERS:-64}" \
  SCREEN_MANIFEST="$train_screen" \
  OPPONENT_DECKS=datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json \
  SELECTED_COUNT=60 \
  SEED=1175001 \
  OUTPUT_ROOT="$output_root/overtime_train" \
  PYTHON_BIN="$python_bin" \
  scripts/run_hog26_overtime_supplement.sh

env \
  WORKERS="${WORKERS:-64}" \
  SCREEN_MANIFEST="$validation_screen" \
  OPPONENT_DECKS=datasets/deck_curriculum_v3_seed1056101/validation.json \
  SELECTED_COUNT=20 \
  SEED=1181001 \
  OUTPUT_ROOT="$output_root/overtime_validation" \
  PYTHON_BIN="$python_bin" \
  scripts/run_hog26_overtime_supplement.sh

for split in train validation; do
  supplement=overtime_train
  [[ "$split" == validation ]] && supplement=overtime_validation
  env PYTHONPATH=src:. "$python_bin" \
    scripts/merge_phase_stratified_counterfactual_corpora.py \
      --uniform-npz "$output_root/uniform/$split.npz" \
      --uniform-report "$output_root/uniform/$split.json" \
      --overtime-npz "$output_root/$supplement/combined.npz" \
      --overtime-report "$output_root/$supplement/combined.json" \
      --output "$output_root/$split.npz" \
      --report "$output_root/$split.json"
done

"$python_bin" - "$output_root" "$train_screen" "$validation_screen" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
screens = [Path(value) for value in sys.argv[2:]]
screen_payloads = [json.loads(path.read_text()) for path in screens]
uniform = json.loads((root / "uniform" / "manifest.json").read_text())
reports = {
    split: json.loads((root / f"{split}.json").read_text())
    for split in ("train", "validation")
}
uniform["schema"] = "clasher.hog26_phase_stratified_terminal_cf.v1"
uniform["structured_state_contract"] = "public-actor-v2-action-time-recurrence"
uniform["query_schedule"] = "phase-stratified-uniform-plus-screened-overtime-v1"
uniform["query_target_ticks"] = reports["train"]["query_target_ticks"]
uniform["query_target_ticks_by_source"] = reports["train"][
    "query_target_ticks_by_source"
]
uniform["counts"] = {
    split: int(report["states_collected"])
    for split, report in reports.items()
}
uniform["total_roots"] = sum(uniform["counts"].values())
uniform["games_requested"] = {
    "train": {"uniform": 500, "screened_overtime": 60},
    "validation": {"uniform": 150, "screened_overtime": 20},
}
uniform["overtime_screen_inputs"] = {
    str(path): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in screens
}
uniform["screened_overtime_game_ids"] = {
    "train": [int(value) for value in screen_payloads[0]["selected_games"][:60]],
    "validation": [
        int(value) for value in screen_payloads[1]["selected_games"][:20]
    ],
}
(root / "manifest.json").write_text(
    json.dumps(uniform, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

env PYTHONPATH=src:. "$python_bin" \
  scripts/verify_hog26_phase_balanced_terminal_cf_corpus.py \
    --root "$output_root" \
    --contract "$contract" \
    --output "$output_root/phase_balanced_verification.json"

printf '%s\n' 'hog26_phase_balanced_terminal_cf_v3_seed1175001_complete_v1' \
  > "$output_root/PHASE_BALANCED_COMPLETE"
