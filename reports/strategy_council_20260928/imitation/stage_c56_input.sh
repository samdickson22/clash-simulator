#!/usr/bin/env bash
# Hub-only staging of read-only comparison NPZs into a fresh imitation directory.
set -euo pipefail
cd /mpac/sdicks02/repos/clasher
[[ $(hostname -s) == 127x01 ]]
base=reports/strategy_council_20260928/imitation/data
mkdir -p "$base/operations"
.venv/bin/python -B - <<'PY'
from pathlib import Path
root=Path('reports/strategy_council_20260928/c56/data/recon/engine-v3')
files=sorted(str(p.relative_to(root)) for p in root.glob('*/shard-*.npz'))
assert len(files)==1767
Path('reports/strategy_council_20260928/imitation/data/operations/c56-input-files.txt').write_text('\n'.join(files)+'\n')
PY
target=/mpac/sdicks02/repos/clasher/$base/c56-input-v1
ssh 127x03 "mkdir -p '$target'"
rsync -cr --files-from="$base/operations/c56-input-files.txt" \
  reports/strategy_council_20260928/c56/data/recon/engine-v3/ "127x03:$target/"
rsync -crni --files-from="$base/operations/c56-input-files.txt" \
  reports/strategy_council_20260928/c56/data/recon/engine-v3/ "127x03:$target/" \
  > "$base/operations/c56-input-verify.txt"
[[ ! -s "$base/operations/c56-input-verify.txt" ]]
ssh 127x03 "cd /mpac/sdicks02/repos/clasher && bash reports/strategy_council_20260928/fleet/fleet_run.sh imitation-t2-production-03-v1 env CLASHER_C56_RECON='$target' .venv/bin/python -B reports/strategy_council_20260928/imitation/replay_sidecars.py --out '$base/c56-sidecars-v1' --partition 1 --partitions 2 --workers 64"
