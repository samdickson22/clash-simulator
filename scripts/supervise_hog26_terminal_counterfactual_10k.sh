#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

part_a_host=${PART_A_HOST:-ubuntu@185.175.111.202}
part_b_host=${PART_B_HOST:-ubuntu@204.12.163.33}
part_a_pod=${PART_A_POD:-446d9316faea4960a2a6d3054c11916c}
part_b_pod=${PART_B_POD:-e4bf732f924b473a9eb807d27f8fb1bb}
ssh_key=${SSH_KEY:-/Users/sam/.ssh/id_ed25519_prime_clasher}
remote_root_a=/home/ubuntu/clasher/datasets/derived/hog26_parent_terminal_cf_10k_seed1164601
remote_root_b=/home/ubuntu/clasher/datasets/derived/hog26_parent_terminal_cf_10k_seed1164601_part_b
local_root=datasets/derived/hog26_parent_terminal_cf_10k_seed1164601
report_root=reports/hog26_parent_terminal_cf_10k_seed1164601
python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
prime_bin=${PRIME_BIN:-/Users/sam/.local/bin/prime}

mkdir -p "$report_root" "$local_root/train/shards" \
  "$local_root/validation/shards" "$local_root/parts"
[[ ! -e "$report_root/SUPERVISOR_COMPLETE" ]] || exit 0

ssh_args=(-i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=15)
remote_complete() {
  local host=$1 root=$2
  ssh "${ssh_args[@]}" "$host" "test -f '$root/COMPLETE'"
}
remote_alive() {
  local host=$1
  ssh "${ssh_args[@]}" "$host" \
    "pgrep -f '[r]un_hog26_terminal_counterfactual_10k|[c]ollect_terminal_counterfactual_corpus' >/dev/null"
}
terminate_owned_pods() {
  "$prime_bin" pods terminate "$part_a_pod" --plain -y || true
  "$prime_bin" pods terminate "$part_b_pod" --plain -y || true
}

while ! remote_complete "$part_a_host" "$remote_root_a" \
  || ! remote_complete "$part_b_host" "$remote_root_b"; do
  if ! remote_complete "$part_a_host" "$remote_root_a" \
    && ! remote_alive "$part_a_host"; then
    printf '%s\n' 'part-a-exited-before-complete' > "$report_root/FAILED"
    terminate_owned_pods
    exit 1
  fi
  if ! remote_complete "$part_b_host" "$remote_root_b" \
    && ! remote_alive "$part_b_host"; then
    printf '%s\n' 'part-b-exited-before-complete' > "$report_root/FAILED"
    terminate_owned_pods
    exit 1
  fi
  date -u '+waiting %Y-%m-%dT%H:%M:%SZ'
  sleep 60
done

rsync_ssh="ssh -i $ssh_key -o StrictHostKeyChecking=no -o ConnectTimeout=15"
rsync -a --partial -e "$rsync_ssh" \
  "$part_a_host:$remote_root_a/train/shards/" "$local_root/train/shards/"
rsync -a --partial -e "$rsync_ssh" \
  "$part_b_host:$remote_root_b/train/shards/" "$local_root/train/shards/"
rsync -a --partial -e "$rsync_ssh" \
  "$part_a_host:$remote_root_a/validation/shards/" \
  "$local_root/validation/shards/"
rsync -a --partial -e "$rsync_ssh" \
  "$part_b_host:$remote_root_b/validation/shards/" \
  "$local_root/validation/shards/"
rsync -a -e "$rsync_ssh" \
  "$part_a_host:$remote_root_a/" "$local_root/parts/a/"
rsync -a -e "$rsync_ssh" \
  "$part_b_host:$remote_root_b/" "$local_root/parts/b/"

"$python_bin" - "$local_root" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
expected_sha = {
    "source_archive": "8077eb371b29cf0a8cf9ebc08fdfcccc31bc099d1d1cab669298a26a21fd71e4",
    "policy": "28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372",
    "collector": "cab1f854ca7be9124757967533beb9f4fdb0049d4d69d91f9c5e028ad2e3ba08",
    "runner": "70d1b17c603a9f54174a9f622255ae22dfb6c5b7068e36b6b0dc33fcd33a22c1",
}
expected_ranges = {
    "a": {"train": [0, 800], "validation": [0, 175]},
    "b": {"train": [800, 600], "validation": [175, 175]},
}
for part in ("a", "b"):
    authority_path = root / "parts" / part / "node_authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    if authority.get("schema") != "clasher.terminal_cf_node_authority.v1":
        raise SystemExit(f"part {part} authority schema mismatch")
    if authority.get("part") != part:
        raise SystemExit(f"part {part} identity mismatch")
    if authority.get("ranges") != expected_ranges[part]:
        raise SystemExit(f"part {part} range mismatch")
    if authority.get("sha256") != expected_sha:
        raise SystemExit(f"part {part} source authority mismatch")

local_inputs = {
    "policy": Path(
        "checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt"
    ),
    "collector": Path("scripts/collect_terminal_counterfactual_corpus.py"),
    "runner": Path("scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh"),
}
for name, path in local_inputs.items():
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha[name]:
        raise SystemExit(f"local {name} differs from remote authority")

for split, count in (("train", 1400), ("validation", 350)):
    shard_root = root / split / "shards"
    ids = {
        int(path.stem.split("_")[1]) for path in shard_root.glob("game_*.json")
    }
    if ids != set(range(count)):
        missing = sorted(set(range(count)).difference(ids))
        extra = sorted(ids.difference(range(count)))
        raise SystemExit(
            f"{split} partition coverage mismatch: missing={missing[:10]} "
            f"extra={extra[:10]}"
        )
PY

terminate_after_copy=1
trap 'if [[ ${terminate_after_copy:-0} == 1 ]]; then terminate_owned_pods; fi' EXIT

env PYTHON_BIN="$python_bin" WORKERS=1 \
  TRAIN_GAME_START=0 TRAIN_GAMES=1400 \
  VALIDATION_GAME_START=0 VALIDATION_GAMES=350 \
  STATES_PER_GAME=8 MINIMUM_TRAIN_ROOTS=8000 MINIMUM_VALIDATION_ROOTS=2000 \
  OUTPUT_ROOT="$local_root" \
  scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh

terminate_owned_pods
terminate_after_copy=0
"$prime_bin" pods list --plain --output json \
  > "$report_root/pods_after_termination.json"

env PYTHON_BIN="$python_bin" DEVICE=mps \
  scripts/run_hog26_action_value_ensemble_seed1164701.sh
if [[ -f checkpoints/hog26_action_value_ensemble_seed1164701/controller.json ]]; then
  env PYTHON_BIN="$python_bin" DEVICE=cpu \
    scripts/run_hog26_action_value_ensemble_gameplay_gate.sh
fi

printf '%s\n' 'hog26_terminal_counterfactual_supervisor_complete_v1' \
  > "$report_root/SUPERVISOR_COMPLETE"
