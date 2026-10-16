#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2
[[ "$(hostname -s)" == 127x03 ]] || exit 2
source "$job/env.sh"
export PYTHONPATH=/mpac/sdicks02/repos/clasher-bot-deckopt2
unset BOT_BELIEF_PRIOR CLASHER_LIVE_FAST
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 6 nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python "$job/projected_parity.py"
