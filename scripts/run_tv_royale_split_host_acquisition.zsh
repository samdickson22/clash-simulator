#!/bin/zsh

set -euo pipefail

repo=${CLASHER_REPO:-${0:A:h:h}}
limit=${CLASHER_SPLIT_HOST_LIMIT:-128}
workers=${CLASHER_SPLIT_HOST_WORKERS:-2}
metadata_jsonl=${CLASHER_METADATA_JSONL:-datasets/source_metadata/tv_royale_youtube_clocked_rotate_20260826/flat_remaining_clocked.jsonl}
metadata_root=${CLASHER_METADATA_ROOT:-datasets/source_metadata/tv_royale_youtube_clocked_rotate_20260826/video_local}
source_root=${CLASHER_SOURCE_ROOT:-datasets/external/tv_royale_youtube_clocked_rotate_20260826}
log_root=${CLASHER_LOG_ROOT:-reports/tv_royale_youtube_clocked_rotate_20260826/local_acquire_logs}
remote_host=${CLASHER_REMOTE_HOST:?CLASHER_REMOTE_HOST is required}
remote_repo=${CLASHER_REMOTE_REPO:-/home/ubuntu/clasher}
remote_source_root=${CLASHER_REMOTE_SOURCE_ROOT:-datasets/external/tv_royale_youtube_clocked_rotate_20260826}
remote_metadata_root=${CLASHER_REMOTE_METADATA_ROOT:-datasets/source_metadata/tv_royale_youtube_clocked_rotate_20260826/video_local}
remote_completion_marker=${CLASHER_REMOTE_COMPLETION_MARKER:-reports/tv_royale_youtube_clocked_rotate_20260826/ACQUISITION_COMPLETE}
ssh_key=${CLASHER_SSH_KEY:-$HOME/.ssh/id_ed25519_prime_clasher}
yt_dlp=${CLASHER_YT_DLP:-$HOME/.local/bin/yt-dlp}
impersonate=${CLASHER_YT_DLP_IMPERSONATE:-Chrome-136:Macos-15}

cd "$repo"
export PYTHONPATH=src:.
mkdir -p "$metadata_root" "$source_root" "$log_root"

if (( limit <= 0 || workers <= 0 )); then
  print -u2 -- "limit and workers must be positive"
  exit 2
fi
if [[ ! -x "$yt_dlp" ]] || [[ ! -f "$metadata_jsonl" ]]; then
  print -u2 -- "yt-dlp or input inventory is unavailable"
  exit 2
fi

ssh_args=(-o BatchMode=yes -i "$ssh_key")
rsync_ssh="ssh -o BatchMode=yes -i $ssh_key"
ssh "${ssh_args[@]}" "$remote_host" \
  "mkdir -p '$remote_repo/$remote_source_root' '$remote_repo/$remote_metadata_root' '$(dirname "$remote_repo/$remote_completion_marker")'"

video_ids=("${(@f)$(head -n "$limit" "$metadata_jsonl" | jq -r .id)}")
if (( ${#video_ids[@]} == 0 )); then
  print -u2 -- "inventory selected zero videos"
  exit 1
fi

run_one() {
  local video_id=$1
  local metadata="$metadata_root/$video_id.json"
  local output="$source_root/$video_id"
  local temporary="$metadata.tmp.$$"
  if [[ ! -f "$output/manifest.json" ]]; then
    "$yt_dlp" \
      --no-playlist \
      --no-warnings \
      --force-ipv4 \
      --impersonate "$impersonate" \
      --dump-single-json \
      --skip-download \
      "https://www.youtube.com/watch?v=$video_id" \
      | jq '
          .url = (.webpage_url // .original_url // ("https://www.youtube.com/watch?v=" + .id))
          | if .availability == "public" then .access_class = "public" else . end
        ' > "$temporary"
    mv "$temporary" "$metadata"
    env PYTHONPATH=src:. nice -n 15 uv run python \
      scripts/acquire_tv_royale_youtube_fullmatch.py \
      --video-json "$metadata" \
      --output-dir "$output" \
      --backend yt-dlp-direct \
      --yt-dlp "$yt_dlp" \
      --yt-dlp-format 308 \
      --yt-dlp-impersonate "$impersonate" \
      --sample-hz 10
  fi
  rsync -az --partial -e "$rsync_ssh" "$output/" \
    "$remote_host:$remote_repo/$remote_source_root/$video_id/"
  rsync -az -e "$rsync_ssh" "$metadata" \
    "$remote_host:$remote_repo/$remote_metadata_root/$video_id.json"
}

pids=()
for video_id in "${video_ids[@]}"; do
  run_one "$video_id" > "$log_root/$video_id.log" 2>&1 &
  pids+=($!)
  if (( ${#pids[@]} >= workers )); then
    for pid in "${pids[@]}"; do
      wait "$pid" || true
    done
    pids=()
  fi
done
for pid in "${pids[@]}"; do
  wait "$pid" || true
done

completed=0
failed=0
for video_id in "${video_ids[@]}"; do
  if [[ -f "$source_root/$video_id/manifest.json" ]]; then
    completed=$((completed + 1))
  else
    failed=$((failed + 1))
  fi
done
ssh "${ssh_args[@]}" "$remote_host" \
  "printf '%s\n' 'selected=${#video_ids[@]} completed=$completed failed=$failed' > '$remote_repo/$remote_completion_marker'"
print -r -- "selected=${#video_ids[@]} completed=$completed failed=$failed"
