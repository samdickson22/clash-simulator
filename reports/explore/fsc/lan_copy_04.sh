#!/usr/bin/env bash
# FSC U4: one LAN copy of the staged FSC runtime 127x03 -> 127x04 (run ON 127x04 by host_session.sh launch; pulls).
# Source: 03's own staged FSC prefix (repo without the x4s2/fsc overlays, native, inputs, staging.json); read-only there.
# Destination: the fresh 04 prefix only. No --delete. Dry-run listing first. Pin SHAs checked at both ends:
# 03's values come from 03's staging.json (computed on 03 at its staging); 04's are computed here after the copy.
set -euo pipefail
J03=/mpac/sdicks02/jobs/clasher/fsc-03-20261013; J04=/mpac/sdicks02/jobs/clasher/fsc-04-20261013
[ "$(hostname)" = 127x04 ] && [ -d "$J04/bundle" ] && [ ! -e "$J04/repo" ] && [ ! -e "$J04/native" ] && [ ! -e "$J04/inputs" ]
mkdir -p "$J04/logs"
args=(-a --rsync-path='nice -n 19 rsync' --exclude=/repo/reports/explore/x4s2/ --exclude=/repo/reports/explore/fsc/
      --exclude=__pycache__ --exclude='*.pyc'
      "127x03:$J03/repo" "127x03:$J03/native" "127x03:$J03/inputs" "127x03:$J03/staging.json" "$J04/")
rsync --dry-run --itemize-changes "${args[@]}" > "$J04/logs/lan-copy-dry-run.txt"
echo "dry-run: $(wc -l < "$J04/logs/lan-copy-dry-run.txt") entries; deletions: $(grep -c '^\*deleting' "$J04/logs/lan-copy-dry-run.txt" || true)"
! grep -q '^\*deleting' "$J04/logs/lan-copy-dry-run.txt"
nice -n 19 rsync "${args[@]}"
mv "$J04/staging.json" "$J04/logs/staging-03.json"
python3 -I - "$J04" <<'EOF'
import hashlib, json, sys
from pathlib import Path
J = Path(sys.argv[1]); s03 = json.loads((J/'logs/staging-03.json').read_text())
assert s03['host'] == '127x03'
pins = {'native/clasher_core.abi3.so': ('44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2', s03['native_sha256']),
        'inputs/main02.pt': ('d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed', s03['inputs_sha256']['main02.pt']),
        'inputs/R3a.pt': ('37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85', s03['inputs_sha256']['R3a.pt'])}
out = {}
for rel, (pin, at03) in pins.items():
    at04 = hashlib.sha256((J/rel).read_bytes()).hexdigest()
    assert pin == at03 == at04, rel
    out[rel] = at04
print(json.dumps(dict(lan_copy='ok', pins_equal_at_03_and_04=out)))
EOF
