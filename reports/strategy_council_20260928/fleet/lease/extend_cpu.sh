#!/usr/bin/env bash
set -euo pipefail
source /mpac/sdicks02/repos/clasher-lease/env.sh
b=$CLASHER_LEASE_ROOT
host=$(hostname -s)
[[ $host == 127x09 || $host == 127x15 ]]
who
"$HOME/.local/bin/fleet-console-users"
python3 "$b/audit.py"
# Verify the target's engine pins before accepting the previously built peer binary.
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT']);pins=json.loads((b/'source-sha256.json').read_text());engine={f:h for f,h in pins.items() if f.startswith('engine-rs/')}
assert engine
assert all(hashlib.sha256((b/'repo'/f).read_bytes()).hexdigest()==h for f,h in engine.items())
(b/'jobs/cpu-upgrade-engine-pins.json').write_text(json.dumps(engine,indent=2)+'\n')
PY
ssh -o BatchMode=yes 127x11 'nice -n 10 python3 -' >"$b/jobs/cpu-upgrade-peer-native.json" <<'PY'
import hashlib,json
from pathlib import Path
b=Path('/mpac/sdicks02/repos/clasher-lease');pins=json.loads((b/'source-sha256.json').read_text());engine={f:h for f,h in pins.items() if f.startswith('engine-rs/')}
assert all(hashlib.sha256((b/'repo'/f).read_bytes()).hexdigest()==h for f,h in engine.items())
h=hashlib.sha256((b/'repo/engine-rs/clasher_core.abi3.so').read_bytes()).hexdigest()
assert h==(b/'jobs/native.sha256').read_text().strip()
p16=json.loads((b/'jobs/p16.json').read_text());assert p16['checked_episodes']==12 and p16['mismatches']==[]
print(json.dumps({'host':'127x11','engine_source_pins':engine,'native_sha256':h,'p16':p16}))
PY
python3 - <<'PY'
import json,os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT']);peer=json.loads((b/'jobs/cpu-upgrade-peer-native.json').read_text());ours=json.loads((b/'jobs/cpu-upgrade-engine-pins.json').read_text());assert peer['engine_source_pins']==ours
PY
rsync -a --bwlimit=50000 --rsync-path='nice -n 10 rsync' 127x11:/mpac/sdicks02/repos/clasher-lease/repo/engine-rs/clasher_core.abi3.so "$b/tmp/cpu-upgrade-clasher_core.abi3.so"
python3 - <<'PY'
import hashlib,json,os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT']);peer=json.loads((b/'jobs/cpu-upgrade-peer-native.json').read_text());p=b/'tmp/cpu-upgrade-clasher_core.abi3.so';assert hashlib.sha256(p.read_bytes()).hexdigest()==peer['native_sha256'];p.replace(b/'repo/engine-rs/clasher_core.abi3.so')
PY
cd "$CLASHER_ROOT"
uv sync --frozen --python 3.12.13
.venv/bin/python -B - <<'PY'
import site,os,platform
from pathlib import Path
assert platform.python_version()=='3.12.13'
(Path(site.getsitepackages()[0])/'clasher_engine_core.pth').write_text(os.environ['CLASHER_ROOT']+'/engine-rs\n')
import clasher_core
print(platform.python_version(),clasher_core.__file__)
PY
python3 - <<'PY'
import os
from pathlib import Path
b=Path(os.environ['CLASHER_LEASE_ROOT']);root=b/'repo';fleet=root/'reports/strategy_council_20260928/fleet'
p=fleet/'identity.sh';s=p.read_text()
if str(root) not in s:
 s=s.replace('/mpac/sdicks02/repos/clasher',str(root)).replace('[[ -f /mpac/sdicks02/jobs/clasher/transfer-ready.json ]]','[[ -f '+str(b/'jobs/source-verified.json')+' ]]').replace('/mpac/sdicks02/jobs/clasher',str(b/'jobs'))
p.write_text(s)
p=root/'reports/strategy_council_20260928/c56/engine/tools/p16_identity.py';s=p.read_text().replace('Path.home() / ".cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"','Path('+repr(str(b/'data/decoded-logic-1e505767/projectiles.csv'))+')');p.write_text(s)
PY
bash reports/strategy_council_20260928/fleet/identity.sh p16 cpu-upgrade-20261008 >"$b/jobs/p16.log" 2>&1
python3 "$b/record_smoke.py"
python3 "$b/audit.py"
