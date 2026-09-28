#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

final_marker=reports/tv_royale_public_v2_final1000_inputs_ready.txt
manifest=datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201/run_manifest.json
output_root=datasets/derived/tv_royale_public_v2_post260_split_seed1056502
success_marker=reports/tv_royale_public_v2_post260_inputs_ready.txt
temporary_marker="${success_marker}.tmp.$$"

if [[ -e "$success_marker" || -e "$output_root" ]]; then
  print -u2 -- "refusing to overwrite post-260 evaluation outputs"
  exit 1
fi
trap 'rm -f -- "$temporary_marker"' EXIT

while [[ ! -f "$final_marker" ]] || \
  [[ $(<"$final_marker") != pretraining_inputs_ready_v1 ]]; do
  sleep 30
done

env PYTHONPATH=src:. uv run python scripts/split_tv_royale_raw_cascade.py \
  --run-manifest "$manifest" \
  --output-dir "$output_root" \
  --decks-path decks.json \
  --seed 1056502 \
  --target-games 1000 \
  --reserve-first-completed 260 \
  --validation-fraction 0.2 \
  --chronology-min-arena 31

env PYTHONPATH=src:. uv run python scripts/split_tv_royale_public_sidecars.py \
  --run-manifest "$manifest" \
  --split-manifest "$output_root/split_manifest.json" \
  --output-dir "$output_root"

env PYTHONPATH=src:. uv run python scripts/verify_tv_royale_post260_split.py \
  --split-manifest "$output_root/split_manifest.json" \
  --run-manifest "$manifest" \
  --target-games 1000 \
  --reserved-games 260 \
  --output reports/tv_royale_public_v2_post260_verification.json

print -r -- 'post260_evaluation_inputs_ready_v1' > "$temporary_marker"
mv -- "$temporary_marker" "$success_marker"
trap - EXIT
print -r -- '{"status":"post260_evaluation_inputs_ready"}'
