#!/usr/bin/env bash
# Stage a distinct reporting namespace from the launch-qualified job (T1 precedent). Runs on the host. No launch.
set -euo pipefail
SRC=$1; DST=$2
test -d "$SRC/repo" && test ! -e "$DST" && test ! -e "$DST.STOP"
mkdir -p "$DST"
for n in repo native native-source inputs corpus cache; do [ -e "$SRC/$n" ] && cp -a "$SRC/$n" "$DST/"; done
for f in inherited-runtime-pin.json runtime-pin.json staging.json TESTS-PASS QUALIFIED BELIEF-QUALIFIED QUALIFICATION-STARTED QUALIFICATION-FINISHED \
         qualification-$(hostname).json qualification.json k4s-qualification.json belief-qualification.json guard-support-qualification.json \
         sd1-manifest-check.txt tests.log source-binding-start.json qualification-source-before.json \
         FROZEN-K4S.json SMOKE-PASS smoke-admission.json reporting-dispatch.json; do
  [ -e "$SRC/$f" ] && cp -a "$SRC/$f" "$DST/$f"
done
ln -s "$DST.STOP" "$DST/STOP"
echo staged "$DST" "$(date -u +%FT%TZ)"
