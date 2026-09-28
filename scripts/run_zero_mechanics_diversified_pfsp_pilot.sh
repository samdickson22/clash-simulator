#!/bin/zsh

set -euo pipefail

repo_root=${0:A:h:h}
cd "$repo_root"

initializer_root=reports/accepted6m_zero_mechanics_rl_initializer_seed1056701/gameplay
initializer_marker="$initializer_root/rl_initializer_ready.txt"
selection_report=reports/parent_selection_seed1056503/compact_vs_accepted6m_v3.json
parent_checkpoint=checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt
post260_marker=reports/tv_royale_public_v2_post260_inputs_ready.txt
visual_audit=reports/tv_royale_public_v2_final1000_visual_audit.json
contact_manifest=reports/tv_royale_public_v2_final1000_contact_sheets/manifest.json
run_manifest=datasets/derived/tv_royale_raw_cascade_public_v2_1000_seed1044201/run_manifest.json

if [[ ! -f "$initializer_marker" ]] || \
  [[ $(<"$initializer_marker") != zero_mechanics_rl_initializer_ready_v1 ]]; then
  print -u2 -- "exact zero-mechanics initializer baseline is not ready"
  exit 1
fi
if [[ ! -f "$post260_marker" ]] || \
  [[ $(<"$post260_marker") != post260_evaluation_inputs_ready_v1 ]]; then
  print -u2 -- "clean post-260 human evaluation split is not ready"
  exit 1
fi
for required in "$selection_report" "$visual_audit" "$contact_manifest" "$run_manifest"; do
  if [[ ! -f "$required" ]]; then
    print -u2 -- "missing final visual-audit input: $required"
    exit 1
  fi
done

uv run python - "$selection_report" "$initializer_root/summary.json" "$parent_checkpoint" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

selection_path, summary_path, parent_path = map(Path, sys.argv[1:])
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
selection = json.loads(selection_path.read_text(encoding="utf-8"))
if selection.get("schema") != "zero-mechanics-pfsp-parent-selection-v3":
    raise SystemExit("unsupported PFSP parent-selection schema")
if selection.get("repair_pilot_authorized") is not True:
    raise SystemExit("targeted mechanics repair pilot is not authorized")
if selection.get("targeted_hog_defect") is not True:
    raise SystemExit("parent selection does not identify the bounded Hog-use defect")
if Path(selection.get("challenger_summary", "")).resolve() != summary_path.resolve():
    raise SystemExit("parent selection identifies another initializer summary")
if selection.get("challenger_summary_sha256") != sha(summary_path):
    raise SystemExit("selected initializer summary changed")
if Path(selection.get("challenger_checkpoint", "")).resolve() != parent_path.resolve():
    raise SystemExit("parent selection identifies another checkpoint")
if selection.get("challenger_checkpoint_sha256") != sha(parent_path):
    raise SystemExit("selected PFSP parent changed")
print(json.dumps({"status": "targeted_repair_parent_verified"}))
PY

env PYTHONPATH=src:. uv run python scripts/verify_tv_royale_final_visual_audit.py \
  --audit "$visual_audit" \
  --contact-manifest "$contact_manifest" \
  --run-manifest "$run_manifest" \
  --expected-games 1000 \
  --output reports/tv_royale_public_v2_final1000_visual_audit_verification.json

export CLASHER_PFSP_INITIALIZER_ROOT="$initializer_root"
export CLASHER_PFSP_INITIALIZER_MARKER=zero_mechanics_rl_initializer_ready_v1
export CLASHER_PFSP_PARENT="$parent_checkpoint"
export CLASHER_PFSP_TAG=accepted6m_mechanics_query_pfsp_seed1056201
export CLASHER_PFSP_SPLIT_ROOT=datasets/derived/tv_royale_public_v2_post260_split_seed1056502
export CLASHER_PFSP_START_UPDATE=20
export CLASHER_PFSP_END_UPDATE=24
export CLASHER_PFSP_TRAIN_ACTION_TYPE=0

exec zsh scripts/run_mechanics_slot_diversified_pfsp_pilot.sh
