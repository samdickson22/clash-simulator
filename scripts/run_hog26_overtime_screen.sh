#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

python_bin=${PYTHON_BIN:-python}
workers=${WORKERS:-64}
policy=${POLICY:-checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt}
learner_decks=${LEARNER_DECKS:-training_decks/katacr_hog26_only.json}
opponent_decks=${OPPONENT_DECKS:?OPPONENT_DECKS is required}
seed=${SEED:?SEED is required}
game_start=${GAME_START:?GAME_START is required}
games=${GAMES:?GAMES is required}
output_root=${OUTPUT_ROOT:?OUTPUT_ROOT is required}

if ((workers < 1 || games < 1 || game_start < 0)); then
  echo "invalid overtime screen sizes" >&2
  exit 1
fi
mkdir -p "$output_root/shards"

screen_game() {
  local game=$1
  local padded partial
  padded=$(printf '%06d' "$game")
  if [[ -f "$output_root/shards/game_${padded}.json" ]]; then
    return 0
  fi
  partial=$(mktemp "$output_root/shards/.partial_${padded}_XXXXXX")
  env PYTHONPATH=src:. OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    "$python_bin" scripts/audit_runtime_entity_identity.py \
      --policy "$policy" \
      --learner-decks "$learner_decks" \
      --opponent-decks "$opponent_decks" \
      --games 1 --game-offset "$game" --seed "$seed" --device cpu \
      --output "$partial" \
      > "$output_root/shards/game_${padded}.log" 2>&1
  mv "$partial" "$output_root/shards/game_${padded}.json"
}

lanes=$workers
((lanes <= games)) || lanes=$games
pids=()
for ((worker = 0; worker < lanes; worker++)); do
  (
    for ((
      game = game_start + worker;
      game < game_start + games;
      game += lanes
    )); do
      screen_game "$game"
    done
  ) &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
((failed == 0)) || exit 1

"$python_bin" - \
  "$output_root" "$seed" "$game_start" "$games" \
  "$policy" "$learner_decks" "$opponent_decks" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
seed = int(sys.argv[2])
game_start = int(sys.argv[3])
games = int(sys.argv[4])
policy = Path(sys.argv[5])
learner_decks = Path(sys.argv[6])
opponent_decks = Path(sys.argv[7])
reports = []
for game in range(game_start, game_start + games):
    path = root / "shards" / f"game_{game:06d}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema") != "clasher.runtime_entity_identity_audit.v1":
        raise SystemExit(f"unexpected overtime screen report: {path}")
    if int(report["unknown_visible_entities"]) != 0:
        raise SystemExit(f"overtime screen found unknown identity: {path}")
    rows = report["game_rows"]
    if len(rows) != 1 or int(rows[0]["game"]) != game:
        raise SystemExit(f"overtime screen game mismatch: {path}")
    reports.append((path, rows[0]))
selected = [
    int(row["game"]) for _path, row in reports if int(row["ticks"]) > 3600
]
manifest = {
    "schema": "clasher.hog26_overtime_screen.v2",
    "seed": seed,
    "game_start": game_start,
    "games": games,
    "selection_rule": "terminal_tick_strictly_greater_than_3600",
    "selected_games": selected,
    "selected_count": len(selected),
    "unknown_visible_entities": 0,
    "input_sha256": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            policy,
            learner_decks,
            opponent_decks,
            Path("src/clasher/rl/deck_pool.py"),
            Path("src/clasher/rl/selfplay_env.py"),
        )
    },
    "report_sha256": {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path, _row in reports
    },
}
(root / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

printf '%s\n' 'hog26_overtime_screen_complete_v2' > "$output_root/COMPLETE"
