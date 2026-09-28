#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
worker_count=${WORKERS:-64}
train_games=${TRAIN_GAMES:-1400}
validation_games=${VALIDATION_GAMES:-350}
train_game_start=${TRAIN_GAME_START:-0}
validation_game_start=${VALIDATION_GAME_START:-0}
states_per_game=${STATES_PER_GAME:-8}
query_stride=${QUERY_STRIDE:-64}
query_schedule=${QUERY_SCHEDULE:-first-eligible}
include_structured_state=${INCLUDE_STRUCTURED_STATE:-0}
include_action_time_recurrent_state=${INCLUDE_ACTION_TIME_RECURRENT_STATE:-0}
minimum_train_roots=${MINIMUM_TRAIN_ROOTS:-8000}
minimum_validation_roots=${MINIMUM_VALIDATION_ROOTS:-2000}
train_seed=${TRAIN_SEED:-1164601}
validation_seed=${VALIDATION_SEED:-1167601}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
learner_decks=${LEARNER_DECKS:-training_decks/katacr_hog26_only.json}
train_opponent_decks=${TRAIN_OPPONENT_DECKS:-datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json}
validation_opponent_decks=${VALIDATION_OPPONENT_DECKS:-datasets/deck_curriculum_v3_seed1056101/validation.json}
output_root=${OUTPUT_ROOT:-datasets/derived/hog26_parent_terminal_cf_10k_seed1164601}

if ((worker_count < 1)); then
  echo "WORKERS must be positive" >&2
  exit 1
fi
if ((train_games < 1 || validation_games < 1 || states_per_game < 1)); then
  echo "game and state counts must be positive" >&2
  exit 1
fi
if ((query_stride < 1)); then
  echo "QUERY_STRIDE must be positive" >&2
  exit 1
fi
if [[ "$query_schedule" != first-eligible && "$query_schedule" != phase-balanced ]]; then
  echo "QUERY_SCHEDULE must be first-eligible or phase-balanced" >&2
  exit 1
fi
if [[ "$include_structured_state" != 0 && "$include_structured_state" != 1 ]]; then
  echo "INCLUDE_STRUCTURED_STATE must be zero or one" >&2
  exit 1
fi
if [[ "$include_action_time_recurrent_state" != 0 && "$include_action_time_recurrent_state" != 1 ]]; then
  echo "INCLUDE_ACTION_TIME_RECURRENT_STATE must be zero or one" >&2
  exit 1
fi
if [[ "$include_action_time_recurrent_state" == 1 && "$include_structured_state" != 1 ]]; then
  echo "action-time recurrence requires structured state" >&2
  exit 1
fi
if ((train_game_start < 0 || validation_game_start < 0)); then
  echo "game offsets must be nonnegative" >&2
  exit 1
fi
for required in \
  "$policy" \
  "$learner_decks" \
  "$train_opponent_decks" \
  "$validation_opponent_decks" \
  decks.json \
  scripts/collect_terminal_counterfactual_corpus.py \
  scripts/combine_terminal_counterfactual_corpora.py; do
  [[ -f "$required" ]] || {
    echo "missing counterfactual input: $required" >&2
    exit 1
  }
done
[[ ! -e "$output_root/COMPLETE" ]] || {
  echo "refusing completed corpus: $output_root" >&2
  exit 1
}

mkdir -p "$output_root/train/shards" "$output_root/validation/shards"

