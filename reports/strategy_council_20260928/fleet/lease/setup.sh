#!/usr/bin/env bash
set -euo pipefail
source /mpac/sdicks02/repos/clasher-lease/env.sh
b=$CLASHER_LEASE_ROOT
host=$(hostname -s)
who
mkdir -p "$b"/{tools/uv,tools/uv-python,cache,config,share,tmp,envs,build,data,jobs,repo}
rsync -a --bwlimit=100000 --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/tools/uv/ "$b/tools/uv/"
rsync -a --bwlimit=100000 --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/tools/uv-python/cpython-3.12.13-linux-x86_64-gnu "$b/tools/uv-python/"
rsync -a --bwlimit=100000 --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/jobs/clasher/lease-source-20261008/repo/ "$b/repo/"
rsync -a --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/jobs/clasher/lease-source-20261008/source-sha256.json "$b/source-sha256.json"
rsync -a --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/jobs/clasher/lease-source-20261008/historical-pin-drift.json "$b/historical-pin-drift.json"
rsync -a --bwlimit=100000 --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/repos/clasher-local-data/decoded-logic-1e505767 "$b/data/"
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT']); pins=json.loads((b/'source-sha256.json').read_text())
bad=[f for f,h in pins.items() if hashlib.sha256((b/'repo'/f).read_bytes()).hexdigest()!=h]
assert not bad,bad
(b/'jobs/source-verified.json').write_text(json.dumps({'files':len(pins),'mismatches':bad})+'\n')
PY
uv --version
uv python find 3.12.13
if [[ $host != 127x09 && $host != 127x15 ]]; then
  rsync -a --bwlimit=100000 --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/tools/cargo/bin "$b/tools/cargo/"
  mkdir -p "$b/tools/rustup/toolchains"
  rsync -a --bwlimit=100000 --rsync-path='nice -n 10 rsync' 127x01:/mpac/sdicks02/tools/rustup/toolchains/1.97.1-x86_64-unknown-linux-gnu "$b/tools/rustup/toolchains/"
  cd "$CLASHER_ROOT"
  uv sync --frozen --python 3.12.13
  rustc --version
  export PYO3_PYTHON=$CLASHER_ROOT/.venv/bin/python
  bash engine-rs/build.sh
  .venv/bin/python -B - <<'PY'
import site,os
from pathlib import Path
(Path(site.getsitepackages()[0])/'clasher_engine_core.pth').write_text(os.environ['CLASHER_ROOT']+'/engine-rs\n')
PY
  python3 - <<'PY'
import os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT']); root=b/'repo'; fleet=root/'reports/strategy_council_20260928/fleet'
p=fleet/'identity.sh'; s=p.read_text().replace('/mpac/sdicks02/repos/clasher',str(root)).replace('[[ -f /mpac/sdicks02/jobs/clasher/transfer-ready.json ]]','[[ -f '+str(b/'jobs/source-verified.json')+' ]]').replace('/mpac/sdicks02/jobs/clasher',str(b/'jobs')); p.write_text(s)
p=root/'reports/strategy_council_20260928/c56/engine/tools/p16_identity.py';s=p.read_text();s=s.replace('Path.home() / ".cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"',repr(str(b/'data/decoded-logic-1e505767/projectiles.csv')));s=s.replace('CATALOG = \'' ,'CATALOG = Path(\'',1).replace("projectiles.csv'\n", "projectiles.csv')\n",1);p.write_text(s)
PY
  bash reports/strategy_council_20260928/fleet/identity.sh p16 lease-20261008 >"$b/jobs/p16.log" 2>&1
  python3 "$b/record_smoke.py"
fi
bash "$b/gpu_env.sh" >"$b/jobs/gpu-env.log" 2>&1
cd "$CLASHER_ROOT"
"$b/envs/clasher-gpu/bin/python" -B "$b/gpu_check.py" --output "$b/tmp/gpu-check.json" >"$b/jobs/gpu-check.stdout.json" 2>"$b/jobs/gpu-check.log"
