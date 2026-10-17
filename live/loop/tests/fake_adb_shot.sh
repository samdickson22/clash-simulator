#!/usr/bin/env bash
# fake adb with screencap: `... exec-out screencap -p` -> the PNG in $FAKE_SHOT; anything else -> fake_adb.sh
if [[ "$*" == *screencap* ]]; then cat "$FAKE_SHOT"; exit 0; fi
exec "$(dirname "$0")/fake_adb.sh" "$@"
