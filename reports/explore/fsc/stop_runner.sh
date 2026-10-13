#!/usr/bin/env bash
# FSC one-shot STOP runner on 127x05 (exploration, NEVER ADOPTABLE). Not cron, not a timer, not a unit: started once,
# detached with setsid right after the launches, exits after one STOP session per host. It never polls hosts.
#   stop_runner.sh AT COMMIT MANIFEST_SHA256 HOST...
# Sleeps until AT (the coordinator's STOP time, <= 04:50Z), then runs `session.sh stop HOST` for every HOST in parallel
# (each a single SSH session) and waits for each by PID. A host already stopped by hand is refused by session.sh.
set -euo pipefail
shopt -s inherit_errexit
export LC_ALL=C
trap 'echo "__RC=$?"' EXIT
DEADLINE=2026-10-13T07:30:00Z
at=${1:-}; commit=${2:-}; msha=${3:-}; shift 3 || exit 2
[[ $at =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z$ ]] || exit 2
if [[ $at > $DEADLINE ]]; then echo "AT after $DEADLINE" >&2; exit 2; fi
[ $# -ge 1 ] || exit 2
for h in "$@"; do [[ $h == 127x03 || $h == 127x04 ]] || exit 2; done
[ "$(hostname)" = 127x05 ] || exit 2
here=$(cd "$(dirname "$0")" && pwd)
S=/mpac/sdicks02/jobs/clasher/fsc-sessions
wait_s=$(( $(date -u -d "$at" +%s) - $(date -u +%s) ))
echo "$(date -u +%FT%TZ) stop runner: STOP sessions for $* at $at (in ${wait_s}s)" >&2
if [ "$wait_s" -gt 0 ]; then sleep "$wait_s"; fi
pids=()
for h in "$@"; do
  bash "$here/session.sh" stop "$h" "$commit" "$msha" > "$S/runner-$h-$(date -u +%Y%m%dT%H%M%SZ).out" 2>&1 &
  pids+=($!)
done
rc=0
for p in "${pids[@]}"; do wait "$p" || rc=1; done
echo "$(date -u +%FT%TZ) stop runner done rc=$rc" >&2
exit "$rc"
