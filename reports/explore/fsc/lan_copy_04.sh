#!/usr/bin/env bash
# FSC U4: one LAN copy of the staged FSC runtime 127x03 -> 127x04. Run ON 127x04 by host_session.sh launch (it pulls).
# Exact allowlist from 03's staged prefix: the S1 pin's repo files, the native dir, three inputs, 03's staging.json.
# Read-only at 03 (rsync sender). Destination: the fresh 04 prefix only. No --delete; symlinks are never copied
# (--no-links) and the prefix is checked link-free afterwards. Dry-run listing first. Two rsync connections to 03 in
# total, each a non-persistent SSH with provisioned host keys. Pin SHAs are checked at both ends: 03's values from
# 03's staging.json (computed on 03 at its staging), 04's computed here after the copy. Any failure exits nonzero.
set -euo pipefail
shopt -s inherit_errexit
export LC_ALL=C
fail() { echo "lan_copy_04 FAIL: $*" >&2; exit 1; }
J03=/mpac/sdicks02/jobs/clasher/fsc-03-20261013; J04=/mpac/sdicks02/jobs/clasher/fsc-04-20261013
SSHOPT='ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ControlPersist=no -o StrictHostKeyChecking=yes -o UpdateHostKeys=no'
STAGE="python3 -I $J04/bundle/fsc/stage.py"
if [ "$(hostname)" != 127x04 ]; then fail "not 127x04"; fi
if [ "$(realpath -e "$J04")" != "$J04" ]; then fail "$J04 not canonical"; fi
if [ ! -d "$J04/bundle" ] || [ -L "$J04/bundle" ]; then fail "no bundle"; fi
for d in repo native inputs staging.json; do
  if [ -e "$J04/$d" ] || [ -L "$J04/$d" ]; then fail "$J04/$d already exists"; fi
done
if [ ! -d "$J04/logs" ] || [ -L "$J04/logs" ]; then fail "no logs dir"; fi
$STAGE allowlist "$J04/bundle" "$J04/logs/repo-allowlist.txt"
{ sed 's|^|repo/|' "$J04/logs/repo-allowlist.txt"; printf '%s\n' native inputs/main02.pt inputs/R3a.pt inputs/R3a-calibration.json staging.json; } \
  > "$J04/logs/lan-allowlist.txt"
args=(-rt --no-links -e "$SSHOPT" --rsync-path='nice -n 19 rsync' --files-from="$J04/logs/lan-allowlist.txt"
      "127x03:$J03/" "$J04/")
nice -n 19 rsync --dry-run --itemize-changes "${args[@]}" > "$J04/logs/lan-copy-dry-run.txt"
set +e; grep -q '^\*deleting' "$J04/logs/lan-copy-dry-run.txt"; g=$?; set -e
case $g in 0) fail "dry-run lists deletions";; 1) ;; *) fail "grep error $g";; esac
set +e; n=$(grep -c '^>f' "$J04/logs/lan-copy-dry-run.txt"); g=$?; set -e
case $g in 0) ;; *) fail "dry-run lists no files (grep $g)";; esac
echo "dry-run: $n files to receive, 0 deletions" >&2
nice -n 19 rsync "${args[@]}"
mv "$J04/staging.json" "$J04/logs/staging-03.json"
$STAGE nolinks "$J04"
python3 -I - "$J04" <<'EOF'
import hashlib, json, sys
from pathlib import Path
J = Path(sys.argv[1]); s03 = json.loads((J/'logs/staging-03.json').read_text())
assert s03['host'] == '127x03'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
native04 = {str(p.relative_to(J/'native')): sha(p) for p in sorted((J/'native').rglob('*')) if p.is_file()}
assert native04 == s03['native_files'], 'native dir differs from 03'
assert native04['clasher_core.abi3.so'] == s03['native_sha256'] == '44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2'
pins = {'main02.pt': 'd77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed',
        'R3a.pt': '37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85',
        'R3a-calibration.json': 'e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414'}
for name, pin in pins.items():
    assert pin == s03['inputs_sha256'][name] == sha(J/'inputs'/name), name
print(json.dumps(dict(lan_copy='ok', native_files=len(native04), inputs_equal_at_03_and_04=sorted(pins))))
EOF
