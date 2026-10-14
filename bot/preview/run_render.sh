#!/bin/bash
# Usage: run_render.sh CASE -- MP4 + GIF for captures/case-CASE.pkl.gz on 127x03.
set -euo pipefail
cd /mpac/sdicks02/jobs/clasher/bot-preview
export SDL_VIDEODRIVER=dummy PYTHONPATH=/mpac/sdicks02/repos/clasher-bot-preview/pylib PYTHONDONTWRITEBYTECODE=1
mkdir -p out
exec nice -n 10 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B code/render.py captures/case-$1.pkl.gz \
    --mp4 out/k4c-r16-vs-v1-case$1.mp4 --gif out/k4c-r16-vs-v1-case$1-highlight.gif
