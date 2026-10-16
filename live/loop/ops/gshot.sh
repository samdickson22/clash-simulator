#!/usr/bin/env bash
# gshot.sh <name>: Android guest screenshot (1080x1920) via our adb -> 05 shots/<name>.png + <name>-small.png (540x960)
n=$1; S=/mpac/sdicks02/scratch/live-loop/shots
ssh -o BatchMode=yes macmini-fleet "\$HOME/clasher-live/tools/platform-tools/adb -P 5047 -s 127.0.0.1:5555 exec-out screencap -p > ~/clasher-live/loop/shots/$n.png" && scp -q macmini-fleet:clasher-live/loop/shots/$n.png $S/ && \
${LL_PY:-/mpac/sdicks02/scratch/live-loop/venv/bin/python} -c "
import cv2; im=cv2.imread('$S/$n.png'); cv2.imwrite('$S/$n-small.png', cv2.resize(im,(540,960),interpolation=cv2.INTER_AREA))"
