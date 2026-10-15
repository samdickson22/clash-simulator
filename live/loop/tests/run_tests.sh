#!/usr/bin/env bash
# 05 dry run of record.py against tests/fake_bsgrab.py (no Mac). Usage: PY=<python with cv2+numpy> tests/run_tests.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd); LOOP=$(dirname "$HERE")
PY=${PY:-/mpac/sdicks02/scratch/live-loop/venv/bin/python}
T=$(mktemp -d); export LL_REC_ROOT=$T/rec; mkdir -p "$LL_REC_ROOT"
FAKE="$T/bsgrab"; printf '#!/bin/sh\nexec %s %s "$@"\n' "$PY" "$HERE/fake_bsgrab.py" > "$FAKE"; chmod +x "$FAKE"
pass=0; fail=0
check() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }
rec() { "$PY" -I "$LOOP/record.py" --bsgrab "$FAKE" --crop 0,0,540,980 "$@" >"$T/out" 2>&1; echo $?; }
j() { "$PY" -c "import json,sys;print(json.load(open('$LL_REC_ROOT/$1/summary.json'))['$2'])"; }

rc=$(rec --name ok --seconds 3 --fps 10)
check "ok rc 0" '[ "$rc" = 0 ]'
check "ok stop=seconds" '[ "$(j ok stop)" = seconds ]'
check "ok ~30 frames" '[ "$(j ok frames)" -ge 25 ] && [ "$(j ok frames)" -le 32 ]'
check "ok jpgs == index rows" '[ "$(ls $LL_REC_ROOT/ok/*.jpg | wc -l)" = "$(wc -l < $LL_REC_ROOT/ok/frames.jsonl)" ]'
check "ok fps ~10" '"$PY" -c "import sys;f=float(\"$(j ok fps)\");sys.exit(not 8<f<11)"'
check "ok latency ~15ms" '"$PY" -c "import sys;f=float(\"$(j ok latency_ms_p50)\");sys.exit(not 14<f<40)"'
check "ok jpeg decodes 540x1140" '"$PY" -c "import cv2,sys;im=cv2.imread(\"$LL_REC_ROOT/ok/000003.jpg\");sys.exit(im.shape!=(1140,540,3))"'
check "ok bsgrab ended after stop" '! pgrep -f "$HERE/fake_bsgrab.py" >/dev/null'
rc=$(FAKE_MODE=badmagic rec --name bad --seconds 3)
check "badmagic rc 1 + stop" '[ "$rc" = 1 ] && j bad stop | grep -q "bad stream"'
check "badmagic kept 3 frames" '[ "$(j bad frames)" = 3 ]'
rc=$(FAKE_MODE=truncate rec --name trunc --seconds 3)
check "truncated frame dropped" '[ "$rc" = 0 ] && [ "$(j trunc frames)" = 5 ] && [ "$(j trunc stop)" = "bsgrab ended" ]'
rc=$(FAKE_MODE=gap rec --name gap --seconds 2)
check "gap counted" '[ "$(j gap seq_gaps)" = 1 ]'
rc=$(rec --name ok --seconds 1)
check "existing dir refused" '[ "$rc" != 0 ] && grep -q FileExistsError $T/out'
rc=$(rec --name ../esc --seconds 1)
check "path escape refused" '[ "$rc" != 0 ] && [ ! -e $T/esc ]'
rc=$(LL_MIN_FREE_GB=1000000 rec --name full --seconds 1)
check "disk guard refuses start" '[ "$rc" != 0 ] && grep -q "below 6 GiB" $T/out && [ ! -e $LL_REC_ROOT/full ]'
rc=$(rec --name cap --seconds 30 --max-gb 0.0005)
check "max-gb stops" '[ "$rc" = 1 ] && [ "$(j cap stop)" = max-gb ]'
rm -rf "$T"; echo "$pass passed, $fail failed"; [ "$fail" = 0 ]
