#!/usr/bin/env bash
# Read-only, bounded service; invoke under home fleet_run.sh.
set -euo pipefail
host=$(hostname -s)
case $host in
  127x01) python=/mpac/sdicks02/envs/clasher-gpu/bin/python; source=/mpac/sdicks02/repos/clasher-v4-data/matches ;;
  127x03) python=/mpac/sdicks02/repos/clasher-v4-cpu/.venv/bin/python; source=/mpac/sdicks02/repos/clasher-v4-cpu/matches ;;
  *) exit 2 ;;
esac
label=${1:?fresh label}; inventory=${2:?pinned inventory}; manifest=${3:?verified manifest}
[[ $label =~ ^v4-cache-transport-server-[a-zA-Z0-9-]+$ ]] || exit 2
jobs=/mpac/sdicks02/jobs/clasher
code=/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/live-loop/v4/l1
"$python" -B - "$jobs/$label.token" <<'PY'
import os,secrets,sys
with os.fdopen(os.open(sys.argv[1],os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
    f.write(secrets.token_hex(32))
PY
exec "$python" -B "$code/cache_transport_v4.py" --source "$source" \
  --cache /mpac/sdicks02/repos/clasher-v4-cache --split "$code/../split.json" \
  --inventory "$inventory" --manifest "$manifest" --token-file "$jobs/$label.token" \
  --ready "$jobs/$label.ready.json" --stop-file "$jobs/$label.stop" --max-seconds 3600
