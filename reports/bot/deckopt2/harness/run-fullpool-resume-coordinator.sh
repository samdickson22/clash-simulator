#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2
while [[ ! -f "$job/fullpool/resume-manifest.json" || -f "$job/fullpool/STOP" ]]; do sleep 10; done
exec /mpac/sdicks02/repos/clasher-bot/.venv/bin/python "$job/fullpool_resume_pipeline.py"
