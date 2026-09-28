#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

corpus_root=${CORPUS_ROOT:-datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
device=${DEVICE:-cpu}
output_root=${OUTPUT_ROOT:-checkpoints/hog26_phase_balanced_structured_rankers_v2}
report_root=${REPORT_ROOT:-reports/hog26_phase_balanced_structured_rankers_v2}
contract=${CONTRACT:-reports/hog26_phase_balanced_structured_ranker_contract_v2.json}

[[ "$device" == cpu ]] || {
  echo "phase-balanced structured rankers require the certified CPU fit path" >&2
  exit 1
}

for required in \
  "$corpus_root/PHASE_BALANCED_COMPLETE" \
  "$corpus_root/train.npz" \
  "$corpus_root/train.json" \
  "$corpus_root/validation.npz" \
  "$corpus_root/validation.json" \
  "$corpus_root/manifest.json" \
  "$contract" \
  "$policy"; do
  [[ -f "$required" ]] || {
    echo "missing phase-balanced ranker input: $required" >&2
    exit 1
  }
done

"$python_bin" - "$contract" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

contract = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if contract.get("schema") != (
    "clasher.hog26_phase_balanced_structured_ranker_contract.v2"
):
    raise SystemExit("unexpected phase-balanced ranker contract")
if contract.get("promotion_authorized") is not False:
    raise SystemExit("ranker fit contract cannot authorize promotion")
for entry in contract["sources"].values():
    path = Path(entry["path"])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != entry["sha256"]:
        raise SystemExit(f"phase-balanced ranker source changed: {path}")
for entry in (contract["source_policy"], {
    "path": contract["corpus"]["collection_contract_path"],
    "sha256": contract["corpus"]["collection_contract_sha256"],
}):
    path = Path(entry["path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        raise SystemExit(f"phase-balanced ranker authority changed: {path}")
PY

mkdir -p "$output_root" "$report_root"

fit_seed() {
  local seed=$1
  local checkpoint=$2
  local report=$3
  env PYTHONPATH=src:. OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 "$python_bin" \
    scripts/fit_structured_public_action_value.py \
      --policy "$policy" \
      --corpus "$corpus_root/train.npz" \
      --corpus-report "$corpus_root/train.json" \
      --corpus-manifest "$corpus_root/manifest.json" \
      --validation-corpus "$corpus_root/validation.npz" \
      --validation-report "$corpus_root/validation.json" \
      --output "$checkpoint" \
      --report "$report" \
      --seed "$seed" \
      --validation-split-seed 1169102 \
      --epochs 120 \
      --patience 25 \
      --batch-size 96 \
      --learning-rate 3e-4 \
      --weight-decay 1e-4 \
      --d-model 96 \
      --num-heads 4 \
      --num-layers 2 \
      --hidden-size 192 \
      --torch-threads 4 \
      --device "$device" \
      > "$report_root/seed_${seed}.log" 2>&1
}

pids=()
for seed in 1176001 1176002 1176003; do
  checkpoint="$output_root/seed_${seed}.pt"
  report="$report_root/seed_${seed}.json"
  if [[ -f "$checkpoint" && -f "$report" ]]; then
    continue
  fi
  if [[ -e "$checkpoint" || -e "$report" ]]; then
    echo "refusing partial structured ranker seed $seed" >&2
    exit 1
  fi
  fit_seed "$seed" "$checkpoint" "$report" &
  pids+=("$!")
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
((failed == 0)) || exit 1

printf '%s\n' 'hog26_phase_balanced_structured_rankers_v2_three_seeds_fit_complete_v1' \
  > "$report_root/THREE_SEEDS_FIT_COMPLETE"

env PYTHONPATH=src:. "$python_bin" \
  scripts/finalize_hog26_phase_balanced_structured_rankers.py \
    --input "$report_root/seed_1176001.json" \
    --input "$report_root/seed_1176002.json" \
    --input "$report_root/seed_1176003.json" \
    --output "$report_root/offline_gate.json" \
    > "$report_root/offline_gate.log" 2>&1

printf '%s\n' 'hog26_phase_balanced_structured_rankers_v2_offline_gate_complete_v1' \
  > "$report_root/THREE_SEEDS_COMPLETE"