collect_game() {
  local split=$1
  local seed=$2
  local opponent_decks=$3
  local game=$4
  local padded final_npz final_json final_log partial_root
  local -a structured_args=()
  if [[ "$include_structured_state" == 1 ]]; then
    structured_args+=(--include-structured-state)
  fi
  if [[ "$include_action_time_recurrent_state" == 1 ]]; then
    structured_args+=(--include-action-time-recurrent-state)
  fi
  padded=$(printf '%06d' "$game")
  final_npz="$output_root/$split/shards/game_$padded.npz"
  final_json="$output_root/$split/shards/game_$padded.json"
  final_log="$output_root/$split/shards/game_$padded.log"
  if [[ -f "$final_npz" && -f "$final_json" ]]; then
    return 0
  fi
  if [[ -e "$final_npz" || -e "$final_json" ]]; then
    echo "incomplete published shard: $split/$padded" >&2
    return 1
  fi
  partial_root=$(mktemp -d \
    "$output_root/$split/shards/.partial_${padded}_XXXXXX")
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    "$python_bin" scripts/collect_terminal_counterfactual_corpus.py \
      --policy "$policy" --decks-path decks.json \
      --learner-sampling-decks-path "$learner_decks" \
      --opponent-sampling-decks-path "$opponent_decks" \
      --games 1 --game-offset "$game" --seed "$seed" \
      --states-per-game "$states_per_game" \
      --minimum-tick 256 --query-stride "$query_stride" \
      --query-schedule "$query_schedule" \
      --decision-interval 8 --max-ticks 6000 \
      --max-candidates 6 --locations-per-slot 1 \
      "${structured_args[@]}" \
      --device cpu --torch-threads 1 \
      --output "$partial_root/shard.npz" \
      --report "$partial_root/shard.json" \
      > "$partial_root/shard.log" 2>&1
  "$python_bin" - "$partial_root/shard.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("schema_version") != 2:
    raise SystemExit("unexpected counterfactual shard schema")
if payload.get("best_action_order") != "outcome-crowns-tower-damage-v1":
    raise SystemExit("unexpected counterfactual terminal preference order")
if int(payload.get("states_collected", 0)) < 1:
    raise SystemExit("counterfactual shard contains no roots")
PY
  mv "$partial_root/shard.npz" "$final_npz"
  mv "$partial_root/shard.json" "$final_json"
  mv "$partial_root/shard.log" "$final_log"
  rmdir "$partial_root"
}

collect_split() {
  local split=$1
  local seed=$2
  local opponent_decks=$3
  local game_start=$4
  local games=$5
  local game pid batch_failed active worker lanes
  local -a pids=()
  if help wait 2>/dev/null | grep -q -- '-n'; then
    active=0
    batch_failed=0
    for ((game = game_start; game < game_start + games; game++)); do
      collect_game "$split" "$seed" "$opponent_decks" "$game" &
      active=$((active + 1))
      if ((active >= worker_count)); then
        wait -n || batch_failed=1
        active=$((active - 1))
      fi
    done
    while ((active > 0)); do
      wait -n || batch_failed=1
      active=$((active - 1))
    done
    ((batch_failed == 0)) || return 1
  else
    # macOS ships Bash 3.2 without wait -n. Fixed-size batches strand cores
    # behind each batch's slowest game, so use persistent interleaved lanes.
    # Every game still publishes atomically and completed shards remain
    # resumable across restarts.
    lanes=$worker_count
    ((lanes <= games)) || lanes=$games
    for ((worker = 0; worker < lanes; worker++)); do
      (
        for ((
          game = game_start + worker;
          game < game_start + games;
          game += lanes
        )); do
          collect_game "$split" "$seed" "$opponent_decks" "$game"
        done
      ) &
      pids+=("$!")
    done
    batch_failed=0
    for pid in "${pids[@]}"; do
      wait "$pid" || batch_failed=1
    done
    ((batch_failed == 0)) || return 1
  fi
  env PYTHONPATH=src:. "$python_bin" \
    scripts/combine_terminal_counterfactual_corpora.py \
      --input-root "$output_root/$split/shards" \
      --output "$output_root/$split.npz" \
      --report "$output_root/$split.json" \
      > "$output_root/$split.combine.log" 2>&1
}

collect_split train "$train_seed" "$train_opponent_decks" \
  "$train_game_start" "$train_games"
collect_split validation "$validation_seed" "$validation_opponent_decks" \
  "$validation_game_start" "$validation_games"

"$python_bin" - \
  "$output_root" \
  "$policy" \
  "$learner_decks" \
  "$train_opponent_decks" \
  "$validation_opponent_decks" \
  "$minimum_train_roots" \
  "$minimum_validation_roots" \
  "$states_per_game" \
  "$train_game_start" \
  "$train_games" \
  "$validation_game_start" \
  "$validation_games" \
  "$train_seed" \
  "$validation_seed" \
  "$query_stride" \
  "$include_structured_state" \
  "$include_action_time_recurrent_state" \
  "$query_schedule" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
