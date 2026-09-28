#!/usr/bin/env bash
set -euo pipefail

repo=${CLASHER_REPO:-/home/ubuntu/clasher}
limit=${CLASHER_BATCH_LIMIT:-40}
acquire_workers=${CLASHER_ACQUIRE_WORKERS:-6}
semantic_workers=${CLASHER_SEMANTIC_WORKERS:-6}
gpu_count=${CLASHER_GPU_COUNT:-2}
acquire_only=${CLASHER_ACQUIRE_ONLY:-0}
semantic_only=${CLASHER_SEMANTIC_ONLY:-0}
acquisition_backend=${CLASHER_ACQUISITION_BACKEND:-yt-dlp}
yt_dlp_impersonate=${CLASHER_YT_DLP_IMPERSONATE:-}
metadata_jsonl=${CLASHER_METADATA_JSONL:-datasets/source_metadata/tv_royale_youtube_persistent_batch_20260824/flat_candidates.jsonl}
metadata_root=${CLASHER_METADATA_ROOT:-datasets/source_metadata/persistent_batch_v1}
source_root=${CLASHER_SOURCE_ROOT:-datasets/external/persistent_batch_v1}
semantic_root=${CLASHER_SEMANTIC_ROOT:-datasets/derived/persistent_batch_v1}
semantic_raw_root=${CLASHER_SEMANTIC_RAW_ROOT:-${semantic_root}_clock_deferred}
log_root=${CLASHER_LOG_ROOT:-reports/persistent_batch_v1/logs}
layout_skip_path=${CLASHER_LAYOUT_SKIP_PATH:-reports/persistent_batch_v1/layout_skips.tsv}
clock_provider_mode=${CLASHER_CLOCK_PROVIDER_MODE:-pinned-linux}
clock_adapter=${CLASHER_CLOCK_ADAPTER:-tools/recognize_public_clock.py}
clock_merger=${CLASHER_CLOCK_MERGER:-scripts/apply_tv_royale_youtube_clock_adapter.py}

cd "$repo"
export PATH="$HOME/bin:$HOME/.local/bin:$HOME/.dotnet:$PATH"
export PYTHONPATH=src:.
export XDG_CONFIG_HOME="$repo/.config"
export MPLCONFIGDIR="$repo/.config/matplotlib"
export YOLO_CONFIG_DIR="$repo/.config/ultralytics"
mkdir -p "$metadata_root" "$source_root" "$semantic_root" "$semantic_raw_root" "$log_root" "$(dirname "$layout_skip_path")" "$XDG_CONFIG_HOME"

if (( gpu_count <= 0 )); then
  echo "CLASHER_GPU_COUNT must be positive" >&2
  exit 2
fi
if [[ "$acquire_only" != 0 && "$acquire_only" != 1 ]]; then
  echo "CLASHER_ACQUIRE_ONLY must be 0 or 1" >&2
  exit 2
fi
if [[ "$semantic_only" != 0 && "$semantic_only" != 1 ]]; then
  echo "CLASHER_SEMANTIC_ONLY must be 0 or 1" >&2
  exit 2
fi
if [[ "$acquire_only" == 1 && "$semantic_only" == 1 ]]; then
  echo "acquire-only and semantic-only are mutually exclusive" >&2
  exit 2
fi
if [[ "$acquisition_backend" != yt-dlp && "$acquisition_backend" != yt-dlp-direct ]]; then
  echo "CLASHER_ACQUISITION_BACKEND must be yt-dlp or yt-dlp-direct" >&2
  exit 2
fi
if [[ "$clock_provider_mode" != pinned-linux && "$clock_provider_mode" != deferred ]]; then
  echo "CLASHER_CLOCK_PROVIDER_MODE must be pinned-linux or deferred" >&2
  exit 2
fi
if [[ "$clock_provider_mode" == pinned-linux ]]; then
  if [[ ! -f "$clock_adapter" ]] || [[ ! -f "$clock_merger" ]]; then
    echo "pinned Linux clock adapter or merger is unavailable" >&2
    exit 2
  fi
fi

