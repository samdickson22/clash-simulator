#!/usr/bin/env bash
set -euo pipefail

if (( $# != 4 )); then
  echo "usage: $0 POD_ID SSH_HOST DEADLINE_EPOCH LOCAL_TAG" >&2
  exit 2
fi

pod_id=$1
ssh_host=$2
deadline_epoch=$3
local_tag=$4
ssh_key=${CLASHER_PRIME_SSH_KEY:-$HOME/.ssh/id_ed25519_prime_clasher}
remote_repo=${CLASHER_REMOTE_REPO:-/home/ubuntu/clasher}
poll_seconds=${CLASHER_SUPERVISOR_POLL_SECONDS:-300}
remote_completion_marker=${CLASHER_REMOTE_COMPLETION_MARKER:-}
source_local="datasets/external/${local_tag}"
semantic_local="datasets/derived/${local_tag}"
metadata_local="datasets/source_metadata/${local_tag}"
report_local="reports/${local_tag}"

if ! [[ "$deadline_epoch" =~ ^[0-9]+$ ]]; then
  echo "deadline must be a Unix epoch" >&2
  exit 2
fi

mkdir -p "$source_local" "$semantic_local" "$metadata_local" "$report_local"

sync_once() {
  rsync -az \
    --include='*/' \
    --include='manifest.json' \
    --include='*.framehash' \
    --exclude='*' \
    -e "ssh -i $ssh_key -o BatchMode=yes" \
    "$ssh_host:$remote_repo/datasets/external/${local_tag}/" "$source_local/"
  rsync -az \
    --exclude='video/*.tmp.*' \
    -e "ssh -i $ssh_key -o BatchMode=yes" \
    "$ssh_host:$remote_repo/datasets/source_metadata/${local_tag}/" "$metadata_local/"
  rsync -az \
    --exclude='.*.staging*' \
    -e "ssh -i $ssh_key -o BatchMode=yes" \
    "$ssh_host:$remote_repo/datasets/derived/${local_tag}/" "$semantic_local/"
  rsync -az \
    --exclude='.*.tmp' \
    -e "ssh -i $ssh_key -o BatchMode=yes" \
    "$ssh_host:$remote_repo/reports/${local_tag}/" "$report_local/"
}

while (( $(date +%s) < deadline_epoch )); do
  pod_state=$(prime --plain pods list --output json \
    | jq -r --arg id "$pod_id" '.pods[] | select(.id == $id) | .status')
  if [[ "$pod_state" != ACTIVE ]]; then
    echo "pod is no longer active: ${pod_state:-missing}" >&2
    exit 1
  fi
  sync_once || true
  if [[ -n "$remote_completion_marker" ]] && ssh -i "$ssh_key" -o BatchMode=yes "$ssh_host" \
    "test -f '$remote_repo/$remote_completion_marker' && \
     ! pgrep -f '[r]un_tv_royale_persistent_l40_batch.sh|[p]ostprocess_tv_royale_persistent_batch.sh|[r]un_tv_royale_prototype_watcher.sh' >/dev/null"; then
    echo "remote completion marker is final and task workers exited"
    break
  fi
  sleep "$poll_seconds"
done

ssh -i "$ssh_key" -o BatchMode=yes "$ssh_host" \
  "pkill -f '[r]un_tv_royale_persistent_l40_batch.sh' || true; \
   pkill -f '[p]ostprocess_tv_royale_persistent_batch.sh' || true; \
   pkill -f 'tv_royale_youtube_1000_20260826' || true" || true
sync_once || true
prime --plain pods terminate "$pod_id" --yes
