#!/bin/bash
# Build the builder's END-A5 runtime on 05 (never inside T1 trees): a copy of T1's END-preparation
# runtime with its e4v3 package replaced by the A3 source commit T1 used for END (f6cebbaa), then
# only e4v3/fleet_validity.py taken from the adopted TIERS A5 commit (8799a0d6), as T1's committed
# END-A5 inventory diff (900bae16) certifies. Verified file-for-file (frozen prepare_bundle.runtime_pins
# + measurement_files + native SHA) against T1's committed END-A3 manifest for 01 (bd9804c3) with
# that single entry replaced (A4 erratum E3). Fails closed; never overwrites.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
W=${MACREG_WORK:-/mpac/sdicks02/jobs/clasher/mac-registration-20261011}
SOURCE=/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-bundle-preparation-r1/runtime
A3_COMMIT=f6cebbaacfeb67337311c4f929b54285de3679ce
A5_COMMIT=8799a0d6
E4V3_REL=reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3
NATIVE=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so
OUT=$W/runtime-a5
[ ! -e "$OUT" ] || { echo "$OUT exists; never overwrite" >&2; exit 2; }
mkdir -p "$W"
for receipt in END-A3-manifest-01-f6cebbaa.json END-A5-runtime-manifest-inventory-diff.json; do
  [ -e "$W/$receipt" ] || git -C "$REPO" show "origin/main:reports/explore/t1/receipts/$receipt" > "$W/$receipt"
done
cp -a "$SOURCE" "$OUT.partial"
rm -rf "$OUT.partial/$E4V3_REL"
mkdir -p "$OUT.partial/$E4V3_REL"
git -C "$REPO" archive "$A3_COMMIT" "$E4V3_REL" | tar -x -C "$OUT.partial"
git -C "$REPO" show "$A5_COMMIT:$E4V3_REL/fleet_validity.py" > "$OUT.partial/$E4V3_REL/fleet_validity.py"
mv "$OUT.partial" "$OUT"
chmod -R a-w "$OUT"
cd /tmp
OMP_NUM_THREADS=1 nice -n 19 taskset -c 63 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -B - "$HERE" "$OUT" "$NATIVE" \
    "$W/END-A3-manifest-01-f6cebbaa.json" "$W/END-A5-runtime-manifest-inventory-diff.json" <<'PY'
import json, sys
sys.path.insert(0, sys.argv[1])
import macreg_io as io
from pathlib import Path
io.add_e4v3(Path(sys.argv[2]) / io.E4V3_REL)
binding = io.verify_runtime(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
binding.update(source=sys.argv[2], e4v3_source_commit="f6cebbaacfeb67337311c4f929b54285de3679ce",
               fleet_validity_source_commit="8799a0d6", utc=io.utc())
io.write_json(Path(sys.argv[2]).parent / "runtime-a5-binding.json", binding)
print(json.dumps(binding))
PY
