#!/usr/bin/env bash
# peek.sh <name>: SCK display capture on the Mac (read-only) -> 05 shots/<name>-bs.png (BlueStacks window region, 1/2)
n=$1; S=/mpac/sdicks02/scratch/live-loop/shots
ssh -o BatchMode=yes macmini-fleet "~/clasher-live/loop/tmp/cur ~/clasher-live/loop/shots/$n.png >/dev/null" && scp -q macmini-fleet:clasher-live/loop/shots/$n.png $S/ && \
${LL_PY:-/mpac/sdicks02/scratch/live-loop/venv/bin/python} -c "
import cv2; im=cv2.imread('$S/$n.png'); cv2.imwrite('$S/$n-bs.png', cv2.resize(im[50:990,244:786],None,fx=.5,fy=.5))"
