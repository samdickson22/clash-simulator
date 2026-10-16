#!/usr/bin/env bash
# tap.sh x y [x y ...] : ADB input taps (Android px, guest only) via our adb server :5047, then peek
A='~/clasher-live/tools/platform-tools/adb -P 5047 -s 127.0.0.1:5555 shell'
cmd=""; while [ $# -ge 2 ]; do cmd="$cmd input tap $1 $2;"; shift 2; done
ssh -o BatchMode=yes macmini-fleet "$A '$cmd'"
