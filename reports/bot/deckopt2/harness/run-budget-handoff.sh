#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2
source "$job/env.sh"
export PYTHONPATH=/mpac/sdicks02/repos/clasher-bot-deckopt2
cd /mpac/sdicks02/repos/clasher-bot-deckopt2
date -u
who
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 42 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python "$job/budget_handoff.py"