inputs = [Path(value) for value in sys.argv[2:6]]
minimum_train_roots = int(sys.argv[6])
minimum_validation_roots = int(sys.argv[7])
states_per_game = int(sys.argv[8])
train_game_start = int(sys.argv[9])
train_games = int(sys.argv[10])
validation_game_start = int(sys.argv[11])
validation_games = int(sys.argv[12])
train_seed = int(sys.argv[13])
validation_seed = int(sys.argv[14])
query_stride = int(sys.argv[15])
include_structured_state = bool(int(sys.argv[16]))
include_action_time_recurrent_state = bool(int(sys.argv[17]))
query_schedule = sys.argv[18]
train_payload = json.loads(inputs[2].read_text(encoding="utf-8"))
validation_payload = json.loads(inputs[3].read_text(encoding="utf-8"))
train_decks = train_payload["decks"]
validation_decks = validation_payload["decks"]
train_signatures = {tuple(sorted(deck["cards"])) for deck in train_decks}
validation_signatures = {
    tuple(sorted(deck["cards"])) for deck in validation_decks
}
overlap = train_signatures.intersection(validation_signatures)
if overlap:
    raise SystemExit(f"opponent deck split overlap: {len(overlap)}")
reports = {
    split: json.loads((root / f"{split}.json").read_text(encoding="utf-8"))
    for split in ("train", "validation")
}
expected_structured_contract = (
    "public-actor-v2-action-time-recurrence"
    if include_action_time_recurrent_state
    else "public-actor-v1"
    if include_structured_state
    else None
)
for split, report in reports.items():
    if report.get("structured_state_contract") != expected_structured_contract:
        raise SystemExit(f"{split} structured state contract mismatch")
    if report.get("query_schedule", "first-eligible") != query_schedule:
        raise SystemExit(f"{split} query schedule mismatch")
    if report.get("best_action_order") != "outcome-crowns-tower-damage-v1":
        raise SystemExit(f"{split} terminal preference order mismatch")
observed_caps = {
    split: sorted(
        {
            int(json.loads(path.read_text(encoding="utf-8"))["states_requested"])
            for path in (root / split / "shards").glob("game_*.json")
        }
    )
    for split in ("train", "validation")
}
counts = {
    split: int(report["states_collected"])
    for split, report in reports.items()
}
if counts["train"] < minimum_train_roots:
    raise SystemExit(
        f"train root gate failed: {counts['train']} < {minimum_train_roots}"
    )
if counts["validation"] < minimum_validation_roots:
    raise SystemExit(
        "validation root gate failed: "
        f"{counts['validation']} < {minimum_validation_roots}"
    )
manifest = {
    "schema": "clasher.hog26_terminal_counterfactual_10k.v1",
    "counts": counts,
    "total_roots": sum(counts.values()),
    "inputs": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in inputs
    },
    "train_seed": train_seed,
    "validation_seed": validation_seed,
    "query_stride": query_stride,
    "query_schedule": query_schedule,
    "query_target_ticks": reports["train"].get("query_target_ticks", []),
    "structured_state_contract": expected_structured_contract,
    "launch_states_per_game_cap": states_per_game,
    "observed_states_per_game_caps": observed_caps,
    "games_requested": {
        "train": {"start": train_game_start, "count": train_games},
        "validation": {
            "start": validation_game_start,
            "count": validation_games,
        },
    },
    "split_contract": "opponent-deck-pool-disjoint",
    "candidate_contract": "base-plus-best-legal-per-action-type-max-six",
    "best_action_order": "outcome-crowns-tower-damage-v1",
    "split_input_sha256": {
        split: report["input_sha256"] for split, report in reports.items()
    },
    "continuation_contract": "terminal-strategy-response-exact-python-simulator",
}
(root / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

printf '%s\n' 'hog26_parent_terminal_cf_10k_seed1164601_complete_v1' \
  > "$output_root/COMPLETE"
