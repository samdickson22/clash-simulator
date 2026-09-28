#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

corpus_root=${CORPUS_ROOT:-datasets/derived/hog26_phase_balanced_terminal_cf_v3_seed1175001}
report_root=${REPORT_ROOT:-reports/hog26_phase_balanced_terminal_cf_v3_seed1175001}
contract=${CONTRACT:-reports/hog26_phase_balanced_terminal_cf_contract_v1.json}
python_bin=${PYTHON_BIN:-/Users/sam/Desktop/code/clasher/.venv/bin/python}
recovery_exit=${RECOVERY_EXIT:-$report_root/local_recovery.exit}

mkdir -p "$report_root"
[[ ! -e "$report_root/SUPERVISOR_COMPLETE" ]] || exit 0

while [[ ! -e "$corpus_root/PHASE_BALANCED_COMPLETE" ]]; do
  if [[ -f "$recovery_exit" ]]; then
    status=$(<"$recovery_exit")
    if [[ "$status" != 0 ]]; then
      printf '%s\n' "local-recovery-exited-$status" \
        > "$report_root/LOCAL_RECOVERY_FAILED"
      exit 1
    fi
  fi
  date -u '+waiting-local-recovery %Y-%m-%dT%H:%M:%SZ'
  sleep 60
done

env PYTHONPATH=src:. "$python_bin" \
  scripts/verify_hog26_phase_balanced_terminal_cf_corpus.py \
    --root "$corpus_root" \
    --contract "$contract" \
    --output "$report_root/local_verification.json"

"$python_bin" - "$corpus_root" "$contract" "$report_root/local_authority.json" <<'PY'
import hashlib
import json
import platform
import sys
from pathlib import Path

corpus_root = Path(sys.argv[1])
contract = Path(sys.argv[2])
output = Path(sys.argv[3])
artifacts = [
    contract,
    corpus_root / "manifest.json",
    corpus_root / "train.npz",
    corpus_root / "train.json",
    corpus_root / "validation.npz",
    corpus_root / "validation.json",
    Path("scripts/verify_hog26_structured_terminal_cf_corpus.py"),
    Path("scripts/verify_hog26_phase_balanced_terminal_cf_corpus.py"),
]
payload = {
    "schema": "clasher.hog26_phase_balanced_local_recovery_authority.v1",
    "host": platform.node(),
    "machine": platform.machine(),
    "artifacts": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in artifacts
    },
    "promotion_authorized": False,
}
output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
PY

printf '%s\n' 'hog26_phase_balanced_terminal_cf_v3_local_recovery_complete_v1' \
  > "$report_root/SUPERVISOR_COMPLETE"
