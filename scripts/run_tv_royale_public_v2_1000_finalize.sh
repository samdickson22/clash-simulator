#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

collector_session=clasher-public-v2-1000
run_root=datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201
scratch_root=datasets/external/tv_royale_raw_stream_public_v2_1000
split_root=datasets/derived/tv_royale_public_v2_final_split_seed1055801
sheet_root=reports/tv_royale_public_v2_final1000_contact_sheets
success_marker=reports/tv_royale_public_v2_final1000_inputs_ready.txt
success_marker_tmp="${success_marker}.tmp.$$"
if [[ -e "$success_marker" ]]; then
  print -u2 -- "refusing to overwrite existing success marker: $success_marker"
  exit 1
fi
trap 'rm -f -- "$success_marker_tmp"' EXIT

while tmux list-sessions -F '#S' 2>/dev/null | rg -Fxq "$collector_session"; do
  sleep 30
done

manifest="$run_root/run_manifest.json"
combined="$run_root/tv_royale_raw_cascade_1000.npz"
public="$run_root/tv_royale_raw_cascade_1000_public_state_v2.npz"

uv run python - "$manifest" "$combined" "$public" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, combined_path, public_path = map(Path, sys.argv[1:])
payload = json.loads(manifest_path.read_text())
if payload.get("completed_games") != 1000:
    raise SystemExit(
        f"public cascade incomplete: {payload.get('completed_games')}/1000 games"
    )
for label, path in (("combined corpus", combined_path), ("public sidecar", public_path)):
    if not path.is_file():
        raise SystemExit(f"missing {label}: {path}")
print(json.dumps({"status": "publication_present", "completed_games": 1000}))
PY

env PYTHONPATH=src:. uv run python scripts/verify_tv_royale_run_integrity.py \
  --run-manifest "$manifest" \
  --scratch-root "$scratch_root" \
  --target-games 1000 \
  --require-public-state-v2 \
  --output reports/tv_royale_public_v2_final1000_integrity.json

env PYTHONPATH=src:. uv run python scripts/verify_tv_royale_public_state_quality.py \
  --run-manifest "$manifest" \
  --target-games 1000 \
  --expected-arenas 20 \
  --minimum-entity-hp-coverage 0.50 \
  --minimum-arena-entity-hp-coverage 0.45 \
  --minimum-mean-entity-hp-confidence 0.45 \
  --minimum-motion-direction-coverage 0.30 \
  --minimum-arena-motion-direction-coverage 0.25 \
  --minimum-tower-hp-measurements-per-sample 3.0 \
  --minimum-arena-tower-hp-measurements-per-sample 2.5 \
  --output reports/tv_royale_public_v2_final1000_quality.json

env PYTHONPATH=src:. uv run python scripts/build_tv_royale_public_contact_sheets.py \
  --run-manifest "$manifest" \
  --output-dir "$sheet_root" \
  --quantiles 4 \
  --expected-arenas 20

env PYTHONPATH=src:. uv run python scripts/split_tv_royale_raw_cascade.py \
  --run-manifest "$manifest" \
  --output-dir "$split_root" \
  --decks-path decks.json \
  --seed 1055801 \
  --target-games 1000 \
  --validation-fraction 0.2 \
  --chronology-min-arena 31

env PYTHONPATH=src:. uv run python scripts/split_tv_royale_public_sidecars.py \
  --run-manifest "$manifest" \
  --split-manifest "$split_root/split_manifest.json" \
  --output-dir "$split_root"

print -r -- 'pretraining_inputs_ready_v1' > "$success_marker_tmp"
mv -- "$success_marker_tmp" "$success_marker"
trap - EXIT
print -r -- '{"status":"pretraining_inputs_ready","games":1000}'
