#!/usr/bin/env bash
# Build ~/clasher-live/loop/MANIFEST.json (staged copy) for drive.py's start-of-session check, on 05.
#   live/loop/ops/build_mac_manifest.sh COMMIT OUT.json UNITS_SPEC EXPORT_DIR [EXTRA ...]
#     COMMIT      main commit holding the deployed live files (drive.py included)
#     UNITS_SPEC  the session's --units value, e.g. yolo:$HOME/clasher-live/yolo/models/X.mlpackage:$HOME/clasher-live/yolo/classes.json:cu=ne,agnostic=1,offsets=$HOME/clasher-live/yolo/ground-offsets-v2.json
#     EXPORT_DIR  the session's --export (perception export dir on the Mac)
#     EXTRA       more Mac files under ~/clasher-live the session loads (e.g. LL_HAND_MODEL's hand.pt + vocab.json)
# Live files: what drive.py imports (14 .py) + digits.npz, hashed from COMMIT. Bot files: reports/live/loop/bot-snapshot-20261016.sha256
# (the Mac's pinned bot/, not main). Model files (mlpackage dir, classes.json, offsets file, export dir): hashed on the Mac
# read-only, stored relative to the code tree (../../../...). Then every entry is checked against the Mac's bytes
# (read-only) and differences are printed (drive.py differs until it is deployed).
set -euo pipefail
COMMIT=$1; OUT=$2; SPEC=$3; EXPORT=$4; shift 4; EXTRA="$*"
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
TREE=/Users/sam/clasher-live/loop/code/15117b86b-w1
LIVE="live/loop/drive.py live/loop/battlelog.py live/loop/canvas.py live/loop/deckread.py live/loop/frames.py live/loop/handread.py
live/loop/overlay.py live/loop/ownplay.py live/loop/towers.py live/loop/digits.npz live/perception/common.py live/perception/events.py
live/perception/infer.py live/perception/unit_filter.py live/perception/yolo_units.py"
body=${SPEC#yolo:}; MLP=${body%%:*}; rest=${body#*:}; CLASSES=${rest%%:*}; OFFS=$(echo "$rest" | tr ',' '\n' | sed -n 's/^.*offsets=//p')
for p in "$MLP" "$CLASSES" "$OFFS" "$EXPORT" $EXTRA; do case $p in /Users/sam/clasher-live/*) ;; *) echo "not under ~/clasher-live: $p"; exit 2;; esac; done
T=$(mktemp -d)
# model / export files hashed on the Mac (absolute), mapped to ../../../<path under ~/clasher-live>
ssh macmini-fleet "find '$MLP' '$EXPORT' -type f ! -name '.DS_Store' -print0 | xargs -0 shasum -a 256; shasum -a 256 '$CLASSES' '$OFFS' $EXTRA; echo __RC=\$?" > $T/models.raw
grep -q '^__RC=0' $T/models.raw || { echo "model hashing failed"; cat $T/models.raw; exit 3; }
grep -v '^__RC=' $T/models.raw | sed 's#  /Users/sam/clasher-live/#  ../../../#' > $T/models.sha
# BOT_SNAPSHOT: a sha256 list of the Mac's bot/ files (default: the pinned 2026-10-16 snapshot; a bot package adds its files)
cat "${BOT_SNAPSHOT:-$REPO/reports/live/loop/bot-snapshot-20261016.sha256}" $T/models.sha > $T/snapshot.sha
python3 "$REPO/live/loop/manifest_build.py" --repo "$REPO" --commit "$COMMIT" --out "$OUT" --snapshot $T/snapshot.sha $LIVE
# check every entry against the Mac (read-only)
python3 -c "import json;[print(h+'  '+r) for r,h in json.load(open('$OUT'))['files'].items()]" > $T/all.sha
ssh macmini-fleet "cd $TREE && shasum -a 256 -c - 2>&1 | grep -v ': OK$'; echo __RC=done" < $T/all.sha | grep -v '^__RC=' || true
echo "entries: $(wc -l < $T/all.sha)  manifest sha256: $(sha256sum "$OUT" | cut -d' ' -f1)"
