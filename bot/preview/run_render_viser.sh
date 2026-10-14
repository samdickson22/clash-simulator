#!/bin/bash
# Usage: run_render_viser.sh CASE -- RoyaleViser MP4 of rsim/rsim-case-CASE.msgpack on 127x03.
set -euo pipefail
cd /mpac/sdicks02/jobs/clasher/bot-preview
export SDL_VIDEODRIVER=dummy PYTHONDONTWRITEBYTECODE=1
exec nice -n 10 /mpac/sdicks02/repos/clasher-bot-rsim/.venv/bin/python -B code/render_viser.py rsim/rsim-case-$1.msgpack rsim/rsim-case-$1.json \
    --mp4 out/k4c-r16-vs-rext-bc-royalesim-case$1.mp4
