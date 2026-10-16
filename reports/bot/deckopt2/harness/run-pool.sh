#!/usr/bin/env bash
set -euo pipefail
job=/mpac/sdicks02/jobs/clasher/bot-deckopt2
source "$job/env.sh"
export PYTHONPATH=/mpac/sdicks02/repos/clasher-bot-deckopt2
root=${1:?ROOT}; stage=${2:?STAGE}; route=${3:?ROUTE}; label=${4:?LABEL}; workers=${5:?WORKERS}
case "$(hostname -s)" in 127x01|127x03|127x04) ;; *) exit 2 ;; esac
[[ "$root" == "$job"* ]] || exit 2
[[ "$workers" =~ ^[0-9]+$ ]] && (( workers >= 1 && workers <= 40 )) || exit 2
entry="$job/pool.py"
if [[ "$stage" == validation ]]; then
  [[ -f "$root/implementation.json" ]] || exit 3
  entry="$job/projected_entry.py"
fi
date -u
set +e
/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh "$((workers+2))" nice -n 15 /mpac/sdicks02/repos/clasher-bot/.venv/bin/python "$entry" --root "$root" --stage "$stage" --route "$route" --label "$label" --workers "$workers"
status=$?
printf '%s\n' "$status" > "$root/$stage-exit-$label.txt"
date -u
exit "$status"
