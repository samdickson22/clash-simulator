#!/usr/bin/env bash
set -euo pipefail

repo=${CLASHER_REPO:-/home/ubuntu/clasher}
workers=${CLASHER_POSTPROCESS_WORKERS:-6}
source_root=${CLASHER_SOURCE_ROOT:-datasets/external/persistent_batch_v1}
semantic_root=${CLASHER_SEMANTIC_ROOT:-datasets/derived/persistent_batch_v1}
report_root=${CLASHER_REPORT_ROOT:-reports/persistent_batch_v1}
sheet_root=${CLASHER_SHEET_ROOT:-reports/eight_card_deck_sheets}
classification_root=${CLASHER_CLASSIFICATION_ROOT:-reports/eight_card_deck_classifications}
clusters_per_player=${CLASHER_CLUSTERS_PER_PLAYER:-32}
cost_calibration_manifest=${CLASHER_COST_CALIBRATION_MANIFEST:-datasets/derived/tv_royale_youtube_fullmatch_visible_cost_gate_hTG8dM4KtM4_20260817/manifest.json}
classification_device=${CLASHER_CLASSIFICATION_DEVICE:-cuda}
wait_for_production=${CLASHER_WAIT_FOR_PRODUCTION:-1}

cd "$repo"
export PATH="$HOME/bin:$HOME/.local/bin:$HOME/.dotnet:$PATH"
export PYTHONPATH=src:.
export XDG_CONFIG_HOME="$repo/.config"
export MPLCONFIGDIR="$repo/.config/matplotlib"
export YOLO_CONFIG_DIR="$repo/.config/ultralytics"
mkdir -p \
  "$report_root/hud_clusters" \
  "$report_root/cycle_events" \
  "$report_root/logs" \
  "$sheet_root" \
  "$classification_root"

if (( clusters_per_player <= 0 )); then
  echo "CLASHER_CLUSTERS_PER_PLAYER must be positive" >&2
  exit 2
fi

if [[ "$wait_for_production" == 1 ]]; then
  while pgrep -f '[r]un_tv_royale_persistent_l40_batch.sh' >/dev/null; do
    sleep 20
  done
elif [[ "$wait_for_production" != 0 ]]; then
  echo "CLASHER_WAIT_FOR_PRODUCTION must be 0 or 1" >&2
  exit 2
fi

mapfile -t video_ids < <(
  find "$semantic_root" -mindepth 2 -maxdepth 2 -name manifest.json -print \
    | sed 's#/manifest.json$##' | xargs -n1 basename | sort
)

postprocess_one() {
  local video_id=$1
  local source="$source_root/$video_id"
  local semantic="$semantic_root/$video_id"
  local semantic_manifest="$semantic/manifest.json"
  local neutral
  neutral=$(jq -r '.artifacts.neutral_sequence.path' "$semantic_manifest")
  if [[ ! -f "$neutral" ]]; then
    echo "semantic manifest identifies a missing neutral artifact: $neutral" >&2
    return 1
  fi
  local clusters="$report_root/hud_clusters/$video_id"
  local events="$report_root/cycle_events/$video_id.json"
  if [[ ! -f "$clusters/manifest.json" ]]; then
    .venv/bin/python scripts/build_tv_royale_hud_cluster_gallery.py \
      --video "$source/source.webm" \
      --source-manifest "$source/manifest.json" \
      --neutral "$neutral" \
      --sample-hz 2 \
      --clusters-per-player "$clusters_per_player" \
      --minimum-candidate-score 0 \
      --persist-representatives \
      --output-dir "$clusters"
  fi
  if [[ ! -f "$events" ]]; then
    .venv/bin/python scripts/extract_tv_royale_hud_cycle_events.py \
      --video "$source/source.webm" \
      --source-manifest "$source/manifest.json" \
      --neutral "$neutral" \
      --cluster-manifest "$clusters/manifest.json" \
      --cluster-arrays "$clusters/hud_clusters.npz" \
      --vocabulary-manifest reports/current_client_youtube_stable_vocabulary_v1.json \
      --output "$events"
  fi
  local sheet="$sheet_root/$video_id/manifest.json"
  local classification="$classification_root/$video_id.json"
  if [[ ! -f "$sheet" ]]; then
    .venv/bin/python scripts/extract_tv_royale_eight_card_deck_sheet.py \
      --video "$source/source.webm" \
      --source-manifest "$source/manifest.json" \
      --neutral "$neutral" \
      --output-dir "$sheet_root/$video_id"
  fi
  if [[ ! -f "$classification" ]]; then
    .venv/bin/python scripts/classify_tv_royale_eight_card_deck_sheet.py \
      --sheet-manifest "$sheet" \
      --vocabulary reports/current_client_youtube_stable_vocabulary_v1.json \
      --cost-calibration-manifest "$cost_calibration_manifest" \
      --template-root datasets/external/CS541-Deep-Learning-Clash-Royale-Project \
      --card-embedding-weight datasets/external/torchvision_weights/mobilenet_v3_small-047dcff4.pth \
      --device "$classification_device" \
      --output "$classification"
  fi
}

active=0
for video_id in "${video_ids[@]}"; do
  postprocess_one "$video_id" >"$report_root/logs/${video_id}.postprocess.log" 2>&1 &
  active=$((active + 1))
  if (( active >= workers )); then
    wait -n || true
    active=$((active - 1))
  fi
done
wait || true

galleries=$(find "$report_root/hud_clusters" -mindepth 2 -maxdepth 2 -name manifest.json -print | wc -l)
events=$(find "$report_root/cycle_events" -maxdepth 1 -name '*.json' -print | wc -l)
sheets=$(find "$sheet_root" -mindepth 2 -maxdepth 2 -name manifest.json -print | wc -l)
classifications=$(find "$classification_root" -maxdepth 1 -name '*.json' -print | wc -l)
printf 'galleries=%s events=%s sheets=%s classifications=%s semantic_inputs=%s\n' \
  "$galleries" "$events" "$sheets" "$classifications" "${#video_ids[@]}"
