#!/bin/bash
# Phase 2 as declared by the coordinator GO (Oct 12): ONE read-only ssh session 05 -> 127x03
# (ControlMaster off), which first sha256sums the 32 pinned capture.pkl.gz on 03 (SHA "before"),
# then streams exactly those 32 files as a tar to stdout. Nothing is written on 03; never games/
# or local-complete.json. Remote work at nice 19 on core 63; local cap 32 MiB/s (ratelimit.py).
# Then verify_captures.py re-hashes every file on 05 (SHA "after") against corpora.json.
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
assert all(n.count("/") == 1 and n.startswith("corpus-") and "games" not in n and "local-complete" not in n for n in names)
print("\n".join(names))
PY
FILES=$(tr '\n' ' ' < "$W/capture-files.txt")
date -u +"start %FT%TZ" | tee "$W/capture-copy.log"
ssh -o ControlMaster=no -o ControlPath=none -o BatchMode=yes 127x03 \
  "cd $REMOTE && nice -n 19 taskset -c 63 sha256sum $FILES 1>&2 && exec nice -n 19 taskset -c 63 tar -cf - $FILES" \
  2> "$W/remote-sha256.txt" | nice -n 19 taskset -c 63 python3 "$HERE/ratelimit.py" 33554432 | nice -n 19 taskset -c 63 tar -xf - -C "$W/captures"
date -u +"end %FT%TZ" | tee -a "$W/capture-copy.log"
nice -n 19 taskset -c 63 python3 "$HERE/verify_captures.py" --corpora "$CORPORA" --captures "$W/captures" \
  --remote-sha256 "$W/remote-sha256.txt" --output "$W/capture-copy-receipt.json"
