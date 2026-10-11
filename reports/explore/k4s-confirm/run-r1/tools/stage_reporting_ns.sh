#!/usr/bin/env bash
# Stage a distinct reporting namespace from the launch-qualified job (T1 precedent). Runs on the host. No launch.
set -euo pipefail
SRC=$1; DST=$2
test -d "$SRC/repo" && test ! -e "$DST" && test ! -e "$DST.STOP"
mkdir -p "$DST"
for n in repo native native-source inputs corpus; do test -e "$SRC/$n"; cp -a "$SRC/$n" "$DST/"; done   # required (Sol ops r1 finding 5)
for f in inherited-runtime-pin.json runtime-pin.json staging.json TESTS-PASS QUALIFIED BELIEF-QUALIFIED QUALIFICATION-STARTED QUALIFICATION-FINISHED \
         qualification-$(hostname).json qualification.json k4s-qualification.json belief-qualification.json guard-support-qualification.json \
         sd1-manifest-check.txt tests.log source-binding-start.json qualification-source-before.json \
         FROZEN-K4S.json SMOKE-PASS smoke-admission.json reporting-dispatch.json; do
  [ -e "$SRC/$f" ] && cp -a "$SRC/$f" "$DST/$f"
done
for n in inherited-runtime-pin.json runtime-pin.json TESTS-PASS QUALIFIED BELIEF-QUALIFIED FROZEN-K4S.json SMOKE-PASS smoke-admission.json; do test -e "$DST/$n"; done
! find "$DST" -type l -lname "$SRC*" | grep -q . || { echo "a staged link resolves into the source job" >&2; exit 3; }
ln -s "$DST.STOP" "$DST/STOP"
# 03: the frozen idle-service pin (identity-checked by the frozen tool; T1/K4S identity 139691386/16152ceb...)
if [ "$(hostname)" = 127x03 ]; then
  (cd "$DST/repo" && K4S_JOB="$DST" nice -n 19 bash reports/explore/k4s-confirm/runtime.sh reports/explore/k4s-confirm/idle_services.py --job "$DST")
  python3 -c "import json,sys;s=json.load(open('$DST/idle-services.json'))['services'][0]['service'];sys.exit(0 if s['start_ticks']==139691386 and s['cmdline_sha256'].startswith('16152ceb') else 1)"
fi
echo staged "$DST" "$(date -u +%FT%TZ)"
