#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
workers=${WORKERS:-10}
output_root=${OUTPUT_ROOT:-datasets/derived/hog26_flat_median_counterfactual_quarantine_seed1191001}
contract=${CONTRACT:-reports/hog26_flat_median_counterfactual_quarantine_contract_v1.json}
policy=checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt
learner_decks=training_decks/katacr_hog26_only.json
opponent_decks=datasets/deck_curriculum_v3_seed1056101/heldout_counterfactual_quarantine_clean_seed1191001.json
games=100
seed=1191001

if ((workers < 1)); then
  echo "WORKERS must be positive" >&2
  exit 1
fi
[[ ! -e "$output_root/COMPLETE" ]] || {
  echo "refusing completed counterfactual quarantine" >&2
  exit 1
}

"$python_bin" - "$contract" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if (
    payload.get("schema")
    != "clasher.hog26_flat_median_counterfactual_quarantine_contract.v1"
    or payload.get("status") != "ready"
    or payload.get("promotion_authorized") is not False
):
    raise SystemExit("unexpected counterfactual quarantine contract")
for entry in payload["sources"].values():
    path = Path(entry["path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise SystemExit(f"counterfactual quarantine authority changed: {path}")
PY

mkdir -p "$output_root/shards"

collect_game() {
  local game=$1
  local padded partial final_npz final_json final_log
  padded=$(printf '%06d' "$game")
  final_npz="$output_root/shards/game_${padded}.npz"
  final_json="$output_root/shards/game_${padded}.json"
  final_log="$output_root/shards/game_${padded}.log"
  if [[ -f "$final_npz" && -f "$final_json" ]]; then
    return 0
  fi
  if [[ -e "$final_npz" || -e "$final_json" ]]; then
    echo "incomplete published quarantine shard: $padded" >&2
    return 1
  fi
  partial=$(mktemp -d "$output_root/shards/.partial_${padded}_XXXXXX")
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    "$python_bin" scripts/collect_terminal_counterfactual_corpus.py \
      --policy "$policy" --decks-path decks.json \
      --learner-sampling-decks-path "$learner_decks" \
      --opponent-sampling-decks-path "$opponent_decks" \
      --games 1 --game-offset "$game" --seed "$seed" \
      --states-per-game 16 --minimum-tick 256 --query-stride 16 \
      --query-schedule phase-balanced --decision-interval 8 --max-ticks 6000 \
      --max-candidates 6 --locations-per-slot 1 \
      --include-structured-state --include-action-time-recurrent-state \
      --device cpu --torch-threads 1 \
      --output "$partial/shard.npz" --report "$partial/shard.json" \
      > "$partial/shard.log" 2>&1
  mv "$partial/shard.npz" "$final_npz"
  mv "$partial/shard.json" "$final_json"
  mv "$partial/shard.log" "$final_log"
  rmdir "$partial"
}

lanes=$workers
((lanes <= games)) || lanes=$games
pids=()
for ((worker = 0; worker < lanes; worker++)); do
  (
    for ((game = worker; game < games; game += lanes)); do
      collect_game "$game"
    done
  ) &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
((failed == 0)) || exit 1

env PYTHONPATH=src:. "$python_bin" \
  scripts/combine_terminal_counterfactual_corpora.py \
    --input-root "$output_root/shards" \
    --output "$output_root/quarantine.npz" \
    --report "$output_root/quarantine.json"

env PYTHONPATH=src:. "$python_bin" - "$output_root" <<'PY'
import json
import sys
from pathlib import Path

from scripts.verify_hog26_structured_terminal_cf_corpus import verify_split

root = Path(sys.argv[1])
result = verify_split(
    root,
    "quarantine",
    100,
    expected_contract="public-actor-v2-action-time-recurrence",
    expected_game_ids=set(range(100)),
)
(root / "verification.json").write_text(
    json.dumps(result, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

env PYTHONPATH=src:. "$python_bin" \
  scripts/audit_weighted_counterfactual_sampling.py \
    --shards "$output_root/shards" --opponent-pool "$opponent_decks" \
    --games 100 --maximum-total-variation 0.15 \
    --schema clasher.hog26_flat_median_counterfactual_quarantine_sampling.v1 \
    --output "$output_root/sampling_audit.json"

printf '%s\n' hog26_flat_median_counterfactual_quarantine_complete_v1 \
  > "$output_root/COMPLETE"