mapfile -t video_ids < <(head -n "$limit" "$metadata_jsonl" | jq -r .id)
if [[ ${#video_ids[@]} -eq 0 ]]; then
  echo "no videos selected" >&2
  exit 1
fi

acquire_one() {
  local video_id=$1
  local video_json="$metadata_root/$video_id.json"
  local output="$source_root/$video_id"
  if [[ -f "$output/manifest.json" ]] && [[ $(jq -r .status "$output/manifest.json") == complete ]]; then
    echo "already complete: $video_id"
    return 0
  fi
  local metadata format_id
  local metadata_args=(--no-playlist --no-warnings --force-ipv4 --dump-single-json --skip-download)
  if [[ -n "$yt_dlp_impersonate" ]]; then
    metadata_args+=(--impersonate "$yt_dlp_impersonate")
  fi
  metadata=$(yt-dlp "${metadata_args[@]}" "https://www.youtube.com/watch?v=$video_id")
  metadata=$(printf '%s' "$metadata" | jq '
    .url = (.webpage_url // .original_url // ("https://www.youtube.com/watch?v=" + .id))
    | if .availability == "public" then .access_class = "public" else . end')
  local metadata_tmp="${video_json}.tmp.$$"
  printf '%s\n' "$metadata" > "$metadata_tmp"
  mv "$metadata_tmp" "$video_json"
  format_id=$(printf '%s' "$metadata" | jq -r '
    if any(.formats[]; .format_id == "308" and .width == 1182 and .height == 2560) then "308"
    elif any(.formats[]; .format_id == "303" and .width == 886 and .height == 1920) then "303"
    else "unsupported"
    end')
  if [[ "$format_id" == unsupported ]]; then
    printf '%s\tunsupported_native_layout\n' "$video_id" >> "$layout_skip_path"
    return 0
  fi
  local acquire_impersonate_args=()
  if [[ -n "$yt_dlp_impersonate" ]]; then
    acquire_impersonate_args+=(--yt-dlp-impersonate "$yt_dlp_impersonate")
  fi
  .venv/bin/python scripts/acquire_tv_royale_youtube_fullmatch.py \
    --video-json "$video_json" \
    --output-dir "$output" \
    --backend "$acquisition_backend" \
    --yt-dlp "$HOME/.local/bin/yt-dlp" \
    --yt-dlp-format "$format_id" \
    "${acquire_impersonate_args[@]}" \
    --sample-hz 10
}

if [[ "$semantic_only" == 0 ]]; then
  active=0
  for video_id in "${video_ids[@]}"; do
    acquire_one "$video_id" >"$log_root/${video_id}.acquire.log" 2>&1 &
    active=$((active + 1))
    if (( active >= acquire_workers )); then
      wait -n || true
      active=$((active - 1))
    fi
  done
  wait || true
fi

if [[ "$acquire_only" == 1 ]]; then
  complete_sources=$(find "$source_root" -mindepth 2 -maxdepth 2 -name manifest.json -print | wc -l)
  printf 'sources=%s selected=%s mode=acquire-only\n' "$complete_sources" "${#video_ids[@]}"
  exit 0
fi

semantic_one() {
  local video_id=$1
  local gpu=$2
  local source="$source_root/$video_id"
  local output="$semantic_root/$video_id"
  local raw_output="$semantic_raw_root/$video_id"
  if [[ ! -f "$source/manifest.json" ]] || [[ $(jq -r .status "$source/manifest.json") != complete ]]; then
    echo "source incomplete: $video_id"
    return 0
  fi
  if [[ -f "$output/manifest.json" ]] && {
    [[ "$clock_provider_mode" == deferred ]] || [[ -f "$output/CLOCK_COMPLETE" ]]
  }; then
    echo "already complete: $video_id"
    return 0
  fi
  if [[ -e "$output" ]]; then
    echo "refusing incomplete or unclocked semantic output: $output" >&2
    return 1
  fi
  if [[ "$clock_provider_mode" == pinned-linux ]] && \
     [[ $(jq -r '.source_media.width == 1182 and .source_media.height == 2560' "$source/manifest.json") != true ]]; then
    printf '%s\tunsupported_portable_clock_layout\n' "$video_id" >> "$layout_skip_path"
    return 0
  fi
  if [[ ! -f "$raw_output/manifest.json" ]]; then
    CUDA_VISIBLE_DEVICES=$gpu .venv/bin/python scripts/extract_tv_royale_youtube_fullmatch.py \
    --input-video "$source/source.webm" \
    --source-manifest "$source/manifest.json" \
    --output-dir "$raw_output" \
    --vocabulary-manifest reports/current_client_youtube_stable_vocabulary_v1.json \
    --template-root datasets/external/CS541-Deep-Learning-Clash-Royale-Project \
    --card-embedding-weight datasets/external/torchvision_weights/mobilenet_v3_small-047dcff4.pth \
    --katacr-root datasets/external/KataCR \
    --detector-weight datasets/external/KataCR/runs/detector1_v0.7.13.pt \
    --detector-weight datasets/external/KataCR/runs/detector2_v0.7.13.pt \
    --device cuda \
    --batch-size 16 \
    --card-preprocess-backend tensor \
    --card-preprocess-workers 2 \
    --detection-nms-backend native \
    --raw-actor-mode deferred \
    --sample-hz 10 \
    --actor-hz 5 \
    --clock-provider-mode deferred
  fi
  if [[ "$clock_provider_mode" == deferred ]]; then
    mv "$raw_output" "$output"
    return 0
  fi

  local clock_root="$semantic_raw_root/${video_id}_clock"
  local anchors="$clock_root/clock_anchors.jsonl"
  mkdir -p "$clock_root"
  if [[ ! -f "$anchors" ]]; then
    .venv/bin/python "$clock_adapter" \
      --source-video "$source/source.webm" \
      --source-manifest "$source/manifest.json" \
      --output-jsonl "$anchors" \
      --sample-hz 10 \
      --anchor-stride-frames 5
  fi
  local provider_sha
  provider_sha=$(.venv/bin/python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$clock_adapter")
  .venv/bin/python "$clock_merger" \
    --input-manifest "$raw_output/manifest.json" \
    --anchors "$anchors" \
    --output-dir "$output" \
    --provider "$clock_adapter" \
    --provider-sha256 "$provider_sha"
  local clocked_neutral
  clocked_neutral=$(jq -r '.artifacts.neutral_sequence.path' "$output/manifest.json")
  .venv/bin/python - "$clocked_neutral" <<'PY'
import gzip
import json
import sys

valid = 0
with gzip.open(sys.argv[1], "rt", encoding="utf-8") as stream:
    for line in stream:
        row = json.loads(line)
        valid += int(row["public"]["clock"]["valid"])
if valid <= 0:
    raise SystemExit("portable clock published zero valid frames")
print(f"clock_valid_frames={valid}")
PY
  printf '%s\n' pinned_linux_clock_complete_v1 > "$output/CLOCK_COMPLETE"
}

if [[ "$semantic_only" == 1 ]]; then
  mapfile -t video_ids < <(
    find "$source_root" -mindepth 2 -maxdepth 2 -name manifest.json -print \
      | sed 's#/manifest.json$##' | xargs -n1 basename | sort
  )
fi

active=0
launched=0
for video_id in "${video_ids[@]}"; do
  gpu=$((launched % gpu_count))
  semantic_one "$video_id" "$gpu" >"$log_root/${video_id}.semantic.log" 2>&1 &
  launched=$((launched + 1))
  active=$((active + 1))
  if (( active >= semantic_workers )); then
    wait -n || true
    active=$((active - 1))
  fi
done
wait || true

complete_sources=$(find "$source_root" -mindepth 2 -maxdepth 2 -name manifest.json -print | wc -l)
complete_semantics=$(find "$semantic_root" -mindepth 2 -maxdepth 2 -name manifest.json -print | wc -l)
printf 'sources=%s semantics=%s selected=%s\n' "$complete_sources" "$complete_semantics" "${#video_ids[@]}"
