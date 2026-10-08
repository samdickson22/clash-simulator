#!/usr/bin/env bash
# Detached recovery continuation; never repairs engine code or changes baselines.
set -euo pipefail
[[ $(hostname -s) == 127x01 ]]
base=/mpac/sdicks02
root=$base/repos/clasher
jobs=$base/jobs/clasher
fleet=$root/reports/strategy_council_20260928/fleet
while [[ ! -f "$jobs/recovery-copy-20261008.exit" ]]; do sleep 15; done
[[ $(cat "$jobs/recovery-copy-20261008.exit") == 0 ]]
[[ $(cat "$jobs/recovery-source-manifest-20261008.exit") == 0 ]]
cp "$jobs/recovery-overlay/"* "$fleet/"
source "$base/env.sh"
cd "$root"
who
bash "$fleet/fleet_run.sh" --worker recovery-bootstrap-20261008 bash "$fleet/bootstrap.sh" >> "$jobs/recovery-bootstrap-20261008.log" 2>&1
sha256sum engine-rs/clasher_core.abi3.so | cut -d ' ' -f1 > "$jobs/recovery-native.sha256"
export CLASHER_FLEET_SOURCE_MANIFEST=$jobs/recovery-source-mac.json
export CLASHER_FLEET_NATIVE_SHA256=$(cat "$jobs/recovery-native.sha256")
.venv/bin/python -B "$fleet/verify_inputs.py" > "$jobs/recovery-verify-inputs.json"
.venv/bin/python -B - <<'PY'
import datetime, hashlib, json
from pathlib import Path
j = Path('/mpac/sdicks02/jobs/clasher')
data = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), hub='127x01',
            source='macmini-fleet:/Users/sam/Desktop/code/clasher',
            source_manifest_sha256=hashlib.sha256((j/'recovery-source-mac.json').read_bytes()).hexdigest(),
            native_sha256=(j/'recovery-native.sha256').read_text().strip(),
            transfer_exit=0, input_verification=json.loads((j/'recovery-verify-inputs.json').read_text()))
(j/'transfer-ready.json.tmp').write_text(json.dumps(data, indent=2)+'\n')
(j/'transfer-ready.json.tmp').replace(j/'transfer-ready.json')
PY
bash "$fleet/fleet_run.sh" recovery-stage6-info-20261008 bash "$fleet/regressions.sh" stage6
bash "$fleet/fleet_run.sh" --worker recovery-gates-20261008 bash "$fleet/gate_sequence.sh" >> "$jobs/recovery-gates-20261008.log" 2>&1
bash "$fleet/fleet_run.sh" --worker recovery-recorded-20261008 bash "$fleet/recorded.sh" >> "$jobs/recovery-recorded-20261008.log" 2>&1
.venv/bin/python -B "$fleet/verify_inputs.py" > "$jobs/recovery-verify-inputs-final.json"
echo 'Hub qualification passed. Fan-out requires a separate launch after inspection.'
