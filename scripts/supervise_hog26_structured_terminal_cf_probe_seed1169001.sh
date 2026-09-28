#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

remote_host=${REMOTE_HOST:-ubuntu@204.12.168.225}
pod_id=${POD_ID:-670a8d184c12464cb02a73eb17e7a860}
ssh_key=${SSH_KEY:-/Users/sam/.ssh/id_ed25519_prime_clasher}
remote_repo=/home/ubuntu/clasher
remote_root=$remote_repo/datasets/derived/hog26_structured_terminal_cf_probe_seed1169001
local_root=datasets/derived/hog26_structured_terminal_cf_probe_seed1169001
report_root=reports/hog26_structured_terminal_cf_probe_seed1169001
checkpoint_root=checkpoints/hog26_structured_action_value_seed1169101
python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
prime_bin=${PRIME_BIN:-/Users/sam/.local/bin/prime}

mkdir -p "$local_root" "$report_root" "$checkpoint_root"
[[ ! -e "$report_root/SUPERVISOR_COMPLETE" ]] || exit 0

ssh_args=(-i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=15)
terminate_owned_pod() {
  "$prime_bin" pods terminate "$pod_id" --plain -y || true
}
remote_complete() {
  ssh "${ssh_args[@]}" "$remote_host" "test -f '$remote_root/COMPLETE'"
}
remote_alive() {
  ssh "${ssh_args[@]}" "$remote_host" \
    "pgrep -f '[r]un_hog26_structured_terminal_cf_probe|[c]ollect_terminal_counterfactual_corpus' >/dev/null"
}

while ! remote_complete; do
  if ! remote_alive; then
    printf '%s\n' 'remote-exited-before-complete' > "$report_root/FAILED"
    terminate_owned_pod
    exit 1
  fi
  date -u '+waiting %Y-%m-%dT%H:%M:%SZ'
  sleep 60
done

terminate_after_copy=1
trap 'if [[ ${terminate_after_copy:-0} == 1 ]]; then terminate_owned_pod; fi' EXIT
rsync_ssh="ssh -i $ssh_key -o StrictHostKeyChecking=no -o ConnectTimeout=15"
rsync -a --partial -e "$rsync_ssh" "$remote_host:$remote_root/" "$local_root/"
rsync -a -e "$rsync_ssh" \
  "$remote_host:$remote_repo/node_authority_structured_1169001.json" \
  "$report_root/node_authority.json"

"$python_bin" - "$local_root" "$report_root/node_authority.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
authority = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
expected = {
    "schema": "clasher.structured_terminal_cf_node_authority.v1",
    "pod_id": "670a8d184c12464cb02a73eb17e7a860",
    "source_archive_sha256": "79ff376864dcd30360795d02f9199b9494fbf562d63e49d5c3442955950f271b",
    "policy_sha256": "28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372",
    "collector_sha256": "fd9c07a7ef1889f2d9d8eae59af287893b895ef0ece2654612213f44f83710e7",
    "combine_sha256": "2349b70eedaeb27c2655599f0f01c332e9dd51b1ef5ee2ea20ece979e4b94b04",
    "runner_sha256": "cb4961295db53f5b33d1c41aa1da55d85aeefb779255f7eae30a1362f45b12e0",
    "wrapper_sha256": "08ebe6e149c3290330d5dd332a8f470f68ead2087f207bb3426dd57d27d9994d",
    "fit_sha256": "86d53b0e0d5d6167266f55f53b032f0165e9b9901453a7d5bf163f1d267673f4",
    "structured_model_sha256": "5ea560ab37700a145955af3c6f472e7ccf4ebf3260d937e2c11add38c5dba0ed",
    "train_games": 300,
    "validation_games": 100,
    "states_per_game": 16,
    "query_stride": 16,
    "structured_state_contract": "public-actor-v1",
}
for key, value in expected.items():
    if authority.get(key) != value:
        raise SystemExit(f"remote structured authority mismatch: {key}")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
if manifest.get("structured_state_contract") != "public-actor-v1":
    raise SystemExit("structured corpus manifest contract mismatch")
if int(manifest.get("query_stride", 0)) != 16:
    raise SystemExit("structured corpus query stride mismatch")
if int(manifest["counts"]["train"]) < 3500:
    raise SystemExit("structured train root gate failed")
if int(manifest["counts"]["validation"]) < 1100:
    raise SystemExit("structured validation root gate failed")
if authority["policy_sha256"] not in set(manifest["inputs"].values()):
    raise SystemExit("structured corpus policy authority mismatch")
