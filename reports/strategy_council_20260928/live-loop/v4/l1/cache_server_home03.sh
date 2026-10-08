#!/usr/bin/env bash
# Bounded attached read-only cache service, launched by home fleet_run.sh.
set -euo pipefail
[[ $(hostname -s) == 127x03 ]] || exit 2
label=${1:?fresh service label}; extension=${2:?verified extension prefix}
[[ $label =~ ^v4-cache-transport-server-[a-zA-Z0-9-]+$ && $extension =~ ^v4-cache-unique-[a-zA-Z0-9-]+$ ]] || exit 2
jobs=/mpac/sdicks02/jobs/clasher
code=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/live-loop/v4/l1
python=/mpac/sdicks02/repos/clasher-v4-cpu/.venv/bin/python
"$python" -B - "$jobs/$label.token" <<'PY'
import os,secrets,sys
with os.fdopen(os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
    f.write(secrets.token_hex(32))
PY
exec "$python" -B "$code/cache_transport_v4.py" \
  --source /mpac/sdicks02/repos/clasher-v4-cpu/matches \
  --cache /mpac/sdicks02/repos/clasher-v4-cache --split "$code/../split.json" \
  --inventory "$jobs/$extension-plan.json" --manifest "$jobs/$extension-manifest.json" \
  --token-file "$jobs/$label.token" --ready "$jobs/$label.ready.json" \
  --stop-file "$jobs/$label.stop" --max-seconds 1800
