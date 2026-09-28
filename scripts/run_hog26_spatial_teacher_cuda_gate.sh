#!/usr/bin/env bash

set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-$root/.venv/bin/python}
base=${BASE_CHECKPOINT:-$root/checkpoints/hog26_factorized_executed_strategy_e3_seed1244001/candidate.pt}
candidate=${CANDIDATE_CHECKPOINT:-$root/checkpoints/hog26_factorized_spatial_teacher_u20_seed1248201/candidate.pt}
output_root=${OUTPUT_ROOT:-$root/reports/hog26_spatial_teacher_cuda_gate}
games=${GAMES:-4}
seed=${SEED:-1249301}

[[ -x "$python_bin" ]] || { echo "missing Python: $python_bin" >&2; exit 1; }
[[ -f "$base" && -f "$candidate" ]] || { echo "missing checkpoint" >&2; exit 1; }
[[ ! -e "$output_root" ]] || { echo "refusing to overwrite output: $output_root" >&2; exit 1; }
[[ "$games" =~ ^[2-9][0-9]*$|^[2468]$ ]] && (( games % 2 == 0 )) || {
  echo "GAMES must be an even integer >=2" >&2
  exit 1
}

"$python_bin" - "$base" "$candidate" <<'PY'
import hashlib
import sys
from pathlib import Path

expected = (
    "3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5",
    "4ec5585f63fd65c30ed977b78a87cc66208ab64d7e125116f1dd32f7d120d8f4",
)
for value, wanted in zip(sys.argv[1:], expected, strict=True):
    actual = hashlib.sha256(Path(value).read_bytes()).hexdigest()
    if actual != wanted:
        raise SystemExit(f"checkpoint SHA-256 mismatch: {value}: {actual}")
PY

mkdir -p "$output_root"
opponent_args=()
for opponent in bridge-pressure slow-push spell-control reactive-defense split-lane balanced random; do
  opponent_args+=(--opponent "$opponent")
done
for arm in base candidate; do
  checkpoint="$base"
  [[ "$arm" == candidate ]] && checkpoint="$candidate"
  env PYTHONPATH="$root/src:$root" "$python_bin" \
    "$root/scripts/evaluate_hog26_simple_policy.py" \
    --checkpoint "$checkpoint" \
    --output "$output_root/$arm.json" \
    --games "$games" --device cuda --seed "$seed" --chunk-steps 32 \
    "${opponent_args[@]}" \
    > "$output_root/$arm.log" 2>&1
done

env PYTHONPATH="$root/src:$root" "$python_bin" \
  "$root/scripts/finalize_hog26_spatial_teacher_cuda_gate.py" \
  --root "$output_root" --games "$games" --seed "$seed"
