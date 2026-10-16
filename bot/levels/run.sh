#!/usr/bin/env bash
# N forked games plus one parent; env.sh honors LEVELS_RUNTIME on 03/04/08.
set -euo pipefail
case "$(hostname -s)" in
    127x01|127x03|127x04|127x08) ;;
    *) echo 'levels runs allowed only on 127x01/03/04/08' >&2; exit 2 ;;
esac
n=${1:?usage: run.sh N ARGS...}; shift
[[ "$n" =~ ^([1-9]|1[0-5])$ ]] || { echo 'N must be in 1..15 (N+1 <= 16)' >&2; exit 2; }
for arg in "$@"; do
    case "$arg" in
        --workers|--workers=*) echo 'workers are set by N; do not pass --workers' >&2; exit 2 ;;
    esac
done
source /mpac/sdicks02/jobs/clasher/bot-levels/dev/env.sh
cd "$REPO"
exec /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$((n+1))" nice -n 10 "$PY" -m bot.levels.run "$@" --workers "$n"