for split, count in (("train", 300), ("validation", 100)):
    report = json.loads((root / f"{split}.json").read_text(encoding="utf-8"))
    if report.get("structured_state_contract") != "public-actor-v1":
        raise SystemExit(f"{split} report lost structured state contract")
    ids = {
        int(path.stem.split("_")[1])
        for path in (root / split / "shards").glob("game_*.json")
    }
    if ids != set(range(count)):
        raise SystemExit(f"{split} structured game coverage mismatch")
    shapes = report["array_shapes"]
    for name in (
        "structured_entity_ids",
        "structured_entity_features",
        "structured_entity_mask",
        "structured_hand_ids",
        "structured_global_features",
    ):
        if name not in shapes or int(shapes[name][0]) != int(report["states_collected"]):
            raise SystemExit(f"{split} missing aligned {name}")
policy = Path(
    "checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt"
)
if hashlib.sha256(policy.read_bytes()).hexdigest() != authority["policy_sha256"]:
    raise SystemExit("local policy differs from structured corpus authority")
local_sources = {
    "collector_sha256": Path("scripts/collect_terminal_counterfactual_corpus.py"),
    "combine_sha256": Path("scripts/combine_terminal_counterfactual_corpora.py"),
    "runner_sha256": Path(
        "scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh"
    ),
    "wrapper_sha256": Path(
        "scripts/run_hog26_structured_terminal_cf_probe_seed1169001.sh"
    ),
}
for field, path in local_sources.items():
    if hashlib.sha256(path.read_bytes()).hexdigest() != authority[field]:
        raise SystemExit(f"local structured source differs: {path}")
local_fit_sources = {
    Path("scripts/fit_structured_public_action_value.py"): (
        "9a90416aeac45a491bd504d8583480e8d889bc5a491bd528e39a13e03afea8f5"
    ),
    Path("src/clasher/rl/structured_action_value.py"): (
        "fc3953050bbd86d6743a161d0c28803d3e39f5af7ceb00a0ca2be8debcfa3a0a"
    ),
    Path("scripts/finalize_hog26_structured_action_value_probe.py"): (
        "cf8e3611d7c3b237dd292014e3f72824e6edd06cc9c80c0d1f62f95c1a9f4b40"
    ),
    Path("scripts/verify_hog26_structured_terminal_cf_corpus.py"): (
        "88b2a396f27ebfb6a0a01418d3a405aafddc2858caf12ea441112ba989369359"
    ),
}
for path, expected_hash in local_fit_sources.items():
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise SystemExit(f"local structured fit source differs: {path}")
PY

"$python_bin" scripts/verify_hog26_structured_terminal_cf_corpus.py \
  --root "$local_root" --output "$report_root/corpus_quality.json"

terminate_owned_pod
terminate_after_copy=0
"$prime_bin" pods list --plain --output json > "$report_root/pods_after_termination.json"

env PYTHONPATH=src:. OMP_NUM_THREADS=4 "$python_bin" \
  scripts/fit_structured_public_action_value.py \
    --policy checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt \
    --corpus "$local_root/train.npz" \
    --corpus-report "$local_root/train.json" \
    --corpus-manifest "$local_root/manifest.json" \
    --validation-corpus "$local_root/validation.npz" \
    --validation-report "$local_root/validation.json" \
    --output "$checkpoint_root/member_0.pt" \
    --report "$report_root/member_0.json" \
    --seed 1169101 --validation-split-seed 1169102 \
    --epochs 120 --patience 25 --batch-size 64 \
    --learning-rate 0.0003 --weight-decay 0.0005 \
    --d-model 64 --num-heads 4 --num-layers 1 --hidden-size 128 \
    --torch-threads 8 --device cpu \
    > "$report_root/member_0.log" 2>&1

if env PYTHONPATH=src:. "$python_bin" \
  scripts/finalize_hog26_structured_action_value_probe.py \
    --report "$report_root/member_0.json" \
    --output "$report_root/decision.json" \
    > "$report_root/decision.log" 2>&1; then
  printf '%s\n' 'hog26_structured_action_value_probe_passed_v1' \
    > "$report_root/PASSED"
else
  printf '%s\n' 'hog26_structured_action_value_probe_rejected_v1' \
    > "$report_root/REJECTED"
fi

printf '%s\n' 'hog26_structured_terminal_cf_probe_seed1169001_complete_v1' \
  > "$report_root/SUPERVISOR_COMPLETE"
