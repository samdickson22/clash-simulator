#!/usr/bin/env bash
# fake adb for live-path driver tests: `... shell '<cmd>'` with dumpsys -> the real 10-16 dumpsys/getprop text;
# a bare `... shell` -> a shell that logs `input ...` lines to $FAKE_ADB_LOG and runs echo (the __ack protocol).
args="$*"
if [[ "$args" == *dumpsys* ]]; then
  printf '    versionCode=160402020 minSdk=32 targetSdk=35\n    versionName=160402020\n    lastUpdateTime=2026-10-15 14:31:42\nAmerica/Los_Angeles\n'
  exit 0
fi
while IFS= read -r line; do
  input() { echo "input $*" >> "${FAKE_ADB_LOG:-/dev/null}"; }
  eval "$line"
done
