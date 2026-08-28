#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
audit_repo=${AUDIT_REPO:-/home/ubuntu/clasher-bench}
audit_report=${AUDIT_REPORT:-$audit_repo/reports/simple_gym_capacity_matrix_e48_f64_20260828.json}
audit_pattern=${AUDIT_PATTERN:-scripts/audit_simple_gym_capacity_matrix.py}
python_bin=${PYTHON_BIN:-python}
poll_seconds=${POLL_SECONDS:-30}

while pgrep -f "$audit_pattern" >/dev/null; do
  sleep "$poll_seconds"
done

[[ -f "$audit_report" ]] || {
  echo "capacity audit exited without publishing $audit_report" >&2
  exit 1
}

"$python_bin" - "$audit_report" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not report["acceptance"]["deterministic"]:
    raise SystemExit("capacity audit repetitions were not deterministic")
if not report["acceptance"]["all_active_rows_native_and_committed"]:
    raise SystemExit("capacity audit found a non-native or uncommitted active row")
decks = report["deck_names"]
hog_cards = {
    "Cannon",
    "Fireball",
    "HogRider",
    "IceGolem",
    "IceSpirit",
    "Musketeer",
    "Skeletons",
    "Log",
}
matches = [index for index, cards in enumerate(decks) if set(cards) == hog_cards]
if len(matches) != 1:
    raise SystemExit(f"expected one exact Hog 2.6 deck, found {matches}")
hog = matches[0]
rows = [
    row
    for row in report["rows"]
    if row["player0_deck"] == hog and row["player1_deck"] == hog
]
if len(rows) != 1:
    raise SystemExit("capacity audit has no unique Hog 2.6 mirror row")
row = rows[0]
if row["invalid_active_row"]:
    raise SystemExit("Hog 2.6 mirror row was not native and committed")
if row["peak_entities"] > 48 or row["peak_effects"] > 64:
    raise SystemExit(f"Hog 2.6 mirror exceeds 48/64: {row}")
print(json.dumps({"hog_deck_index": hog, "hog_mirror": row}, sort_keys=True))
PY

cd "$repo_root"
PYTHON_BIN="$python_bin" scripts/run_hog26_capacity48_cuda_batch_ab.sh
