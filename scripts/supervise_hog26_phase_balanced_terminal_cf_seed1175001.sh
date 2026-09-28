#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

remote_host=${REMOTE_HOST:-ubuntu@204.12.170.121}
pod_id=${POD_ID:-121af294c51d446198fe71365c53c3e0}
ssh_key=${SSH_KEY:-/Users/sam/.ssh/id_ed25519_prime_clasher}
remote_repo=/home/ubuntu/clasher
remote_root=$remote_repo/datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001
local_root=datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001
report_root=reports/hog26_phase_balanced_terminal_cf_v3_seed1175001
contract=reports/hog26_phase_balanced_terminal_cf_contract_v1.json
python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
prime_bin=${PRIME_BIN:-/Users/sam/.local/bin/prime}

mkdir -p "$local_root" "$report_root"
[[ ! -e "$report_root/SUPERVISOR_COMPLETE" ]] || exit 0

ssh_args=(-i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=15)
terminate_owned_pod() {
  "$prime_bin" pods terminate "$pod_id" --plain -y || true
}
remote_complete() {
  ssh "${ssh_args[@]}" "$remote_host" \
    "test -f '$remote_root/PHASE_BALANCED_COMPLETE'"
}
remote_alive() {
  ssh "${ssh_args[@]}" "$remote_host" \
    "pgrep -f '[r]un_hog26_phase_balanced_terminal_cf|[c]ollect_terminal_counterfactual_corpus|[c]ombine_terminal_counterfactual_corpora' >/dev/null"
}

copy_remote_output() {
  local rsync_ssh
  rsync_ssh="ssh -i $ssh_key -o StrictHostKeyChecking=no -o ConnectTimeout=15"
  rsync -a --partial -e "$rsync_ssh" "$remote_host:$remote_root/" "$local_root/"
  if ssh "${ssh_args[@]}" "$remote_host" \
    "test -f '$remote_repo/reports/hog26_phase_balanced_terminal_cf_v3_seed1175001/node_authority.json'"; then
    rsync -a -e "$rsync_ssh" \
      "$remote_host:$remote_repo/reports/hog26_phase_balanced_terminal_cf_v3_seed1175001/node_authority.json" \
      "$report_root/node_authority.remote.json"
  fi
}

while ! remote_complete; do
  if ! remote_alive; then
    printf '%s\n' 'remote-exited-before-phase-balanced-complete' \
      > "$report_root/FAILED"
    # A strict remote verifier can fail after collection and merge. Preserve
    # every recoverable artifact before releasing the ephemeral root disk.
    copy_remote_output || true
    terminate_owned_pod
    exit 1
  fi
  date -u '+waiting %Y-%m-%dT%H:%M:%SZ'
  sleep 60
done

terminate_after_copy=1
trap 'if [[ ${terminate_after_copy:-0} == 1 ]]; then terminate_owned_pod; fi' EXIT
copy_remote_output

"$python_bin" - "$report_root/node_authority.remote.json" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

authority = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expected = {
    "schema": "clasher.hog26_phase_balanced_node_authority.v3",
    "pod_id": "121af294c51d446198fe71365c53c3e0",
    "source_archive_sha256": "c64df399c388b6f1506721f6fefddc15606ddd6c81d341db8958226ca647a27f",
    "contract_sha256": "8354b54a0a5d35c45b761fea1575198e6ac314c8ff2334dee66f9ab68d169115",
    "policy_sha256": "28f575c95bf5d00478aac7a74b5614016019cb00a3ffd6e17be7c5d2437b4372",
}
for key, value in expected.items():
    if authority.get(key) != value:
        raise SystemExit(f"phase-balanced node authority mismatch: {key}")
paths = {
    "structured_observation": Path("src/clasher/rl/structured_obs.py"),
    "collector": Path("scripts/collect_terminal_counterfactual_corpus.py"),
    "combiner": Path("scripts/combine_terminal_counterfactual_corpora.py"),
    "generic_runner": Path(
        "scripts/run_hog26_terminal_counterfactual_10k_seed1164601.sh"
    ),
    "phase_runner": Path(
        "scripts/run_hog26_phase_balanced_terminal_cf_seed1175001.sh"
    ),
    "base_verifier": Path(
        "scripts/verify_hog26_structured_terminal_cf_corpus.py"
    ),
    "phase_verifier": Path(
        "scripts/verify_hog26_phase_balanced_terminal_cf_corpus.py"
    ),
    "overtime_screen": Path("scripts/run_hog26_overtime_screen.sh"),
    "overtime_supplement": Path("scripts/run_hog26_overtime_supplement.sh"),
    "phase_stratified_merger": Path(
        "scripts/merge_phase_stratified_counterfactual_corpora.py"
    ),
    "schedule": Path("src/clasher/rl/counterfactual_schedule.py"),
    "recurrent_state": Path("src/clasher/rl/recurrent_state_contract.py"),
}
for name, path in paths.items():
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != authority["pipeline_sources"][name]:
        raise SystemExit(f"phase-balanced local source differs: {path}")
for path, expected_hash in (
    (
        Path("reports/hog26_phase_balanced_terminal_cf_contract_v1.json"),
        authority["contract_sha256"],
    ),
    (
        Path("checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt"),
        authority["policy_sha256"],
    ),
    (
        Path("training_decks/katacr_hog26_only.json"),
        authority["learner_decks_sha256"],
    ),
    (
        Path("datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json"),
        authority["train_opponents_sha256"],
    ),
    (
        Path("datasets/deck_curriculum_v3_seed1056101/validation.json"),
        authority["validation_opponents_sha256"],
    ),
):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise SystemExit(f"phase-balanced local authority differs: {path}")
PY

env PYTHONPATH=src:. "$python_bin" \
  scripts/verify_hog26_phase_balanced_terminal_cf_corpus.py \
    --root "$local_root" \
    --contract "$contract" \
    --output "$report_root/local_verification.json"

terminate_owned_pod
terminate_after_copy=0
"$prime_bin" pods list --plain --output json > "$report_root/pods_after_termination.json"
printf '%s\n' 'hog26_phase_balanced_terminal_cf_v3_seed1175001_supervised_complete_v1' \
  > "$report_root/SUPERVISOR_COMPLETE"
