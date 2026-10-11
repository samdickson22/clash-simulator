#!/bin/bash
# Phase 3 on 127x05 (nice 19, core 63, one thread, no timing). Usage: run_phase3.sh build|reference|memory|crosscheck|seal
#   (once)      build_runtime.sh creates and verifies $W/runtime-a3
#   build:      build_sets -> assemble_states -> convert_states --states --expect-fingerprint
#   reference:  student_reference compute (B.6)
#   memory:     memory_check (blocking)
#   crosscheck: student_reference cross-check vs T1's pooled END speed-reference.json (END_SPEED, END_SPEED_SHA256)
#   seal:       seal_receipt (B.7)
# Launch long steps detached (setsid nohup) so they survive a session restart.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=${MACREG_WORK:-/mpac/sdicks02/jobs/clasher/mac-registration-20261011}
RT=$W/runtime-a3  # build_runtime.sh: END-A3-equal runtime (bd9804c3), full check in build/assemble/reference/memory stages
E4V3=$RT/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3
NATIVE=/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so
T1JOB=/mpac/sdicks02/jobs/clasher/t1-20261010-r1
END_DIGESTS=$E4V3/receipts/amendment3-loader-20261011/canonical-row-digests.json
END_DIGESTS_SHA256=648832802ccca885be4359159efdebd52cd1b5e43948d38fdd98e035da08dd4a
CORPORA=$HERE/../t1/corpora/corpus-03-a51ea64c/corpora.json
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
PY="nice -n 19 taskset -c 63 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -B"
RUNTIME=(--runtime-root "$RT" --native "$NATIVE" --end-manifest "$W/END-A3-manifest-01-f6cebbaa.json"
         --extra-path "$RT/imitation/evaluation/runtime_dependencies" --extra-path "$RT/reports/strategy_council_20260928/imitation")
CONVERT_RUNTIME=(--runtime-root "$RT" --native "$NATIVE" --extra-path "$RT/imitation/evaluation/runtime_dependencies"
         --extra-path "$RT/reports/strategy_council_20260928/imitation")
json() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(eval('d'+sys.argv[2]))" "$@"; }
case "${1:?step}" in
build)
  $PY "$HERE/build_sets.py" "${RUNTIME[@]}" --corpora "$CORPORA" --end-digests "$END_DIGESTS" \
      --end-digests-sha256 "$END_DIGESTS_SHA256" --captures "$W/captures" --output "$W/selection"
  $PY "$HERE/assemble_states.py" "${RUNTIME[@]}" --corpora "$CORPORA" --end-digests "$END_DIGESTS" \
      --end-digests-sha256 "$END_DIGESTS_SHA256" --captures "$W/captures" \
      --public "$T1JOB/corpus-publication-staging-r1/states.pkl" --golden "$T1JOB/end-bundle-preparation-r1/golden-states.pkl" \
      --selection "$W/selection" --output "$W/assembly"
  SHA=$(json "$W/assembly/assembly.json" "['states']['sha256']")
  FP=$(json "$W/assembly/assembly.json" "['expected_fingerprint']")
  $PY "$E4V3/convert_states.py" "${CONVERT_RUNTIME[@]}" --states "$W/assembly/states.pkl" --states-sha256 "$SHA" \
      --assembled-sha256 "$SHA" --expect-fingerprint "$FP" --output "$W/state-rows" > "$W/convert.log" 2>&1 ;;
reference)
  $PY "$HERE/student_reference.py" compute "${RUNTIME[@]}" --selection "$W/selection" --assembly "$W/assembly" \
      --state-rows "$W/state-rows" --v1 /mpac/sdicks02/jobs/clasher/e4v3-bundle-05-final/v1.pt \
      --student /mpac/sdicks02/jobs/clasher/e4v3-bundle-05-final/R3a.pt --output "$W/reference" ;;
memory)
  $PY "$HERE/memory_check.py" "${RUNTIME[@]}" --selection "$W/selection" --reference "$W/reference" --output "$W/memory" ;;
crosscheck)
  $PY "$HERE/student_reference.py" cross-check --runtime-root "$RT" --selection "$W/selection" --reference "$W/reference" \
      --end-speed-reference "${END_SPEED:?pooled END speed-reference.json}" --end-speed-reference-sha256 "${END_SPEED_SHA256:?}" ;;
seal)
  $PY "$HERE/seal_receipt.py" --runtime-root "$RT" --selection "$W/selection" --assembly "$W/assembly" --state-rows "$W/state-rows" \
      --reference "$W/reference" --memory "$W/memory" --output "$W/handoff" ;;
*) echo "unknown step $1" >&2; exit 2 ;;
esac
