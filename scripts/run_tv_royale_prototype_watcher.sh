#!/usr/bin/env bash
set -euo pipefail

repo=${CLASHER_REPO:-/home/ubuntu/clasher}
sheet_root=${CLASHER_SHEET_ROOT:-reports/tv_royale_youtube_1000_20260826/eight_card_deck_sheets}
output_root=${CLASHER_PROTOTYPE_OUTPUT_ROOT:-reports/tv_royale_youtube_1000_20260826/prototype_candidates}
log_root=${CLASHER_PROTOTYPE_LOG_ROOT:-reports/tv_royale_youtube_1000_20260826/prototype_logs}
bank_manifest=${CLASHER_PROTOTYPE_BANK_MANIFEST:-reports/tv_royale_card_prototype_v1/manifest.json}
workers=${CLASHER_PROTOTYPE_WORKERS:-8}
device=${CLASHER_PROTOTYPE_DEVICE:-cpu}
watch_pid=${CLASHER_WATCH_PID:-}
poll_seconds=${CLASHER_PROTOTYPE_POLL_SECONDS:-120}

cd "$repo"
export PATH="$HOME/bin:$HOME/.local/bin:$PATH"
export PYTHONPATH=src:.
mkdir -p "$output_root" "$log_root"

run_one() {
  local video_id=$1
  local manifest=$2
  .venv/bin/python scripts/classify_tv_royale_eight_card_prototypes.py \
    --sheet-manifest "$manifest" \
    --bank-manifest "$bank_manifest" \
    --vocabulary reports/current_client_youtube_stable_vocabulary_v1.json \
    --template-root datasets/external/CS541-Deep-Learning-Clash-Royale-Project \
    --card-embedding-weight datasets/external/torchvision_weights/mobilenet_v3_small-047dcff4.pth \
    --device "$device" \
    --output "$output_root/$video_id.json"
}

run_pass() {
  local active=0 video_id manifest
  while IFS= read -r manifest; do
    video_id=$(basename "$(dirname "$manifest")")
    [[ -f "$output_root/$video_id.json" ]] && continue
    run_one "$video_id" "$manifest" >"$log_root/$video_id.log" 2>&1 &
    active=$((active + 1))
    if (( active >= workers )); then
      wait -n || true
      active=$((active - 1))
    fi
  done < <(find "$sheet_root" -mindepth 2 -maxdepth 2 -name manifest.json -print | sort)
  wait || true
}

if [[ -z "$watch_pid" ]]; then
  run_pass
  exit 0
fi
if ! [[ "$watch_pid" =~ ^[0-9]+$ ]]; then
  echo "CLASHER_WATCH_PID must be numeric" >&2
  exit 2
fi
while kill -0 "$watch_pid" 2>/dev/null; do
  run_pass
  sleep "$poll_seconds"
done
run_pass
