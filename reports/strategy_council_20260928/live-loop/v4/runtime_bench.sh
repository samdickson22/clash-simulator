#!/usr/bin/env bash
# Execute through fleet/fleet_run.sh with a unique label. No emulator commands.
set -euo pipefail
: "${CLASHER_ROOT:?repository path}"
data=${1:?train replay staging directory}
output=${2:?new results directory}
python_bin=${3:?CPU interpreter}
export YOLO_AUTOINSTALL=false
export PYTHONPATH="$CLASHER_ROOT/src:$CLASHER_ROOT/engine-rs:$data/python-deps"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$CLASHER_ROOT"
mkdir -p "$output"
for seed in 1975100700 1975100701; do
  run="$output/$seed"
  # A completed run is immutable. Interrupted output is retained for diagnosis;
  # resumption uses a fresh suite label, never deletes or overwrites a receipt.
  if [ -f "$run/complete" ]; then continue; fi
  "$python_bin" -B -m clasher.live \
    --replay "$data/matches/v4-phase-a-$seed" \
    --split "$data/registration/split.json" \
    --prior reports/strategy_council_20260928/search-noise-s4/runtime/support/human_deck_catalog.json \
    --body "$data/weights/body.pt" --hud "$data/weights/hud.npz" \
    --output "$run" > "$output/$seed.log" 2>&1
  date -u +%FT%TZ > "$run/complete"
done
