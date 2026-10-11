#!/bin/bash
# Phase 2 (proposal §C.2): ONE read of T1's 32 capture.pkl.gz from 127x03, run on 05.
# Only inside a coordinator-declared 03 window, after Amendment 4 adoption.
# One ssh session (rsync), no ControlMaster, remote rsync at nice 19 on one core,
# 32 MiB/s cap, only the files corpora.json pins (never games/ or local-complete.json),
# nothing written on 03. Then SHA-verify on 05 (verify_captures.py) and post "released".
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=${MACREG_WORK:-/mpac/sdicks02/jobs/clasher/mac-registration-20261011}
REMOTE=/mpac/sdicks02/jobs/clasher/t1-20261010-r1/corpus-reviewed-03-r1/captures
CORPORA=$HERE/../t1/corpora/corpus-03-a51ea64c/corpora.json
[ "$(hostname)" = 127x05 ] || { echo "run on 127x05" >&2; exit 2; }
[ "$(sha256sum "$CORPORA" | cut -d' ' -f1)" = 3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13 ] || { echo "corpora.json pin" >&2; exit 2; }
[ ! -e "$W/captures" ] || { echo "$W/captures exists; never overwrite" >&2; exit 2; }
mkdir -p "$W/captures"
python3 - "$CORPORA" "$REMOTE" > "$W/capture-files.txt" <<'PY'
import json, sys
corpora, remote = json.load(open(sys.argv[1])), sys.argv[2].rstrip("/") + "/"
paths = sorted(p for t in corpora["tiers"].values() for p in t["source_capture_shas"])
assert len(paths) == 32 and all(p.startswith(remote) and p.endswith("/capture.pkl.gz") for p in paths)
names = [p[len(remote):] for p in paths]
assert all(n.count("/") == 1 and "games" not in n and "local-complete" not in n for n in names)
print("\n".join(names))
PY
date -u +"start %FT%TZ" | tee "$W/capture-copy.log"
nice -n 19 taskset -c 63 rsync -a --files-from="$W/capture-files.txt" --bwlimit=32768 \
  --rsync-path='nice -n 19 taskset -c 63 rsync' \
  -e 'ssh -o ControlMaster=no -o ControlPath=none -o BatchMode=yes' \
  "127x03:$REMOTE/" "$W/captures/" 2>&1 | tee -a "$W/capture-copy.log"
date -u +"end %FT%TZ" | tee -a "$W/capture-copy.log"
nice -n 19 taskset -c 63 python3 "$HERE/verify_captures.py" --corpora "$CORPORA" --captures "$W/captures" --output "$W/capture-copy-receipt.json"
