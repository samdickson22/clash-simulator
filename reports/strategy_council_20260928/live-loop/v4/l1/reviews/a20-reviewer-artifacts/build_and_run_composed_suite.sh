#!/bin/bash
# Reviewer: compose A19 r5 tests/fixtures + A20 composed runtime (11 pinned files) in a
# scratch tree whose parents[2] mirrors l1, then run every test_a*.py (A19 + A20) under
# Python 3.12.12 / nice 19. Usage: build_and_run_composed_suite.sh <scratch-dir> <log>
set -euo pipefail
L=$(cd "$(dirname "$0")/../.." && pwd); S=$1; LOG=$2
PY=${PY:-$HOME/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12}
mkdir -p "$S/prepared/composed"; cd "$S"
for d in receipts amendments; do ln -sfn "$L/$d" $d; done
for d in amendment18-review-r2 amendment19-review-r5 amendment20-review-r1; do ln -sfn "$L/prepared/$d" prepared/$d; done
C=prepared/composed
cp -p "$L"/prepared/amendment19-review-r5/* $C/
cp -p "$L"/prepared/amendment20-review-r1/composed-runtime/*.py $C/
cp -p "$L"/prepared/amendment20-review-r1/test_a20_*.py "$L"/prepared/amendment20-review-r1/execution-plan-a19-r5-a20-r1.json $C/
ln -sfn "$L/prepared/amendment20-review-r1/composed-runtime" $C/composed-runtime
(cd $C && sha256sum a19_*.py a20_io.py) > "$LOG.runtime-sha256"
PYTHONPATH=$S/$C nice -n 19 "$PY" -B -m unittest discover -s $C -p 'test_a*.py' -v > "$LOG" 2>&1 || echo "exit=$?" >> "$LOG"
